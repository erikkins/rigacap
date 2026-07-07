"""Multi-window robustness — is the regime-adaptive 20% real or a 2021-26 fluke?

Runs the regime-adaptive switch (uncapped Bull Rider in bull, Bear Ripper in bear,
on a t30v core) across 5 rolling ~5-year windows over the full EXT history, and
reports the best CAGR-within-20%-DD and best-Sharpe allocation in each. If it
lands ~18-20% consistently it's a system; if only 2021-26 shines it's a window.

NOTE: pre-2016 is survivorship-BIASED (labeled). CAGR/Sharpe are solid on the
biweekly grid; MaxDD here is BIWEEKLY-APPROX (true daily DD is deeper — see the
daily t30v finding). RESEARCH ONLY, local.
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
import pitfwu_veneer as v
v.EXT = True  # full history (set before any panel load)
from shape_lab import bull_regime
from shapes_portfolio import perf, CAP0
from shapes_orthogonality import real_ensemble_equity
from three_way_blend import sleeve, BULL, BEAR

WINDOWS = [
    ("2009-2013 (GFC recov, 2011)", "2009-01-02", "2013-12-31"),
    ("2012-2016 (2015-16)",         "2012-01-03", "2016-12-31"),
    ("2015-2019 (2018 Q4)",         "2015-01-02", "2019-12-31"),
    ("2018-2022 (COVID, 2022)",     "2018-01-02", "2022-12-31"),
    ("2021-2026 (recent)",          "2021-01-01", "2026-05-29"),
]


def best(start, end):
    t30v, eres = real_ensemble_equity(start, end)
    bull = sleeve(BULL, start, end, cap=False)
    bear = sleeve(BEAR, start, end)
    grid = t30v.index
    rt = t30v.pct_change()
    rb = bull.reindex(grid, method="ffill").pct_change()
    rr = bear.reindex(grid, method="ffill").pct_change()
    reg = bull_regime(end).reindex(grid, method="ffill").fillna(True).astype(bool)
    df = pd.DataFrame({"t": rt, "bull": rb, "bear": rr, "reg": reg}).dropna()
    off = pd.Series(np.where(df["reg"].to_numpy(), df["bull"].to_numpy(), df["bear"].to_numpy()), index=df.index)
    rows = []
    for wt in np.arange(0, 1.01, 0.1):
        r = wt * df["t"] + (1 - wt) * off
        cagr, shp, mdd = perf(CAP0 * (1 + r).cumprod(), ppy=26)
        rows.append((round(wt, 1), cagr, shp, mdd))
    feas = [x for x in rows if x[3] >= -20.0]
    bg = max(feas, key=lambda x: x[1]) if feas else None
    bs = max(rows, key=lambda x: x[2])
    return eres, bg, bs, df["reg"].mean() * 100


if __name__ == "__main__":
    print("REGIME-ADAPTIVE ROBUSTNESS across rolling windows (EXT, pre-2016 surv-biased)\n", flush=True)
    print(f"  {'window':<28} {'%bull':>5} | {'t30v CAGR/Shp':>14} | {'bestCAGR<20DD':>22} | {'bestSharpe':>22}", flush=True)
    for label, s, e in WINDOWS:
        eres, bg, bs, bf = best(pd.Timestamp(s), pd.Timestamp(e))
        bgs = f"{bg[1]:.1f}%/{bg[2]:.2f}/{bg[3]:.0f}%@c{bg[0]*100:.0f}" if bg else "none<20DD"
        bss = f"{bs[1]:.1f}%/{bs[2]:.2f}/{bs[3]:.0f}%@c{bs[0]*100:.0f}"
        print(f"  {label:<28} {bf:>4.0f}% | {eres['ann']:>6.1f}%/{eres['sharpe']:>5.2f}  | {bgs:>22} | {bss:>22}", flush=True)
