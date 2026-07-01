"""Daily-resolution allocator — the true-drawdown honesty check, headlining the
LAST 2 YEARS (the marketing-relevant window; the future rhymes with the recent past).

Biweekly understated MaxDD. Here everything is DAILY: t30v via a single-backtest
proxy at the t30v config (the walk-forward only emits biweekly), daily sleeves, daily
regime routing (pure rotation). Read the DAILY MaxDD. t30v proxy is slightly
conservative (holds longer than the biweekly walk-forward) — so daily DD here is, if
anything, a worst-case. RESEARCH ONLY, local.
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
import pitfwu_wf as pwf

CALM_BULL = {"strong_bull", "weak_bull"}
CAPITULATION = {"panic_crash", "recovery", "weak_bear"}

WINDOWS = [("LAST 2YR (2024-05→2026-05)", pd.Timestamp("2024-05-29"), pd.Timestamp("2026-05-29")),
           ("2021-2026", pd.Timestamp("2021-01-01"), pd.Timestamp("2026-05-29"))]


def t30v_daily(start, end):
    m = pwf.run(start.to_pydatetime(), end.to_pydatetime(), trail=0.30, max_pos=20, size=0.045)
    ec = m.get("equity_curve") or []
    return pd.Series([x["equity"] for x in ec],
                     index=pd.to_datetime([x["date"] for x in ec])).sort_index()


if __name__ == "__main__":
    for label, start, end in WINDOWS:
        print(f"\n================ {label} ================", flush=True)
        data = load_data(start, end)
        pb = sleeve_curve(data, start, end, PULLBACK, "pullback_ma")
        ob = sleeve_curve(data, start, end, OVERSOLD, "oversold_bounce")
        t = t30v_daily(start, end)
        grid = t.index
        df = pd.DataFrame({"t": t.pct_change(),
                           "p": pb.reindex(grid, method="ffill").pct_change(),
                           "o": ob.reindex(grid, method="ffill").pct_change()}).dropna()
        reg = regime_series(start, end).reindex(df.index, method="ffill").fillna("none")
        calm = reg.isin(CALM_BULL).to_numpy(); cap = reg.isin(CAPITULATION).to_numpy()
        off = np.where(calm, df["p"].to_numpy(), np.where(cap, df["o"].to_numpy(), df["t"].to_numpy()))
        port = pd.Series(off, index=df.index)  # pure rotation (core 0%)
        tc, ts, tm = perf(CAP0 * (1 + df["t"]).cumprod(), ppy=252)
        ac, ash, am = perf(CAP0 * (1 + port).cumprod(), ppy=252)
        print(f"  regime mix: calm_bull {100*calm.mean():.0f}%  capitulation {100*cap.mean():.0f}%  "
              f"other {100*(1-calm.mean()-cap.mean()):.0f}%  ({len(df)} trading days)")
        print(f"  t30v (daily)      : CAGR {tc:.1f}%  Sharpe {ts:.2f}  MaxDD {tm:.1f}%")
        print(f"  ALLOCATOR (daily) : CAGR {ac:.1f}%  Sharpe {ash:.2f}  MaxDD {am:.1f}%   "
              f"(ΔCAGR {ac-tc:+.1f}  ΔShp {ash-ts:+.2f}  ΔMaxDD {am-tm:+.1f})", flush=True)
