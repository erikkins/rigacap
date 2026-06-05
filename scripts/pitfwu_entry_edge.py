"""Entry-edge measurement — the true fundamental.

Strips exits, sizing, concentration, regime. Asks one question: do the stocks
that PASS the ensemble entry filter, on average, beat the universe average over
the next N days? If yes, there's a real signal to build on. If no, every param
we ever tuned was polishing noise.

Method (on clean, survivorship-free, split-correct PITFWU data):
  - each date, each universe member: does it pass the entry filter?
  - forward return at 5/10/20/40/60 trading days
  - EDGE = mean forward return of qualifiers MINUS mean forward return of the
    whole universe on the same dates (the no-skill baseline)
  - report edge, win-rate vs baseline, and signal count per horizon

Usage: AWS_PROFILE=rigacap python scripts/pitfwu_entry_edge.py
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
from datetime import datetime
import pitfwu_veneer as v
from app.services.scanner import _EXCLUDED_SET

HORIZONS = [5, 10, 20, 40, 60]
CA = v.load_corp_actions()
DWAP_THRESH = 0.05      # price > dwap * 1.05
NEAR_HIGH = 0.03        # within 3% of 50-day high
MIN_VOL = 500_000
MIN_PRICE = 15.0


def _frame(sym, end):
    df = v.split_adjusted(sym, asof=end, ca=CA)[["close", "volume"]].copy()
    c = df["close"]
    df["dwap"] = (c * df["volume"]).rolling(200, min_periods=50).sum() / df["volume"].rolling(200, min_periods=50).sum()
    df["ma20"] = c.rolling(20, min_periods=1).mean()
    df["ma50"] = c.rolling(50, min_periods=1).mean()
    df["hi50"] = c.rolling(50, min_periods=1).max()
    # qualifies = ensemble entry filter
    df["qual"] = (
        (c > df["dwap"] * (1 + DWAP_THRESH)) &
        (c >= df["hi50"] * (1 - NEAR_HIGH)) &
        (c > df["ma20"]) & (c > df["ma50"]) &
        (df["volume"] >= MIN_VOL) & (c >= MIN_PRICE)
    )
    for h in HORIZONS:
        df[f"f{h}"] = c.shift(-h) / c - 1.0
    return df


def measure(start, end, label):
    union = set()
    for d in pd.date_range(start, end, freq="14D"):
        union |= set([s for s in v.universe_asof_prod(d, 300, 15.0) if s not in _EXCLUDED_SET and not s.startswith("^")][:100])
    frames = {}
    for s in union:
        try: frames[s] = _frame(s, end)
        except Exception: pass
    # gather qualifier vs universe forward returns, by date
    rows_q = {h: [] for h in HORIZONS}     # qualifier forward returns
    rows_u = {h: [] for h in HORIZONS}     # ALL-member forward returns (baseline)
    dates = pd.date_range(start, end, freq="B")
    for s, df in frames.items():
        sub = df.loc[(df.index >= pd.Timestamp(start)) & (df.index <= pd.Timestamp(end))]
        for h in HORIZONS:
            fv = sub[f"f{h}"].dropna()
            rows_u[h].extend(fv.tolist())
            qv = sub.loc[sub["qual"], f"f{h}"].dropna()
            rows_q[h].extend(qv.tolist())
    print(f"\n=== ENTRY EDGE — {label} ({start.date()}..{end.date()}), {len(frames)} names ===")
    print(f"  {'horiz':>6} {'n_signals':>10} {'signal_ret':>11} {'univ_ret':>10} {'EDGE':>8} {'win_vs_univ':>12}")
    for h in HORIZONS:
        q = np.array(rows_q[h]); u = np.array(rows_u[h])
        if len(q) == 0: continue
        sig = q.mean() * 100; uni = u.mean() * 100; edge = sig - uni
        win = (q > u.mean()).mean() * 100
        print(f"  {h:>6} {len(q):>10} {sig:>10.2f}% {uni:>9.2f}% {edge:>+7.2f}% {win:>11.1f}%")


if __name__ == "__main__":
    measure(datetime(2024, 6, 3), datetime(2026, 3, 31), "recent-2y")
    measure(datetime(2022, 1, 3), datetime(2026, 3, 31), "bear-incl 4y")
