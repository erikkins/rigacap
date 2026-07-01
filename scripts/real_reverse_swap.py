"""Real reverse-swap (exit-selection layer) — does our per-shape EXIT choice overfit?

For each shape: pick the best exit on half A, then SCORE that exit out-of-sample on
half B — and vice versa. Two tells of overfit:
  - DISAGREE: best exit on A != best exit on B (the "best" is unstable).
  - DECAY: the A-picked exit, applied to B, scores far below B's own-best (and rev).
If the same exit wins both halves and travels well out-of-sample, the choice is real.
A=2016-20, B=2021-26 (both clean). Per-trade MEDIAN net (robust). RESEARCH ONLY.
"""
import os, sys
R = "/Users/erikkins/CODE/stocker-app"
sys.path.insert(0, os.path.join(R, "backend")); sys.path.insert(0, os.path.join(R, "scripts"))
for _l in open(os.path.join(R, ".env")):
    if _l.startswith("DATABASE_URL="):
        os.environ["DATABASE_URL"] = _l.strip().split("=", 1)[1]; break
os.environ.setdefault("LAMBDA_ROLE", "worker")

import pandas as pd
from exit_lab import EXITS, collect_entries, stats

SHAPES_TEST = ["cup_handle", "vcp", "double_bottom", "inv_hs"]
A = (pd.Timestamp("2016-06-01"), pd.Timestamp("2020-12-31"))
B = (pd.Timestamp("2021-01-01"), pd.Timestamp("2026-05-29"))


def best_exit(entries):
    # by per-trade MEDIAN net (robust); stats() -> (n, median, win, sharpe, hold)
    return max(EXITS, key=lambda ex: stats(entries, EXITS[ex])[1])


def med(entries, ex):
    return stats(entries, EXITS[ex])[1]


if __name__ == "__main__":
    print("REAL REVERSE-SWAP — exit selection (A=2016-20, B=2021-26), per-trade median net\n", flush=True)
    print(f"  {'shape':<14} {'bestA':>10} {'bestB':>10} {'agree?':>7} | "
          f"{'A-sel→B':>8} {'(B-own)':>8} | {'B-sel→A':>8} {'(A-own)':>8}", flush=True)
    for sh in SHAPES_TEST:
        eA = collect_entries(sh, *A)
        eB = collect_entries(sh, *B)
        bA, bB = best_exit(eA), best_exit(eB)
        a_on_b = med(eB, bA)          # A's pick, scored OOS on B
        b_own = med(eB, bB)           # B's own best
        b_on_a = med(eA, bB)          # B's pick, scored OOS on A
        a_own = med(eA, bA)           # A's own best
        agree = "YES" if bA == bB else "no"
        print(f"  {sh:<14} {bA:>10} {bB:>10} {agree:>7} | "
              f"{a_on_b:>7.2f}% {b_own:>7.2f}% | {b_on_a:>7.2f}% {a_own:>7.2f}%", flush=True)
    print("\n  read: agree=YES + A-sel→B near B-own (and rev) = exit choice is REAL, not overfit.")
