"""Reverse-swap (Erik) — is the regime-adaptive result robust WITHIN the modern era,
or overfit to 2021-26?

Modern era split: A = 2016-20, B = 2021-26 (both clean, survivorship-free). Pick the
best regime-adaptive core/offense weight (by Sharpe) on one half, then apply that SAME
weight OUT-OF-SAMPLE to the other — both directions. If both out-of-sample results stay
strong, it's robust within the modern regime; if either collapses, it's overfit.
RESEARCH ONLY, local. (MaxDD biweekly-approx.)
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
from shape_lab import bull_regime
from shapes_portfolio import perf, CAP0
from shapes_orthogonality import real_ensemble_equity
from three_way_blend import sleeve, BULL, BEAR


def streams(start, end):
    t30v, eres = real_ensemble_equity(start, end)
    bull = sleeve(BULL, start, end, cap=False)
    bear = sleeve(BEAR, start, end)
    grid = t30v.index
    rt = t30v.pct_change()
    rb = bull.reindex(grid, method="ffill").pct_change()
    rr = bear.reindex(grid, method="ffill").pct_change()
    reg = bull_regime(end).reindex(grid, method="ffill").fillna(True).astype(bool)
    df = pd.DataFrame({"t": rt, "bull": rb, "bear": rr, "reg": reg}).dropna()
    off = pd.Series(np.where(df["reg"].to_numpy(), df["bull"].to_numpy(), df["bear"].to_numpy()), index=df.index)
    return df, off, eres


def bp(df, off, wt):
    r = wt * df["t"] + (1 - wt) * off
    return perf(CAP0 * (1 + r).cumprod(), ppy=26)


def best_w(df, off):  # best core weight by Sharpe
    return max((round(wt, 1) for wt in np.arange(0, 1.01, 0.1)),
              key=lambda wt: bp(df, off, wt)[1])


def fmt(p):
    return f"{p[0]:.1f}% / {p[1]:.2f} / {p[2]:.0f}%"


if __name__ == "__main__":
    print("Building streams for A (2016-20) and B (2021-26)...", flush=True)
    dfA, offA, erA = streams(pd.Timestamp("2016-06-01"), pd.Timestamp("2020-12-31"))
    dfB, offB, erB = streams(pd.Timestamp("2021-01-01"), pd.Timestamp("2026-05-29"))
    wA, wB = best_w(dfA, offA), best_w(dfB, offB)

    print(f"\n  refs: t30v A {erA['ann']:.1f}%/{erA['sharpe']:.2f}   t30v B {erB['ann']:.1f}%/{erB['sharpe']:.2f}")
    print("\n  === FORWARD: fit on A, test on B ===")
    print(f"    best core weight on A: {wA*100:.0f}% core / {(1-wA)*100:.0f}% offense")
    print(f"    A in-sample : {fmt(bp(dfA, offA, wA))}")
    print(f"    B OUT-of-sample: {fmt(bp(dfB, offB, wA))}")
    print("\n  === REVERSE: fit on B, test on A ===")
    print(f"    best core weight on B: {wB*100:.0f}% core / {(1-wB)*100:.0f}% offense")
    print(f"    B in-sample : {fmt(bp(dfB, offB, wB))}")
    print(f"    A OUT-of-sample: {fmt(bp(dfA, offA, wB))}")
    print("\n  (CAGR / Sharpe / MaxDD; out-of-sample Sharpe staying ~strong both ways = robust within modern era)")
