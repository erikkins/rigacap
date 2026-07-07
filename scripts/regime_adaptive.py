"""Regime-adaptive switch — the real shot at 20%/<20%.

Static blends lose because they hold Bull Rider through bears (it bleeds) and Bear
Ripper through bulls (it idles). This routes the OFFENSE sleeve by market regime:
  - SPY > 200-MA (bull)  -> offense = Bull Rider
  - SPY < 200-MA (bear)  -> offense = Bear Ripper
on top of the always-on t30v core. Sweeps the core/offense split vs Erik's
20% CAGR / <20% MaxDD target, and compares to t30v-alone + the best static blend.
RESEARCH ONLY, local. (MDD on biweekly grid ~ approximate.)
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
from shape_lab import bull_regime
from shapes_portfolio import perf, CAP0
from shapes_orthogonality import real_ensemble_equity
from three_way_blend import sleeve, BULL, BEAR


def run(start, end, label):
    print(f"\n================ {label} ================", flush=True)
    t30v, eres = real_ensemble_equity(start, end)
    bull = sleeve(BULL, start, end, cap=False)   # UNCAPPED — only used in bull regime, so its
    bear = sleeve(BEAR, start, end)              # bear-period drawdown is sidestepped by the switch
    grid = t30v.index
    rt = t30v.pct_change()
    rb = bull.reindex(grid, method="ffill").pct_change()
    rr = bear.reindex(grid, method="ffill").pct_change()
    reg = bull_regime(end).reindex(grid, method="ffill").fillna(True).astype(bool)
    df = pd.DataFrame({"t": rt, "bull": rb, "bear": rr, "reg": reg}).dropna()
    # regime-adaptive offense: Bull Rider in bull, Bear Ripper in bear
    off = np.where(df["reg"].to_numpy(), df["bull"].to_numpy(), df["bear"].to_numpy())
    off = pd.Series(off, index=df.index)
    bull_frac = df["reg"].mean() * 100

    def stat(series):
        return perf(CAP0 * (1 + series).cumprod(), ppy=26)

    ct, st, mt = eres["ann"], eres["sharpe"], -abs(eres["mdd"])
    print(f"  ({bull_frac:.0f}% of periods bull)   t30v: {ct:.1f}% / {st:.2f} / {mt:.1f}%")
    print(f"  {'core%':>6} {'off%':>5} | {'CAGR':>6} {'Sharpe':>7} {'MaxDD':>7}")
    rows = []
    for wt in np.arange(0, 1.01, 0.1):
        r = wt * df["t"] + (1 - wt) * off
        cagr, shp, mdd = stat(r)
        rows.append((round(wt, 1), cagr, shp, mdd))
        print(f"  {wt*100:>5.0f}% {(1-wt)*100:>4.0f}% | {cagr:>5.1f}% {shp:>7.2f} {mdd:>6.1f}%")
    feas = [x for x in rows if x[3] >= -20.0]
    if feas:
        bg = max(feas, key=lambda x: x[1])
        print(f"  >> best CAGR @ MaxDD<20%: core {bg[0]*100:.0f}% / regime-offense {(1-bg[0])*100:.0f}% "
              f"-> CAGR {bg[1]:.1f}% Sharpe {bg[2]:.2f} MaxDD {bg[3]:.1f}%")
    bs = max(rows, key=lambda x: x[2])
    print(f"  >> best Sharpe:           core {bs[0]*100:.0f}% / regime-offense {(1-bs[0])*100:.0f}% "
          f"-> CAGR {bs[1]:.1f}% Sharpe {bs[2]:.2f} MaxDD {bs[3]:.1f}%")


if __name__ == "__main__":
    run(pd.Timestamp("2021-01-01"), pd.Timestamp("2026-05-29"), "Tier-2 HELD-OUT (2021-26)")
    run(pd.Timestamp("2016-06-01"), pd.Timestamp("2026-05-29"), "Full (2016-2026)")
