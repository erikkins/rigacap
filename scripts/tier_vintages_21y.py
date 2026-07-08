"""21-year DAILY walk-forward of Preserver + Maximizer — apples-to-apples with Core.

Full history 2007-2026, daily resolution. Pre-2016 is EXT (survivorship-BIASED — the SAME
caveat Core's 21-year number carries); 2016+ is survivorship-free & point-in-time. Routing +
vol-brake identical to the productionized tiers. Outputs metrics + equity curves (for the
Track Record chart). RESEARCH; run locally.
"""
import os, sys, json
R = "/Users/erikkins/CODE/stocker-app"
sys.path.insert(0, os.path.join(R, "backend")); sys.path.insert(0, os.path.join(R, "scripts"))
for _l in open(os.path.join(R, ".env")):
    if _l.startswith("DATABASE_URL="):
        os.environ["DATABASE_URL"] = _l.strip().split("=", 1)[1]; break
os.environ.setdefault("LAMBDA_ROLE", "worker")

import numpy as np
import pandas as pd
import pitfwu_veneer as v
v.EXT = True  # full continuous history; pre-2016 survivorship-biased (same caveat as Core)
from shape_tpe import load_data
from stack_sleeves import sleeve_curve, PULLBACK, OVERSOLD
from regime_allocator_v2 import BREAKOUT
from regime_research import regime_series
from shapes_portfolio import perf, CAP0
import pitfwu_wf as pwf

CALM_BULL = {"strong_bull", "weak_bull"}
CAPITULATION = {"panic_crash", "recovery", "weak_bear"}
ROTATING = {"rotating_bull"}
START, END = pd.Timestamp("2007-01-03"), pd.Timestamp("2026-05-29")


def t30v_daily(start, end):
    m = pwf.run(start.to_pydatetime(), end.to_pydatetime(), trail=0.30, max_pos=20, size=0.045)
    ec = m.get("equity_curve") or []
    return pd.Series([x["equity"] for x in ec],
                     index=pd.to_datetime([x["date"] for x in ec])).sort_index()


def vol_scale(ret, target=0.20):
    rv = (ret.rolling(20).std() * np.sqrt(252)).shift(1)
    return (target / rv).clip(upper=1.0).fillna(1.0)


if __name__ == "__main__":
    print(f"Loading {START.date()}..{END.date()} DAILY (EXT full history)...", flush=True)
    data = load_data(START, END)
    print("  sleeve curves...", flush=True)
    pb = sleeve_curve(data, START, END, PULLBACK, "pullback_ma")
    ob = sleeve_curve(data, START, END, OVERSOLD, "oversold_bounce")
    bk = sleeve_curve(data, START, END, BREAKOUT, "breakout")
    print("  core walk-forward (t30v)...", flush=True)
    t = t30v_daily(START, END)
    grid = t.index
    rt = t.pct_change()
    rp = pb.reindex(grid, method="ffill").pct_change()
    ro = ob.reindex(grid, method="ffill").pct_change()
    rb = bk.reindex(grid, method="ffill").pct_change()
    reg = regime_series(START, END).reindex(grid, method="ffill").fillna("none")
    calm = reg.isin(CALM_BULL).to_numpy(); cap = reg.isin(CAPITULATION).to_numpy(); rot = reg.isin(ROTATING).to_numpy()
    df = pd.DataFrame({"t": rt, "p": rp, "o": ro, "b": rb}).fillna(0.0)
    b_scaled = df["b"] * vol_scale(df["b"])
    preserver = pd.Series(np.where(calm, df["p"], np.where(cap, df["o"], df["t"])), index=grid)
    maxpp = pd.Series(np.where(calm, df["p"], np.where(cap, df["o"], np.where(rot, b_scaled, df["t"]))), index=grid)

    curves = {}
    print(f"\n  {'tier':<20} {'Annualized':>11} {'Sharpe':>8} {'MaxDD':>8}  ({START.year}-{END.year}, daily)", flush=True)
    for name, r in [("Core (INTERNAL)", df["t"]), ("Preserver", preserver), ("Maximizer", maxpp)]:
        eq = CAP0 * (1 + r).cumprod()
        c, s, m = perf(eq, ppy=252)
        print(f"  {name:<20} {c:>10.1f}% {s:>8.2f} {m:>7.1f}%", flush=True)
        curves[name] = {"cagr": round(float(c), 2), "sharpe": round(float(s), 2), "maxdd": round(float(m), 1),
                        "dates": [d.strftime("%Y-%m-%d") for d in eq.index],
                        "equity": [round(float(x), 2) for x in eq.values]}
    json.dump(curves, open(os.path.join(R, "scripts", "tier_curves_21y.json"), "w"))
    print("\nSaved -> scripts/tier_curves_21y.json (metrics + equity curves for Track Record)", flush=True)
