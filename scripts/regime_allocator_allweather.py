"""All-weather core weight for the 7-regime allocator.

Pure rotation (core 0%) crushed it in turbulent windows but dragged in the rare
dead-calm grind (2013-2015). Find ONE core weight (t30v vs regime-routed offense)
that is robust across EVERY window 2009->2026 — so we have a single honest setting.
All windows run EXT for apples-to-apples (pre-2016 surv-biased -> read relatively).
Selection rule: maximize the WORST-window Sharpe, subject to worst-window MaxDD >= -20%.
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
v.EXT = True  # all windows on full history for consistency (pre-2016 surv-biased)
from shape_tpe import load_data
from stack_sleeves import sleeve_curve, PULLBACK, OVERSOLD
from regime_research import regime_series
from shapes_portfolio import perf, CAP0
from shapes_orthogonality import real_ensemble_equity

CALM_BULL = {"strong_bull", "weak_bull"}
CAPITULATION = {"panic_crash", "recovery", "weak_bear"}
CORES = [round(x, 1) for x in np.arange(0, 1.01, 0.1)]

WINDOWS = [("2009-2012", pd.Timestamp("2009-01-02"), pd.Timestamp("2012-12-31")),
           ("2013-2015", pd.Timestamp("2013-01-02"), pd.Timestamp("2015-12-31")),
           ("2016-2020", pd.Timestamp("2016-06-01"), pd.Timestamp("2020-12-31")),
           ("2021-2026", pd.Timestamp("2021-01-01"), pd.Timestamp("2026-05-29"))]


def sweep_window(start, end):
    data = load_data(start, end)
    pb = sleeve_curve(data, start, end, PULLBACK, "pullback_ma")
    ob = sleeve_curve(data, start, end, OVERSOLD, "oversold_bounce")
    t30v, _ = real_ensemble_equity(start, end)
    grid = t30v.index
    df = pd.DataFrame({"t": t30v.pct_change(),
                       "p": pb.reindex(grid, method="ffill").pct_change(),
                       "o": ob.reindex(grid, method="ffill").pct_change()}).dropna()
    reg = regime_series(start, end).reindex(df.index, method="ffill").fillna("none")
    calm = reg.isin(CALM_BULL).to_numpy(); cap = reg.isin(CAPITULATION).to_numpy()
    off = np.where(calm, df["p"].to_numpy(), np.where(cap, df["o"].to_numpy(), df["t"].to_numpy()))
    off = pd.Series(off, index=df.index)
    t30v_perf = perf(CAP0 * (1 + df["t"]).cumprod(), ppy=26)
    sweep = {wc: perf(CAP0 * (1 + (wc * df["t"] + (1 - wc) * off)).cumprod(), ppy=26) for wc in CORES}
    return t30v_perf, sweep


if __name__ == "__main__":
    res = {}
    for label, s, e in WINDOWS:
        tp, sweep = sweep_window(s, e)
        res[label] = (tp, sweep)
        print(f"  {label}: t30v {tp[0]:.1f}%/{tp[1]:.2f}/{tp[2]:.0f}%  "
              f"| rotation(0%) {sweep[0.0][0]:.1f}%/{sweep[0.0][1]:.2f}/{sweep[0.0][2]:.0f}%", flush=True)

    print(f"\n  {'core':>5} | " + " | ".join(f"{w:>16}" for w, _, _ in WINDOWS) + " || minShp  avgCAGR  worstDD")
    best = None
    for wc in CORES:
        cells, sharpes, cagrs, mdds = [], [], [], []
        for label, _, _ in WINDOWS:
            c, sh, m = res[label][1][wc]
            cells.append(f"{c:>5.1f}/{sh:.2f}/{m:>5.0f}"); sharpes.append(sh); cagrs.append(c); mdds.append(m)
        minshp, avgcagr, worstdd = min(sharpes), np.mean(cagrs), min(mdds)
        print(f"  {wc*100:>4.0f}% | " + " | ".join(f"{x:>16}" for x in cells) + f" || {minshp:>5.2f}  {avgcagr:>6.1f}  {worstdd:>6.0f}")
        if worstdd >= -20.0 and (best is None or minshp > best[1]):
            best = (wc, minshp, avgcagr, worstdd)
    if best:
        print(f"\n  >> ALL-WEATHER core = {best[0]*100:.0f}% t30v / {(1-best[0])*100:.0f}% regime-offense "
              f"(worst-window Sharpe {best[1]:.2f}, avg CAGR {best[2]:.1f}%, worst DD {best[3]:.0f}%)")
