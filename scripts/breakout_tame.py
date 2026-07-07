"""Can a MECHANICAL regime flag (no new tuned params) have saved the breakout's -33%?

The breakout only ENTERS in rotating_bull but HOLDS 29 days through any regime change.
Test a mechanical rule: stay invested only while the regime is 'safe', flatten otherwise
(uses the existing 7-regime classifier — a binary flag, not a curve-fit threshold).
First decompose WHERE the drawdown lives (2021 vs last-2yr vs full), then overlay a few
discrete safe-sets. RESEARCH ONLY, local, daily.
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
from shape_tpe import load_data, detect
from shapes_portfolio import simulate, perf, CAP0

STATIC = {"regime": "rotating", "buffer": 0.014, "vol_mult": 1.38, "mom_min": -0.005, "hold": 29}
FULL_S, FULL_E = pd.Timestamp("2016-06-01"), pd.Timestamp("2026-05-29")
CACHE = os.path.expanduser("~/pitfwu_cache/regime")

# discrete safe-sets (mechanical — regime-label groups, no tuned numbers)
SAFE_SETS = {
    "none (baseline hold)": None,
    "stay in rotating_bull": {"rotating_bull"},
    "stay in any bull":      {"strong_bull", "weak_bull", "rotating_bull"},
    "exit only on bear":     {"strong_bull", "weak_bull", "rotating_bull", "range_bound", "recovery"},
}


def dd_in(eq, s, e):
    x = eq[(eq.index >= pd.Timestamp(s)) & (eq.index <= pd.Timestamp(e))]
    return float((x / x.cummax() - 1).min() * 100) if len(x) > 2 else 0.0


if __name__ == "__main__":
    print("Loading 2016-2026 once...", flush=True)
    data = load_data(FULL_S, FULL_E)
    _, close, dvol, feats = data
    sig = pd.DataFrame(detect(feats, STATIC, "breakout")).reindex(close.index).fillna(False)
    base = simulate(close, sig, dvol, FULL_S, FULL_E, 15, int(STATIC["hold"]))
    base_ret = base.pct_change().fillna(0.0)

    reg = pd.concat([pd.read_pickle(os.path.join(CACHE, "regime_2016-06-01_2020-12-31.pkl")),
                     pd.read_pickle(os.path.join(CACHE, "regime_2021-01-01_2026-05-29.pkl"))]).sort_index()
    reg = reg.reindex(base_ret.index, method="ffill").fillna("none")

    print("\n  regime mix during the 2021 unwind (Feb-May 2021):", flush=True)
    r21 = reg[(reg.index >= "2021-02-01") & (reg.index <= "2021-05-31")]
    print("   ", r21.value_counts(normalize=True).mul(100).round(0).to_dict(), flush=True)

    print(f"\n  {'safe-set (mechanical)':<24} | {'CAGR':>6} {'Shp':>5} {'fullDD':>7} | {'2021DD':>7} {'last2yrDD':>9}", flush=True)
    for name, safe in SAFE_SETS.items():
        if safe is None:
            r = base_ret
        else:
            mask = reg.isin(safe).to_numpy()
            r = base_ret.where(mask, 0.0)   # flat (cash) when regime not in safe-set
        eq = CAP0 * (1 + r).cumprod()
        c, s, m = perf(eq, ppy=252)
        print(f"  {name:<24} | {c:>5.1f}% {s:>5.2f} {m:>6.1f}% | "
              f"{dd_in(eq, '2021-01-01', '2021-12-31'):>6.1f}% {dd_in(eq, '2024-05-29', '2026-05-29'):>8.1f}%", flush=True)
