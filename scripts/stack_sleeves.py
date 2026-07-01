"""Stack the two durable diversifiers on t30v.

pullback_ma@calm_bull (+0.33) and oversold_bounce@bull (+0.23) fire in DIFFERENT
regimes — so their blend lifts should ADD, not overlap. This builds both optimized
sleeve curves + the REAL t30v, aligns on t30v's grid, and compares:
  t30v alone  vs  t30v+pullback  vs  t30v+oversold  vs  t30v+BOTH
in each half (A=2016-20, B=2021-26) and the full window. If 3-way beats both 2-ways,
the diversifiers stack. RESEARCH ONLY, local. (MaxDD biweekly-approx.)
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
from shape_tpe import load_data, detect, N_POS
from shapes_portfolio import simulate, perf, CAP0
from shapes_orthogonality import real_ensemble_equity

# the TPE-validated winners
PULLBACK = {"regime": "calm_bull", "depth_min": 0.034, "depth_band": 0.057,
            "dryup": 1.106, "mom_min": 0.457, "hold": 40}
OVERSOLD = {"regime": "bull", "rsi_max": 15.07, "drop_min": 0.209, "mom_min": 0.30, "hold": 11}

WINDOWS = [("A 2016-20", pd.Timestamp("2016-06-01"), pd.Timestamp("2020-12-31")),
           ("B 2021-26", pd.Timestamp("2021-01-01"), pd.Timestamp("2026-05-29")),
           ("FULL 2016-26", pd.Timestamp("2016-06-01"), pd.Timestamp("2026-05-29"))]


def sleeve_curve(data, start, end, p, shape):
    _, close, dvol, feats = data
    sig = pd.DataFrame(detect(feats, p, shape)).reindex(close.index).fillna(False)
    return simulate(close, sig, dvol, start, end, N_POS, int(p["hold"]))


def best_blend(df, use_p, use_o):
    """Sweep weights (t, p, o) summing to 1, restricting p/o to 0 if not used.
    Returns (cagr, sharpe, mdd, (wt,wp,wo))."""
    grid = np.arange(0, 1.01, 0.1)
    best = None
    for wt in grid:
        for wp in (grid if use_p else [0.0]):
            wo = round(1 - wt - wp, 2)
            if wo < -1e-9 or (not use_o and wo > 1e-9):
                continue
            r = wt * df["t"] + wp * df["p"] + wo * df["o"]
            c, s, m = perf(CAP0 * (1 + r).cumprod(), ppy=26)
            if best is None or s > best[1]:
                best = (c, s, m, (round(wt, 1), round(wp, 1), round(wo, 2)))
    return best


if __name__ == "__main__":
    for label, start, end in WINDOWS:
        print(f"\n================ {label} ================", flush=True)
        data = load_data(start, end)
        pb = sleeve_curve(data, start, end, PULLBACK, "pullback_ma")
        ob = sleeve_curve(data, start, end, OVERSOLD, "oversold_bounce")
        t30v, _ = real_ensemble_equity(start, end)
        grid = t30v.index
        df = pd.DataFrame({"t": t30v.pct_change(),
                           "p": pb.reindex(grid, method="ffill").pct_change(),
                           "o": ob.reindex(grid, method="ffill").pct_change()}).dropna()
        ts, tshp, tmdd = perf(CAP0 * (1 + df["t"]).cumprod(), ppy=26)
        print(f"  t30v alone      : CAGR {ts:.1f}%  Sharpe {tshp:.2f}  MaxDD {tmdd:.1f}%")
        for name, up, uo in [("+ pullback     ", True, False),
                             ("+ oversold     ", False, True),
                             ("+ BOTH (stack) ", True, True)]:
            c, s, m, w = best_blend(df, up, uo)
            print(f"  {name}: CAGR {c:.1f}%  Sharpe {s:.2f}  MaxDD {m:.1f}%  "
                  f"(+{s - tshp:.2f} Shp)  w(t/pb/ob)={w}", flush=True)
