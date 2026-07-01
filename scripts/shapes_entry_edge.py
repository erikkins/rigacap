"""Shapes entry-edge — does chart-pattern detection have forward-return edge?

RESEARCH ONLY. Touches nothing in prod. Reads survivorship-free, split-correct
PITFWU bars (same veneer as pitfwu_entry_edge.py) and asks the one fundamental
question for a *Bull Rider* sleeve built on shapes:

    On the day a pattern completes (breakout), do those names beat the universe
    baseline over the next N days? If yes, the shape carries signal worth turning
    into a strategy. If no, we learned it cheaply.

First shape: CUP-AND-HANDLE. The idea comes from the legacy `findCupAndHandle`
proc, but the logic here is rewritten with modern, explicit geometry (the legacy
SQL math is not trusted — Erik's call). A clean detector:

  - LEFT LIP: a prior local peak in the older half of a ~6mo window.
  - CUP: a rounded decline then recovery back near the left lip; depth 12-35%,
    and U-shaped not V (bottom sits in the middle third, not at an edge).
  - RIGHT LIP: price recovers to within ~6% of the left lip.
  - HANDLE: a short shallow pullback (3-15%) off the right lip on lighter volume.
  - BREAKOUT (the signal): today closes above the handle's high, volume > avg.

EDGE = median forward return of breakout days MINUS median forward return of all
(symbol,date) cells in the same window (the no-skill baseline). Median is used
because momentum names have lottery right-tails that distort the mean.

Usage: AWS_PROFILE=rigacap python scripts/shapes_entry_edge.py [start] [end]
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
from datetime import datetime
import pitfwu_veneer as v
from app.services.scanner import _EXCLUDED_SET

HORIZONS = [5, 10, 20, 40, 60]
CA = v.load_corp_actions()

# ── Cup-and-handle geometry (modern rewrite of the legacy idea) ──────────────
WIN = 130           # ~6mo lookback window the cup must fit inside
CUP_MIN, CUP_MAX = 0.12, 0.35   # cup depth band
RIGHT_LIP_TOL = 0.06            # right side must recover within 6% of left lip
HANDLE_MAX = 25                 # handle forms within last N days
HANDLE_MIN_PB, HANDLE_MAX_PB = 0.03, 0.15  # handle pullback depth band
MIN_PRICE = 15.0
MIN_VOL = 500_000


def cup_and_handle_breakouts(c: np.ndarray, vol: np.ndarray) -> np.ndarray:
    """Return a boolean array: True on days a cup-and-handle breakout completes."""
    n = len(c)
    sig = np.zeros(n, dtype=bool)
    for t in range(WIN, n):
        if c[t] < MIN_PRICE or vol[t] < MIN_VOL:
            continue
        w = c[t - WIN:t + 1]
        m = len(w)
        # left lip = peak in the older half
        left_hi = w[: m // 2].max()
        left_idx = int(np.argmax(w[: m // 2]))
        # cup bottom = min after the left lip
        after = w[left_idx:]
        bottom = after.min()
        bottom_idx = left_idx + int(np.argmin(after))
        if left_hi <= 0:
            continue
        depth = (left_hi - bottom) / left_hi
        if not (CUP_MIN <= depth <= CUP_MAX):
            continue
        # U-shape, not V or J: bottom should sit in the middle third of the window
        if not (0.30 * m <= bottom_idx <= 0.80 * m):
            continue
        # right lip: recent recovery to within tolerance of the left lip
        right_region = w[bottom_idx:]
        right_hi = right_region.max()
        if right_hi < left_hi * (1 - RIGHT_LIP_TOL):
            continue
        # handle forms in the days BEFORE today (shallow pullback off the right
        # lip); the breakout is TODAY closing above the handle high. Keeping
        # today out of the handle window is what makes a breakout possible.
        handle = w[-(HANDLE_MAX + 1):-1]
        if len(handle) < 3:
            continue
        handle_hi = handle.max()
        am = int(np.argmax(handle))
        handle_lo = handle[am:].min()
        pb = (handle_hi - handle_lo) / handle_hi if handle_hi > 0 else 0.0
        if not (HANDLE_MIN_PB <= pb <= HANDLE_MAX_PB):
            continue
        # breakout: today closes above the handle high on above-average volume
        vbase = vol[max(0, t - 20):t].mean() if t >= 5 else vol[t]
        if c[t] > handle_hi and vol[t] > vbase:
            sig[t] = True
    return sig


def _frame(sym, end):
    df = v.split_adjusted(sym, asof=end, ca=CA)[["close", "volume"]].copy()
    c = df["close"].to_numpy(dtype=float)
    vol = df["volume"].to_numpy(dtype=float)
    df["sig"] = cup_and_handle_breakouts(c, vol)
    for h in HORIZONS:
        df[f"f{h}"] = df["close"].shift(-h) / df["close"] - 1.0
    return df


def measure(start, end, label, naive=False):
    if naive:
        # NAIVE (survivorship-biased): only the names liquid as of the window END
        # — i.e. today's survivors, applied backward. The failures/delistings that
        # happened during the window are silently excluded.
        union = set([s for s in v.universe_asof_prod(end, 300, 15.0)
                     if s not in _EXCLUDED_SET and not s.startswith("^")][:100])
    else:
        # RIGOROUS: point-in-time, survivorship-free union — every name that was
        # actually liquid at each date through the window, delistings included.
        union = set()
        for d in pd.date_range(start, end, freq="14D"):
            union |= set([s for s in v.universe_asof_prod(d, 300, 15.0)
                          if s not in _EXCLUDED_SET and not s.startswith("^")][:100])
    frames = {}
    for s in union:
        try:
            frames[s] = _frame(s, end)
        except Exception:
            pass

    rows_sig = {h: [] for h in HORIZONS}     # breakout-day forward returns
    rows_base = {h: [] for h in HORIZONS}    # all-cell baseline forward returns
    n_breakouts = 0
    for s, df in frames.items():
        sub = df.loc[(df.index >= pd.Timestamp(start)) & (df.index <= pd.Timestamp(end))]
        smask = sub["sig"].to_numpy()
        n_breakouts += int(smask.sum())
        for h in HORIZONS:
            fr = sub[f"f{h}"]
            rows_sig[h].extend(fr[smask].dropna().tolist())
            rows_base[h].extend(fr.dropna().tolist())

    print(f"\n=== CUP-AND-HANDLE entry edge — {label} ({start.date()}..{end.date()}) ===")
    print(f"  {len(frames)} names, {n_breakouts} breakout signals")
    print(f"  {'horiz':>6} {'n_sig':>7} {'med_SIG':>9} {'med_base':>9} {'EDGE':>8} {'%pos_SIG':>9} {'%pos_base':>10}")
    out = {"label": label, "start": str(start.date()), "end": str(end.date()),
           "names": len(frames), "breakouts": n_breakouts, "horizons": {}}
    for h in HORIZONS:
        sg = np.array(rows_sig[h]); bs = np.array(rows_base[h])
        if len(sg) == 0:
            print(f"  {h:>6} {'0':>7}  (no signals)")
            continue
        msig, mbase = np.median(sg) * 100, np.median(bs) * 100
        ppos_s = (sg > 0).mean() * 100
        ppos_b = (bs > 0).mean() * 100
        print(f"  {h:>6} {len(sg):>7} {msig:>8.2f}% {mbase:>8.2f}% {msig - mbase:>7.2f}% {ppos_s:>8.1f}% {ppos_b:>9.1f}%")
        out["horizons"][h] = {"n": len(sg), "med_sig": msig, "med_base": mbase,
                              "edge": msig - mbase, "ppos_sig": ppos_s, "ppos_base": ppos_b}
    return out


if __name__ == "__main__":
    # Two-step over ~10y of clean (survivorship-free, 2016+) PITFWU. The edge test
    # is no-fit, so the split is for STABILITY: a real shape edge should show in
    # both the early window and the later, held-out one — not one lucky stretch.
    # (When we later TUNE detector params, fit on Tier-1, confirm on Tier-2.)
    if len(sys.argv) > 2:
        windows = [(pd.Timestamp(sys.argv[1]), pd.Timestamp(sys.argv[2]), "custom")]
    else:
        windows = [
            (pd.Timestamp("2016-06-01"), pd.Timestamp("2020-12-31"), "Tier-1 (2016-2020)"),
            (pd.Timestamp("2021-01-01"), pd.Timestamp("2026-05-29"), "Tier-2 held-out (2021-2026)"),
        ]
    results = []
    contrast = []
    path = os.path.join(R, "scripts", "shapes_entry_edge_results.json")
    for start, end, label in windows:
        rig = measure(start, end, label + " · RIGOROUS (survivorship-free PiT)", naive=False)
        nai = measure(start, end, label + " · NAIVE (survivors only)", naive=True)
        results += [rig, nai]
        contrast.append((label, nai["names"], rig["names"],
                         nai["horizons"].get(20, {}).get("edge"),
                         rig["horizons"].get(20, {}).get("edge")))
        json.dump(results, open(path, "w"), indent=2)  # checkpoint after each window
    print("\n\n=============== NAIVE vs RIGOROUS — 20-day edge ===============")
    print(f"  {'window':<30} {'naive_n':>8} {'rig_n':>6} {'NAIVE':>8} {'RIGOROUS':>9} {'inflation':>10}")
    for lbl, nn, rn, ne, re in contrast:
        if ne is None or re is None:
            continue
        print(f"  {lbl:<30} {nn:>8} {rn:>6} {ne:>7.2f}% {re:>8.2f}% {ne - re:>9.2f}%")
    print("  inflation = how much the survivorship-biased backtest OVERSTATES the real 20d edge")
    print(f"\nsaved → {path}")
