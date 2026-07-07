"""Pressure-test the breakout sleeve — how much of the 41% is REAL?

Two honest tests:
 (1) WALK-FORWARD: expanding train window, re-optimize breakout params on the PAST,
     apply frozen to the NEXT unseen year, stitch the out-of-sample years. Kills the
     "tuned on the eval window" optimism the static +41% carried.
 (2) COST SENSITIVITY: the breakout is higher-turnover (~monthly holds) — re-run the
     static winner at 15 / 30 / 50 bps per side.
Regime gate fixed to rotating_bull (the validated habitat). RESEARCH ONLY, local.
"""
import os, sys
R = "/Users/erikkins/CODE/stocker-app"
sys.path.insert(0, os.path.join(R, "backend")); sys.path.insert(0, os.path.join(R, "scripts"))
for _l in open(os.path.join(R, ".env")):
    if _l.startswith("DATABASE_URL="):
        os.environ["DATABASE_URL"] = _l.strip().split("=", 1)[1]; break
os.environ.setdefault("LAMBDA_ROLE", "worker")

import numpy as np
import pandas as pd
import optuna
from optuna.samplers import TPESampler
from shape_tpe import load_data, detect
import shapes_portfolio as sp
from shapes_portfolio import simulate, perf, CAP0

optuna.logging.set_verbosity(optuna.logging.WARNING)
N_POS = 15
STATIC = {"regime": "rotating", "buffer": 0.014, "vol_mult": 1.38, "mom_min": -0.005, "hold": 29}

FULL_S, FULL_E = pd.Timestamp("2016-06-01"), pd.Timestamp("2026-05-29")
# (train_start, train_end, test_start, test_end) — expanding window, next-year OOS
FOLDS = [("2016-06-01", "2019-12-31", "2020-01-01", "2020-12-31"),
         ("2016-06-01", "2020-12-31", "2021-01-01", "2021-12-31"),
         ("2016-06-01", "2021-12-31", "2022-01-01", "2022-12-31"),
         ("2016-06-01", "2022-12-31", "2023-01-01", "2023-12-31"),
         ("2016-06-01", "2023-12-31", "2024-01-01", "2024-12-31"),
         ("2016-06-01", "2024-12-31", "2025-01-01", "2026-05-29")]

_DATA = None


def sleeve_ret(p, start, end):
    _, close, dvol, feats = _DATA
    sigs = detect(feats, p, "breakout")
    n = int(sum(s.sum() for s in sigs.values()))
    sig = pd.DataFrame(sigs).reindex(close.index).fillna(False)
    eq = simulate(close, sig, dvol, start, end, N_POS, int(p["hold"]))
    return eq, n


def optimize(train_s, train_e, ntrials=30):
    def obj(trial):
        p = {"regime": "rotating",
             "buffer": trial.suggest_float("buffer", 0.0, 0.03),
             "vol_mult": trial.suggest_float("vol_mult", 1.0, 2.0),
             "mom_min": trial.suggest_float("mom_min", -0.10, 0.50),
             "hold": trial.suggest_int("hold", 10, 40)}
        eq, n = sleeve_ret(p, train_s, train_e)
        if n < 200:
            return -9.0
        return perf(eq)[1]  # train Sharpe
    st = optuna.create_study(direction="maximize", sampler=TPESampler(seed=1, n_startup_trials=10))
    st.optimize(obj, n_trials=ntrials)
    bp = dict(st.best_params); bp["regime"] = "rotating"
    return bp


if __name__ == "__main__":
    print("Loading 2016-2026 data once...", flush=True)
    _DATA = load_data(FULL_S, FULL_E)

    print("\n=== (1) WALK-FORWARD (re-optimize on past, test next unseen year, 15bps) ===", flush=True)
    sp.COST = 0.0015
    oos = []
    for ts, te, ss, se in FOLDS:
        bp = optimize(pd.Timestamp(ts), pd.Timestamp(te))
        eq, _ = sleeve_ret(bp, pd.Timestamp(ss), pd.Timestamp(se))
        r = eq.pct_change().dropna()
        c, s, m = perf(eq, ppy=252)
        oos.append(r)
        print(f"  test {ss[:4]}: CAGR {c:>6.1f}%  Sharpe {s:>5.2f}  MaxDD {m:>6.1f}%  "
              f"| params buf {bp['buffer']:.3f} vol {bp['vol_mult']:.2f} mom {bp['mom_min']:.2f} hold {bp['hold']}", flush=True)
    wf = pd.concat(oos).sort_index()
    wc, ws, wm = perf(CAP0 * (1 + wf).cumprod(), ppy=252)
    print(f"  >> WALK-FORWARD OOS (stitched): CAGR {wc:.1f}%  Sharpe {ws:.2f}  MaxDD {wm:.1f}%", flush=True)

    print("\n=== (2) COST SENSITIVITY — static winner over 2016-2026 (daily) ===", flush=True)
    for cost in [0.0015, 0.0030, 0.0050]:
        sp.COST = cost
        eq, n = sleeve_ret(STATIC, FULL_S, FULL_E)
        c, s, m = perf(eq, ppy=252)
        print(f"  {cost*1e4:>4.0f} bps/side: CAGR {c:>6.1f}%  Sharpe {s:>5.2f}  MaxDD {m:>6.1f}%  (n={n})", flush=True)
