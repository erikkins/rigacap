"""Shapes strategy sim — does the cup-and-handle ENTRY edge survive into a
tradable NET return after an exit rule + transaction costs?

RESEARCH ONLY. Reuses the survivorship-free, point-in-time PITFWU detector from
shapes_entry_edge.py. For every cup-and-handle breakout (a "trade"):

  - ENTRY at that day's close.
  - EXIT at the first of: (a) trailing stop TRAIL% off the high-water mark since
    entry, or (b) a MAX_HOLD-day time stop. (20d was the proven edge horizon.)
  - NET return = exit/entry - 1 - COST (round-trip slippage+commission).

Reports per-trade net return (mean/median), win-rate, avg hold, and a rough
"always-deployed" annualized proxy — for Tier-1 and Tier-2 held-out, RIGOROUS
universe only (the honest book). NOT a portfolio sim (concurrency/sizing = #3).

Usage: AWS_PROFILE=rigacap PITFWU_LOCAL=~/pitfwu_cache \
       backend/venv/bin/python scripts/shapes_strategy.py
"""
import os, sys
R = "/Users/erikkins/CODE/stocker-app"
sys.path.insert(0, os.path.join(R, "backend")); sys.path.insert(0, os.path.join(R, "scripts"))
for _l in open(os.path.join(R, ".env")):
    if _l.startswith("DATABASE_URL="):
        os.environ["DATABASE_URL"] = _l.strip().split("=", 1)[1]; break
os.environ.setdefault("LAMBDA_ROLE", "worker")

import json
import numpy as np
import pandas as pd
import pitfwu_veneer as v
from app.services.scanner import _EXCLUDED_SET
import shapes_entry_edge as S

MAX_HOLD = 20            # trading days — the proven edge horizon
TRAIL = 0.10            # trailing stop: exit if price falls 10% off its high since entry
COST = 0.0015          # round-trip cost (15 bps: ~commission + slippage on liquid names)


def _rigorous_union(start, end):
    union = set()
    for d in pd.date_range(start, end, freq="14D"):
        union |= set([s for s in v.universe_asof_prod(d, 300, 15.0)
                      if s not in _EXCLUDED_SET and not s.startswith("^")][:100])
    return union


def _simulate_trade(c: np.ndarray, t: int):
    """Walk forward from entry day t; return (net_return, hold_days, exit_reason)."""
    entry = c[t]
    hi = entry
    last = min(t + MAX_HOLD, len(c) - 1)
    for k in range(t + 1, last + 1):
        hi = max(hi, c[k])
        if c[k] <= hi * (1 - TRAIL):
            return c[k] / entry - 1 - COST, k - t, "trail"
    return c[last] / entry - 1 - COST, last - t, "time"


def run(start, end, label):
    union = _rigorous_union(start, end)
    rets, holds, reasons = [], [], []
    for s in union:
        try:
            df = v.split_adjusted(s, asof=end, ca=S.CA)[["close", "volume"]]
        except Exception:
            continue
        c = df["close"].to_numpy(float)
        vol = df["volume"].to_numpy(float)
        sig = S.cup_and_handle_breakouts(c, vol)
        idx = df.index
        for t in np.where(sig)[0]:
            if not (pd.Timestamp(start) <= idx[t] <= pd.Timestamp(end)):
                continue
            if t >= len(c) - 2:
                continue
            r, h, why = _simulate_trade(c, t)
            rets.append(r); holds.append(h); reasons.append(why)

    rets = np.array(rets); holds = np.array(holds)
    n = len(rets)
    if n == 0:
        print(f"\n=== {label}: no trades ==="); return {"label": label, "trades": 0}
    mean, med = rets.mean() * 100, np.median(rets) * 100
    win = (rets > 0).mean() * 100
    avg_hold = holds.mean()
    trail_pct = np.mean([1 for x in reasons if x == "trail"]) / n * 100 if n else 0
    # Rough "always-deployed" annualized proxy: compound the MEAN net per-trade
    # return at the realized turnover (252/avg_hold trades per year). Single-slot
    # proxy — a real portfolio (concurrency) is #3; this is a sanity gauge only.
    ann = ((1 + rets.mean()) ** (252.0 / avg_hold) - 1) * 100 if avg_hold > 0 else 0
    print(f"\n=== STRATEGY — {label} ===")
    print(f"  trades={n}  avg_hold={avg_hold:.1f}d  trail-stop exits={trail_pct:.0f}%  "
          f"(MAX_HOLD={MAX_HOLD}d, TRAIL={TRAIL:.0%}, COST={COST*1e4:.0f}bps)")
    print(f"  net/trade: mean {mean:+.2f}%  median {med:+.2f}%  win-rate {win:.1f}%")
    print(f"  always-deployed annualized proxy (single slot): {ann:+.1f}%")
    return {"label": label, "trades": int(n), "avg_hold": float(avg_hold),
            "net_mean_pct": mean, "net_median_pct": med, "win_rate": win,
            "trail_exit_pct": trail_pct, "ann_proxy_pct": ann}


if __name__ == "__main__":
    windows = [
        (pd.Timestamp("2016-06-01"), pd.Timestamp("2020-12-31"), "Tier-1 (2016-2020)"),
        (pd.Timestamp("2021-01-01"), pd.Timestamp("2026-05-29"), "Tier-2 held-out (2021-2026)"),
    ]
    out = []
    path = os.path.join(R, "scripts", "shapes_strategy_results.json")
    for start, end, label in windows:
        out.append(run(start, end, label))
        json.dump(out, open(path, "w"), indent=2)
    print(f"\nsaved → {path}")
