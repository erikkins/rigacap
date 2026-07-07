"""7-regime adaptive allocator — the synthesis.

Static stacking crushed drawdown but tanked CAGR (capital parked in flat,
cash-when-not-in-regime sleeves). Fix: ROUTE the offense by the live regime, so
capital is always deployed in whatever's active —
    calm_bull      -> pullback_ma   (orderly-trend dip buy)
    capitulation   -> oversold_bounce (panic_crash/recovery/weak_bear snapback)
    everything else (mostly rotating_bull) -> t30v core
portfolio_ret = w_core*t30v + (1-w_core)*offense_routed.
w_core=0 is pure regime rotation. Compare vs t30v-alone in A/B/full.
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
from shape_tpe import load_data
from stack_sleeves import sleeve_curve, PULLBACK, OVERSOLD
from regime_research import regime_series
from shapes_portfolio import perf, CAP0
from shapes_orthogonality import real_ensemble_equity

CALM_BULL = {"strong_bull", "weak_bull"}
CAPITULATION = {"panic_crash", "recovery", "weak_bear"}

WINDOWS = [("A 2016-20", pd.Timestamp("2016-06-01"), pd.Timestamp("2020-12-31")),
           ("B 2021-26", pd.Timestamp("2021-01-01"), pd.Timestamp("2026-05-29")),
           ("FULL 2016-26", pd.Timestamp("2016-06-01"), pd.Timestamp("2026-05-29"))]


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
        reg = regime_series(start, end).reindex(df.index, method="ffill").fillna("none")
        calm = reg.isin(CALM_BULL).to_numpy()
        cap = reg.isin(CAPITULATION).to_numpy()
        # route offense by regime: pullback in calm_bull, oversold in capitulation, else t30v
        off = np.where(calm, df["p"].to_numpy(), np.where(cap, df["o"].to_numpy(), df["t"].to_numpy()))
        off = pd.Series(off, index=df.index)
        pct = lambda m: 100.0 * m.mean()
        print(f"  regime mix on grid: calm_bull {pct(calm):.0f}%  capitulation {pct(cap):.0f}%  "
              f"other(ride t30v) {100-pct(calm)-pct(cap):.0f}%", flush=True)

        ts, tshp, tmdd = perf(CAP0 * (1 + df["t"]).cumprod(), ppy=26)
        print(f"  t30v alone        : CAGR {ts:.1f}%  Sharpe {tshp:.2f}  MaxDD {tmdd:.1f}%")
        rows = []
        for wc in np.arange(0, 1.01, 0.1):
            r = wc * df["t"] + (1 - wc) * off
            c, s, m = perf(CAP0 * (1 + r).cumprod(), ppy=26)
            rows.append((round(wc, 1), c, s, m))
        for wc, c, s, m in rows:
            tag = "  <- pure rotation" if wc == 0 else ("  <- t30v" if wc == 1 else "")
            print(f"    core {wc*100:>4.0f}% / offense {(1-wc)*100:>4.0f}% | CAGR {c:>5.1f}%  Sharpe {s:>4.2f}  MaxDD {m:>6.1f}%{tag}")
        feas = [x for x in rows if x[3] >= -20.0]
        bg = max(feas, key=lambda x: x[1]) if feas else None
        bs = max(rows, key=lambda x: x[2])
        if bg:
            print(f"  >> best CAGR @ MaxDD<20%: core {bg[0]*100:.0f}% -> CAGR {bg[1]:.1f}%  Sharpe {bg[2]:.2f}  MaxDD {bg[3]:.1f}%")
        print(f"  >> best Sharpe          : core {bs[0]*100:.0f}% -> CAGR {bs[1]:.1f}%  Sharpe {bs[2]:.2f}  MaxDD {bs[3]:.1f}%")
