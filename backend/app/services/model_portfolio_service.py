"""
Model Portfolio Service — Dual live + walk-forward portfolio tracking.

Two parallel model portfolios run forward from launch:
1. Live Portfolio: Intraday monitoring (5 min), trailing stop/regime exits, no forced rebalancing.
2. Walk-Forward Portfolio: Biweekly rebalancing (Feb 1 canonical dates), daily close checks,
   force-close at period boundaries.

Both generate "We Called It" social content on profitable exits.
"""

import json
import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import asc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import ModelPosition, ModelPortfolioState, ModelPortfolioSnapshot

logger = logging.getLogger(__name__)

# Constants
PORTFOLIO_TYPES = ("live", "walkforward")
MAX_POSITIONS = 6
POSITION_SIZE_PCT = 0.15  # 15% of available cash per position
TRAILING_STOP_PCT = 12.0
STARTING_CAPITAL = 100_000.0
WF_ANCHOR_DATE = date(2026, 2, 1)  # Canonical biweekly boundaries
WF_PERIOD_DAYS = 14

# Signal track record: tracks EVERY fresh pick (no position limit, flat sizing)
SIGNAL_TRACK_RECORD = "signal_track_record"
SIGNAL_TRACK_NOTIONAL = 10000.0  # Flat $10K per pick for clean % tracking

# Ghost portfolio configurations for parallel universe comparison
GHOST_CONFIGS = {
    "ghost_aggressive": {"trailing_stop": 8.0, "max_positions": 8, "position_size": 0.12,
                         "label": "Aggressive", "description": "Tight stops, more positions"},
    "ghost_conservative": {"trailing_stop": 18.0, "max_positions": 4, "position_size": 0.20,
                           "label": "Conservative", "description": "Wide stops, fewer positions"},
    "ghost_top3": {"trailing_stop": 12.0, "max_positions": 3, "position_size": 0.30,
                   "label": "Top-3 Only", "description": "Concentrated best picks"},
}
ALL_PORTFOLIO_TYPES = PORTFOLIO_TYPES + tuple(GHOST_CONFIGS.keys()) + (SIGNAL_TRACK_RECORD,)


def _get_regime_trailing_stop(dashboard_data: Optional[dict] = None) -> float:
    """Extract regime-adjusted trailing stop from dashboard cache. Falls back to 12%."""
    if dashboard_data:
        regime_adj = dashboard_data.get("regime_adjustments")
        if regime_adj and isinstance(regime_adj, dict):
            adjusted = regime_adj.get("effective", {}).get("trailing_stop_pct")
            if adjusted is not None:
                return float(adjusted)
    return TRAILING_STOP_PCT


class ModelPortfolioService:
    """Track dual model portfolios: live (intraday) and walk-forward (biweekly)."""

    async def _get_or_create_state(
        self, db: AsyncSession, portfolio_type: str
    ) -> ModelPortfolioState:
        """Lazy-init portfolio state row with starting capital."""
        result = await db.execute(
            select(ModelPortfolioState).where(
                ModelPortfolioState.portfolio_type == portfolio_type
            )
        )
        state = result.scalar_one_or_none()
        if not state:
            state = ModelPortfolioState(
                portfolio_type=portfolio_type,
                starting_capital=STARTING_CAPITAL,
                current_cash=STARTING_CAPITAL,
                total_trades=0,
                winning_trades=0,
                total_pnl=0.0,
            )
            db.add(state)
            await db.flush()
            logger.info(f"[MODEL-{portfolio_type.upper()}] Initialized with ${STARTING_CAPITAL:,.0f}")
        return state

    async def _get_open_positions(
        self, db: AsyncSession, portfolio_type: str
    ) -> List[ModelPosition]:
        result = await db.execute(
            select(ModelPosition).where(
                ModelPosition.portfolio_type == portfolio_type,
                ModelPosition.status == "open",
            )
        )
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Entry logic
    # ------------------------------------------------------------------

    async def process_entries(
        self, db: AsyncSession, portfolio_type: str
    ) -> dict:
        """
        After daily scan, enter fresh ensemble signals.

        Reads buy signals from dashboard cache (S3 JSON). Filters to is_fresh=True,
        skips symbols already held. Sorts by ensemble_score, enters up to
        MAX_POSITIONS - open_count.

        For WF portfolio: only enters at biweekly boundaries.
        """
        if portfolio_type not in PORTFOLIO_TYPES:
            return {"error": f"Invalid portfolio type: {portfolio_type}"}

        # WF portfolio only enters at period boundaries (once per period)
        today = date.today()
        current_period = self._get_wf_period(today)
        if portfolio_type == "walkforward":
            if not self._is_wf_period_boundary(today) or current_period == self._last_wf_period_processed:
                return {"entries": 0, "reason": "Not a WF period boundary"}

        state = await self._get_or_create_state(db, portfolio_type)
        open_positions = await self._get_open_positions(db, portfolio_type)
        open_count = len(open_positions)

        if open_count >= MAX_POSITIONS:
            return {"entries": 0, "reason": "Max positions reached"}

        held_symbols = {p.symbol for p in open_positions}
        slots = MAX_POSITIONS - open_count

        # Read fresh signals from dashboard cache
        from app.services.data_export import data_export_service

        dashboard = data_export_service.read_dashboard_json()
        if not dashboard:
            return {"entries": 0, "reason": "No dashboard cache available"}

        # Freshness gate: refuse to trade on stale dashboard data
        data_date_str = dashboard.get('data_date')
        if data_date_str:
            from zoneinfo import ZoneInfo
            from app.services.health_monitor_service import _last_market_day
            data_date = datetime.strptime(data_date_str, '%Y-%m-%d').date()
            now_et = datetime.now(ZoneInfo('America/New_York'))
            expected = _last_market_day(now_et.date())
            if data_date < expected:
                logger.warning(f"STALE DASHBOARD: data_date={data_date}, expected={expected} — refusing to enter trades")
                return {"entries": 0, "reason": f"Stale data ({data_date} < {expected})"}

        buy_signals = dashboard.get("buy_signals", [])
        fresh_signals = [
            s for s in buy_signals
            if s.get("is_fresh") and s["symbol"] not in held_symbols
        ]
        fresh_signals.sort(key=lambda x: -x.get("ensemble_score", 0))

        entries = 0
        for sig in fresh_signals[:slots]:
            symbol = sig["symbol"]
            price = sig.get("price", 0)
            if price <= 0:
                continue

            # Position sizing: 15% of current cash
            alloc = state.current_cash * POSITION_SIZE_PCT
            if alloc < 100:  # Minimum allocation
                break

            shares = alloc / price

            pos = ModelPosition(
                portfolio_type=portfolio_type,
                symbol=symbol,
                entry_date=datetime.utcnow(),
                entry_price=price,
                shares=shares,
                cost_basis=alloc,
                highest_price=price,
                status="open",
                signal_data_json=json.dumps(sig),
            )
            db.add(pos)
            state.current_cash -= alloc
            entries += 1

            logger.info(
                f"[MODEL-{portfolio_type.upper()}] Entered {symbol} @ ${price:.2f} "
                f"x {shares:.1f} shares (${alloc:,.0f})"
            )

        if entries:
            state.updated_at = datetime.utcnow()
            await db.commit()

        return {"entries": entries, "cash_remaining": round(state.current_cash, 2)}

    # ------------------------------------------------------------------
    # Exit logic — Live (intraday)
    # ------------------------------------------------------------------

    async def process_live_exits(
        self,
        db: AsyncSession,
        live_prices: Dict[str, float],
        regime_forecast: Optional[dict] = None,
        day_highs: Optional[Dict[str, float]] = None,
        trailing_stop_pct: Optional[float] = None,
    ) -> List[dict]:
        """
        Called by intraday monitor every 5 min.
        Checks all open live positions for trailing stop and regime exit.
        Updates highest_price using day_high to capture peaks between checks.
        """
        positions = await self._get_open_positions(db, "live")
        if not positions:
            return []

        closed = []
        for pos in positions:
            price = live_prices.get(pos.symbol)
            if price is None:
                continue

            # Update HWM using day_high to capture peaks between 5-min checks
            hwm_price = max(price, (day_highs or {}).get(pos.symbol, price))
            if hwm_price > (pos.highest_price or pos.entry_price):
                pos.highest_price = hwm_price

            hwm = pos.highest_price or pos.entry_price
            stop_pct = trailing_stop_pct if trailing_stop_pct is not None else TRAILING_STOP_PCT
            trailing_stop_level = hwm * (1 - stop_pct / 100)

            exit_reason = None

            # Check regime exit
            if regime_forecast:
                rec = regime_forecast.get("recommended_action", "stay_invested")
                if rec == "go_to_cash":
                    exit_reason = "regime_exit"

            # Check trailing stop (overrides regime)
            if price <= trailing_stop_level:
                exit_reason = "trailing_stop"

            if exit_reason:
                result = await self._close_position(db, pos, price, exit_reason)
                closed.append(result)

        if closed:
            await db.commit()

        return closed

    # ------------------------------------------------------------------
    # Exit logic — Walk-Forward (daily close)
    # ------------------------------------------------------------------

    async def process_wf_exits(
        self, db: AsyncSession, trailing_stop_pct: Optional[float] = None
    ) -> List[dict]:
        """
        Called once daily after market close.
        Checks all open WF positions using daily close prices.
        Force-closes all if today is a biweekly boundary (rebalance_exit).
        """
        positions = await self._get_open_positions(db, "walkforward")
        if not positions:
            return []

        today = date.today()
        current_period = self._get_wf_period(today)
        is_boundary = (
            self._is_wf_period_boundary(today)
            and current_period != self._last_wf_period_processed
        )

        # Get daily close prices from scanner cache
        from app.services.scanner import scanner_service

        closed = []
        for pos in positions:
            df = scanner_service.data_cache.get(pos.symbol)
            if df is None or df.empty:
                continue

            close_price = float(df["close"].iloc[-1])

            # Update HWM
            if close_price > (pos.highest_price or pos.entry_price):
                pos.highest_price = close_price

            exit_reason = None

            # Period boundary → force close
            if is_boundary:
                exit_reason = "rebalance_exit"
            else:
                # Check trailing stop
                hwm = pos.highest_price or pos.entry_price
                stop_pct = trailing_stop_pct if trailing_stop_pct is not None else TRAILING_STOP_PCT
                trailing_stop_level = hwm * (1 - stop_pct / 100)
                if close_price <= trailing_stop_level:
                    exit_reason = "trailing_stop"

            if exit_reason:
                result = await self._close_position(db, pos, close_price, exit_reason)
                closed.append(result)

        if closed:
            await db.commit()

        # Mark this period as processed so boundary doesn't fire again
        if is_boundary:
            self._last_wf_period_processed = current_period

        return closed

    # ------------------------------------------------------------------
    # Shared close logic
    # ------------------------------------------------------------------

    async def _close_position(
        self,
        db: AsyncSession,
        position: ModelPosition,
        exit_price: float,
        exit_reason: str,
    ) -> dict:
        """Close a model position: set exit fields, calculate P&L, update state."""
        pnl_dollars = (exit_price - position.entry_price) * position.shares
        pnl_pct = ((exit_price / position.entry_price) - 1) * 100

        position.exit_date = datetime.utcnow()
        position.exit_price = exit_price
        position.exit_reason = exit_reason
        position.pnl_dollars = round(pnl_dollars, 2)
        position.pnl_pct = round(pnl_pct, 2)
        position.status = "closed"

        # Update portfolio state
        state = await self._get_or_create_state(db, position.portfolio_type)
        state.current_cash += position.cost_basis + pnl_dollars
        state.total_trades += 1
        state.total_pnl += pnl_dollars
        if pnl_pct > 0:
            state.winning_trades += 1
        state.updated_at = datetime.utcnow()

        logger.info(
            f"[MODEL-{position.portfolio_type.upper()}] Closed {position.symbol} "
            f"@ ${exit_price:.2f} ({pnl_pct:+.1f}%) — {exit_reason}"
        )

        # Generate social content for profitable exits
        if pnl_pct >= 5 and not position.social_post_generated:
            try:
                await self._generate_exit_content(db, position)
                position.social_post_generated = True
            except Exception as e:
                logger.error(f"[MODEL-PORTFOLIO] Social content generation failed: {e}")

        return {
            "symbol": position.symbol,
            "portfolio_type": position.portfolio_type,
            "entry_price": position.entry_price,
            "exit_price": exit_price,
            "pnl_pct": round(pnl_pct, 2),
            "pnl_dollars": round(pnl_dollars, 2),
            "exit_reason": exit_reason,
        }

    # ------------------------------------------------------------------
    # Social content generation on exit
    # ------------------------------------------------------------------

    async def _generate_exit_content(
        self, db: AsyncSession, position: ModelPosition
    ) -> None:
        """
        Generate social posts for profitable model portfolio exits.
        trade_result for >5%, we_called_it for >10%.
        """
        from app.services.ai_content_service import ai_content_service
        from app.services.post_scheduler_service import post_scheduler_service

        trade = {
            "symbol": position.symbol,
            "entry_price": position.entry_price,
            "exit_price": position.exit_price,
            "entry_date": position.entry_date.isoformat() if position.entry_date else "",
            "exit_date": position.exit_date.isoformat() if position.exit_date else "",
            "pnl_pct": position.pnl_pct,
            "exit_reason": position.exit_reason,
        }

        post_type = "we_called_it" if position.pnl_pct >= 10 else "trade_result"

        for platform in ("twitter", "instagram"):
            post = await ai_content_service.generate_post(
                trade=trade,
                post_type=post_type,
                platform=platform,
            )
            if post:
                db.add(post)
                await db.flush()
                # Auto-schedule the draft
                await post_scheduler_service.auto_schedule_drafts(db)

        logger.info(
            f"[MODEL-PORTFOLIO] Generated {post_type} content for "
            f"{position.symbol} ({position.pnl_pct:+.1f}%)"
        )

    # ------------------------------------------------------------------
    # Portfolio summary
    # ------------------------------------------------------------------

    async def get_portfolio_summary(
        self, db: AsyncSession, portfolio_type: Optional[str] = None
    ) -> dict:
        """
        Returns current state: capital, cash, open positions, realized/unrealized P&L,
        win rate, recent trades. If portfolio_type=None, returns both side by side.
        """
        types = [portfolio_type] if portfolio_type else list(PORTFOLIO_TYPES)
        result = {}

        for ptype in types:
            state = await self._get_or_create_state(db, ptype)
            open_positions = await self._get_open_positions(db, ptype)

            # Get live prices for unrealized P&L
            from app.services.scanner import scanner_service

            open_data = []
            unrealized_pnl = 0.0
            for pos in open_positions:
                df = scanner_service.data_cache.get(pos.symbol)
                current_price = float(df["close"].iloc[-1]) if df is not None and not df.empty else pos.entry_price
                pos_pnl = (current_price - pos.entry_price) * pos.shares
                unrealized_pnl += pos_pnl
                open_data.append({
                    "symbol": pos.symbol,
                    "entry_date": pos.entry_date.isoformat() if pos.entry_date else None,
                    "entry_price": pos.entry_price,
                    "shares": round(pos.shares, 2),
                    "current_price": round(current_price, 2),
                    "pnl_pct": round(((current_price / pos.entry_price) - 1) * 100, 2),
                    "pnl_dollars": round(pos_pnl, 2),
                    "highest_price": pos.highest_price,
                })

            # Recent closed trades
            recent_result = await db.execute(
                select(ModelPosition)
                .where(
                    ModelPosition.portfolio_type == ptype,
                    ModelPosition.status == "closed",
                )
                .order_by(ModelPosition.exit_date.desc())
                .limit(10)
            )
            recent_trades = [
                {
                    "id": t.id,
                    "symbol": t.symbol,
                    "entry_date": t.entry_date.isoformat() if t.entry_date else None,
                    "exit_date": t.exit_date.isoformat() if t.exit_date else None,
                    "entry_price": t.entry_price,
                    "exit_price": t.exit_price,
                    "pnl_pct": t.pnl_pct,
                    "pnl_dollars": t.pnl_dollars,
                    "exit_reason": t.exit_reason,
                }
                for t in recent_result.scalars().all()
            ]

            positions_value = sum(p["current_price"] * p["shares"] for p in open_data)
            total_value = state.current_cash + positions_value

            win_rate = (
                (state.winning_trades / state.total_trades * 100)
                if state.total_trades > 0
                else 0
            )

            result[ptype] = {
                "starting_capital": state.starting_capital,
                "current_cash": round(state.current_cash, 2),
                "total_value": round(total_value, 2),
                "total_return_pct": round(
                    ((total_value / state.starting_capital) - 1) * 100, 2
                ),
                "realized_pnl": round(state.total_pnl, 2),
                "unrealized_pnl": round(unrealized_pnl, 2),
                "total_trades": state.total_trades,
                "winning_trades": state.winning_trades,
                "win_rate": round(win_rate, 1),
                "open_positions": open_data,
                "recent_trades": recent_trades,
            }

        return result if not portfolio_type else result.get(portfolio_type, {})

    # ------------------------------------------------------------------
    # Walk-forward biweekly boundary logic
    # ------------------------------------------------------------------

    @staticmethod
    def _get_close_for_date(df, target_date: date, fallback_latest: bool = False) -> Optional[float]:
        """Get close price from a DataFrame for a specific date.

        Handles both tz-aware and tz-naive indexes by comparing .date().
        If fallback_latest=True and exact date not found, returns most recent
        close on or before target_date.
        """
        try:
            dates = [d.date() if hasattr(d, 'date') else d for d in df.index]
            # Exact match
            for i, d in enumerate(dates):
                if d == target_date:
                    return float(df.iloc[i]["close"])

            # Fallback: most recent close on or before target_date
            if fallback_latest:
                best_idx = None
                best_date = None
                for i, d in enumerate(dates):
                    if d <= target_date:
                        if best_date is None or d > best_date:
                            best_date = d
                            best_idx = i
                if best_idx is not None:
                    return float(df.iloc[best_idx]["close"])

            return None
        except Exception:
            return None

    def _get_wf_period(self, d: date) -> int:
        """Return which biweekly period a date belongs to (-1 if before anchor)."""
        days_since = (d - WF_ANCHOR_DATE).days
        if days_since < 0:
            return -1
        return days_since // WF_PERIOD_DAYS

    def _is_wf_period_boundary(self, today: date, prev_trading_day: Optional[date] = None) -> bool:
        """Check if today is the first trading day of a new biweekly period.

        If prev_trading_day is provided (backfill mode), compares periods directly.
        Otherwise (live mode), checks if any of the previous 6 calendar days
        falls in a prior period. Live callers must deduplicate (only act once
        per period) using _last_wf_period_processed.
        """
        current_period = self._get_wf_period(today)
        if current_period < 0:
            return False

        if prev_trading_day is not None:
            return self._get_wf_period(prev_trading_day) < current_period

        # Live mode: check if a period boundary exists in the recent window
        for offset in range(1, 7):
            prev = today - timedelta(days=offset)
            if self._get_wf_period(prev) < current_period:
                return True
        return False

    _last_wf_period_processed: int = -1

    # ------------------------------------------------------------------
    # Reset (admin/testing)
    # ------------------------------------------------------------------

    async def reset_portfolio(
        self, db: AsyncSession, portfolio_type: Optional[str] = None
    ) -> dict:
        """Reset one or both portfolios. Deletes all positions and resets state."""
        from sqlalchemy import delete

        types = [portfolio_type] if portfolio_type else list(PORTFOLIO_TYPES)
        deleted = 0

        for ptype in types:
            result = await db.execute(
                delete(ModelPosition).where(
                    ModelPosition.portfolio_type == ptype
                )
            )
            deleted += result.rowcount

            await db.execute(
                delete(ModelPortfolioState).where(
                    ModelPortfolioState.portfolio_type == ptype
                )
            )

            # Also clear snapshots
            await db.execute(
                delete(ModelPortfolioSnapshot).where(
                    ModelPortfolioSnapshot.portfolio_type == ptype
                )
            )

        await db.commit()
        return {"deleted_positions": deleted, "reset_types": types}

    # ------------------------------------------------------------------
    # Backfill walk-forward portfolio from a historical date
    # ------------------------------------------------------------------

    async def backfill_from_date(
        self,
        db: AsyncSession,
        as_of_date: str = "2026-02-01",
        force: bool = False,
        portfolio_type: str = "walkforward",
        config_override: Optional[dict] = None,
    ) -> dict:
        """
        Backfill a portfolio from a historical date through today.

        Steps:
        1. Reset portfolio if force=True
        2. Load signals from snapshot or live computation for the start date
        3. Enter top fresh ensemble signals
        4. Walk forward day by day: update HWM, check trailing stop, rebalance at boundaries
        5. Take daily snapshots for equity curve

        config_override: {"trailing_stop": 8.0, "max_positions": 8, "position_size": 0.12}
        """
        import pandas as pd
        from sqlalchemy import delete

        # Use config override or defaults
        trailing_stop = TRAILING_STOP_PCT
        max_pos = MAX_POSITIONS
        pos_size = POSITION_SIZE_PCT
        if config_override:
            trailing_stop = config_override.get("trailing_stop", TRAILING_STOP_PCT)
            max_pos = config_override.get("max_positions", MAX_POSITIONS)
            pos_size = config_override.get("position_size", POSITION_SIZE_PCT)

        if force:
            await self.reset_portfolio(db, portfolio_type)
            logger.info(f"[BACKFILL] Reset {portfolio_type} portfolio")

        # Get scanner data for price lookups
        from app.services.scanner import scanner_service

        spy_df = scanner_service.data_cache.get("SPY")
        if spy_df is None or spy_df.empty:
            return {"error": "SPY data not in cache — run a scan first"}

        # Build trading calendar from SPY index
        start = pd.Timestamp(as_of_date).normalize()
        today = pd.Timestamp(date.today()).normalize()

        # Build trading calendar from SPY index using .date() for tz safety
        trading_days = sorted([
            d.date() if hasattr(d, 'date') else d
            for d in spy_df.index
            if start.date() <= (d.date() if hasattr(d, 'date') else d) <= today.date()
        ])
        if not trading_days:
            return {"error": f"No trading days found between {as_of_date} and today"}

        # Initialize state
        state = await self._get_or_create_state(db, portfolio_type)
        summary = {
            "portfolio_type": portfolio_type,
            "start_date": str(start.date()),
            "end_date": str(today.date()),
            "trading_days": len(trading_days),
            "entries": 0,
            "exits": 0,
            "rebalances": 0,
            "snapshots": 0,
        }

        logger.info(
            f"[BACKFILL-{portfolio_type.upper()}] {len(trading_days)} trading days, "
            f"stop={trailing_stop}%, max={max_pos}, size={pos_size*100:.0f}%"
        )

        prev_trading_day = None
        for day_date in trading_days:
            is_boundary = self._is_wf_period_boundary(day_date, prev_trading_day)

            # Get current open positions
            open_positions = await self._get_open_positions(db, portfolio_type)

            # --- Check exits ---
            for pos in open_positions:
                df = scanner_service.data_cache.get(pos.symbol)
                if df is None or df.empty:
                    continue

                # Get close price for this day (fallback to latest on boundary)
                close_price = self._get_close_for_date(df, day_date, fallback_latest=is_boundary)
                if close_price is None:
                    continue

                # Update HWM
                if close_price > (pos.highest_price or pos.entry_price):
                    pos.highest_price = close_price

                exit_reason = None
                if is_boundary:
                    exit_reason = "rebalance_exit"
                else:
                    hwm = pos.highest_price or pos.entry_price
                    stop_level = hwm * (1 - trailing_stop / 100)
                    if close_price <= stop_level:
                        exit_reason = "trailing_stop"

                if exit_reason:
                    pnl_dollars = (close_price - pos.entry_price) * pos.shares
                    pnl_pct = ((close_price / pos.entry_price) - 1) * 100

                    pos.exit_date = datetime.combine(day_date, datetime.min.time())
                    pos.exit_price = close_price
                    pos.exit_reason = exit_reason
                    pos.pnl_dollars = round(pnl_dollars, 2)
                    pos.pnl_pct = round(pnl_pct, 2)
                    pos.status = "closed"

                    state.current_cash += pos.cost_basis + pnl_dollars
                    state.total_trades += 1
                    state.total_pnl += pnl_dollars
                    if pnl_pct > 0:
                        state.winning_trades += 1

                    summary["exits"] += 1

            # Flush so subsequent queries see closed positions
            if summary["exits"] > 0:
                await db.flush()

            # --- Enter new positions at boundaries or first day ---
            if is_boundary or day_date == trading_days[0]:
                if is_boundary and day_date != trading_days[0]:
                    summary["rebalances"] += 1

                # Load signals for this date
                signals = await self._get_signals_for_date(day_date)
                if signals:
                    open_positions = await self._get_open_positions(db, portfolio_type)
                    held = {p.symbol for p in open_positions}
                    slots = max_pos - len(open_positions)

                    fresh = [
                        s for s in signals
                        if s.get("is_fresh") and s["symbol"] not in held
                    ]
                    fresh.sort(key=lambda x: -x.get("ensemble_score", 0))

                    for sig in fresh[:slots]:
                        symbol = sig["symbol"]
                        # Get close price for entry day
                        df = scanner_service.data_cache.get(symbol)
                        if df is None or df.empty:
                            continue

                        price = self._get_close_for_date(df, day_date)
                        if price is None:
                            continue
                        if price <= 0:
                            continue

                        alloc = state.current_cash * pos_size
                        if alloc < 100:
                            break

                        shares = alloc / price
                        pos = ModelPosition(
                            portfolio_type=portfolio_type,
                            symbol=symbol,
                            entry_date=datetime.combine(day_date, datetime.min.time()),
                            entry_price=price,
                            shares=shares,
                            cost_basis=alloc,
                            highest_price=price,
                            status="open",
                            signal_data_json=json.dumps(sig),
                        )
                        db.add(pos)
                        state.current_cash -= alloc
                        summary["entries"] += 1

            # --- Take daily snapshot ---
            open_positions = await self._get_open_positions(db, portfolio_type)
            positions_value = 0.0
            for pos in open_positions:
                df = scanner_service.data_cache.get(pos.symbol)
                if df is None or df.empty:
                    continue
                close_price = self._get_close_for_date(df, day_date, fallback_latest=True)
                if close_price is not None:
                    positions_value += close_price * pos.shares

            spy_close = self._get_close_for_date(spy_df, day_date)

            snapshot = ModelPortfolioSnapshot(
                portfolio_type=portfolio_type,
                snapshot_date=datetime.combine(day_date, datetime.min.time()),
                total_value=round(state.current_cash + positions_value, 2),
                cash=round(state.current_cash, 2),
                positions_value=round(positions_value, 2),
                num_positions=len(open_positions),
                spy_close=spy_close,
            )
            db.add(snapshot)
            summary["snapshots"] += 1

            # Flush periodically to keep session clean
            if summary["snapshots"] % 10 == 0:
                await db.flush()

            prev_trading_day = day_date

        state.updated_at = datetime.utcnow()
        await db.commit()

        logger.info(
            f"[BACKFILL-{portfolio_type.upper()}] Complete: {summary['entries']} entries, "
            f"{summary['exits']} exits, {summary['rebalances']} rebalances, "
            f"{summary['snapshots']} snapshots"
        )
        return summary

    async def backfill_ghosts(
        self, db: AsyncSession, as_of_date: str = "2026-02-01", force: bool = False
    ) -> dict:
        """Backfill all ghost portfolios with their respective configurations."""
        results = {}
        for ghost_type, config in GHOST_CONFIGS.items():
            logger.info(f"[GHOST] Backfilling {ghost_type} ({config['label']})")
            result = await self.backfill_from_date(
                db, as_of_date, force,
                portfolio_type=ghost_type,
                config_override=config,
            )
            results[ghost_type] = result
        return results

    async def _get_signals_for_date(self, target_date: date) -> Optional[List[dict]]:
        """Load ensemble signals for a given date from snapshot or live computation."""
        from app.services.data_export import data_export_service

        date_str = target_date.isoformat()

        # Try snapshot first
        snapshot = data_export_service.read_snapshot(date_str)
        if snapshot:
            return snapshot.get("buy_signals", [])

        # No snapshot available — skip (can't time-travel without cached data)
        logger.debug(f"[BACKFILL] No snapshot for {date_str}")
        return None

    # ------------------------------------------------------------------
    # Daily snapshot for equity curve
    # ------------------------------------------------------------------

    async def take_daily_snapshot(
        self, db: AsyncSession, snapshot_date: Optional[date] = None
    ) -> dict:
        """
        Take a snapshot of each portfolio's value for the equity curve.
        Uses scanner cache for current prices + SPY close.
        Upserts to avoid duplicates.
        """
        from app.services.scanner import scanner_service

        if snapshot_date is None:
            from zoneinfo import ZoneInfo
            snapshot_date = datetime.now(ZoneInfo('America/New_York')).date()

        snapshot_dt = datetime.combine(snapshot_date, datetime.min.time())
        results = {}

        for ptype in ALL_PORTFOLIO_TYPES:
            state = await self._get_or_create_state(db, ptype)
            open_positions = await self._get_open_positions(db, ptype)

            positions_value = 0.0
            for pos in open_positions:
                df = scanner_service.data_cache.get(pos.symbol)
                if df is not None and not df.empty:
                    positions_value += float(df["close"].iloc[-1]) * pos.shares

            spy_df = scanner_service.data_cache.get("SPY")
            spy_close = float(spy_df["close"].iloc[-1]) if spy_df is not None and not spy_df.empty else None

            total_value = state.current_cash + positions_value

            # Upsert: check existing
            existing = await db.execute(
                select(ModelPortfolioSnapshot).where(
                    ModelPortfolioSnapshot.portfolio_type == ptype,
                    ModelPortfolioSnapshot.snapshot_date == snapshot_dt,
                )
            )
            snap = existing.scalar_one_or_none()

            if snap:
                snap.total_value = round(total_value, 2)
                snap.cash = round(state.current_cash, 2)
                snap.positions_value = round(positions_value, 2)
                snap.num_positions = len(open_positions)
                snap.spy_close = spy_close
            else:
                snap = ModelPortfolioSnapshot(
                    portfolio_type=ptype,
                    snapshot_date=snapshot_dt,
                    total_value=round(total_value, 2),
                    cash=round(state.current_cash, 2),
                    positions_value=round(positions_value, 2),
                    num_positions=len(open_positions),
                    spy_close=spy_close,
                )
                db.add(snap)

            results[ptype] = {
                "total_value": round(total_value, 2),
                "positions_value": round(positions_value, 2),
                "num_positions": len(open_positions),
            }

        await db.commit()
        logger.info(f"[SNAPSHOT] Taken for {snapshot_date}: {results}")
        return results

    # ------------------------------------------------------------------
    # Equity curve
    # ------------------------------------------------------------------

    async def get_equity_curve(
        self, db: AsyncSession, portfolio_type: Optional[str] = None
    ) -> List[dict]:
        """
        Return equity curve data points for charting.
        Normalizes SPY to $100K starting value for comparison.
        """
        from sqlalchemy import asc

        query = select(ModelPortfolioSnapshot).order_by(
            asc(ModelPortfolioSnapshot.snapshot_date)
        )
        if portfolio_type:
            query = query.where(ModelPortfolioSnapshot.portfolio_type == portfolio_type)

        result = await db.execute(query)
        snapshots = result.scalars().all()

        if not snapshots:
            return []

        # Group by date
        by_date: Dict[str, dict] = {}
        first_spy = None

        for s in snapshots:
            date_str = s.snapshot_date.strftime("%Y-%m-%d") if s.snapshot_date else ""
            if date_str not in by_date:
                by_date[date_str] = {"date": date_str}

            key = f"{s.portfolio_type}_value"
            by_date[date_str][key] = s.total_value

            if s.spy_close and first_spy is None:
                first_spy = s.spy_close

            if s.spy_close and first_spy:
                by_date[date_str]["spy_value"] = round(
                    STARTING_CAPITAL * (s.spy_close / first_spy), 2
                )

        return sorted(by_date.values(), key=lambda x: x["date"])

    # ------------------------------------------------------------------
    # Trade journal
    # ------------------------------------------------------------------

    async def get_all_trades(
        self,
        db: AsyncSession,
        portfolio_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[dict]:
        """Return all trades (closed + open) ordered by entry_date desc."""
        query = select(ModelPosition).order_by(ModelPosition.entry_date.desc())
        if portfolio_type:
            query = query.where(ModelPosition.portfolio_type == portfolio_type)
        query = query.limit(limit)

        result = await db.execute(query)
        trades = []
        for t in result.scalars().all():
            sig = {}
            if t.signal_data_json:
                try:
                    sig = json.loads(t.signal_data_json)
                except (json.JSONDecodeError, TypeError):
                    pass

            days_held = None
            if t.entry_date:
                end = t.exit_date or datetime.utcnow()
                days_held = (end - t.entry_date).days

            trades.append({
                "id": t.id,
                "portfolio_type": t.portfolio_type,
                "symbol": t.symbol,
                "status": t.status,
                "entry_date": t.entry_date.isoformat() if t.entry_date else None,
                "exit_date": t.exit_date.isoformat() if t.exit_date else None,
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "shares": round(t.shares, 2) if t.shares else None,
                "cost_basis": round(t.cost_basis, 2) if t.cost_basis else None,
                "pnl_pct": t.pnl_pct,
                "pnl_dollars": t.pnl_dollars,
                "exit_reason": t.exit_reason,
                "days_held": days_held,
                "ensemble_score": sig.get("ensemble_score"),
                "momentum_rank": sig.get("momentum_rank"),
            })

        return trades

    async def get_trade_detail(self, db: AsyncSession, trade_id: int) -> Optional[dict]:
        """Return full detail for a single trade including signal replay."""
        result = await db.execute(
            select(ModelPosition).where(ModelPosition.id == trade_id)
        )
        t = result.scalar_one_or_none()
        if not t:
            return None

        sig = {}
        if t.signal_data_json:
            try:
                sig = json.loads(t.signal_data_json)
            except (json.JSONDecodeError, TypeError):
                pass

        days_held = None
        if t.entry_date:
            end = t.exit_date or datetime.utcnow()
            days_held = (end - t.entry_date).days

        # Calculate max gain during hold
        max_gain_pct = None
        if t.highest_price and t.entry_price:
            max_gain_pct = round(((t.highest_price / t.entry_price) - 1) * 100, 2)

        # Parse autopsy if available
        autopsy = None
        if t.autopsy_json:
            try:
                autopsy = json.loads(t.autopsy_json)
            except (json.JSONDecodeError, TypeError):
                pass

        return {
            "id": t.id,
            "portfolio_type": t.portfolio_type,
            "symbol": t.symbol,
            "status": t.status,
            "entry_date": t.entry_date.isoformat() if t.entry_date else None,
            "exit_date": t.exit_date.isoformat() if t.exit_date else None,
            "entry_price": t.entry_price,
            "exit_price": t.exit_price,
            "shares": round(t.shares, 2) if t.shares else None,
            "cost_basis": round(t.cost_basis, 2) if t.cost_basis else None,
            "highest_price": t.highest_price,
            "pnl_pct": t.pnl_pct,
            "pnl_dollars": t.pnl_dollars,
            "exit_reason": t.exit_reason,
            "days_held": days_held,
            "max_gain_pct": max_gain_pct,
            # Signal replay
            "ensemble_score": sig.get("ensemble_score"),
            "momentum_rank": sig.get("momentum_rank"),
            "pct_above_dwap": sig.get("pct_above_dwap"),
            "sector": sig.get("sector"),
            "short_momentum": sig.get("short_momentum"),
            "long_momentum": sig.get("long_momentum"),
            "volatility": sig.get("volatility"),
            "dwap_crossover_date": sig.get("dwap_crossover_date"),
            "ensemble_entry_date": sig.get("ensemble_entry_date"),
            # AI autopsy
            "autopsy": autopsy,
        }

    # ------------------------------------------------------------------
    # Ghost portfolio comparison
    # ------------------------------------------------------------------

    async def get_ghost_comparison(self, db: AsyncSession) -> dict:
        """Return side-by-side metrics for all portfolio types (WF + ghosts)."""
        from sqlalchemy import asc, func as sqlfunc

        comparison = {}
        for ptype in ["walkforward"] + list(GHOST_CONFIGS.keys()):
            state = await self._get_or_create_state(db, ptype)

            # Get latest snapshot value
            latest_snap = await db.execute(
                select(ModelPortfolioSnapshot)
                .where(ModelPortfolioSnapshot.portfolio_type == ptype)
                .order_by(ModelPortfolioSnapshot.snapshot_date.desc())
                .limit(1)
            )
            snap = latest_snap.scalar_one_or_none()

            total_value = snap.total_value if snap else state.starting_capital
            total_return = ((total_value / state.starting_capital) - 1) * 100 if state.starting_capital else 0
            win_rate = (state.winning_trades / state.total_trades * 100) if state.total_trades > 0 else 0

            config = GHOST_CONFIGS.get(ptype, {})
            comparison[ptype] = {
                "label": config.get("label", "Walk-Forward"),
                "description": config.get("description", "Canonical ensemble strategy"),
                "total_value": round(total_value, 2),
                "total_return_pct": round(total_return, 2),
                "win_rate": round(win_rate, 1),
                "total_trades": state.total_trades,
                "trailing_stop": config.get("trailing_stop", TRAILING_STOP_PCT),
                "max_positions": config.get("max_positions", MAX_POSITIONS),
                "position_size": config.get("position_size", POSITION_SIZE_PCT),
            }

        # Find the best-performing portfolio
        best = max(comparison.items(), key=lambda x: x[1]["total_return_pct"])
        comparison["_best"] = best[0]
        comparison["_best_label"] = best[1]["label"]

        return comparison

    # ------------------------------------------------------------------
    # "What If You Followed Us" Calculator
    # ------------------------------------------------------------------

    async def calculate_what_if(
        self,
        db: AsyncSession,
        start_date: str,
        initial_capital: float = 10000,
    ) -> dict:
        """
        Calculate what a user's portfolio would look like if they followed
        our model portfolio signals from a given date.
        """
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")

        # Get WF snapshots from start_date onward
        result = await db.execute(
            select(ModelPortfolioSnapshot)
            .where(
                ModelPortfolioSnapshot.portfolio_type == "walkforward",
                ModelPortfolioSnapshot.snapshot_date >= start_dt,
            )
            .order_by(asc(ModelPortfolioSnapshot.snapshot_date))
        )
        snapshots = list(result.scalars().all())

        if not snapshots:
            return {"error": f"No walkforward snapshots found from {start_date}"}

        first_snap = snapshots[0]
        first_value = first_snap.total_value
        first_spy = first_snap.spy_close

        if not first_value or first_value <= 0:
            return {"error": "First snapshot has no value"}

        equity_curve = []
        best_day_pct = 0
        worst_day_pct = 0
        prev_value = initial_capital

        for snap in snapshots:
            user_value = initial_capital * (snap.total_value / first_value)
            spy_value = None
            if first_spy and snap.spy_close:
                spy_value = round(initial_capital * (snap.spy_close / first_spy), 2)

            day_return = ((user_value / prev_value) - 1) * 100 if prev_value else 0
            if day_return > best_day_pct:
                best_day_pct = day_return
            if day_return < worst_day_pct:
                worst_day_pct = day_return

            equity_curve.append({
                "date": snap.snapshot_date.strftime("%Y-%m-%d") if snap.snapshot_date else "",
                "value": round(user_value, 2),
                "spy": spy_value,
            })
            prev_value = user_value

        current_value = equity_curve[-1]["value"] if equity_curve else initial_capital
        total_return = ((current_value / initial_capital) - 1) * 100

        spy_return = None
        alpha = None
        if first_spy and snapshots[-1].spy_close:
            spy_return = ((snapshots[-1].spy_close / first_spy) - 1) * 100
            alpha = total_return - spy_return

        # Inception return — earliest WF snapshot to latest
        inception_return_pct = None
        inception_date = None
        inception_result = await db.execute(
            select(ModelPortfolioSnapshot)
            .where(ModelPortfolioSnapshot.portfolio_type == "walkforward")
            .order_by(asc(ModelPortfolioSnapshot.snapshot_date))
            .limit(1)
        )
        inception_snap = inception_result.scalar_one_or_none()
        last_snap = snapshots[-1]
        if inception_snap and inception_snap.total_value and inception_snap.total_value > 0:
            inception_return_pct = round(
                ((last_snap.total_value / inception_snap.total_value) - 1) * 100, 1
            )
            inception_date = inception_snap.snapshot_date.strftime("%Y-%m-%d")

        # Best trade since user's start date
        best_trade_result = await db.execute(
            select(ModelPosition)
            .where(
                ModelPosition.portfolio_type == "walkforward",
                ModelPosition.status == "closed",
                ModelPosition.entry_date >= start_dt,
                ModelPosition.pnl_pct.isnot(None),
            )
            .order_by(ModelPosition.pnl_pct.desc())
            .limit(1)
        )
        best_trade = best_trade_result.scalar_one_or_none()

        # Win/loss count since signup
        trade_stats = await db.execute(
            select(
                func.count().label("total"),
                func.count().filter(ModelPosition.pnl_pct > 0).label("wins"),
            )
            .where(
                ModelPosition.portfolio_type == "walkforward",
                ModelPosition.status == "closed",
                ModelPosition.entry_date >= start_dt,
            )
        )
        stats_row = trade_stats.one()

        return {
            "start_date": start_date,
            "initial_capital": initial_capital,
            "current_value": round(current_value, 2),
            "total_return_pct": round(total_return, 2),
            "spy_return_pct": round(spy_return, 2) if spy_return is not None else None,
            "alpha_pct": round(alpha, 2) if alpha is not None else None,
            "best_day_pct": round(best_day_pct, 2),
            "worst_day_pct": round(worst_day_pct, 2),
            "days_invested": len(equity_curve),
            "equity_curve": equity_curve,
            "inception_return_pct": inception_return_pct,
            "inception_date": inception_date,
            "best_trade": {
                "symbol": best_trade.symbol,
                "pnl_pct": round(best_trade.pnl_pct, 1),
                "entry_date": best_trade.entry_date.strftime("%Y-%m-%d"),
                "exit_date": best_trade.exit_date.strftime("%Y-%m-%d"),
            } if best_trade and best_trade.pnl_pct and best_trade.pnl_pct > 0 else None,
            "trades_since_signup": stats_row.total,
            "wins_since_signup": stats_row.wins,
        }

    # ------------------------------------------------------------------
    # Subscriber preview
    # ------------------------------------------------------------------

    async def get_subscriber_view(self, db: AsyncSession) -> dict:
        """
        Return a subscriber-safe preview of the WF portfolio.
        Shows positions (symbol + P&L only), recent winners, and aggregate stats.
        """
        # Prefer WF portfolio (more history after backfill)
        state = await self._get_or_create_state(db, "walkforward")
        open_positions = await self._get_open_positions(db, "walkforward")

        from app.services.scanner import scanner_service

        # Open positions: symbol + P&L only (no shares/sizes)
        positions = []
        for pos in open_positions:
            df = scanner_service.data_cache.get(pos.symbol)
            current_price = float(df["close"].iloc[-1]) if df is not None and not df.empty else pos.entry_price
            pnl_pct = ((current_price / pos.entry_price) - 1) * 100
            positions.append({
                "symbol": pos.symbol,
                "pnl_pct": round(pnl_pct, 2),
            })

        # Recent winners (last 5 profitable closed trades)
        winners_result = await db.execute(
            select(ModelPosition)
            .where(
                ModelPosition.portfolio_type == "walkforward",
                ModelPosition.status == "closed",
                ModelPosition.pnl_pct > 0,
            )
            .order_by(ModelPosition.exit_date.desc())
            .limit(5)
        )
        recent_winners = [
            {
                "symbol": t.symbol,
                "pnl_pct": t.pnl_pct,
                "exit_date": t.exit_date.isoformat() if t.exit_date else None,
            }
            for t in winners_result.scalars().all()
        ]

        # Aggregate stats
        positions_value = 0.0
        for pos in open_positions:
            df = scanner_service.data_cache.get(pos.symbol)
            if df is not None and not df.empty:
                positions_value += float(df["close"].iloc[-1]) * pos.shares

        total_value = state.current_cash + positions_value
        portfolio_return_pct = ((total_value / state.starting_capital) - 1) * 100 if state.starting_capital else 0

        win_rate = (
            (state.winning_trades / state.total_trades * 100)
            if state.total_trades > 0
            else 0
        )

        # Find inception date from earliest position
        earliest = await db.execute(
            select(ModelPosition)
            .where(ModelPosition.portfolio_type == "walkforward")
            .order_by(ModelPosition.entry_date.asc())
            .limit(1)
        )
        first_pos = earliest.scalar_one_or_none()
        inception_date = first_pos.entry_date.date().isoformat() if first_pos and first_pos.entry_date else None
        active_days = (date.today() - first_pos.entry_date.date()).days if first_pos and first_pos.entry_date else 0

        return {
            "open_positions": positions,
            "recent_winners": recent_winners,
            "portfolio_return_pct": round(portfolio_return_pct, 2),
            "win_rate": round(win_rate, 1),
            "total_trades": state.total_trades,
            "inception_date": inception_date,
            "active_since_days": active_days,
        }


    # ------------------------------------------------------------------
    # Signal Track Record — every fresh pick, no position limits
    # ------------------------------------------------------------------

    async def process_signal_track_entries(self, db: AsyncSession) -> dict:
        """
        Enter EVERY fresh signal into the signal track record.
        No position limit, no cash gating — flat $10K notional per pick.
        """
        from app.services.data_export import data_export_service

        dashboard = data_export_service.read_dashboard_json()
        if not dashboard:
            return {"entries": 0, "reason": "No dashboard cache available"}

        buy_signals = dashboard.get("buy_signals", [])
        fresh_signals = [s for s in buy_signals if s.get("is_fresh")]
        if not fresh_signals:
            return {"entries": 0, "reason": "No fresh signals"}

        # Skip symbols already open in signal track record
        open_positions = await self._get_open_positions(db, SIGNAL_TRACK_RECORD)
        held_symbols = {p.symbol for p in open_positions}

        entries = 0
        for sig in fresh_signals:
            symbol = sig["symbol"]
            if symbol in held_symbols:
                continue

            price = sig.get("price", 0)
            if price <= 0:
                continue

            shares = SIGNAL_TRACK_NOTIONAL / price

            pos = ModelPosition(
                portfolio_type=SIGNAL_TRACK_RECORD,
                symbol=symbol,
                entry_date=datetime.utcnow(),
                entry_price=price,
                shares=shares,
                cost_basis=SIGNAL_TRACK_NOTIONAL,
                highest_price=price,
                status="open",
                signal_data_json=json.dumps(sig),
            )
            db.add(pos)
            entries += 1
            held_symbols.add(symbol)

            logger.info(
                f"[SIGNAL-TRACK] Entered {symbol} @ ${price:.2f} "
                f"(${SIGNAL_TRACK_NOTIONAL:,.0f} notional)"
            )

        if entries:
            await db.commit()

        return {"entries": entries, "open_total": len(held_symbols)}

    async def process_signal_track_exits(
        self, db: AsyncSession, trailing_stop_pct: Optional[float] = None
    ) -> List[dict]:
        """
        Daily close exit check for signal track record positions.
        Regime-adjusted trailing stop from HWM. No rebalance force-close.
        """
        from app.services.scanner import scanner_service

        positions = await self._get_open_positions(db, SIGNAL_TRACK_RECORD)
        if not positions:
            return []

        closed = []
        for pos in positions:
            df = scanner_service.data_cache.get(pos.symbol)
            if df is None or df.empty:
                continue

            close_price = float(df["close"].iloc[-1])

            # Update HWM
            if close_price > (pos.highest_price or pos.entry_price):
                pos.highest_price = close_price

            # Check trailing stop
            hwm = pos.highest_price or pos.entry_price
            stop_pct = trailing_stop_pct if trailing_stop_pct is not None else TRAILING_STOP_PCT
            trailing_stop_level = hwm * (1 - stop_pct / 100)

            if close_price <= trailing_stop_level:
                result = await self._close_position(
                    db, pos, close_price, "trailing_stop"
                )
                closed.append(result)

        if closed:
            await db.commit()

        return closed

    async def get_signal_track_stats(self, db: AsyncSession) -> dict:
        """
        Compute aggregate stats for the signal track record.
        Returns win rate, avg gain/loss, best/worst, holding days, recent trades.
        """
        from sqlalchemy import func as sqlfunc

        # All closed positions
        closed_result = await db.execute(
            select(ModelPosition).where(
                ModelPosition.portfolio_type == SIGNAL_TRACK_RECORD,
                ModelPosition.status == "closed",
            )
        )
        closed_positions = list(closed_result.scalars().all())

        # Open positions
        open_positions = await self._get_open_positions(db, SIGNAL_TRACK_RECORD)

        total_picks = len(closed_positions) + len(open_positions)
        if not total_picks:
            return {
                "total_picks": 0,
                "open_count": 0,
                "closed_count": 0,
                "win_rate": 0,
                "avg_gain_pct": 0,
                "avg_loss_pct": 0,
                "avg_pnl_pct": 0,
                "avg_holding_days": 0,
                "best_pick": None,
                "worst_pick": None,
                "recent_closed": [],
            }

        # Win/loss stats from closed trades
        winners = [p for p in closed_positions if p.pnl_pct and p.pnl_pct > 0]
        losers = [p for p in closed_positions if p.pnl_pct is not None and p.pnl_pct <= 0]

        win_rate = (len(winners) / len(closed_positions) * 100) if closed_positions else 0
        avg_gain = (
            sum(p.pnl_pct for p in winners) / len(winners)
            if winners else 0
        )
        avg_loss = (
            sum(p.pnl_pct for p in losers) / len(losers)
            if losers else 0
        )
        avg_pnl = (
            sum(p.pnl_pct for p in closed_positions) / len(closed_positions)
            if closed_positions else 0
        )

        # Holding days
        holding_days = []
        for p in closed_positions:
            if p.entry_date and p.exit_date:
                holding_days.append((p.exit_date - p.entry_date).days)
        avg_holding = sum(holding_days) / len(holding_days) if holding_days else 0

        # Best/worst picks
        best = max(closed_positions, key=lambda p: p.pnl_pct or 0, default=None)
        worst = min(closed_positions, key=lambda p: p.pnl_pct or 0, default=None)

        def _pick_summary(p):
            if not p:
                return None
            return {
                "symbol": p.symbol,
                "pnl_pct": round(p.pnl_pct, 2) if p.pnl_pct else 0,
                "entry_date": p.entry_date.isoformat() if p.entry_date else None,
                "exit_date": p.exit_date.isoformat() if p.exit_date else None,
                "exit_reason": p.exit_reason,
            }

        # Recent closed (last 20)
        recent = sorted(
            closed_positions,
            key=lambda p: p.exit_date or datetime.min,
            reverse=True,
        )[:20]

        # Open positions with current unrealized P&L
        from app.services.scanner import scanner_service

        open_data = []
        for pos in open_positions:
            df = scanner_service.data_cache.get(pos.symbol)
            current_price = (
                float(df["close"].iloc[-1])
                if df is not None and not df.empty
                else pos.entry_price
            )
            pnl_pct = ((current_price / pos.entry_price) - 1) * 100
            open_data.append({
                "symbol": pos.symbol,
                "entry_date": pos.entry_date.isoformat() if pos.entry_date else None,
                "entry_price": pos.entry_price,
                "current_price": round(current_price, 2),
                "pnl_pct": round(pnl_pct, 2),
                "highest_price": pos.highest_price,
            })

        return {
            "total_picks": total_picks,
            "open_count": len(open_positions),
            "closed_count": len(closed_positions),
            "win_rate": round(win_rate, 1),
            "avg_gain_pct": round(avg_gain, 2),
            "avg_loss_pct": round(avg_loss, 2),
            "avg_pnl_pct": round(avg_pnl, 2),
            "avg_holding_days": round(avg_holding, 1),
            "best_pick": _pick_summary(best),
            "worst_pick": _pick_summary(worst),
            "open_positions": open_data,
            "recent_closed": [
                {
                    "symbol": t.symbol,
                    "entry_date": t.entry_date.isoformat() if t.entry_date else None,
                    "exit_date": t.exit_date.isoformat() if t.exit_date else None,
                    "entry_price": t.entry_price,
                    "exit_price": t.exit_price,
                    "pnl_pct": round(t.pnl_pct, 2) if t.pnl_pct else 0,
                    "exit_reason": t.exit_reason,
                }
                for t in recent
            ],
        }

    async def backfill_signal_track_record(
        self,
        db: AsyncSession,
        as_of_date: str = "2026-02-01",
        force: bool = False,
    ) -> dict:
        """
        Backfill signal track record from a historical date through today.

        Walks through each trading day, enters ALL fresh signals from snapshots,
        checks trailing stop exits using daily close prices. No position limit,
        no cash logic — flat $10K notional per pick.
        """
        import pandas as pd
        from sqlalchemy import delete

        if force:
            await db.execute(
                delete(ModelPosition).where(
                    ModelPosition.portfolio_type == SIGNAL_TRACK_RECORD
                )
            )
            await db.execute(
                delete(ModelPortfolioState).where(
                    ModelPortfolioState.portfolio_type == SIGNAL_TRACK_RECORD
                )
            )
            await db.flush()
            logger.info("[SIGNAL-TRACK-BACKFILL] Reset signal track record")

        from app.services.scanner import scanner_service

        spy_df = scanner_service.data_cache.get("SPY")
        if spy_df is None or spy_df.empty:
            return {"error": "SPY data not in cache — run a scan first"}

        start = pd.Timestamp(as_of_date).normalize()
        today = pd.Timestamp(date.today()).normalize()

        trading_days = sorted([
            d.date() if hasattr(d, 'date') else d
            for d in spy_df.index
            if start.date() <= (d.date() if hasattr(d, 'date') else d) <= today.date()
        ])
        if not trading_days:
            return {"error": f"No trading days found between {as_of_date} and today"}

        summary = {
            "start_date": str(start.date()),
            "end_date": str(today.date()),
            "trading_days": len(trading_days),
            "entries": 0,
            "exits": 0,
        }

        logger.info(
            f"[SIGNAL-TRACK-BACKFILL] {len(trading_days)} trading days "
            f"from {as_of_date}"
        )

        for day_date in trading_days:
            open_positions = await self._get_open_positions(db, SIGNAL_TRACK_RECORD)

            # --- Check exits (trailing stop) ---
            for pos in open_positions:
                df = scanner_service.data_cache.get(pos.symbol)
                if df is None or df.empty:
                    continue

                close_price = self._get_close_for_date(df, day_date)
                if close_price is None:
                    continue

                # Update HWM
                if close_price > (pos.highest_price or pos.entry_price):
                    pos.highest_price = close_price

                hwm = pos.highest_price or pos.entry_price
                stop_level = hwm * (1 - TRAILING_STOP_PCT / 100)
                if close_price <= stop_level:
                    pnl_dollars = (close_price - pos.entry_price) * pos.shares
                    pnl_pct = ((close_price / pos.entry_price) - 1) * 100

                    pos.exit_date = datetime.combine(day_date, datetime.min.time())
                    pos.exit_price = close_price
                    pos.exit_reason = "trailing_stop"
                    pos.pnl_dollars = round(pnl_dollars, 2)
                    pos.pnl_pct = round(pnl_pct, 2)
                    pos.status = "closed"
                    summary["exits"] += 1

            await db.flush()

            # --- Enter fresh signals for this date ---
            signals = await self._get_signals_for_date(day_date)
            if signals:
                held = {p.symbol for p in await self._get_open_positions(db, SIGNAL_TRACK_RECORD)}
                fresh = [s for s in signals if s.get("is_fresh") and s["symbol"] not in held]

                for sig in fresh:
                    symbol = sig["symbol"]
                    df = scanner_service.data_cache.get(symbol)
                    if df is None or df.empty:
                        continue

                    price = self._get_close_for_date(df, day_date)
                    if price is None or price <= 0:
                        continue

                    shares = SIGNAL_TRACK_NOTIONAL / price
                    pos = ModelPosition(
                        portfolio_type=SIGNAL_TRACK_RECORD,
                        symbol=symbol,
                        entry_date=datetime.combine(day_date, datetime.min.time()),
                        entry_price=price,
                        shares=shares,
                        cost_basis=SIGNAL_TRACK_NOTIONAL,
                        highest_price=price,
                        status="open",
                        signal_data_json=json.dumps(sig),
                    )
                    db.add(pos)
                    summary["entries"] += 1

            # Flush periodically
            if (summary["entries"] + summary["exits"]) % 20 == 0:
                await db.flush()

        await db.commit()

        logger.info(
            f"[SIGNAL-TRACK-BACKFILL] Complete: {summary['entries']} entries, "
            f"{summary['exits']} exits over {summary['trading_days']} days"
        )
        return summary


# Singleton
model_portfolio_service = ModelPortfolioService()
