"""Allocator v2 — route the DOMINANT rotating_bull regime to the breakout engine.

v1 rode t30v in rotating_bull (~85% of the time). The breakout@rotating_bull sleeve
(+0.369 blend-improvement, Sharpe 1.2+) beat t30v THERE — so route rotating_bull to it:
    calm_bull    -> pullback_ma
    capitulation -> oversold_bounce
    rotating_bull-> breakout            (NEW: the dominant-regime engine)
    else (range_bound) -> t30v
Compare v2 vs v1 (t30v in rotating) vs t30v-alone. CAUTION: breakout is momentum-family
+ likely modern-only — EXT holdout is the real test. RESEARCH ONLY. (MaxDD biweekly-approx.)
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
v.EXT = True  # all windows on full history (pre-2016 surv-biased) so breakout gets its EXT holdout
from shape_tpe import load_data
from stack_sleeves import sleeve_curve, PULLBACK, OVERSOLD
from regime_research import regime_series
from shapes_portfolio import perf, CAP0
from shapes_orthogonality import real_ensemble_equity

BREAKOUT = {"regime": "rotating", "buffer": 0.014, "vol_mult": 1.38, "mom_min": -0.005, "hold": 29}
CALM_BULL = {"strong_bull", "weak_bull"}
CAPITULATION = {"panic_crash", "recovery", "weak_bear"}
ROTATING = {"rotating_bull"}

WINDOWS = [("EXT 2009-2012 *holdout*", pd.Timestamp("2009-01-02"), pd.Timestamp("2012-12-31")),
           ("EXT 2013-2015 *holdout*", pd.Timestamp("2013-01-02"), pd.Timestamp("2015-12-31")),
           ("2016-2020", pd.Timestamp("2016-06-01"), pd.Timestamp("2020-12-31")),
           ("2021-2026", pd.Timestamp("2021-01-01"), pd.Timestamp("2026-05-29"))]


if __name__ == "__main__":
    for label, start, end in WINDOWS:
        print(f"\n================ {label} ================", flush=True)
        data = load_data(start, end)
        pb = sleeve_curve(data, start, end, PULLBACK, "pullback_ma")
        ob = sleeve_curve(data, start, end, OVERSOLD, "oversold_bounce")
        bk = sleeve_curve(data, start, end, BREAKOUT, "breakout")
        t30v, _ = real_ensemble_equity(start, end)
        grid = t30v.index
        df = pd.DataFrame({"t": t30v.pct_change(),
                           "p": pb.reindex(grid, method="ffill").pct_change(),
                           "o": ob.reindex(grid, method="ffill").pct_change(),
                           "b": bk.reindex(grid, method="ffill").pct_change()}).dropna()
        reg = regime_series(start, end).reindex(df.index, method="ffill").fillna("none")
        calm = reg.isin(CALM_BULL).to_numpy(); cap = reg.isin(CAPITULATION).to_numpy()
        rot = reg.isin(ROTATING).to_numpy()
        # v1: rotating -> t30v ; v2: rotating -> breakout
        off1 = np.where(calm, df["p"], np.where(cap, df["o"], df["t"]))
        off2 = np.where(calm, df["p"], np.where(cap, df["o"], np.where(rot, df["b"], df["t"])))
        for name, series in [("t30v alone      ", df["t"]),
                             ("v1 (rot->t30v)  ", pd.Series(off1, index=df.index)),
                             ("v2 (rot->break) ", pd.Series(off2, index=df.index))]:
            c, s, m = perf(CAP0 * (1 + series).cumprod(), ppy=26)
            print(f"  {name}: CAGR {c:>5.1f}%  Sharpe {s:>4.2f}  MaxDD {m:>6.1f}%", flush=True)
