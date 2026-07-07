"""Three-way blend — the 20%/<20% test.

Combines the REAL prod t30v + capped Bull Rider basket + bear-gated Bear Ripper,
aligned on t30v's biweekly grid, and sweeps the weight simplex. Reports the
weighting that best approaches Erik's north star: 20% CAGR / <20% MaxDD.
RESEARCH ONLY, local. (MDD on biweekly grid ~ approximate.)

Usage: AWS_PROFILE=rigacap PITFWU_LOCAL=~/pitfwu_cache backend/venv/bin/python scripts/three_way_blend.py
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
from shape_lab import load
from shapes_portfolio import simulate, perf, CAP0
from shapes_orthogonality import real_ensemble_equity

BULL = ["cup_handle", "vcp", "double_bottom", "inv_hs"]
BEAR = ["pullback_bounce"]
N, HOLD = 15, 20


def sleeve(shapes, start, end, cap=True):
    close, sig, dvol, hold, sid, exspecs = load(shapes, start, end)
    cps = max(1, (N + len(shapes) - 1) // len(shapes)) if cap else None
    return simulate(close, sig, dvol, start, end, N, HOLD, hold_panel=hold, shape_panel=sid,
                    cap_per_shape=cps, exit_specs=exspecs)


def run(start, end, label):
    print(f"\n================ {label} ================", flush=True)
    t30v, eres = real_ensemble_equity(start, end)
    bull = sleeve(BULL, start, end)
    bear = sleeve(BEAR, start, end)
    grid = t30v.index
    rt = t30v.pct_change()
    rb = bull.reindex(grid, method="ffill").pct_change()
    rr = bear.reindex(grid, method="ffill").pct_change()
    df = pd.DataFrame({"t": rt, "bull": rb, "bear": rr}).dropna()

    def stat(wt, wbull, wbear):
        r = wt * df["t"] + wbull * df["bull"] + wbear * df["bear"]
        return perf(CAP0 * (1 + r).cumprod(), ppy=26)

    print(f"  reference: t30v {eres['ann']:.1f}%/{eres['sharpe']:.2f}/{eres['mdd']:.1f}%  "
          f"bull {perf(bull)[0]:.1f}%/{perf(bull)[1]:.2f}  bear {perf(bear)[0]:.1f}%/{perf(bear)[1]:.2f}")
    print(f"  {'t30v':>5} {'bull':>5} {'bear':>5} | {'CAGR':>6} {'Sharpe':>7} {'MaxDD':>7}")
    grid_w = []
    for wt in np.arange(0, 1.01, 0.1):
        for wbull in np.arange(0, 1.0 - wt + 1e-9, 0.1):
            wbear = round(1 - wt - wbull, 2)
            if wbear < -1e-9:
                continue
            cagr, shp, mdd = stat(wt, wbull, wbear)
            grid_w.append((round(wt, 1), round(wbull, 1), wbear, cagr, shp, mdd))

    # a few illustrative mixes
    for wt, wbull, wbear in [(1, 0, 0), (0.5, 0.5, 0), (0.5, 0.25, 0.25), (0.4, 0.4, 0.2),
                             (0.34, 0.33, 0.33), (0.5, 0, 0.5)]:
        cagr, shp, mdd = stat(wt, wbull, wbear)
        print(f"  {wt:>5.2f} {wbull:>5.2f} {wbear:>5.2f} | {cagr:>5.1f}% {shp:>7.2f} {mdd:>6.1f}%")

    # best toward goal: highest CAGR with MaxDD >= -20%
    feas = [g for g in grid_w if g[5] >= -20.0]
    if feas:
        bg = max(feas, key=lambda g: g[3])
        print(f"  >> best CAGR @ MaxDD<20%: t30v {bg[0]} bull {bg[1]} bear {bg[2]} -> "
              f"CAGR {bg[3]:.1f}% Sharpe {bg[4]:.2f} MaxDD {bg[5]:.1f}%")
    bs = max(grid_w, key=lambda g: g[4])
    print(f"  >> best Sharpe overall:     t30v {bs[0]} bull {bs[1]} bear {bs[2]} -> "
          f"CAGR {bs[3]:.1f}% Sharpe {bs[4]:.2f} MaxDD {bs[5]:.1f}%")


if __name__ == "__main__":
    run(pd.Timestamp("2021-01-01"), pd.Timestamp("2026-05-29"), "Tier-2 HELD-OUT (2021-26)")
    run(pd.Timestamp("2016-06-01"), pd.Timestamp("2026-05-29"), "Full (2016-2026)")
