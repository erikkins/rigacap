"""Phase 1 — publishable tier vintages in the CANONICAL lens.

The site publishes t30v as a 21-year continuous walk-forward (8.3% / 0.73 / 19%). To make
the 3 tiers comparable + shippable, run all three as a SINGLE continuous long-history path
and report annualized / Sharpe / MaxDD in the same lens:
  - t30v (Core, live)   — the base momentum engine (SANITY: should land near 8.3/0.73/19).
  - Preserver (v1)      — calm_bull->pullback, capitulation->oversold, else->t30v.
  - Maximizer++ (v2)    — as v1 but rotating_bull->breakout, WITH the momentum-factor
                          vol-scaling brake (Barroso-style, cap 1x, no leverage).
Pre-2016 is EXT (survivorship-biased) — label it. MaxDD biweekly-approx. RESEARCH ONLY.
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
v.EXT = True  # long continuous history (pre-2016 survivorship-biased)
from shape_tpe import load_data
from stack_sleeves import sleeve_curve, PULLBACK, OVERSOLD
from regime_allocator_v2 import BREAKOUT
from regime_research import regime_series
from shapes_portfolio import perf, CAP0
from shapes_orthogonality import real_ensemble_equity

CALM_BULL = {"strong_bull", "weak_bull"}
CAPITULATION = {"panic_crash", "recovery", "weak_bear"}
ROTATING = {"rotating_bull"}
START, END = pd.Timestamp("2009-01-02"), pd.Timestamp("2026-05-29")


def vol_scale(ret, target=0.20):
    """Barroso momentum-crash brake: scale down by trailing realized vol (lagged, cap 1x)."""
    rv = (ret.rolling(20).std() * np.sqrt(26)).shift(1)   # biweekly-grid annualized vol
    return (target / rv).clip(upper=1.0).fillna(1.0)


if __name__ == "__main__":
    print(f"Loading {START.date()}..{END.date()} (EXT continuous)...", flush=True)
    data = load_data(START, END)
    pb = sleeve_curve(data, START, END, PULLBACK, "pullback_ma")
    ob = sleeve_curve(data, START, END, OVERSOLD, "oversold_bounce")
    bk = sleeve_curve(data, START, END, BREAKOUT, "breakout")
    t30v, _ = real_ensemble_equity(START, END)
    grid = t30v.index
    rt = t30v.pct_change()
    rp = pb.reindex(grid, method="ffill").pct_change()
    ro = ob.reindex(grid, method="ffill").pct_change()
    rb = bk.reindex(grid, method="ffill").pct_change()
    reg = regime_series(START, END).reindex(grid, method="ffill").fillna("none")
    calm = reg.isin(CALM_BULL).to_numpy(); cap = reg.isin(CAPITULATION).to_numpy(); rot = reg.isin(ROTATING).to_numpy()
    df = pd.DataFrame({"t": rt, "p": rp, "o": ro, "b": rb}).fillna(0.0)

    # Maximizer++ breakout leg gets the vol-scaling brake
    b_scaled = df["b"] * vol_scale(df["b"])
    preserver = pd.Series(np.where(calm, df["p"], np.where(cap, df["o"], df["t"])), index=grid)
    maxpp = pd.Series(np.where(calm, df["p"], np.where(cap, df["o"], np.where(rot, b_scaled, df["t"]))), index=grid)

    print(f"\n  TIER VINTAGES — continuous {START.year}-{END.year} (EXT; pre-2016 surv-biased) — biweekly grid\n", flush=True)
    print(f"  {'tier':<22} {'Annualized':>11} {'Sharpe':>7} {'MaxDD':>7}", flush=True)
    for name, r in [("Core (t30v) [SANITY]", df["t"]),
                    ("Preserver (v1)", preserver),
                    ("Maximizer++ (v2, vol-sc)", maxpp)]:
        c, s, m = perf(CAP0 * (1 + r).cumprod(), ppy=26)
        print(f"  {name:<22} {c:>10.1f}% {s:>7.2f} {m:>6.1f}%", flush=True)
    print(f"\n  (canonical t30v published lens = 8.3% / 0.73 / 19% — compare the Core row as the sanity check)", flush=True)
