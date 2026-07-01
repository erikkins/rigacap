"""Shape-parameter TPE harness — search a shape's geometry levers for a parameterization
with REAL, durable, portfolio-level edge.

Every lesson we earned is baked in:
  - OBJECTIVE = portfolio Sharpe (NOT per-trade median — the vcp -52% blowup taught us
    per-trade metrics are blind to correlated tail risk).
  - REVERSE-SWAP IN THE OBJECTIVE = TPE maximizes min(Sharpe_A, Sharpe_B), so a winner
    must be good in BOTH halves (2016-20 AND 2021-26) by construction — can't overfit one.
  - PRE-2016 EXT sanity on the winner = a quasi-third holdout (independent era; surv-biased).
  - Few knobs + modest trials = less overfit. Reusable: swap DETECT/SPACE for any shape.

Speed: each symbol's rolling features are precomputed ONCE; a trial is just vectorized
boolean combines + two portfolio sims. RESEARCH ONLY, local.

Usage: AWS_PROFILE=rigacap PITFWU_LOCAL=~/pitfwu_cache backend/venv/bin/python scripts/shape_tpe.py [n_trials]
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
import pitfwu_veneer as v
from app.services.scanner import _EXCLUDED_SET
import shapes_entry_edge as S
from shapes_portfolio import simulate, perf, CAP0
from shape_lab import bull_regime  # SPY>200MA (legacy binary, still injected for reference)
from regime_research import regime_series  # production 7-regime labels (cached)

SHAPE = "pullback_ma"  # which shape to hunt (set from argv in __main__)

# Regime gates — TPE picks ONE per shape. Built on the production 7-regime labels;
# grouped because single rare regimes (strong_bull ~1-5% of days) give too few signals.
REGIME_GATES = {
    "all":          None,
    "bull":         {"strong_bull", "weak_bull", "rotating_bull", "recovery"},
    "rotating":     {"rotating_bull"},
    "chop":         {"rotating_bull", "range_bound"},
    "calm_bull":    {"strong_bull", "weak_bull"},
    "bear":         {"weak_bear", "panic_crash"},
    "capitulation": {"panic_crash", "recovery", "weak_bear"},
    "recovery":     {"recovery", "panic_crash"},
}

optuna.logging.set_verbosity(optuna.logging.WARNING)

A = (pd.Timestamp("2016-06-01"), pd.Timestamp("2020-12-31"))
B = (pd.Timestamp("2021-01-01"), pd.Timestamp("2026-05-29"))
N_POS = 15


# ── the shape under optimization: pullback_ma, fully parameterized ───────────────
# Knobs (kept few): how deep the dip, volume dry-up on the dip, leadership (own 126d
# momentum floor), and the time-stop hold. SPACE defines TPE's search ranges.
SPACES = {
    "pullback_ma": {
        "depth_min":  ("float", 0.02, 0.12),   # min pullback off the 20d high
        "depth_band": ("float", 0.04, 0.25),   # depth_max = depth_min + depth_band
        "dryup":      ("float", 0.5, 1.4),      # dip-day volume < dryup x 50d avg vol
        "mom_min":    ("float", -0.10, 0.50),   # own 126d return floor (RS/leadership proxy)
        "hold":       ("int",   8, 40),
    },
    "oversold_bounce": {                        # bull cousin of OMR: deep RSI-oversold reclaim
        "rsi_max":   ("float", 15.0, 40.0),     # yesterday's RSI14 below this = oversold
        "drop_min":  ("float", 0.05, 0.25),     # pulled back >= this off the 20d high
        "mom_min":   ("float", -0.20, 0.40),    # own 126d return floor (leadership)
        "hold":      ("int",   5, 30),
    },
    "breakout": {                               # momentum breakout above the 50d high on volume
        "buffer":    ("float", 0.0, 0.03),      # break above prior 50d high by this much
        "vol_mult":  ("float", 1.0, 2.0),       # breakout-day volume > mult x 50d avg
        "mom_min":   ("float", -0.10, 0.50),    # own 126d return floor (leadership)
        "hold":      ("int",   10, 40),
    },
}


def features(arrs):
    """Precompute per-symbol rolling arrays ONCE (param-independent)."""
    feats = {}
    for s, (o, h, l, c, vol, idx) in arrs.items():
        cs = pd.Series(c)
        ma50 = cs.rolling(50, min_periods=10).mean().to_numpy()
        ma200 = cs.rolling(200, min_periods=50).mean().to_numpy()
        ma50_10 = pd.Series(ma50).shift(10).to_numpy()
        hi20 = cs.rolling(20, min_periods=5).max().to_numpy()
        vol50 = pd.Series(vol).rolling(50, min_periods=10).mean().to_numpy()
        mom126 = (cs / cs.shift(126) - 1.0).to_numpy()
        delta = cs.diff()                                  # RSI(14)
        gain = delta.clip(lower=0).rolling(14, min_periods=5).mean()
        loss = (-delta.clip(upper=0)).rolling(14, min_periods=5).mean()
        rsi = (100 - 100 / (1 + gain / loss.replace(0, np.nan))).to_numpy()
        hi50_1 = cs.rolling(50, min_periods=15).max().shift(1).to_numpy()  # prior 50d high (excl today)
        feats[s] = dict(o=o, c=c, vol=vol, idx=idx, ma50=ma50, ma200=ma200,
                        ma50_10=ma50_10, hi20=hi20, vol50=vol50, mom126=mom126,
                        c1=cs.shift(1).to_numpy(), hi20_1=pd.Series(hi20).shift(1).to_numpy(),
                        vol1=pd.Series(vol).shift(1).to_numpy(), vol50_1=pd.Series(vol50).shift(1).to_numpy(),
                        rsi1=pd.Series(rsi).shift(1).to_numpy(), hi50_1=hi50_1)
    return feats


def _pullback_ma(f, p):
    c, o = f["c"], f["o"]
    dmin, dmax = p["depth_min"], p["depth_min"] + p["depth_band"]
    uptrend = (f["ma50"] > f["ma200"]) & (f["ma50"] > f["ma50_10"]) & (c > f["ma50"])
    depth_y = np.where(f["hi20_1"] > 0, (f["hi20_1"] - f["c1"]) / f["hi20_1"], 0.0)  # yesterday's dip
    pulled = (depth_y >= dmin) & (depth_y <= dmax)
    dry = f["vol1"] < p["dryup"] * f["vol50_1"]                  # dry-up on the dip day
    lead = f["mom126"] > p["mom_min"]
    turn = (c > f["c1"]) & (c > o)                              # turn back up today
    return uptrend & pulled & dry & lead & turn


def _oversold_bounce(f, p):
    c, o = f["c"], f["o"]
    uptrend = c > f["ma200"]                                     # dip within a longer-term uptrend
    oversold = f["rsi1"] < p["rsi_max"]                         # yesterday RSI14 oversold
    depth_y = np.where(f["hi20_1"] > 0, (f["hi20_1"] - f["c1"]) / f["hi20_1"], 0.0)
    dropped = depth_y >= p["drop_min"]
    lead = f["mom126"] > p["mom_min"]
    turn = (c > f["c1"]) & (c > o)                              # reclaim: turn back up
    return uptrend & oversold & dropped & lead & turn


def _breakout(f, p):
    c = f["c"]
    uptrend = (f["ma50"] > f["ma200"]) & (c > f["ma50"])
    prior_hi = f["hi50_1"]
    broke = c > prior_hi * (1 + p["buffer"])          # break above prior 50d high + buffer
    fresh = f["c1"] <= prior_hi                        # crossed it today (fresh breakout)
    volspike = f["vol"] > p["vol_mult"] * f["vol50"]
    lead = f["mom126"] > p["mom_min"]
    return uptrend & broke & fresh & volspike & lead


DETECTORS = {"pullback_ma": _pullback_ma, "oversold_bounce": _oversold_bounce, "breakout": _breakout}


def detect(feats, p, shape):
    """Vectorized per-shape signal -> {sym: bool Series}. Fast (no python loop)."""
    fn = DETECTORS[shape]
    out = {}
    for s, f in feats.items():
        sig = fn(f, p) & (f["c"] >= 15) & (f["vol"] >= 500_000)
        gate = REGIME_GATES[p.get("regime", "all")]
        if gate is not None:
            sig = sig & np.isin(f["regime"], list(gate))         # TPE-chosen 7-regime gate
        out[s] = pd.Series(np.nan_to_num(sig, nan=0.0).astype(bool), index=f["idx"])
    return out


# ── data + evaluation ────────────────────────────────────────────────────────
def load_data(start, end):
    union = set()
    for d in pd.date_range(start, end, freq="14D"):
        union |= set([s for s in v.universe_asof_prod(d, 300, 15.0)
                      if s not in _EXCLUDED_SET and not s.startswith("^")][:100])
    arrs, closes, dvols = {}, {}, {}
    for s in union:
        try:
            df = v.split_adjusted(s, asof=end, ca=S.CA)[["open", "high", "low", "close", "volume"]]
        except Exception:
            continue
        o, h, l, c, vol = (df[k].to_numpy(float) for k in ["open", "high", "low", "close", "volume"])
        arrs[s] = (o, h, l, c, vol, df.index)
        closes[s] = df["close"]
        dvols[s] = (df["close"] * df["volume"]).rolling(20, min_periods=5).mean()
    close = pd.DataFrame(closes).sort_index()
    idx = close.index
    feats = features(arrs)
    bull = bull_regime(end)  # legacy binary (kept for reference)
    reg = regime_series(start, end)  # cached production 7-regime labels (date -> label)
    for s, f in feats.items():
        f["bull"] = bull.reindex(f["idx"], method="ffill").fillna(False).to_numpy().astype(bool)
        f["regime"] = reg.reindex(f["idx"], method="ffill").fillna("none").to_numpy()
    return arrs, close, pd.DataFrame(dvols).reindex(idx), feats


def evalh(data, start, end, p):
    arrs, close, dvol, feats = data
    sigs = detect(feats, p, SHAPE)
    sig = pd.DataFrame(sigs).reindex(close.index).fillna(False)
    eq = simulate(close, sig, dvol, start, end, N_POS, int(p["hold"]))
    return eq, int(sum(s.sum() for s in sigs.values()))


def blend_improvement(sleeve_eq, t30v):
    """How much the best t30v+sleeve blend Sharpe beats t30v-alone (same grid, self-
    consistent). Beta sleeve -> best blend at 100% t30v -> ~0. Orthogonal positive
    sleeve -> best blend at w<1 -> >0. Returns (improvement, best_core_weight)."""
    rs = sleeve_eq.reindex(t30v["grid"], method="ffill").pct_change()
    df = pd.DataFrame({"t": t30v["rt"], "s": rs}).dropna()
    if len(df) < 10:
        return -9.0, 1.0
    sharpes = {}
    for w in np.arange(0, 1.01, 0.1):
        r = w * df["t"] + (1 - w) * df["s"]
        sharpes[round(w, 1)] = perf(CAP0 * (1 + r).cumprod(), ppy=26)[1]
    bw = max(sharpes, key=sharpes.get)
    return sharpes[bw] - sharpes[1.0], bw


if __name__ == "__main__":
    from shapes_orthogonality import real_ensemble_equity  # lazy: pulls the t30v engine
    SHAPE = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].isdigit() else "oversold_bounce"
    n_trials = int([a for a in sys.argv[1:] if a.isdigit()][0]) if any(a.isdigit() for a in sys.argv[1:]) else 80
    SPACE = SPACES[SHAPE]
    print(f"=== HUNTING shape '{SHAPE}' (regime = TPE knob over {list(REGIME_GATES)}) ===", flush=True)
    print("Loading A (2016-20) and B (2021-26) data + features...", flush=True)
    dataA = load_data(*A)
    dataB = load_data(*B)
    print("  building REAL t30v reference for each half...", flush=True)
    enA, _ = real_ensemble_equity(*A)
    enB, _ = real_ensemble_equity(*B)
    T = {"A": {"grid": enA.index, "rt": enA.pct_change(), "shp": perf(enA, ppy=26)[1]},
         "B": {"grid": enB.index, "rt": enB.pct_change(), "shp": perf(enB, ppy=26)[1]}}
    print(f"  t30v Sharpe — A {T['A']['shp']:.2f}, B {T['B']['shp']:.2f}. "
          f"Hunting orthogonal edge, {n_trials} trials...\n", flush=True)

    def objective(trial):
        p = {"regime": trial.suggest_categorical("regime", list(REGIME_GATES))}  # regime is a knob
        for k, spec in SPACE.items():
            p[k] = trial.suggest_int(k, spec[1], spec[2]) if spec[0] == "int" else trial.suggest_float(k, spec[1], spec[2])
        eqA, na = evalh(dataA, *A, p)
        eqB, nb = evalh(dataB, *B, p)
        if na < 30 or nb < 30:      # too few trades = not a real strategy
            return -9.0
        impA, wA = blend_improvement(eqA, T["A"])
        impB, wB = blend_improvement(eqB, T["B"])
        ca, sa, ma = perf(eqA); cb, sb, mb = perf(eqB)
        # store: blend improvement, best core weight, sleeve standalone, n
        trial.set_user_attr("A", (round(impA, 3), wA, round(ca, 1), round(sa, 2), na))
        trial.set_user_attr("B", (round(impB, 3), wB, round(cb, 1), round(sb, 2), nb))
        return min(impA, impB)      # reward orthogonal+positive in BOTH halves (rev-swap baked in)

    study = optuna.create_study(direction="maximize", sampler=TPESampler(seed=42, n_startup_trials=40))
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)

    def fmt(u):  # (blendImprov, coreW, sleeveCAGR, sleeveShp, n)
        return f"+{u[0]:.2f}Shp@core{u[1]*100:.0f}% (sleeve {u[2]}%/{u[3]}, n={u[4]})"

    bt = study.best_trial
    print(f"BEST min blend-improvement = +{bt.value:.3f} Sharpe (t30v A {T['A']['shp']:.2f} / B {T['B']['shp']:.2f})")
    print("  params:", {k: round(v_, 3) if isinstance(v_, float) else v_ for k, v_ in bt.params.items()})
    print(f"  A 2016-20: {fmt(bt.user_attrs['A'])}")
    print(f"  B 2021-26: {fmt(bt.user_attrs['B'])}")
    print("\n  top 6 by min blend-improvement:")
    for t in sorted([t for t in study.trials if t.value is not None and t.value > -9], key=lambda t: -t.value)[:6]:
        pr = {k: round(x, 3) if isinstance(x, float) else x for k, x in t.params.items()}
        print(f"    +{t.value:.2f} | A {fmt(t.user_attrs['A'])} | B {fmt(t.user_attrs['B'])} | {pr}")
