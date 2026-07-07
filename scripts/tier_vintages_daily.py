"""Phase 1 — DAILY, shippable tier vintages on the recent (CLEAN) windows.

The long-history cut was biweekly (understates DD) + EXT (survivorship-biased). Here:
  - DAILY resolution (true drawdowns, esp. Maximizer++'s momentum crash).
  - Recent windows only (2021-26, last-2yr) = CLEAN survivorship-free data, no EXT caveat.
  - Lead marketing with these (recent past ~ near future).
t30v daily = single-backtest proxy at t30v config (walk-forward emits only biweekly; the
proxy is slightly conservative on DD). Maximizer++ breakout leg wears the vol-scaling brake.
RESEARCH ONLY, local.
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
from regime_allocator_v2 import BREAKOUT
from regime_research import regime_series
from shapes_portfolio import perf, CAP0
import pitfwu_wf as pwf

CALM_BULL = {"strong_bull", "weak_bull"}
CAPITULATION = {"panic_crash", "recovery", "weak_bear"}
ROTATING = {"rotating_bull"}
WINDOWS = [("LAST 2YR (2024-05->2026-05)", pd.Timestamp("2024-05-29"), pd.Timestamp("2026-05-29")),
           ("2021-2026 (incl 2022 + momo-crash)", pd.Timestamp("2021-01-01"), pd.Timestamp("2026-05-29"))]


def t30v_daily(start, end):
    m = pwf.run(start.to_pydatetime(), end.to_pydatetime(), trail=0.30, max_pos=20, size=0.045)
    ec = m.get("equity_curve") or []
    return pd.Series([x["equity"] for x in ec], index=pd.to_datetime([x["date"] for x in ec])).sort_index()


def vol_scale(ret, target=0.20):
    rv = (ret.rolling(20).std() * np.sqrt(252)).shift(1)   # daily annualized, lagged
    return (target / rv).clip(upper=1.0).fillna(1.0)


if __name__ == "__main__":
    for label, start, end in WINDOWS:
        print(f"\n================ {label} — DAILY, clean data ================", flush=True)
        data = load_data(start, end)
        pb = sleeve_curve(data, start, end, PULLBACK, "pullback_ma")
        ob = sleeve_curve(data, start, end, OVERSOLD, "oversold_bounce")
        bk = sleeve_curve(data, start, end, BREAKOUT, "breakout")
        t = t30v_daily(start, end)
        grid = t.index
        rt = t.pct_change()
        rp = pb.reindex(grid, method="ffill").pct_change()
        ro = ob.reindex(grid, method="ffill").pct_change()
        rb = bk.reindex(grid, method="ffill").pct_change()
        reg = regime_series(start, end).reindex(grid, method="ffill").fillna("none")
        calm = reg.isin(CALM_BULL).to_numpy(); cap = reg.isin(CAPITULATION).to_numpy(); rot = reg.isin(ROTATING).to_numpy()
        df = pd.DataFrame({"t": rt, "p": rp, "o": ro, "b": rb}).fillna(0.0)
        b_scaled = df["b"] * vol_scale(df["b"])
        preserver = pd.Series(np.where(calm, df["p"], np.where(cap, df["o"], df["t"])), index=grid)
        maxpp = pd.Series(np.where(calm, df["p"], np.where(cap, df["o"], np.where(rot, b_scaled, df["t"]))), index=grid)
        print(f"  {'tier':<24} {'Annualized':>11} {'Sharpe':>7} {'MaxDD':>8}", flush=True)
        for name, r in [("Core (t30v)", df["t"]), ("Preserver (v1)", preserver), ("Maximizer++ (v2 vol-sc)", maxpp)]:
            c, s, m = perf(CAP0 * (1 + r).cumprod(), ppy=252)
            print(f"  {name:<24} {c:>10.1f}% {s:>7.2f} {m:>7.1f}%", flush=True)
