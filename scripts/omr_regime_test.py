"""Does a MARKET-regime gate rescue OMR? (Erik's hypothesis)

OMR = mean-reversion dip-buy. It must fail in a bear (dips keep falling). It only
checks the STOCK's 200-MA today, not the MARKET. This splits OMR's held-out
forward returns by market regime (SPY > its 200-day MA = "bull") to see if the
edge lives entirely in non-bear regimes. RESEARCH ONLY, local.

Usage: AWS_PROFILE=rigacap PITFWU_LOCAL=~/pitfwu_cache backend/venv/bin/python scripts/omr_regime_test.py
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
v.EXT = True   # full ~21y history (pre-2016 is survivorship-BIASED — label it; less
               # distorting for a short-hold mean-reversion bear strategy than buy-hold)
from app.services.scanner import _EXCLUDED_SET
import shapes_entry_edge as S
from shape_lab import SHAPES

CA = S.CA
OMR = SHAPES["pullback_bounce"]["fn"]


def bull_series(end):
    spy = v.split_adjusted("SPY", asof=end, ca=CA)["close"]
    return spy > spy.rolling(200, min_periods=50).mean()   # date -> bull?


def test(start, end, label, horizons=(5, 10)):
    bull = bull_series(end)
    union = set()
    for d in pd.date_range(start, end, freq="14D"):
        union |= set([s for s in v.universe_asof_prod(d, 300, 15.0)
                      if s not in _EXCLUDED_SET and not s.startswith("^")][:100])
    res = {hz: {"bull": [], "bear": [], "all": []} for hz in horizons}
    for s in union:
        try:
            df = v.split_adjusted(s, asof=end, ca=CA)[["open", "high", "low", "close", "volume"]]
        except Exception:
            continue
        o, h, l, c, vol = (df[k].to_numpy(float) for k in ["open", "high", "low", "close", "volume"])
        sig = OMR(o, h, l, c, vol)
        bull_on = bull.reindex(df.index, method="ffill").to_numpy()
        cs = df["close"]
        for hz in horizons:
            fwd = (cs.shift(-hz) / cs - 1.0).to_numpy()
            for t in np.where(sig)[0]:
                d = df.index[t]
                if not (pd.Timestamp(start) <= d <= pd.Timestamp(end)) or np.isnan(fwd[t]):
                    continue
                res[hz]["all"].append(fwd[t])
                (res[hz]["bull"] if bull_on[t] else res[hz]["bear"]).append(fwd[t])

    print(f"\n=== OMR by market regime — {label} ===")
    print(f"  {'horiz':>5} {'bucket':>5} {'n':>6} {'median':>8} {'win%':>7}")
    for hz in horizons:
        for b in ("bull", "bear", "all"):
            a = np.array(res[hz][b])
            if len(a) == 0:
                print(f"  {hz:>5} {b:>5} {0:>6}  --"); continue
            print(f"  {hz:>5} {b:>5} {len(a):>6} {np.median(a)*100:>7.2f}% {(a>0).mean()*100:>6.1f}%")


if __name__ == "__main__":
    # Two independent eras, each with its own bears — if bear-OMR holds in BOTH,
    # it's not a single-bear fluke. (Pre-2016 = survivorship-biased; labeled.)
    test(pd.Timestamp("2005-06-01"), pd.Timestamp("2015-12-31"), "EXT 2005-2015 (GFC/2011/2015) *surv-biased*")
    test(pd.Timestamp("2016-01-01"), pd.Timestamp("2026-05-29"), "2016-2026 (2018/2020/2022) clean")
