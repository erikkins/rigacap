"""7-regime research wrapper — point-in-time regime labels across PITFWU history,
using the PRODUCTION classifier (app.services.market_regime), so research gates
match what prod actually detects.

Returns a cached per-date Series of regime labels (strong_bull / weak_bull /
rotating_bull / range_bound / weak_bear / panic_crash / recovery). The classifier
slices its inputs to as_of_date internally and carries hysteresis, so we feed full
dfs once and call per-date IN ORDER. SPY/VIX loaded with full history (indices have
no survivorship issue) so the 200-day lookback is satisfied even for early dates.

Why this matters: our shapes' "era-dependence" is likely REGIME-dependence — a binary
bull/bear gate lumps strong_bull (breakout habitat) with rotating_bull (mean-reversion
habitat). This gives the harness the real regimes. RESEARCH ONLY, local.

  from regime_research import regime_series
  reg = regime_series(start, end)   # pd.Series date -> regime label
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
import shapes_entry_edge as S
from app.services.market_regime import market_regime_service

CA = S.CA
CACHE = os.path.expanduser("~/pitfwu_cache/regime")


def _load_vix():
    try:
        import yfinance as yf
        x = yf.download("^VIX", start="2004-06-01", end="2026-06-05", progress=False, auto_adjust=False)
        if isinstance(x.columns, pd.MultiIndex):
            x.columns = x.columns.get_level_values(0)
        x.columns = [str(c).lower() for c in x.columns]
        x.index = pd.to_datetime(x.index).tz_localize(None).normalize()
        return x[["close"]].dropna()
    except Exception as e:
        print(f"  VIX load failed ({e}) -> implied-vol fallback", flush=True)
        return None


def _breadth_universe(start, end, k=50):
    syms = set()
    for d in pd.date_range(start, end, freq="45D"):
        syms |= set([s for s in v.universe_asof_prod(d, 200, 15.0) if not s.startswith("^")][:k])
    return list(syms)


def regime_series(start, end, k=50):
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, f"regime_{start.date()}_{end.date()}.pkl")
    if os.path.exists(path):
        return pd.read_pickle(path)
    prev_ext = v.EXT
    v.EXT = True  # full SPY/universe history so the 200-day lookback is always satisfied
    spy = v.split_adjusted("SPY", asof=end, ca=CA)
    vix = _load_vix()
    udfs = {}
    for s in _breadth_universe(start, end, k):
        try:
            udfs[s] = v.split_adjusted(s, asof=end, ca=CA)
        except Exception:
            pass
    # fresh classifier state (hysteresis is sequential; reset before a clean run)
    market_regime_service._current_regime_type = None
    market_regime_service._cache = {}
    market_regime_service._regime_history = []
    dates = spy.index[(spy.index >= start) & (spy.index <= end)]
    out = {}
    for d in dates:
        try:
            r = market_regime_service.detect_regime(spy, udfs, vix, as_of_date=d.to_pydatetime())
            out[d] = r.regime_type.value
        except Exception:
            out[d] = None
    ser = pd.Series(out).sort_index()
    ser.to_pickle(path)
    v.EXT = prev_ext
    return ser


if __name__ == "__main__":
    for label, s, e in [("A 2016-20", "2016-06-01", "2020-12-31"),
                        ("B 2021-26", "2021-01-01", "2026-05-29")]:
        ser = regime_series(pd.Timestamp(s), pd.Timestamp(e))
        comp = ser.value_counts(normalize=True).mul(100).round(1)
        print(f"\n{label} ({len(ser)} days) regime composition:", flush=True)
        for reg, pct in comp.items():
            print(f"  {reg:<14} {pct:>5.1f}%", flush=True)
