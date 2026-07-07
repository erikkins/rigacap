"""Maximizer daily signal builder (SHADOW) — mirrors preserver_signal_service.

Same strategy-agnostic inputs (regime label, scanner_service.data_cache, live t30v
buy_signals) but routed by the MAXIMIZER table (maximizer_sleeves.route):
  rotating_bull  -> breakout sleeve (NEW vs Preserver — the aggressive leg)
  calm_bull      -> pullback_ma       (shared with Preserver)
  capitulation   -> oversold_bounce   (shared with Preserver)
  range_bound / unknown -> t30v (passthrough of the live Core buy_signals)

Note: the breakout leg's vol-brake (maximizer_sleeves.vol_scale) is a book-level EXPOSURE
overlay, applied in the portfolio/book layer — not at signal-selection time. This builder
just emits the routed BUY candidates. PURE / additive: no DB, no live t30v path.
"""
from __future__ import annotations

from typing import Dict, List, Tuple
import numpy as np
import pandas as pd

from app.services.maximizer_sleeves import route, SLEEVE_FNS, SLEEVE_HOLD

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
    """Return (source, signals) for the Maximizer book on `signal_date`.

    source == 't30v'  -> passthrough of the live t30v buy_signals (range_bound / unknown).
    else              -> the routed sleeve's firing names (breakout / pullback_ma /
                         oversold_bounce), ranked by recent 20d $-volume, capped.
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
        dvol = float(np.nanmean((df["close"] * df["volume"]).tail(20).to_numpy()))
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
