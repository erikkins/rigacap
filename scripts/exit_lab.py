"""Exit factory — the symmetric twin of the shape factory.

Register an exit rule once; the entry×exit `sweep` runs every shape against every
exit, survivorship-free, two-step (Tier-1 2016-20 / Tier-2 held-out 21-26), and
reports HELD-OUT per-trade stats. That answers, with data not opinion:
  - is the 20-day time-exit actually arbitrary? what beats it held-out?
  - is the best exit UNIVERSAL (same winner across shapes) or PER-SHAPE
    (breakouts vs reversals want different exits)?

Add an exit =
    @register_exit("my_exit")
    def my_exit(o, h, l, c, vol, t):   # entry at bar t
        return net_return_fraction, hold_days   # net of round-trip cost

OBJECTIVE = per-trade Sharpe (mean/std of net returns) — robust, won't tail-chase
the way max-return optimisation did. Fixed sensible params per exit (no per-exit
knob-tuning) keeps it interpretable + overfit-resistant. RESEARCH ONLY, local.

CLI:
  python scripts/exit_lab.py list
  python scripts/exit_lab.py sweep cup_handle
  python scripts/exit_lab.py sweep cup_handle,double_bottom
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
from app.services.scanner import _EXCLUDED_SET
import shapes_entry_edge as S
from shape_lab import SHAPES, TIERS  # reuse the shape registry + tier defs

COST = 0.0015
MAXH = 60  # safety cap for path-based exits

# ── exit registry ────────────────────────────────────────────────────────────
EXITS = {}


def register_exit(name):
    def deco(fn):
        EXITS[name] = fn
        return fn
    return deco


def _stop_walk(o, h, l, c, vol, t, stop_of_hi=None, hard_stop=None, target=None,
               be_trig=None, key_rev=False, vol_mult=0.0, max_hold=MAXH):
    """Shared forward-walk used by most exits. Returns (net_return, hold_days)."""
    entry = c[t]
    hi = entry
    hard = entry * (1 - hard_stop) if hard_stop else 0.0
    be_done = False
    last = min(t + max_hold, len(c) - 1)
    for k in range(t + 1, last + 1):
        hi = max(hi, h[k])
        if be_trig and not be_done and h[k] >= entry * (1 + be_trig):
            hard = max(hard, entry); be_done = True
        if target and h[k] >= entry * (1 + target):
            return target - COST, k - t
        level = hard
        if stop_of_hi:
            level = max(level, hi * (1 - stop_of_hi))
        if level and l[k] <= level:
            honor = True
            if vol_mult:
                vbase = vol[max(0, k - 20):k].mean() if k >= 5 else vol[k]
                honor = vol[k] >= vol_mult * vbase
            if honor:
                return min(o[k], level) / entry - 1 - COST, k - t
        if key_rev and h[k] > h[k - 1] and c[k] < l[k - 1]:
            return c[k] / entry - 1 - COST, k - t
    return c[last] / entry - 1 - COST, last - t


# ── the menu (fixed, sensible params) ────────────────────────────────────────
@register_exit("time_3")  # for fast mean-reversion shapes (e.g. OMR)
def time_3(o, h, l, c, vol, t):
    last = min(t + 3, len(c) - 1); return c[last] / c[t] - 1 - COST, last - t


@register_exit("time_5")
def time_5(o, h, l, c, vol, t):
    last = min(t + 5, len(c) - 1); return c[last] / c[t] - 1 - COST, last - t


@register_exit("time_10")
def time_10(o, h, l, c, vol, t):
    last = min(t + 10, len(c) - 1); return c[last] / c[t] - 1 - COST, last - t


@register_exit("time_20")  # the current "arbitrary but works" baseline
def time_20(o, h, l, c, vol, t):
    last = min(t + 20, len(c) - 1); return c[last] / c[t] - 1 - COST, last - t


@register_exit("time_40")
def time_40(o, h, l, c, vol, t):
    last = min(t + 40, len(c) - 1); return c[last] / c[t] - 1 - COST, last - t


@register_exit("trail_10")
def trail_10(o, h, l, c, vol, t): return _stop_walk(o, h, l, c, vol, t, stop_of_hi=0.10)


@register_exit("trail_20")
def trail_20(o, h, l, c, vol, t): return _stop_walk(o, h, l, c, vol, t, stop_of_hi=0.20)


@register_exit("trail_30")
def trail_30(o, h, l, c, vol, t): return _stop_walk(o, h, l, c, vol, t, stop_of_hi=0.30)


@register_exit("tgt20_stop8")  # legacy "up-20 / down-8"
def tgt20_stop8(o, h, l, c, vol, t): return _stop_walk(o, h, l, c, vol, t, target=0.20, hard_stop=0.08)


@register_exit("stairstep")  # breakeven at +15%, then 20% trail
def stairstep(o, h, l, c, vol, t): return _stop_walk(o, h, l, c, vol, t, stop_of_hi=0.20, be_trig=0.15)


@register_exit("keyrev_60")  # key-reversal exit, 60d time backstop
def keyrev_60(o, h, l, c, vol, t): return _stop_walk(o, h, l, c, vol, t, key_rev=True)


@register_exit("volstop_20")  # 20% trail but only honour the stop on >=1.5x volume (Erik's idea)
def volstop_20(o, h, l, c, vol, t): return _stop_walk(o, h, l, c, vol, t, stop_of_hi=0.20, vol_mult=1.5)


# ── collect entries for a shape, then run each exit over them ─────────────────
def collect_entries(shape, start, end):
    fn = SHAPES[shape]["fn"]
    union = set()
    for d in pd.date_range(start, end, freq="14D"):
        union |= set([s for s in v.universe_asof_prod(d, 300, 15.0)
                      if s not in _EXCLUDED_SET and not s.startswith("^")][:100])
    entries = []
    for s in union:
        try:
            df = v.split_adjusted(s, asof=end, ca=S.CA)[["open", "high", "low", "close", "volume"]]
        except Exception:
            continue
        o, hi, lo, c, vol = (df[k].to_numpy(float) for k in ["open", "high", "low", "close", "volume"])
        sig = fn(o, hi, lo, c, vol)
        idx = df.index
        for t in np.where(sig)[0]:
            if (pd.Timestamp(start) <= idx[t] <= pd.Timestamp(end)) and t < len(c) - 2:
                entries.append((o, hi, lo, c, vol, int(t)))
    return entries


def stats(entries, exit_fn):
    r = np.array([exit_fn(*e[:5], e[5])[0] for e in entries])
    holds = np.array([exit_fn(*e[:5], e[5])[1] for e in entries])
    sd = r.std()
    return len(r), np.median(r) * 100, (r > 0).mean() * 100, (r.mean() / sd if sd > 0 else 0.0), holds.mean()


def cmd_sweep(shapes, exits=None):
    exits = exits or list(EXITS)
    for shape in shapes:
        print(f"\n### EXIT SWEEP — entry = {shape} ###")
        ent = {lbl: collect_entries(shape, s, e) for s, e, lbl in TIERS}
        t1lbl, t2lbl = TIERS[0][2], TIERS[1][2]
        print(f"  {'exit':<14} | {'T1 med':>7} {'T1 win':>6} {'T1 shp':>7} | "
              f"{'T2 med':>7} {'T2 win':>6} {'T2 shp':>7} {'T2 hold':>8}")
        rows = []
        for ex in exits:
            n1, m1, w1, s1, h1 = stats(ent[t1lbl], EXITS[ex])
            n2, m2, w2, s2, h2 = stats(ent[t2lbl], EXITS[ex])
            rows.append((ex, m2, s2, (m1, w1, s1, m2, w2, s2, h2)))
            print(f"  {ex:<14} | {m1:>6.2f}% {w1:>5.1f}% {s1:>+7.3f} | "
                  f"{m2:>6.2f}% {w2:>5.1f}% {s2:>+7.3f} {h2:>7.1f}d")
        best_shp = max(rows, key=lambda x: x[2])
        best_med = max(rows, key=lambda x: x[1])
        print(f"  >> held-out best by Sharpe: {best_shp[0]} ({best_shp[2]:+.3f})   "
              f"by median: {best_med[0]} ({best_med[1]:+.2f}%)   [baseline time_20]")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    names = sys.argv[2].split(",") if len(sys.argv) > 2 else ["cup_handle"]
    if cmd == "list":
        print("registered exits:", list(EXITS))
        print("registered shapes:", list(SHAPES))
    elif cmd == "sweep":
        for nm in names:
            if nm not in SHAPES:
                print(f"unknown shape '{nm}'. registered: {list(SHAPES)}"); sys.exit(1)
        cmd_sweep(names)
    else:
        print("commands: list | sweep <shape1,shape2,...>")
