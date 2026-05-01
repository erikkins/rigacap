"""Intraday-accurate trailing-stop simulation against historical WF trades.

Closes the parity gap: production scanner fires trailing stops intraday (every
5 min during market hours); WF backtester fires only at EOD close. This module
re-runs each WF trade with intraday-aware exit logic so we can measure the
actual delta — does production execution outperform what we publish, or
underperform it?

Public flow:
    validator = IntradayWFValidator(trailing_stop_pct=0.12)
    results = await validator.validate_trades(trades, daily_bars_lookup, cache)

Outputs per-trade comparisons + aggregate stats (price-improvement distribution,
sum of pnl delta, count of trades where intraday fired earlier).

Scope: trades with exit_reason == 'trailing_stop'. Market-regime and rebalance
exits are batch-driven by daily signals, not intraday-actionable.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Callable, Dict, List, Optional, Awaitable

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class IntradayTradeResult:
    """Per-trade comparison: original EOD-based exit vs intraday-aware exit."""
    trade_idx: int
    symbol: str
    entry_date: str
    entry_price: float

    # Original (from WF backtester — EOD-based trailing stop)
    original_exit_date: str
    original_exit_price: float
    original_pnl_pct: float

    # Intraday simulation (minute-by-minute HWM tracking)
    intraday_exit_date: str
    intraday_exit_price: float
    intraday_exit_minute: Optional[str]  # ISO timestamp
    intraday_pnl_pct: float
    intraday_running_hwm: float  # the HWM at the moment of stop trigger

    # Delta
    pnl_delta_pct: float          # intraday - original (positive = intraday better)
    exit_earlier_days: int        # how many days earlier intraday exited (0 = same day)
    fired_intraday: bool          # True if intraday stop fired at all
    minute_bars_used: bool        # did simulator actually walk minutes for this trade


@dataclass
class IntradayValidationSummary:
    total_trades: int = 0
    trades_simulated: int = 0          # trades where minute-bar simulation ran
    trades_no_change: int = 0          # intraday matched original
    trades_intraday_better: int = 0
    trades_intraday_worse: int = 0
    sum_pnl_delta_pct: float = 0.0
    avg_pnl_delta_pct: float = 0.0
    median_pnl_delta_pct: float = 0.0
    median_earlier_exit_days: float = 0.0
    minute_bar_fetches: int = 0
    minute_bar_cache_hits: int = 0


class IntradayWFValidator:
    """Walks each trade minute-by-minute when an EOD-impossible-but-intraday-possible
    trailing-stop trigger may exist. Uses cached minute bars so re-runs are free."""

    def __init__(self, trailing_stop_pct: float = 0.12):
        self.trailing_stop_pct = float(trailing_stop_pct)

    async def validate_trades(
        self,
        trades: List[dict],
        daily_bars_lookup: Callable[[str], Optional[pd.DataFrame]],
        cache,  # IntradayBarCache; passed in to avoid circular import
        only_trailing_stop: bool = True,
    ) -> Dict:
        """Run intraday simulation across every trade.

        daily_bars_lookup: callable(symbol) -> daily OHLCV DataFrame indexed by date.
        cache: IntradayBarCache instance (for minute-bar fetches).
        only_trailing_stop: skip non-trailing-stop trades (default True — those exits
                            are batch-driven and not intraday-actionable).
        """
        results: List[IntradayTradeResult] = []
        skipped = 0
        for idx, trade in enumerate(trades):
            if only_trailing_stop and trade.get("exit_reason") != "trailing_stop":
                skipped += 1
                continue

            symbol = trade["symbol"]
            daily = daily_bars_lookup(symbol)
            if daily is None or daily.empty:
                logger.warning(f"no daily bars for {symbol}, skipping trade {idx}")
                skipped += 1
                continue

            try:
                res = await self._validate_one(idx, trade, daily, cache)
                if res is not None:
                    results.append(res)
                else:
                    skipped += 1
            except Exception as e:
                logger.warning(f"trade {idx} ({symbol}) validation failed: {e}")
                skipped += 1

        summary = self._summarize(results)

        return {
            "summary": asdict(summary),
            "results": [asdict(r) for r in results],
            "skipped": skipped,
            "trailing_stop_pct": self.trailing_stop_pct,
        }

    async def _validate_one(
        self,
        trade_idx: int,
        trade: dict,
        daily: pd.DataFrame,
        cache,
    ) -> Optional[IntradayTradeResult]:
        symbol = trade["symbol"]
        entry_date = trade["entry_date"]
        exit_date = trade["exit_date"]
        entry_price = float(trade["entry_price"])
        original_exit_price = float(trade["exit_price"])
        original_pnl_pct = float(trade["pnl_pct"])

        # Slice daily bars: entry_date through exit_date (inclusive).
        # daily index is normalized datetime; trade dates are strings.
        entry_dt = pd.to_datetime(entry_date).normalize()
        exit_dt = pd.to_datetime(exit_date).normalize()
        if daily.index.tz is not None:
            holding = daily[(daily.index.tz_localize(None) >= entry_dt) & (daily.index.tz_localize(None) <= exit_dt)]
        else:
            holding = daily[(daily.index >= entry_dt) & (daily.index <= exit_dt)]
        if holding.empty:
            return None

        # Walk daily bars day-by-day, tracking running HWM (high watermark).
        # On any day where intraday LOW could have triggered the stop given the
        # CURRENT HWM, fetch minute bars and walk minute-by-minute to nail the
        # exact exit price.
        running_hwm = entry_price  # HWM seeded at entry
        intraday_fired = False
        intraday_exit_date = exit_date
        intraday_exit_price = original_exit_price
        intraday_exit_minute: Optional[str] = None
        minute_bars_used = False
        cache_hits = 0
        fetches = 0

        for day_ts, row in holding.iterrows():
            day_high = float(row["high"])
            day_low = float(row["low"])
            day_close = float(row["close"])
            date_str = pd.Timestamp(day_ts).strftime("%Y-%m-%d")

            # Stop trigger price BEFORE this day's high is incorporated:
            stop_at_day_open = running_hwm * (1 - self.trailing_stop_pct)

            # If the day's intraday LOW could have crossed the existing stop OR
            # could have crossed a new stop set by an intraday new high, we need
            # minute bars to find the exact moment.
            day_max_possible_stop = max(running_hwm, day_high) * (1 - self.trailing_stop_pct)
            could_fire = day_low <= day_max_possible_stop

            if not could_fire:
                # Stop mathematically can't fire today — update HWM with the day's
                # high (cheapest update path) and move on.
                if day_high > running_hwm:
                    running_hwm = day_high
                continue

            # Need minute bars for this day.
            was_cached = cache.is_cached(symbol, date_str)
            df_min = await cache.get_or_fetch(symbol, date_str)
            if was_cached:
                cache_hits += 1
            else:
                fetches += 1

            if df_min is None or df_min.empty:
                # No minute data — fall back to daily H/L approximation.
                if day_low <= running_hwm * (1 - self.trailing_stop_pct):
                    intraday_fired = True
                    intraday_exit_date = date_str
                    intraday_exit_price = round(running_hwm * (1 - self.trailing_stop_pct), 4)
                    intraday_exit_minute = None
                    break
                else:
                    if day_high > running_hwm:
                        running_hwm = day_high
                    continue

            minute_bars_used = True
            # Walk minute-by-minute. Update HWM on each bar's HIGH; check trigger
            # against bar's LOW. First bar that triggers wins.
            for ts, m_row in df_min.iterrows():
                m_high = float(m_row["high"])
                m_low = float(m_row["low"])
                # Stop fires if minute LOW crosses HWM * (1 - pct) using the HWM
                # AS OF the start of this minute (i.e., not including m_high yet).
                stop_price = running_hwm * (1 - self.trailing_stop_pct)
                if m_low <= stop_price:
                    intraday_fired = True
                    intraday_exit_date = date_str
                    intraday_exit_price = round(stop_price, 4)
                    intraday_exit_minute = pd.Timestamp(ts).isoformat()
                    break
                # Otherwise, fold this minute's high into HWM
                if m_high > running_hwm:
                    running_hwm = m_high
            if intraday_fired:
                break
            # Day completed without trigger — running_hwm was updated minute by
            # minute already. Continue to next day.

        # Compute deltas
        if intraday_fired:
            intraday_pnl_pct = ((intraday_exit_price - entry_price) / entry_price) * 100.0
        else:
            intraday_pnl_pct = original_pnl_pct

        pnl_delta = intraday_pnl_pct - original_pnl_pct

        # Earlier exit calculation
        if intraday_fired and intraday_exit_date != exit_date:
            try:
                d_orig = datetime.strptime(exit_date, "%Y-%m-%d")
                d_new = datetime.strptime(intraday_exit_date, "%Y-%m-%d")
                earlier_days = max(0, (d_orig - d_new).days)
            except Exception:
                earlier_days = 0
        else:
            earlier_days = 0

        return IntradayTradeResult(
            trade_idx=trade_idx,
            symbol=symbol,
            entry_date=entry_date,
            entry_price=entry_price,
            original_exit_date=exit_date,
            original_exit_price=original_exit_price,
            original_pnl_pct=original_pnl_pct,
            intraday_exit_date=intraday_exit_date,
            intraday_exit_price=intraday_exit_price,
            intraday_exit_minute=intraday_exit_minute,
            intraday_pnl_pct=round(intraday_pnl_pct, 4),
            intraday_running_hwm=round(running_hwm, 4),
            pnl_delta_pct=round(pnl_delta, 4),
            exit_earlier_days=earlier_days,
            fired_intraday=intraday_fired,
            minute_bars_used=minute_bars_used,
        )

    def _summarize(self, results: List[IntradayTradeResult]) -> IntradayValidationSummary:
        s = IntradayValidationSummary()
        s.total_trades = len(results)
        s.trades_simulated = sum(1 for r in results if r.minute_bars_used)
        deltas = [r.pnl_delta_pct for r in results]
        earlier_days = [r.exit_earlier_days for r in results if r.fired_intraday]

        s.trades_no_change = sum(1 for r in results if abs(r.pnl_delta_pct) < 0.01)
        s.trades_intraday_better = sum(1 for r in results if r.pnl_delta_pct > 0.01)
        s.trades_intraday_worse = sum(1 for r in results if r.pnl_delta_pct < -0.01)
        s.sum_pnl_delta_pct = round(sum(deltas), 4)
        s.avg_pnl_delta_pct = round(sum(deltas) / max(len(deltas), 1), 4)
        if deltas:
            srt = sorted(deltas)
            mid = len(srt) // 2
            s.median_pnl_delta_pct = round(srt[mid] if len(srt) % 2 else (srt[mid - 1] + srt[mid]) / 2, 4)
        if earlier_days:
            srt2 = sorted(earlier_days)
            mid2 = len(srt2) // 2
            s.median_earlier_exit_days = float(srt2[mid2] if len(srt2) % 2 else (srt2[mid2 - 1] + srt2[mid2]) / 2)
        s.minute_bar_fetches = sum(0 if r.minute_bars_used else 0 for r in results)  # placeholder; counted in handler
        return s
