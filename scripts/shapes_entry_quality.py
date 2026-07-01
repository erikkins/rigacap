"""Entry-quality sweep — can quality gates lift the cup-and-handle WIN-RATE?

The exit-menu TPE proved the exit isn't the lever: held-out, the typical trade
still loses (median <0, win <50%) because the entry catches too many fizzled
breakouts. This tests the actual lever — ENTRY QUALITY. We layer interpretable
gates onto the breakout and measure the held-out 20-day forward return WIN-RATE,
median, and signal count for each, survivorship-free, two-step (Tier-1 / Tier-2).

Gates (all computable from per-stock OHLCV — no extra data, runs offline):
  - vol  : breakout-day volume >= V x 20d-avg (conviction)
  - trend: close > 200-day MA (long-term uptrend; skip breakouts in downtrends)
  - mom  : 126-day (6mo) return >= M (relative-strength proxy; lead names)

A gate is worth it if it pushes the held-out win-rate toward/over 50% and the
median positive WITHOUT collapsing the signal count. RESEARCH ONLY, local, ~$0.

Usage: AWS_PROFILE=rigacap PITFWU_LOCAL=~/pitfwu_cache \
       backend/venv/bin/python scripts/shapes_entry_quality.py
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

FWD = 20  # the proven edge horizon

CONFIGS = [
    ("base", {}),
    ("vol>=1.5x", {"vol": 1.5}),
    ("vol>=2.0x", {"vol": 2.0}),
    ("trend(>MA200)", {"trend": True}),
    ("mom126>0", {"mom": 0.0}),
    ("mom126>20%", {"mom": 0.20}),
    ("vol1.5+trend", {"vol": 1.5, "trend": True}),
    ("vol1.5+mom>0", {"vol": 1.5, "mom": 0.0}),
    ("all(v1.5,trend,mom0)", {"vol": 1.5, "trend": True, "mom": 0.0}),
]


def _frames(start, end):
    """Per name: close, fwd20, breakout sig, and the gate inputs (vol/vol20, ma200, ret126)."""
    union = set()
    for d in pd.date_range(start, end, freq="14D"):
        union |= set([s for s in v.universe_asof_prod(d, 300, 15.0)
                      if s not in _EXCLUDED_SET and not s.startswith("^")][:100])
    out = []
    for s in union:
        try:
            df = v.split_adjusted(s, asof=end, ca=S.CA)[["close", "volume"]].copy()
        except Exception:
            continue
        c = df["close"]
        df["fwd"] = c.shift(-FWD) / c - 1.0
        df["sig"] = S.cup_and_handle_breakouts(c.to_numpy(float), df["volume"].to_numpy(float))
        df["vol20"] = df["volume"].rolling(20, min_periods=5).mean()
        df["ma200"] = c.rolling(200, min_periods=50).mean()
        df["ret126"] = c / c.shift(126) - 1.0
        out.append(df)
    return out


def _gate_mask(df, f):
    m = df["sig"].to_numpy()
    if f.get("vol"):
        m = m & (df["volume"].to_numpy() >= f["vol"] * df["vol20"].to_numpy())
    if f.get("trend"):
        m = m & (df["close"].to_numpy() > df["ma200"].to_numpy())
    if "mom" in f:
        m = m & (df["ret126"].to_numpy() >= f["mom"])
    return m


def evaluate(frames, start, end, label):
    base_fwd = []  # universe baseline (all cells) for edge reference
    per_cfg = {name: [] for name, _ in CONFIGS}
    for df in frames:
        sub = df.loc[(df.index >= pd.Timestamp(start)) & (df.index <= pd.Timestamp(end))]
        base_fwd.extend(sub["fwd"].dropna().tolist())
        for name, f in CONFIGS:
            mask = _gate_mask(sub, f)
            fr = sub["fwd"].to_numpy()[mask]
            per_cfg[name].extend(fr[~np.isnan(fr)].tolist())
    base_med = np.median(base_fwd) * 100 if base_fwd else 0.0

    print(f"\n=== ENTRY QUALITY — {label} (fwd {FWD}d, baseline median {base_med:+.2f}%) ===")
    print(f"  {'config':<22} {'n_sig':>6} {'median':>8} {'win%':>7} {'edge_vs_base':>13}")
    rows = []
    for name, _ in CONFIGS:
        a = np.array(per_cfg[name])
        if len(a) == 0:
            print(f"  {name:<22} {'0':>6}  (no signals)"); continue
        med = np.median(a) * 100
        win = (a > 0).mean() * 100
        print(f"  {name:<22} {len(a):>6} {med:>7.2f}% {win:>6.1f}% {med - base_med:>12.2f}%")
        rows.append({"config": name, "n": int(len(a)), "median": med, "win": win, "edge": med - base_med})
    return {"label": label, "baseline_median": base_med, "configs": rows}


if __name__ == "__main__":
    windows = [
        (pd.Timestamp("2016-06-01"), pd.Timestamp("2020-12-31"), "Tier-1 (2016-2020)"),
        (pd.Timestamp("2021-01-01"), pd.Timestamp("2026-05-29"), "Tier-2 held-out (2021-2026)"),
    ]
    out = []
    path = os.path.join(R, "scripts", "shapes_entry_quality_results.json")
    for start, end, label in windows:
        frames = _frames(start, end)
        out.append(evaluate(frames, start, end, label))
        json.dump(out, open(path, "w"), indent=2)
    print(f"\nThe gate to want: held-out win% toward/over 50 and median positive, "
          f"without crushing n_sig.\nsaved → {path}")
