"""Exit-menu TPE — optimize a Bull Rider EXIT over cup-and-handle entries.

Fixes the survivorship-free, point-in-time cup-and-handle ENTRY (shapes_entry_edge),
precomputes every breakout's price path ONCE, then Optuna(TPE) searches the EXIT
menu drawn from the legacy DB:
  - trailing stop %        - hard stop % ("down 8")      - profit target % ("up 20")
  - max-hold time stop     - breakeven ratchet (stairstep-lite, lock at +X%)
  - key-reversal exit      - VOLUME-GATED stop (Erik's idea: only honor a stop
                             touch if that day's volume >= mult x 20d-avg volume)

Two-step discipline: OPTIMIZE on Tier-1 (2016-2020), VALIDATE held-out on Tier-2
(2021-2026). Entries are fixed, so each trial only re-runs the exit walk → fast.
Fills are realistic: target at the target px, stop at min(open, stop) (gap-through),
key-rev/time at the close. RESEARCH ONLY, local, ~$0.

Usage: AWS_PROFILE=rigacap PITFWU_LOCAL=~/pitfwu_cache \
       backend/venv/bin/python scripts/shapes_tpe.py [trials]
"""
import os, sys
R = "/Users/erikkins/CODE/stocker-app"
sys.path.insert(0, os.path.join(R, "backend")); sys.path.insert(0, os.path.join(R, "scripts"))
for _l in open(os.path.join(R, ".env")):
    if _l.startswith("DATABASE_URL="):
        os.environ["DATABASE_URL"] = _l.strip().split("=", 1)[1]; break
os.environ.setdefault("LAMBDA_ROLE", "worker")

import json
import numpy as np
import pandas as pd
import optuna
from optuna.samplers import TPESampler
import pitfwu_veneer as v
from app.services.scanner import _EXCLUDED_SET
import shapes_entry_edge as S

optuna.logging.set_verbosity(optuna.logging.WARNING)
COST = 0.0015


def rigorous_entries(start, end):
    """Precompute (o,h,l,c,vol,t) for every cup-and-handle breakout in the window."""
    union = set()
    for d in pd.date_range(start, end, freq="14D"):
        union |= set([s for s in v.universe_asof_prod(d, 300, 15.0)
                      if s not in _EXCLUDED_SET and not s.startswith("^")][:100])
    entries = []
    for s in union:
        try:
            df = v.split_adjusted(s, asof=end, ca=S.CA)[["open", "high", "low", "close", "volume"]]
        except Exception:
            continue
        o, h, l, c, vol = (df[col].to_numpy(float) for col in ["open", "high", "low", "close", "volume"])
        sig = S.cup_and_handle_breakouts(c, vol)
        idx = df.index
        for t in np.where(sig)[0]:
            if not (pd.Timestamp(start) <= idx[t] <= pd.Timestamp(end)):
                continue
            if t >= len(c) - 2:
                continue
            entries.append((o, h, l, c, vol, int(t)))
    return entries


def exit_sim(o, h, l, c, vol, t, p):
    """One trade: walk forward from entry t under exit params p → net return."""
    entry = c[t]
    hi = entry
    hard = entry * (1 - p["hard_stop"] / 100.0)
    be_done = False
    last = min(t + p["max_hold"], len(c) - 1)
    for k in range(t + 1, last + 1):
        hi = max(hi, h[k])
        # breakeven ratchet (stairstep-lite): once up be_trig%, lift the hard stop to entry
        if p["be_trig"] > 0 and not be_done and h[k] >= entry * (1 + p["be_trig"] / 100.0):
            hard = max(hard, entry)
            be_done = True
        trail = hi * (1 - p["trail"] / 100.0)
        stop_level = max(hard, trail)
        # profit target (intraday)
        if p["target"] > 0 and h[k] >= entry * (1 + p["target"] / 100.0):
            return (entry * (1 + p["target"] / 100.0)) / entry - 1 - COST
        # stop touch (intraday low), optionally volume-gated
        if l[k] <= stop_level:
            honor = True
            if p["vol_mult"] > 0:
                vbase = vol[max(0, k - 20):k].mean() if k >= 5 else vol[k]
                honor = vol[k] >= p["vol_mult"] * vbase
            if honor:
                fill = min(o[k], stop_level)  # gap-through fills at the open
                return fill / entry - 1 - COST
        # key-reversal exit: outside-down day (today's high>yest high, close<yest low)
        if p["key_rev"] and h[k] > h[k - 1] and c[k] < l[k - 1]:
            return c[k] / entry - 1 - COST
    return c[last] / entry - 1 - COST


def metrics(entries, p):
    r = np.array([exit_sim(e[0], e[1], e[2], e[3], e[4], e[5], p) for e in entries])
    sd = r.std()
    return {"n": int(len(r)), "mean": float(r.mean() * 100), "median": float(np.median(r) * 100),
            "win": float((r > 0).mean() * 100), "sharpe": float(r.mean() / sd if sd > 0 else 0.0)}


T1, T2 = None, None


def suggest(trial):
    return {
        "trail": trial.suggest_float("trail", 5, 30, step=1),
        "hard_stop": trial.suggest_float("hard_stop", 4, 15, step=1),
        "target": trial.suggest_categorical("target", [0, 15, 20, 25, 30, 40, 50]),
        "max_hold": trial.suggest_int("max_hold", 10, 60, step=5),
        "be_trig": trial.suggest_categorical("be_trig", [0, 5, 10, 15, 20]),
        "key_rev": trial.suggest_categorical("key_rev", [True, False]),
        "vol_mult": trial.suggest_categorical("vol_mult", [0.0, 0.5, 1.0, 1.5, 2.0]),
    }


# Objective: 'sharpe' (default, robust — balances return vs consistency so it
# can't tail-chase), 'median' (target the typical trade), or 'mean' (tail-prone).
OBJ = os.environ.get("TPE_OBJ", "sharpe")


def objective(trial):
    p = suggest(trial)
    m = metrics(T1, p)
    trial.set_user_attr("p", p)
    trial.set_user_attr("t1", m)
    return m[OBJ]  # optimize Tier-1; Tier-2 held-out is the honest verdict


def fmt(m):
    return f"n={m['n']:>4} mean {m['mean']:+.2f}% median {m['median']:+.2f}% win {m['win']:.1f}% sharpe {m['sharpe']:+.3f}"


if __name__ == "__main__":
    trials = int(sys.argv[1]) if len(sys.argv) > 1 else 150
    print("Precomputing entries (one-time)...")
    T1 = rigorous_entries(pd.Timestamp("2016-06-01"), pd.Timestamp("2020-12-31"))
    T2 = rigorous_entries(pd.Timestamp("2021-01-01"), pd.Timestamp("2026-05-29"))
    print(f"  Tier-1 entries: {len(T1)} | Tier-2 entries: {len(T2)}")

    # baseline (the simple 20d + 10% trail from shapes_strategy) for reference
    base = {"trail": 10, "hard_stop": 100, "target": 0, "max_hold": 20, "be_trig": 0, "key_rev": False, "vol_mult": 0.0}
    print(f"\nBASELINE  Tier-1: {fmt(metrics(T1, base))}")
    print(f"BASELINE  Tier-2: {fmt(metrics(T2, base))}")

    # Persistent study → survives laptop sleep, session-close, or kill. Re-running
    # the SAME command resumes from the last completed trial (SQLite on disk).
    db = f"sqlite:///{os.path.join(R, 'scripts', 'shapes_tpe.db')}"
    study = optuna.create_study(direction="maximize", sampler=TPESampler(seed=42),
                                storage=db, study_name=f"exit_{OBJ}", load_if_exists=True)
    done = sum(1 for t in study.trials if t.state.is_finished())
    remaining = max(0, trials - done)
    print(f"\nObjective={OBJ}. Target {trials} — {done} done, running {remaining} more "
          f"(resumable: re-run to continue).")
    if remaining:
        study.optimize(objective, n_trials=remaining, show_progress_bar=False)

    best = study.best_trial
    bp = best.user_attrs["p"]
    print("\n================ BEST EXIT (by Tier-1 mean) ================")
    print(f"  params: {bp}")
    print(f"  Tier-1 (train):      {fmt(metrics(T1, bp))}")
    print(f"  Tier-2 (HELD-OUT):   {fmt(metrics(T2, bp))}")

    # overfit check: how do the top-8 Tier-1 trials hold up out-of-sample?
    top = sorted(study.trials, key=lambda t: t.value, reverse=True)[:8]
    print("\n--- top-8 Tier-1 configs → held-out Tier-2 (overfit check) ---")
    print(f"  {'t1_mean':>8} {'t2_mean':>8} {'t2_median':>9} {'t2_win':>7} {'t2_sharpe':>9}  params")
    rows = []
    for t in top:
        m2 = metrics(T2, t.user_attrs["p"])
        print(f"  {t.user_attrs['t1']['mean']:>7.2f}% {m2['mean']:>7.2f}% {m2['median']:>8.2f}% {m2['win']:>6.1f}% {m2['sharpe']:>9.3f}  {t.user_attrs['p']}")
        rows.append({"t1": t.user_attrs["t1"], "t2": m2, "p": t.user_attrs["p"]})

    out = {"best_params": bp, "best_t1": metrics(T1, bp), "best_t2": metrics(T2, bp),
           "baseline_t1": metrics(T1, base), "baseline_t2": metrics(T2, base), "top8": rows}
    path = os.path.join(R, "scripts", "shapes_tpe_results.json")
    json.dump(out, open(path, "w"), indent=2)
    print(f"\nsaved → {path}")
