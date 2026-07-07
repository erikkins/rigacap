"""A secondary proxy for momentum crashes — the momentum factor's OWN realized vol.

Market-regime (SPY/VIX/breadth) is blind to momentum crashes (index stays healthy while
leadership unwinds — see 2021, 100% rotating_bull through a -32% sleeve drawdown). But the
momentum factor's OWN volatility spikes into a crash (Barroso-Santa-Clara; Daniel-Moskowitz).
So sample the breakout sleeve's own trailing realized vol and scale exposure inversely.
LAGGED vol only (no lookahead). vol-TARGET has NO threshold to overfit. RESEARCH ONLY, daily.
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
from shape_tpe import load_data, detect
from shapes_portfolio import simulate, perf, CAP0

STATIC = {"regime": "rotating", "buffer": 0.014, "vol_mult": 1.38, "mom_min": -0.005, "hold": 29}
FULL_S, FULL_E = pd.Timestamp("2016-06-01"), pd.Timestamp("2026-05-29")


def dd_in(eq, s, e):
    x = eq[(eq.index >= pd.Timestamp(s)) & (eq.index <= pd.Timestamp(e))]
    return float((x / x.cummax() - 1).min() * 100) if len(x) > 2 else 0.0


if __name__ == "__main__":
    print("Loading 2016-2026 once...", flush=True)
    _, close, dvol, feats = load_data(FULL_S, FULL_E)
    sig = pd.DataFrame(detect(feats, STATIC, "breakout")).reindex(close.index).fillna(False)
    base = simulate(close, sig, dvol, FULL_S, FULL_E, 15, int(STATIC["hold"]))
    r = base.pct_change().fillna(0.0)

    # the secondary proxy: sleeve's OWN trailing realized vol (annualized), LAGGED 1 day
    rv = (r.rolling(20).std() * np.sqrt(252)).shift(1)
    print(f"\n  momentum-factor realized vol (ann): median {rv.median()*100:.0f}%  "
          f"| into 2021 crash (Jan 2021): {rv.loc['2021-01-01':'2021-02-15'].mean()*100:.0f}%  "
          f"| 2016-2019 avg: {rv.loc[:'2019-12-31'].mean()*100:.0f}%", flush=True)

    def report(name, scaled):
        eq = CAP0 * (1 + scaled).cumprod()
        c, s, m = perf(eq, ppy=252)
        print(f"  {name:<26} | {c:>5.1f}% {s:>5.2f} {m:>6.1f}% | "
              f"{dd_in(eq, '2021-01-01', '2021-12-31'):>6.1f}% {dd_in(eq, '2024-05-29', '2026-05-29'):>8.1f}%", flush=True)

    print(f"\n  {'variant':<26} | {'CAGR':>6} {'Shp':>5} {'fullDD':>7} | {'2021DD':>7} {'last2yrDD':>9}", flush=True)
    report("baseline (no scaling)", r)
    for tgt in [0.15, 0.20, 0.25]:                        # vol-TARGET: no threshold, cap at 1x (de-risk only)
        scale = (tgt / rv).clip(upper=1.0).fillna(1.0)
        report(f"vol-target {int(tgt*100)}% (cap 1x)", r * scale)
    for tgt in [0.20]:                                    # vol-target allowing modest leverage
        scale = (tgt / rv).clip(upper=1.5).fillna(1.0)
        report(f"vol-target 20% (cap 1.5x)", r * scale)
    # vol-FLAG: step aside when vol in top quartile of its own trailing 1y (self-calibrating pctile)
    thresh = rv.rolling(252, min_periods=60).quantile(0.75)
    flag = (rv <= thresh).fillna(True)
    report("vol-flag (<75th pctile)", r.where(flag, 0.0))
