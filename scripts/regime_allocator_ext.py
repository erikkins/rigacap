"""EXT third-holdout for the 7-regime allocator — PROVE it's not tuned-to-the-test.

Same allocator, FROZEN sleeve params (tuned only on 2016-26), run on pre-2016 EXT
windows the diversifiers have NEVER seen. Pre-2016 is survivorship-BIASED, so read
the RELATIVE improvement over t30v (both run on the same biased data), not absolute
levels. If the allocator beats t30v on all axes here too, the edge is real.
RESEARCH ONLY, local. (MaxDD biweekly-approx.)
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
v.EXT = True  # pre-2016 history (survivorship-biased — relative comparison only)
from shape_tpe import load_data
from stack_sleeves import sleeve_curve, PULLBACK, OVERSOLD
from regime_research import regime_series
from shapes_portfolio import perf, CAP0
from shapes_orthogonality import real_ensemble_equity

CALM_BULL = {"strong_bull", "weak_bull"}
CAPITULATION = {"panic_crash", "recovery", "weak_bear"}

WINDOWS = [("EXT 2009-2012 *surv-biased*", pd.Timestamp("2009-01-02"), pd.Timestamp("2012-12-31")),
           ("EXT 2013-2015 *surv-biased*", pd.Timestamp("2013-01-02"), pd.Timestamp("2015-12-31"))]


def run(label, start, end):
    print(f"\n================ {label} ================", flush=True)
    data = load_data(start, end)
    pb = sleeve_curve(data, start, end, PULLBACK, "pullback_ma")
    ob = sleeve_curve(data, start, end, OVERSOLD, "oversold_bounce")
    t30v, _ = real_ensemble_equity(start, end)
    grid = t30v.index
    df = pd.DataFrame({"t": t30v.pct_change(),
                       "p": pb.reindex(grid, method="ffill").pct_change(),
                       "o": ob.reindex(grid, method="ffill").pct_change()}).dropna()
    reg = regime_series(start, end).reindex(df.index, method="ffill").fillna("none")
    calm = reg.isin(CALM_BULL).to_numpy()
    cap = reg.isin(CAPITULATION).to_numpy()
    off = np.where(calm, df["p"].to_numpy(), np.where(cap, df["o"].to_numpy(), df["t"].to_numpy()))
    off = pd.Series(off, index=df.index)
    print(f"  regime mix: calm_bull {100*calm.mean():.0f}%  capitulation {100*cap.mean():.0f}%  "
          f"other(t30v) {100*(1-calm.mean()-cap.mean()):.0f}%", flush=True)
    ts, tshp, tmdd = perf(CAP0 * (1 + df["t"]).cumprod(), ppy=26)
    print(f"  t30v alone   : CAGR {ts:.1f}%  Sharpe {tshp:.2f}  MaxDD {tmdd:.1f}%")
    rows = [(round(wc, 1), *perf(CAP0 * (1 + (wc * df["t"] + (1 - wc) * off)).cumprod(), ppy=26))
            for wc in np.arange(0, 1.01, 0.1)]
    pr = rows[0]  # core 0% = pure rotation
    print(f"  ALLOCATOR(pure rotation, core 0%): CAGR {pr[1]:.1f}%  Sharpe {pr[2]:.2f}  MaxDD {pr[3]:.1f}%")
    bs = max(rows, key=lambda x: x[2])
    print(f"  ALLOCATOR(best Sharpe, core {bs[0]*100:.0f}%): CAGR {bs[1]:.1f}%  Sharpe {bs[2]:.2f}  MaxDD {bs[3]:.1f}%")
    verdict = "BEATS t30v" if (pr[1] > ts and pr[2] > tshp and pr[3] > tmdd) else "mixed"
    print(f"  >> pure-rotation vs t30v: {verdict}  (ΔCAGR {pr[1]-ts:+.1f}  ΔShp {pr[2]-tshp:+.2f}  ΔMaxDD {pr[3]-tmdd:+.1f})")


if __name__ == "__main__":
    for label, s, e in WINDOWS:
        run(label, s, e)
