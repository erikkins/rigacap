"""A — harden the crash defense with an INDEPENDENT momentum-factor vol proxy.

v1 scaled the breakout by its OWN vol (self-referential, though that's the Barroso
standard). Here we build a SEPARATE momentum factor from the whole universe and use
ITS vol to throttle the breakout:
  - WML  : winners-minus-losers (top-decile minus bottom-decile 126d momentum) — the
           classic academic momentum factor (Daniel-Moskowitz crash indicator).
  - TOPD : long-only top-decile momentum (closer to what our long sleeves trade).
Scale = trailing-median-vol / current-vol, capped at 1x (de-risk only, self-calibrating,
no absolute threshold, no lookahead). If independent proxies tame the crash ~as well as
self-vol, the defense is robust + reusable across sleeves. RESEARCH ONLY, daily.
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


def dd_in(eq, s, e):
    x = eq[(eq.index >= pd.Timestamp(s)) & (eq.index <= pd.Timestamp(e))]
    return float((x / x.cummax() - 1).min() * 100) if len(x) > 2 else 0.0


def realized_vol(ret):
    return (ret.rolling(20).std() * np.sqrt(252)).shift(1)   # lagged, annualized


def scale_by(proxy_vol):
    ref = proxy_vol.rolling(252, min_periods=60).median()    # self-calibrating, trailing (no lookahead)
    return (ref / proxy_vol).clip(upper=1.0).fillna(1.0)      # de-risk only


if __name__ == "__main__":
    print("Loading 2016-2026 once...", flush=True)
    _, close, dvol, feats = load_data(FULL_S, FULL_E)
    sig = pd.DataFrame(detect(feats, STATIC, "breakout")).reindex(close.index).fillna(False)
    base = simulate(close, sig, dvol, FULL_S, FULL_E, 15, int(STATIC["hold"]))
    r = base.pct_change().fillna(0.0)

    # independent momentum factors from the whole universe
    ret = close.pct_change()
    mom = (close / close.shift(126) - 1.0)
    rank = mom.shift(1).rank(axis=1, pct=True)               # lagged cross-sectional rank
    top = ret.where(rank >= 0.90).mean(axis=1)
    bot = ret.where(rank <= 0.10).mean(axis=1)
    wml = (top - bot).reindex(r.index).fillna(0.0)           # winners - losers
    topd = top.reindex(r.index).fillna(0.0)                  # long-only top decile

    PROXIES = {"self (breakout own)": r, "WML (winners-losers)": wml, "TOPD (top-decile long)": topd}
    print("\n  proxy vol into Jan-2021 crash vs its own median:", flush=True)
    for nm, series in PROXIES.items():
        v = realized_vol(series)
        print(f"    {nm:<22}: Jan2021 {v.loc['2021-01-01':'2021-02-15'].mean()*100:>3.0f}%  "
              f"median {v.median()*100:>3.0f}%", flush=True)

    def report(name, scaled):
        eq = CAP0 * (1 + scaled).cumprod()
        c, s, m = perf(eq, ppy=252)
        print(f"  {name:<26} | {c:>5.1f}% {s:>5.2f} {m:>6.1f}% | "
              f"{dd_in(eq, '2021-01-01', '2021-12-31'):>6.1f}% {dd_in(eq, '2024-05-29', '2026-05-29'):>8.1f}%", flush=True)

    print(f"\n  {'variant':<26} | {'CAGR':>6} {'Shp':>5} {'fullDD':>7} | {'2021DD':>7} {'last2yrDD':>9}", flush=True)
    report("baseline (no scaling)", r)
    for nm, series in PROXIES.items():
        report(f"scaled by {nm}", r * scale_by(realized_vol(series)))
