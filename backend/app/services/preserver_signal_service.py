"""Preserver daily signal builder (SHADOW) — Phase 2 Step 2.

Produces the Preserver tier's daily BUY set by routing on the market regime and reusing
the SAME strategy-agnostic inputs the live t30v scan already computes:
  - the regime label (market_regime_service, already run in compute_shared_dashboard_data)
  - scanner_service.data_cache (per-symbol OHLCV+indicators DataFrames)
  - the existing t30v buy_signals (for the dominant rotating-bull / range-bound regimes)

Routing (see preserver_sleeves.route):
  rotating_bull / range_bound (~70-75% of days) -> Preserver book == t30v book (passthrough)
  calm_bull                                     -> pullback_ma sleeve
  capitulation (panic_crash/recovery/weak_bear) -> oversold_bounce sleeve

This module is PURE / additive: it takes inputs as args, touches no live storage and no
t30v path. Storage (a NEW parallel table, migration-first) + daily-scan wiring are the next
sub-steps; this builder is unit-testable against the research book first (shadow validation).
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from app.services.preserver_sleeves import route, SLEEVE_FNS, SLEEVE_HOLD

_MIN_BARS = 200


def _excluded() -> set:
    try:
        from app.services.scanner import _EXCLUDED_SET
        return set(_EXCLUDED_SET)
    except Exception:
        return set()


def build_daily_signals(
    data_cache: Dict[str, pd.DataFrame],
    regime: str,
    t30v_buy_signals: List[dict],
    signal_date,
    max_positions: int = 15,
) -> Tuple[str, List[dict]]:
    """Return (source, signals) for the Preserver book on `signal_date`.

    source == 't30v'  -> signals is the passed-through t30v buy_signals (dominant regime).
    else              -> signals is the sleeve's firing names, ranked by recent $-volume
                         (matching the research selection) and capped at max_positions.
    """
    src = route(regime)
    if src == "t30v":
        return "t30v", list(t30v_buy_signals)

    fn = SLEEVE_FNS[src]
    excluded = _excluded()
    cands: List[dict] = []
    for symbol, df in data_cache.items():
        if symbol in excluded or symbol.startswith("^"):
            continue
        if df is None or len(df) < _MIN_BARS:
            continue
        if not {"open", "high", "low", "close", "volume"}.issubset(df.columns):
            continue
        o, h, l, c, vol = (df[k].to_numpy(float) for k in ("open", "high", "low", "close", "volume"))
        sig = fn(o, h, l, c, vol)
        if not bool(sig[-1]):            # only TODAY's fresh signal
            continue
        price = float(c[-1])
        dvol = float(np.nanmean((df["close"] * df["volume"]).tail(20).to_numpy()))  # research selects by $-vol
        cands.append({
            "symbol": symbol,
            "price": price,
            "dollar_volume": dvol,
            "source": src,
            "regime": regime,
            "hold_days": SLEEVE_HOLD[src],
            "signal_date": str(signal_date),
        })
    cands.sort(key=lambda x: -x["dollar_volume"])
    return src, cands[:max_positions]
