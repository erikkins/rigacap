"""
Scheduler Service - Daily market data updates

Runs after market close (4:30 PM ET) on trading days to:
1. Fetch fresh price data from yfinance
2. Run market scan for new signals
3. Store signals in database
4. Check open positions for stop/target hits
"""

import asyncio
from datetime import datetime, time
from typing import Optional, Callable, List
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from app.core.config import settings
from app.core.timezone import trading_today, days_since_et
from app.services.scanner import scanner_service
from app.services.email_service import email_service, admin_email_service, ADMIN_EMAILS, get_email_failures, clear_email_failures
from app.services.push_notification_service import push_notification_service
from app.services.data_export import data_export_service
from app.services.stock_universe import MUST_INCLUDE

logger = logging.getLogger(__name__)

# Admin email for alerts
ADMIN_EMAIL = "erik@rigacap.com"

# US Eastern timezone for market hours
ET = pytz.timezone('US/Eastern')


class SchedulerService:
    """
    Manages scheduled jobs for market data updates
    """

    def __init__(self):
        self.scheduler: Optional[AsyncIOScheduler] = None
        self.is_running = False
        self.last_run: Optional[datetime] = None
        self.last_run_status: Optional[str] = None
        self.run_count = 0
        self.callbacks: List[Callable] = []
        # Track alerted double signals to avoid duplicate alerts
        self._alerted_double_signals: set = set()
        # Track alerted sell positions to avoid duplicate intraday alerts
        self._alerted_sell_positions: set = set()

    def add_callback(self, callback: Callable):
        """Add a callback to be called after each scheduled run"""
        self.callbacks.append(callback)

    async def daily_update(self):
        """
        Main daily update job

        Runs after market close to:
        1. Fetch fresh data
        2. Generate signals
        3. Log results
        """
        start_time = datetime.now(ET)
        logger.info(f"🕐 Starting daily update at {start_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")

        try:
            # Check if market was open today (skip weekends/holidays)
            if not self._is_trading_day(start_time):
                logger.info("📅 Not a trading day, skipping update")
                self.last_run_status = "skipped_non_trading_day"
                return

            # Ensure universe is loaded
            await scanner_service.ensure_universe_loaded()
            universe_size = len(scanner_service.universe)
            cache_size = len(scanner_service.data_cache)
            coverage = cache_size / universe_size if universe_size > 0 else 0

            # Check if we need to fill gaps or just do incremental update
            COVERAGE_THRESHOLD = 0.9  # 90% coverage required for incremental mode

            if coverage < COVERAGE_THRESHOLD:
                # Below threshold - need to fill gaps with full historical fetch
                logger.info(f"📊 Cache coverage {coverage:.1%} below {COVERAGE_THRESHOLD:.0%} threshold")
                logger.info(f"📊 Fetching full historical data to fill gaps...")
                await scanner_service.fetch_data(period="5y")
                symbols_loaded = len(scanner_service.data_cache)
                new_coverage = symbols_loaded / universe_size if universe_size > 0 else 0
                logger.info(f"✅ Full fetch complete: {symbols_loaded} symbols ({new_coverage:.1%} coverage)")
            else:
                # Good coverage - just get today's prices (fast incremental update)
                logger.info(f"📊 Cache coverage {coverage:.1%} OK - fetching today's prices (incremental)...")
                fetch_result = await scanner_service.fetch_incremental()
                symbols_loaded = len(scanner_service.data_cache)
                logger.info(f"✅ Incremental update: {fetch_result.get('updated', 0)} updated, "
                           f"{fetch_result.get('skipped', 0)} skipped, {symbols_loaded} total symbols "
                           f"(source: {fetch_result.get('source', 'unknown')})")

                # Auto-retry with alternate source if >10% symbols failed
                if fetch_result.get("failed", 0) > cache_size * 0.1:
                    from app.services.market_data_provider import market_data_provider
                    alt = "alpaca" if market_data_provider._get_primary_source() == "yfinance" else "yfinance"
                    logger.warning(f"⚠️ High failure rate ({fetch_result['failed']} failed), retrying with {alt}...")
                    market_data_provider.force_source = alt
                    retry_result = await scanner_service.fetch_incremental()
                    market_data_provider.force_source = None
                    logger.info(f"📡 Retry: {retry_result.get('updated', 0)} updated, "
                               f"{retry_result.get('failed', 0)} still failed")

            # Auto-save to S3/local after fetching new data
            logger.info("💾 Saving price data to persistent storage...")
            export_result = data_export_service.export_consolidated(scanner_service.data_cache)
            if export_result.get("success"):
                logger.info(f"✅ Saved {export_result.get('count', 0)} symbols to {export_result.get('storage', 'storage')}")
            else:
                logger.warning(f"⚠️ Data export failed: {export_result.get('message', 'unknown error')}")

            # Run scan
            logger.info("🔍 Running market scan...")
            signals = await scanner_service.scan(refresh_data=False)
            strong_signals = [s for s in signals if s.is_strong]

            logger.info(f"📈 Found {len(signals)} signals ({len(strong_signals)} strong)")

            # Log signal details
            for sig in signals[:5]:  # Log top 5
                logger.info(
                    f"   {'🔥' if sig.is_strong else '📊'} {sig.symbol}: "
                    f"${sig.price:.2f} ({sig.pct_above_dwap:+.1f}% > DWAP)"
                )

            # Run callbacks (e.g., store to DB, send alerts)
            for callback in self.callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(signals)
                    else:
                        callback(signals)
                except Exception as e:
                    logger.error(f"Callback error: {e}")

            # Run daily walk-forward simulation for dashboard stats
            try:
                logger.info("📊 Running daily walk-forward simulation...")
                await self._run_daily_walk_forward()
                logger.info("✅ Walk-forward simulation complete")
            except Exception as wf_err:
                logger.error(f"⚠️ Walk-forward simulation failed: {wf_err}")
                # Don't fail the whole update if walk-forward fails

            # Export pre-computed dashboard data to S3 for instant frontend loading
            try:
                await self._export_dashboard_cache()
            except Exception as cache_err:
                logger.error(f"⚠️ Dashboard cache export failed: {cache_err}")

            # Persist ensemble signals to database for audit trail + email consistency
            try:
                from app.services.ensemble_signal_service import ensemble_signal_service
                from app.core.database import async_session as es_session

                dashboard_data = data_export_service.read_dashboard_json()
                if dashboard_data and dashboard_data.get('buy_signals'):
                    async with es_session() as sig_db:
                        result = await ensemble_signal_service.persist_signals(
                            sig_db, dashboard_data['buy_signals'], trading_today()
                        )
                        invalidated = await ensemble_signal_service.invalidate_stale_signals(
                            sig_db, trading_today(),
                            {s['symbol'] for s in dashboard_data['buy_signals']}
                        )
                        logger.info(
                            f"📝 Persisted {result['inserted']} ensemble signal(s), "
                            f"invalidated {invalidated}"
                        )
                else:
                    logger.info("📝 No buy signals to persist")
            except Exception as e:
                logger.error(f"⚠️ Signal persistence failed: {e}")

            # Model portfolio: process entries + WF exits after dashboard cache
            try:
                from app.services.model_portfolio_service import model_portfolio_service, _get_regime_trailing_stop
                from app.core.database import async_session as mp_session

                sched_regime_stop = _get_regime_trailing_stop(dashboard_data)

                async with mp_session() as mp_db:
                    for ptype in ("live", "walkforward"):
                        entry_result = await model_portfolio_service.process_entries(mp_db, ptype)
                        if entry_result.get("entries"):
                            logger.info(f"[MODEL-{ptype.upper()}] Entered {entry_result['entries']} position(s)")

                    # WF daily close exit check (trailing stop + rebalance boundary)
                    wf_closed = await model_portfolio_service.process_wf_exits(
                        mp_db, trailing_stop_pct=sched_regime_stop
                    )
                    if wf_closed:
                        logger.info(f"[MODEL-WF] Closed {len(wf_closed)} position(s)")

                    # Signal track record: enter ALL fresh signals (no position limit)
                    track_entries = await model_portfolio_service.process_signal_track_entries(mp_db)
                    if track_entries.get("entries"):
                        logger.info(f"[SIGNAL-TRACK] Entered {track_entries['entries']} pick(s)")

                    # Signal track record: daily exit checks (regime-adjusted trailing stop)
                    track_closed = await model_portfolio_service.process_signal_track_exits(
                        mp_db, trailing_stop_pct=sched_regime_stop
                    )
                    if track_closed:
                        logger.info(f"[SIGNAL-TRACK] Closed {len(track_closed)} pick(s)")

                    # Take daily equity curve snapshot
                    snap_result = await model_portfolio_service.take_daily_snapshot(mp_db)
                    logger.info(f"[MODEL-SNAPSHOT] {snap_result}")
            except Exception as e:
                logger.error(f"[MODEL-PORTFOLIO] Entry/exit processing failed: {e}")

            # Regime forecast snapshot
            try:
                from app.services.regime_forecast_service import regime_forecast_service
                from app.core.database import async_session as rfs_session

                async with rfs_session() as rfs_db:
                    forecast_result = await regime_forecast_service.take_snapshot(rfs_db)
                    logger.info(f"[REGIME-FORECAST] {forecast_result}")
            except Exception as e:
                logger.error(f"[REGIME-FORECAST] Snapshot failed: {e}")

            # Update status
            self.last_run = datetime.now(ET)
            self.last_run_status = "success"
            self.run_count += 1

            elapsed = (datetime.now(ET) - start_time).total_seconds()
            logger.info(f"✅ Daily update complete in {elapsed:.1f}s")

        except Exception as e:
            logger.error(f"❌ Daily update failed: {e}")
            self.last_run_status = f"error: {str(e)}"
            raise

    async def _run_daily_walk_forward(self):
        """
        Run a 1-year walk-forward simulation and cache results for dashboard.

        Uses biweekly reoptimization without AI to keep it fast (~30 seconds).
        Results are stored in WalkForwardSimulation table with is_daily_cache=True.
        """
        from datetime import timedelta
        from app.core.database import async_session, WalkForwardSimulation
        from app.services.walk_forward_service import walk_forward_service
        from sqlalchemy import select, delete

        from zoneinfo import ZoneInfo
        now_et = datetime.now(ZoneInfo("America/New_York"))
        end_date = now_et.replace(tzinfo=None)
        start_date = end_date - timedelta(days=365)  # 1 year lookback

        async with async_session() as db:
            try:
                # Delete old daily cache entries (keep only last one)
                await db.execute(
                    delete(WalkForwardSimulation).where(
                        WalkForwardSimulation.is_daily_cache == True
                    )
                )

                # Create new job record
                job = WalkForwardSimulation(
                    simulation_date=datetime.utcnow(),
                    start_date=start_date,
                    end_date=end_date,
                    reoptimization_frequency="biweekly",
                    status="running",
                    is_daily_cache=True,  # Mark as dashboard cache
                    total_return_pct=0,
                    sharpe_ratio=0,
                    max_drawdown_pct=0,
                    num_strategy_switches=0,
                    benchmark_return_pct=0,
                )
                db.add(job)
                await db.commit()
                await db.refresh(job)
                job_id = job.id

                logger.info(f"[DAILY-WF] Starting 1-year walk-forward (job {job_id})")

                # Run walk-forward with ensemble strategy (production strategy)
                result = await walk_forward_service.run_walk_forward_simulation(
                    db=db,
                    start_date=start_date,
                    end_date=end_date,
                    reoptimization_frequency="biweekly",
                    min_score_diff=10.0,
                    enable_ai_optimization=False,  # No AI for speed
                    max_symbols=500,  # Match production universe
                    existing_job_id=job_id,
                    fixed_strategy_id=5,  # Ensemble (DWAP+Momentum)
                    carry_positions=True,  # Match production: trailing stop only
                )

                logger.info(f"[DAILY-WF] Complete: {result.total_return_pct:.1f}% return, "
                           f"{result.num_strategy_switches} switches, "
                           f"benchmark {result.benchmark_return_pct:.1f}%")

            except Exception as e:
                logger.error(f"[DAILY-WF] Failed: {e}")
                # Update job status to failed
                result = await db.execute(
                    select(WalkForwardSimulation).where(WalkForwardSimulation.id == job_id)
                )
                job = result.scalar_one_or_none()
                if job:
                    job.status = "failed"
                    await db.commit()
                raise

    async def _run_nightly_walk_forward(self):
        """
        Nightly walk-forward simulation for missed opportunities + social content.

        Runs at 8 PM ET (after daily emails at 6 PM) on trading days.
        1. Runs 90-day rolling WF simulation with ensemble strategy
        2. Stores results with is_nightly_missed_opps=True for dashboard
        3. Generates social media content from best trades
        """
        from datetime import timedelta
        from app.core.database import async_session, WalkForwardSimulation
        from app.services.walk_forward_service import walk_forward_service
        from sqlalchemy import select, delete

        now = datetime.now(ET)
        if not self._is_trading_day(now):
            logger.info("📅 Not a trading day, skipping nightly walk-forward")
            return

        logger.info("🌙 Starting nightly walk-forward simulation...")

        end_date = datetime.now()
        start_date = end_date - timedelta(days=90)

        async with async_session() as db:
            try:
                # Delete old nightly missed opps cache
                await db.execute(
                    delete(WalkForwardSimulation).where(
                        WalkForwardSimulation.is_nightly_missed_opps == True
                    )
                )

                # Create new job record
                job = WalkForwardSimulation(
                    simulation_date=datetime.utcnow(),
                    start_date=start_date,
                    end_date=end_date,
                    reoptimization_frequency="biweekly",
                    status="running",
                    is_nightly_missed_opps=True,
                    total_return_pct=0,
                    sharpe_ratio=0,
                    max_drawdown_pct=0,
                    num_strategy_switches=0,
                    benchmark_return_pct=0,
                )
                db.add(job)
                await db.commit()
                await db.refresh(job)
                job_id = job.id

                logger.info(f"[NIGHTLY-WF] Starting 90-day walk-forward (job {job_id})")

                # Run walk-forward with ensemble strategy, no AI
                result = await walk_forward_service.run_walk_forward_simulation(
                    db=db,
                    start_date=start_date,
                    end_date=end_date,
                    reoptimization_frequency="biweekly",
                    min_score_diff=10.0,
                    enable_ai_optimization=False,
                    max_symbols=500,
                    existing_job_id=job_id,
                    fixed_strategy_id=5,  # Ensemble strategy
                    carry_positions=True,
                )

                logger.info(f"[NIGHTLY-WF] Complete: {result.total_return_pct:.1f}% return, "
                           f"{result.num_strategy_switches} switches")

                # Re-export dashboard cache with updated missed opportunities
                try:
                    await self._export_dashboard_cache()
                except Exception as cache_err:
                    logger.error(f"[NIGHTLY-WF] Dashboard cache re-export failed: {cache_err}")

                # Social content generation from WF trades — DISABLED
                # Re-enable once we have real tracked positions producing exits.
                # The nightly WF uses simulated trades, not real user-tracked positions.
                # When ready: generate posts from real position exits (sell alerts),
                # not walk-forward simulation results.
                logger.info("[NIGHTLY-WF] Social content generation skipped (waiting for real trades)")

            except Exception as e:
                logger.error(f"[NIGHTLY-WF] Failed: {e}")
                import traceback
                traceback.print_exc()
                # Update job status to failed
                try:
                    result = await db.execute(
                        select(WalkForwardSimulation).where(WalkForwardSimulation.id == job_id)
                    )
                    job = result.scalar_one_or_none()
                    if job:
                        job.status = "failed"
                        await db.commit()
                except Exception:
                    pass

    def _is_trading_day(self, dt: datetime) -> bool:
        """
        Check if the given date is a trading day

        Basic check: weekday only (Mon-Fri)
        TODO: Add holiday calendar (NYSE holidays)
        """
        return dt.weekday() < 5  # 0-4 = Mon-Fri

    def _check_sell_trigger(
        self,
        position,
        live_price: float,
        regime_forecast: dict = None,
        trailing_stop_pct: float = 12.0,
    ) -> dict:
        """
        Check if a single position triggers a sell or warning signal.

        Args:
            position: DB Position object (has entry_price, highest_price)
            live_price: Current live price
            regime_forecast: Regime forecast dict from dashboard cache (optional)
            trailing_stop_pct: Trailing stop percentage (ensemble uses 12%)

        Returns:
            Dict with action/reason/stop_price if triggered, or None
        """
        entry_price = position.entry_price or 0
        high_water_mark = max(
            entry_price,
            position.highest_price or entry_price,
            live_price,
        )

        trailing_stop_level = high_water_mark * (1 - trailing_stop_pct / 100)
        distance_to_stop_pct = (
            (live_price - trailing_stop_level) / trailing_stop_level * 100
            if trailing_stop_level > 0 else 100
        )

        action = None
        reason = None

        # Check regime-based exits first
        if regime_forecast:
            rec = regime_forecast.get("recommended_action", "stay_invested")
            if rec == "go_to_cash":
                action = "sell"
                reason = f"Market regime exit — {regime_forecast.get('outlook_detail', 'high risk detected')}"
            elif rec == "reduce_exposure":
                action = "warning"
                reason = "Regime deteriorating — consider reducing exposure"
            elif rec == "tighten_stops":
                action = "warning"
                reason = f"Tighten stops — {regime_forecast.get('outlook_detail', 'risk increasing')}"

        # Check trailing stop (overrides regime warning)
        if live_price <= trailing_stop_level:
            action = "sell"
            reason = f"Trailing stop hit — price ${live_price:.2f} below stop ${trailing_stop_level:.2f}"

        # Check proximity to trailing stop (warning zone)
        elif distance_to_stop_pct < 3 and action != "sell":
            action = "warning"
            if not reason:
                reason = f"Within {distance_to_stop_pct:.1f}% of trailing stop ${trailing_stop_level:.2f}"

        if action:
            return {
                "action": action,
                "reason": reason,
                "stop_price": round(trailing_stop_level, 2),
            }
        return None

    async def _intraday_position_monitor(self):
        """
        Check live prices for all open positions across all users.
        Send sell/warning alert emails when trailing stop or regime exit triggers.

        Runs every 5 minutes during market hours (Mon-Fri 9:00-15:59 ET).
        """
        logger.info("📡 Starting intraday position monitor...")

        try:
            now = datetime.now(ET)
            if not self._is_trading_day(now):
                logger.info("📅 Not a trading day, skipping intraday monitor")
                return

            # Freshness gate — only enforce after 5 PM (before that, yesterday's close is fine)
            if now.hour >= 17 and not await self._validate_data_freshness("intraday_monitor"):
                return

            from app.core.database import async_session, Position as DBPosition, User as DBUser
            from sqlalchemy import select
            import yfinance as yf

            async with async_session() as db:
                # 1. Query all open positions with user email
                result = await db.execute(
                    select(DBPosition, DBUser.email, DBUser.name, DBUser.id, DBUser.email_preferences)
                    .join(DBUser, DBPosition.user_id == DBUser.id)
                    .where(DBPosition.status == 'open')
                )
                rows = result.all()

                if not rows:
                    logger.info("📡 No open positions to monitor")
                    return

                logger.info(f"📡 Monitoring {len(rows)} open position(s)")

                # 2. Collect unique symbols (user positions + model portfolio)
                symbols = list({row[0].symbol for row in rows})
                try:
                    from app.core.database import ModelPosition as MPModel
                    mp_result = await db.execute(
                        select(MPModel.symbol).where(MPModel.status == "open", MPModel.portfolio_type == "live")
                    )
                    model_syms = {r[0] for r in mp_result.all()}
                    symbols = list(set(symbols) | model_syms)
                except Exception:
                    pass  # Model tables may not exist yet

                live_prices = {}
                day_highs = {}
                try:
                    tickers = yf.Tickers(' '.join(symbols))
                    for sym in symbols:
                        try:
                            ticker = tickers.tickers.get(sym)
                            if ticker:
                                fi = ticker.fast_info
                                live_prices[sym] = fi.last_price
                                day_highs[sym] = fi.day_high
                        except Exception:
                            continue
                except Exception as e:
                    logger.error(f"📡 Failed to fetch live prices: {e}")
                    return

                logger.info(f"📡 Got live prices for {len(live_prices)}/{len(symbols)} symbols")

                # 3. Get regime forecast from cached dashboard data
                regime_forecast = None
                regime_stop = None
                try:
                    dashboard_data = data_export_service.read_dashboard_json()
                    if dashboard_data:
                        regime_forecast = dashboard_data.get('regime_forecast')
                        from app.services.model_portfolio_service import _get_regime_trailing_stop
                        regime_stop = _get_regime_trailing_stop(dashboard_data)
                except Exception as e:
                    logger.warning(f"📡 Could not read regime forecast: {e}")

                # 4. Check each position for sell triggers
                alerts_sent = 0
                today = trading_today()

                for position, user_email, user_name, uid, email_prefs in rows:
                    sym = position.symbol
                    if sym not in live_prices:
                        continue

                    live_price = live_prices[sym]

                    # Use day_high for HWM to capture peaks between 5-min checks
                    hwm_price = max(live_price, day_highs.get(sym, live_price))
                    if hwm_price > (position.highest_price or position.entry_price):
                        position.highest_price = hwm_price

                    # Check sell trigger (regime-adjusted stop)
                    guidance = self._check_sell_trigger(
                        position, live_price, regime_forecast,
                        trailing_stop_pct=regime_stop or 12.0,
                    )

                    if guidance and guidance['action'] in ('sell', 'warning'):
                        # Check user email preference
                        sell_pref = (email_prefs or {}).get('sell_alerts', True) if email_prefs else True
                        if not sell_pref:
                            continue
                        dedup_key = f"{position.id}_{guidance['action']}_{today}"
                        if dedup_key not in self._alerted_sell_positions:
                            try:
                                await email_service.send_sell_alert(
                                    to_email=user_email,
                                    user_name=user_name or "",
                                    symbol=sym,
                                    action=guidance['action'],
                                    reason=guidance['reason'],
                                    current_price=live_price,
                                    entry_price=position.entry_price,
                                    stop_price=guidance.get('stop_price'),
                                    user_id=str(uid),
                                )
                                self._alerted_sell_positions.add(dedup_key)
                                alerts_sent += 1
                                logger.info(
                                    f"📡 {guidance['action'].upper()} alert sent for {sym} "
                                    f"to {user_email}: {guidance['reason']}"
                                )
                            except Exception as e:
                                logger.error(f"📡 Failed to send alert for {sym}: {e}")

                            # Push notification (never blocks email delivery)
                            try:
                                await push_notification_service.send_sell_alert_push(
                                    db, str(uid), sym,
                                    guidance['action'], guidance['reason'],
                                )
                            except Exception as e:
                                logger.debug(f"📡 Push sell alert failed for {sym}: {e}")

                # Persist high water mark updates
                await db.commit()

                # --- Model portfolio: check live exits (intraday, regime-adjusted stop) ---
                try:
                    from app.services.model_portfolio_service import model_portfolio_service
                    mp_closed = await model_portfolio_service.process_live_exits(
                        db, live_prices, regime_forecast, day_highs=day_highs,
                        trailing_stop_pct=regime_stop,
                    )
                    if mp_closed:
                        logger.info(f"[MODEL-LIVE] Closed {len(mp_closed)} position(s)")
                except Exception as e:
                    logger.error(f"[MODEL-LIVE] Exit check failed: {e}")

                # --- 5. Intraday DWAP crossover check (watchlist stocks) ---
                intraday_signals_added = 0
                try:
                    from app.services.stock_universe import stock_universe_service

                    watchlist = []
                    if dashboard_data:
                        watchlist = dashboard_data.get('watchlist', [])

                    if watchlist:
                        # Fetch live prices for watchlist stocks not already fetched
                        wl_symbols = [w['symbol'] for w in watchlist if w['symbol'] not in live_prices]
                        if wl_symbols:
                            try:
                                wl_tickers = yf.Tickers(' '.join(wl_symbols))
                                for sym in wl_symbols:
                                    try:
                                        ticker = wl_tickers.tickers.get(sym)
                                        if ticker:
                                            live_prices[sym] = ticker.fast_info.last_price
                                    except Exception:
                                        continue
                            except Exception as e:
                                logger.warning(f"📡 Failed to fetch watchlist prices: {e}")

                        # Check each watchlist stock for DWAP crossover
                        new_intraday_signals = []
                        for w in watchlist:
                            sym = w['symbol']
                            if sym not in live_prices:
                                continue

                            lp = live_prices[sym]
                            dwap_val = w.get('dwap', 0)
                            if dwap_val <= 0:
                                continue

                            pct_above = (lp / dwap_val - 1) * 100
                            if pct_above >= 5.0:
                                dedup_key = f"intraday_signal_{sym}_{today}"
                                if dedup_key not in self._alerted_sell_positions:
                                    info = stock_universe_service.symbol_info.get(sym, {})
                                    sector = info.get('sector', '')
                                    mom_rank = w.get('momentum_rank')

                                    new_intraday_signals.append({
                                        'symbol': sym,
                                        'live_price': lp,
                                        'dwap': dwap_val,
                                        'pct_above_dwap': round(pct_above, 2),
                                        'momentum_rank': mom_rank,
                                        'sector': sector,
                                    })
                                    self._alerted_sell_positions.add(dedup_key)

                        if new_intraday_signals:
                            # Send email alerts to subscribed users,
                            # skipping users who already hold the stock
                            user_result = await db.execute(
                                select(DBUser.id, DBUser.email, DBUser.name, DBUser.email_preferences)
                                .where(DBUser.is_active == True)
                            )
                            active_users = user_result.all()

                            # Build set of (user_id, symbol) for open positions
                            held_positions = set()
                            for pos, *_ in rows:
                                held_positions.add((pos.user_id, pos.symbol))

                            for sig in new_intraday_signals:
                                for user_id, user_email, user_name, email_prefs in active_users:
                                    if (user_id, sig['symbol']) in held_positions:
                                        logger.info(f"📡 Skipping intraday alert for {sig['symbol']} to {user_email} (already holds position)")
                                        continue
                                    # Check user email preference
                                    if not (email_prefs or {}).get('intraday_signals', True):
                                        continue
                                    try:
                                        await email_service.send_intraday_signal_alert(
                                            to_email=user_email,
                                            user_name=user_name or "",
                                            symbol=sig['symbol'],
                                            live_price=sig['live_price'],
                                            dwap=sig['dwap'],
                                            pct_above_dwap=sig['pct_above_dwap'],
                                            momentum_rank=sig['momentum_rank'],
                                            sector=sig['sector'],
                                            user_id=str(user_id),
                                        )
                                    except Exception as e:
                                        logger.error(f"📡 Failed to send intraday alert for {sig['symbol']} to {user_email}: {e}")

                                logger.info(
                                    f"📡 INTRADAY CROSSOVER: {sig['symbol']} at ${sig['live_price']:.2f} "
                                    f"(DWAP +{sig['pct_above_dwap']:.1f}%)"
                                )

                            # Update dashboard.json in S3 with new intraday signals
                            try:
                                current_dashboard = data_export_service.read_dashboard_json()
                                if current_dashboard:
                                    existing_signals = current_dashboard.get('buy_signals', [])
                                    existing_symbols = {s['symbol'] for s in existing_signals}

                                    for sig in new_intraday_signals:
                                        if sig['symbol'] not in existing_symbols:
                                            existing_signals.insert(0, {
                                                'symbol': sig['symbol'],
                                                'price': sig['live_price'],
                                                'dwap': sig['dwap'],
                                                'pct_above_dwap': sig['pct_above_dwap'],
                                                'momentum_rank': sig['momentum_rank'],
                                                'sector': sig['sector'],
                                                'is_fresh': True,
                                                'is_intraday': True,
                                                'days_since_crossover': 0,
                                                'ensemble_score': 0,
                                            })
                                            intraday_signals_added += 1

                                    current_dashboard['buy_signals'] = existing_signals
                                    # Remove crossed stocks from watchlist
                                    crossed = {s['symbol'] for s in new_intraday_signals}
                                    current_dashboard['watchlist'] = [
                                        w for w in current_dashboard.get('watchlist', [])
                                        if w['symbol'] not in crossed
                                    ]
                                    data_export_service.export_dashboard_json(current_dashboard)
                                    logger.info(f"📡 Updated dashboard.json with {intraday_signals_added} intraday signal(s)")
                            except Exception as e:
                                logger.error(f"📡 Failed to update dashboard.json: {e}")

                except Exception as e:
                    logger.error(f"📡 Intraday DWAP crossover check failed: {e}")
                    import traceback
                    traceback.print_exc()

                # Trim dedup set to prevent unbounded growth
                if len(self._alerted_sell_positions) > 200:
                    self._alerted_sell_positions = set(
                        list(self._alerted_sell_positions)[-100:]
                    )

                logger.info(
                    f"📡 Intraday monitor complete: {len(rows)} positions checked, "
                    f"{alerts_sent} alert(s) sent, {intraday_signals_added} intraday signal(s) added"
                )

        except Exception as e:
            logger.error(f"❌ Intraday position monitor failed: {e}")
            import traceback
            traceback.print_exc()

    # =========================================================================
    # DATA FRESHNESS GATES
    # =========================================================================

    async def _validate_data_freshness(self, job_name: str) -> bool:
        """
        Check that the daily scan ran successfully today before sending communications.

        Returns True if data is fresh enough to proceed, False if stale (emails should be held).
        Primary check is S3 dashboard timestamp (survives across Lambda instances).
        In-memory last_run is a secondary signal.
        """
        today = trading_today()

        # Primary check: S3 dashboard JSON freshness (durable, cross-instance)
        try:
            dashboard = data_export_service.read_dashboard_json()
            if dashboard:
                generated = dashboard.get('generated_at', '')
                if generated and today.isoformat() in generated:
                    logger.warning(f"✅ Data freshness validated for {job_name} (dashboard generated today: {generated})")
                    return True
                elif generated:
                    await self._alert_stale_data(
                        job_name,
                        f"Dashboard generated_at ({generated}) doesn't match today ({today})"
                    )
                    return False
        except Exception as e:
            logger.warning(f"Could not check dashboard freshness: {e}")

        # Fallback: in-memory last_run (same-instance only)
        if self.last_run is None:
            await self._alert_stale_data(job_name, "Daily scan has not run yet and no fresh dashboard found in S3")
            return False

        last_run_date = self.last_run.date()
        if last_run_date != today:
            await self._alert_stale_data(
                job_name,
                f"Daily scan last ran on {last_run_date}, expected {today}"
            )
            return False

        if self.last_run_status != "success":
            await self._alert_stale_data(
                job_name,
                f"Daily scan status: {self.last_run_status}"
            )
            return False

        logger.warning(f"✅ Data freshness validated for {job_name} (in-memory last_run)")
        return True

    async def _validate_regime_report_freshness(self) -> bool:
        """
        Relaxed freshness check for the Monday regime report.

        Friday's successful scan is fine for a Monday report, so we allow up to 3 days stale.
        """
        if self.last_run is None:
            await self._alert_stale_data("weekly_regime_report", "Daily scan has never run")
            return False

        days_stale = (datetime.now(ET) - self.last_run).days
        if days_stale > 3:
            await self._alert_stale_data(
                "weekly_regime_report",
                f"Last scan was {days_stale} days ago"
            )
            return False

        if self.last_run_status != "success":
            await self._alert_stale_data(
                "weekly_regime_report",
                f"Last scan status: {self.last_run_status}"
            )
            return False

        logger.info("Data freshness validated for weekly_regime_report")
        return True

    async def _alert_stale_data(self, job_name: str, reason: str):
        """Alert admins that data is stale and a communication job was held."""
        msg = (
            f"HELD {job_name}: {reason}\n\n"
            "Emails/alerts will NOT be sent until the daily scan completes successfully."
        )
        logger.warning(msg)
        try:
            await admin_email_service.send_admin_alert(
                to_email=ADMIN_EMAIL,
                subject=f"HELD: {job_name} — stale data",
                message=msg,
            )
        except Exception as e:
            logger.error(f"Failed to send stale data alert: {e}")

    def start(self):
        """Start the scheduler"""
        if self.is_running:
            logger.warning("Scheduler already running")
            return

        self.scheduler = AsyncIOScheduler(timezone=ET)

        # Schedule daily update at 4:30 PM ET (after market close)
        self.scheduler.add_job(
            self.daily_update,
            CronTrigger(
                day_of_week='mon-fri',
                hour=16,
                minute=30,
                timezone=ET
            ),
            id='daily_market_update',
            name='Daily Market Update',
            replace_existing=True
        )

        # Also run a pre-market update at 9:00 AM ET
        self.scheduler.add_job(
            self._premarket_update,
            CronTrigger(
                day_of_week='mon-fri',
                hour=9,
                minute=0,
                timezone=ET
            ),
            id='premarket_update',
            name='Pre-Market Data Refresh',
            replace_existing=True
        )

        # Send daily email summary at 6:00 PM ET (dinnertime)
        self.scheduler.add_job(
            self.send_daily_emails,
            CronTrigger(
                day_of_week='mon-fri',
                hour=18,
                minute=0,
                timezone=ET
            ),
            id='daily_email',
            name='Daily Email Summary',
            replace_existing=True
        )

        # Check for new double signals at 5:00 PM ET (after daily update)
        # Sends alert email when momentum stocks cross DWAP +5%
        self.scheduler.add_job(
            self.check_double_signal_alerts,
            CronTrigger(
                day_of_week='mon-fri',
                hour=17,
                minute=0,
                timezone=ET
            ),
            id='double_signal_alert',
            name='Double Signal Alert Check',
            replace_existing=True
        )

        # Ticker health check at 7:00 AM ET (before market open)
        # Checks open positions and must-include symbols for data issues
        self.scheduler.add_job(
            self.check_ticker_health,
            CronTrigger(
                day_of_week='mon-fri',
                hour=7,
                minute=0,
                timezone=ET
            ),
            id='ticker_health_check',
            name='Ticker Health Check',
            replace_existing=True
        )

        # Nightly walk-forward + social content at 8 PM ET
        self.scheduler.add_job(
            self._run_nightly_walk_forward,
            CronTrigger(
                day_of_week='mon-fri',
                hour=20,
                minute=0,
                timezone=ET
            ),
            id='nightly_walk_forward',
            name='Nightly Walk-Forward + Social Content',
            replace_existing=True
        )

        # Intraday position monitor - every 5 minutes during market hours
        # Checks live prices for open positions and sends sell/warning alerts
        self.scheduler.add_job(
            self._intraday_position_monitor,
            CronTrigger(
                day_of_week='mon-fri',
                hour='9-15',
                minute='*/5',
                timezone=ET
            ),
            id='intraday_position_monitor',
            name='Intraday Position Monitor',
            replace_existing=True
        )

        # Auto-publish scheduled social posts every 15 minutes
        self.scheduler.add_job(
            self._publish_scheduled_posts,
            CronTrigger(
                minute='*/15',
                timezone=ET
            ),
            id='publish_scheduled_posts',
            name='Publish Scheduled Social Posts',
            replace_existing=True
        )

        # Social post notifications every hour
        self.scheduler.add_job(
            self._send_post_notifications,
            CronTrigger(
                minute=0,
                timezone=ET
            ),
            id='post_notifications',
            name='Social Post Notifications',
            replace_existing=True
        )

        # Reply scanner — every 4 hours during waking hours (Twitter + Threads)
        self.scheduler.add_job(
            self._scan_reply_opportunities,
            CronTrigger(
                hour='8,12,16,20',
                minute=15,
                timezone=ET
            ),
            id='reply_scanner',
            name='Social Reply Scanner',
            replace_existing=True
        )

        # Instagram comment reply scanner — every 4 hours, offset from reply scanner
        self.scheduler.add_job(
            self._scan_instagram_comments,
            CronTrigger(
                hour='9,13,17,21',
                minute=30,
                timezone=ET
            ),
            id='instagram_comment_scanner',
            name='Instagram Comment Scanner',
            replace_existing=True
        )

        # Threads token refresh — weekly on Mondays at 3 AM ET
        self.scheduler.add_job(
            self._refresh_threads_token,
            CronTrigger(
                day_of_week='mon',
                hour=3,
                minute=0,
                timezone=ET
            ),
            id='threads_token_refresh',
            name='Threads Token Refresh',
            replace_existing=True
        )

        # Strategy auto-analysis every other Friday at 6 PM ET
        # Runs biweekly strategy analysis and potential auto-switch
        self.scheduler.add_job(
            self._strategy_auto_analysis,
            CronTrigger(
                day_of_week='fri',
                hour=18,
                minute=30,
                week='*/2',  # Every 2 weeks
                timezone=ET
            ),
            id='strategy_auto_analysis',
            name='Strategy Auto-Analysis',
            replace_existing=True
        )

        # Nightly email failure report at 9 PM ET (after all daily email jobs)
        self.scheduler.add_job(
            self._send_email_failure_report,
            CronTrigger(
                day_of_week='mon-fri',
                hour=21,
                minute=0,
                timezone=ET
            ),
            id='email_failure_report',
            name='Email Failure Report',
            replace_existing=True
        )

        # Weekly regime report — Mondays 9 AM ET
        self.scheduler.add_job(
            self._send_weekly_regime_report,
            CronTrigger(
                day_of_week='mon',
                hour=9,
                minute=0,
                timezone=ET
            ),
            id='weekly_regime_report',
            name='Weekly Regime Report',
            replace_existing=True
        )

        self.scheduler.start()
        self.is_running = True

        next_run = self.scheduler.get_job('daily_market_update').next_run_time
        logger.info(f"📅 Scheduler started. Next daily update: {next_run}")

    async def _premarket_update(self):
        """
        Pre-market update - just refresh data, don't scan

        Useful to have fresh data available when market opens.
        Uses incremental fetch if coverage is good, otherwise fills gaps.
        """
        logger.info("🌅 Pre-market data refresh starting...")
        try:
            # Ensure universe is loaded
            await scanner_service.ensure_universe_loaded()
            universe_size = len(scanner_service.universe)
            cache_size = len(scanner_service.data_cache)
            coverage = cache_size / universe_size if universe_size > 0 else 0

            COVERAGE_THRESHOLD = 0.9

            if coverage < COVERAGE_THRESHOLD:
                # Fill gaps with full fetch
                logger.info(f"📊 Coverage {coverage:.1%} below threshold - filling gaps...")
                await scanner_service.fetch_data(period="5y")
                logger.info(f"✅ Full fetch complete: {len(scanner_service.data_cache)} symbols")
            else:
                # Incremental update
                fetch_result = await scanner_service.fetch_incremental()
                logger.info(f"✅ Pre-market refresh complete: {fetch_result.get('updated', 0)} updated, "
                           f"{len(scanner_service.data_cache)} total symbols")

            # Auto-save to S3/local
            export_result = data_export_service.export_consolidated(scanner_service.data_cache)
            if export_result.get("success"):
                logger.info(f"💾 Saved to {export_result.get('storage', 'storage')}")

            # Export dashboard cache for instant frontend loading
            try:
                await self._export_dashboard_cache()
            except Exception as cache_err:
                logger.error(f"⚠️ Dashboard cache export failed: {cache_err}")
        except Exception as e:
            logger.error(f"❌ Pre-market refresh failed: {e}")

    async def check_ticker_health(self):
        """
        Daily health check for ticker issues.

        Runs at 7 AM ET to detect:
        - Open positions with missing/stale data
        - Must-include symbols that fail to resolve

        Sends alert email if issues found.
        """
        logger.info("🏥 Starting daily ticker health check...")

        try:
            issues = []

            # Import database components
            try:
                from app.core.database import async_session, db_available
                from app.core.database import Position as DBPosition
                from sqlalchemy import select
            except ImportError as e:
                logger.warning(f"Database not available for health check: {e}")
                db_available = False

            # Check 1: Open positions
            if db_available:
                try:
                    async with async_session() as session:
                        result = await session.execute(
                            select(DBPosition).where(DBPosition.status == "open")
                        )
                        positions = result.scalars().all()

                        for pos in positions:
                            symbol = pos.symbol
                            issue = await self._check_symbol_health(symbol)
                            if issue:
                                issue['last_price'] = f"{pos.entry_price:.2f}" if pos.entry_price else "N/A"
                                issue['last_date'] = pos.entry_date.strftime('%Y-%m-%d') if pos.entry_date else "N/A"
                                issue['suggestion'] = f"You have an open position in {symbol}. Research if ticker changed or company was acquired."
                                issues.append(issue)

                        logger.info(f"✅ Checked {len(positions)} open positions")
                except Exception as e:
                    logger.error(f"Failed to check positions: {e}")

            # Check 2: Must-include symbols (sample check - top 10)
            must_check = MUST_INCLUDE[:10]  # Check first 10 must-includes
            for symbol in must_check:
                # Skip if already in issues
                if any(i['symbol'] == symbol for i in issues):
                    continue

                issue = await self._check_symbol_health(symbol)
                if issue:
                    issue['suggestion'] = f"{symbol} is in MUST_INCLUDE list. Check for ticker change and update stock_universe.py."
                    issues.append(issue)

            logger.info(f"✅ Checked {len(must_check)} must-include symbols")

            # Send alert if issues found
            if issues:
                logger.warning(f"⚠️ Found {len(issues)} ticker issues!")
                for issue in issues:
                    logger.warning(f"   • {issue['symbol']}: {issue['issue']}")

                # Send alert email
                await admin_email_service.send_ticker_alert(
                    to_email=ADMIN_EMAIL,
                    issues=issues,
                    check_type="position"
                )
                logger.info(f"📧 Alert email sent to {ADMIN_EMAIL}")
            else:
                logger.info("✅ All tickers healthy - no issues found")

        except Exception as e:
            logger.error(f"❌ Health check failed: {e}")
            import traceback
            traceback.print_exc()

    async def _check_symbol_health(self, symbol: str) -> dict:
        """
        Check if a symbol can return valid data.

        Returns:
            dict with issue details if problem found, None if healthy
        """
        try:
            import yfinance as yf

            # First check cache
            if symbol in scanner_service.data_cache:
                df = scanner_service.data_cache[symbol]
                if not df.empty:
                    # Check if data is recent (within 7 days)
                    last_date = df.index[-1]
                    days_old = (datetime.now() - last_date.to_pydatetime().replace(tzinfo=None)).days
                    if days_old <= 7:
                        return None  # Healthy

            # Try to fetch fresh data
            stock = yf.Ticker(symbol)
            hist = stock.history(period="5d")

            if hist.empty:
                # Check if ticker info exists at all
                info = stock.info
                if not info or not info.get('regularMarketPrice'):
                    return {
                        'symbol': symbol,
                        'issue': 'No data available - possibly delisted or ticker changed',
                        'last_price': 'N/A',
                        'last_date': 'N/A'
                    }

            return None  # Healthy

        except Exception as e:
            return {
                'symbol': symbol,
                'issue': f'Failed to fetch data: {str(e)[:50]}',
                'last_price': 'N/A',
                'last_date': 'N/A'
            }

    def _load_double_signal_dedup(self) -> set:
        """Load persisted double signal dedup keys from S3 (survives Lambda cold starts)."""
        try:
            import boto3, json, os
            from datetime import timedelta
            bucket = os.environ.get("PRICE_DATA_BUCKET") or os.environ.get("S3_BUCKET")
            if not bucket:
                return set()
            s3 = boto3.client("s3")
            obj = s3.get_object(Bucket=bucket, Key="signals/double_signal_dedup.json")
            data = json.loads(obj["Body"].read())
            # Keep keys from last 7 days (covers weekends + 3-day lookback)
            cutoff = (datetime.now(ET) - timedelta(days=7)).strftime('%Y-%m-%d')
            keys = set()
            for k in data.get("keys", []):
                # Key format: SYMBOL_YYYY-MM-DD — extract date suffix
                parts = k.rsplit("_", 1)
                if len(parts) == 2 and parts[1] >= cutoff:
                    keys.add(k)
            logger.info(f"Loaded {len(keys)} double signal dedup keys from S3")
            return keys
        except Exception:
            return set()

    def _save_double_signal_dedup(self, keys: set):
        """Persist double signal dedup keys to S3."""
        try:
            import boto3, json, os
            bucket = os.environ.get("PRICE_DATA_BUCKET") or os.environ.get("S3_BUCKET")
            if not bucket:
                return
            s3 = boto3.client("s3")
            s3.put_object(
                Bucket=bucket,
                Key="signals/double_signal_dedup.json",
                Body=json.dumps({"keys": list(keys)}),
                ContentType="application/json",
            )
            logger.info(f"Saved {len(keys)} double signal dedup keys to S3")
        except Exception as e:
            logger.warning(f"Failed to save double signal dedup to S3: {e}")

    async def check_double_signal_alerts(self):
        """
        Check for new double signals and send email alerts.

        Runs at 5:00 PM ET to detect momentum stocks that just crossed DWAP +5%.
        Only alerts on NEW crossovers (not previously alerted).
        Dedup persisted to S3 to survive Lambda cold starts.
        """
        logger.info("⚡ Checking for new double signal alerts...")

        try:
            # Check if this is a trading day
            now = datetime.now(ET)
            if not self._is_trading_day(now):
                logger.info("📅 Not a trading day, skipping double signal check")
                return

            # Freshness gate — HOLD alerts if data is stale
            if not await self._validate_data_freshness("double_signal_alerts"):
                return

            # Load persisted dedup from S3 (survives cold starts)
            persisted_dedup = self._load_double_signal_dedup()
            self._alerted_double_signals.update(persisted_dedup)

            import pandas as pd
            from app.api.signals import find_dwap_crossover_date

            # Read dashboard signals — the SINGLE SOURCE OF TRUTH for what's a signal
            from app.services.data_export import data_export_service
            dashboard = data_export_service.read_dashboard_json()
            dashboard_signals = {}
            if dashboard and dashboard.get('buy_signals'):
                dashboard_signals = {s['symbol']: s for s in dashboard['buy_signals']}

            # Find NEW double signals from dashboard signals only
            new_signals = []
            approaching = []
            today_str = now.strftime('%Y-%m-%d')

            for symbol, sig in dashboard_signals.items():
                pct_above = sig.get('pct_above_dwap', 0)
                days_since = sig.get('days_since_crossover')
                crossover_date = sig.get('dwap_crossover_date')

                # Only alert if crossover was recent (within last 3 days) and not already alerted
                alert_key = f"{symbol}_{crossover_date or today_str}"

                if days_since is not None and days_since <= 3 and alert_key not in self._alerted_double_signals:
                    new_signals.append({
                        'symbol': symbol,
                        'price': sig.get('price', 0),
                        'dwap': sig.get('dwap', 0),
                        'pct_above_dwap': pct_above,
                        'momentum_rank': sig.get('momentum_rank', 0),
                        'momentum_score': sig.get('momentum_score', 0),
                        'short_momentum': sig.get('short_momentum', 0),
                        'long_momentum': sig.get('long_momentum', 0),
                        'dwap_crossover_date': crossover_date or today_str,
                        'days_since_crossover': days_since or 0,
                    })
                    self._alerted_double_signals.add(alert_key)

            # Check for approaching signals (momentum stocks near DWAP threshold)
            # These use their own ranking since they're not yet ensemble signals
            try:
                regime_effective_params = None
                from app.services.market_regime import market_regime_service, get_regime_adjusted_params
                current_regime = market_regime_service.get_current_regime()
                if current_regime:
                    regime_effective_params = get_regime_adjusted_params(current_regime)['effective']

                momentum_rankings = scanner_service.rank_stocks_momentum(
                    apply_market_filter=True,
                    regime_params=regime_effective_params,
                )
                for i, r in enumerate(momentum_rankings[:20]):
                    if r.symbol in dashboard_signals:
                        continue  # Already a signal
                    df = scanner_service.data_cache.get(r.symbol)
                    if df is None or len(df) < 1:
                        continue
                    row = df.iloc[-1]
                    price = row['close']
                    dwap_val = row.get('dwap')
                    if pd.isna(dwap_val) or dwap_val <= 0:
                        continue
                    pct_above = (price / dwap_val - 1) * 100
                    if 2.0 <= pct_above < 5.0:
                        approaching.append({
                            'symbol': r.symbol,
                            'price': float(price),
                            'pct_above_dwap': pct_above,
                            'distance_to_trigger': 5.0 - pct_above,
                            'momentum_rank': i + 1,
                        })
            except Exception as ap_err:
                logger.warning(f"Approaching signals (non-fatal): {ap_err}")

            # Persist dedup to S3 (always save — even if no new signals, to maintain state)
            self._save_double_signal_dedup(self._alerted_double_signals)

            # Send alert email if new signals found
            if new_signals:
                logger.info(f"⚡ Found {len(new_signals)} new double signal(s)!")
                for sig in new_signals:
                    logger.info(f"   • {sig['symbol']}: ${sig['price']:.2f} (+{sig['pct_above_dwap']:.1f}%) - Mom #{sig['momentum_rank']}")

                # Get market regime from S3 dashboard (not in-memory — may be stale on cold start)
                regime = None
                try:
                    from app.services.data_export import data_export_service
                    dash = data_export_service.read_dashboard_json()
                    if dash:
                        ms = dash.get('market_stats', {})
                        regime = {
                            'regime': ms.get('regime', 'neutral'),
                            'spy_price': ms.get('spy_price', 0),
                        }
                except Exception as dash_err:
                    logger.warning(f"Failed to load dashboard for regime context: {dash_err}")

                # Query subscribers with valid subscriptions
                from app.core.database import async_session as async_sess, User as DBUser2, Subscription as DBSub2
                from sqlalchemy.orm import selectinload as sel_load

                async with async_sess() as db2:
                    sub_result = await db2.execute(
                        select(DBUser2)
                        .options(sel_load(DBUser2.subscription))
                        .where(DBUser2.is_active == True)
                    )
                    sub_users = sub_result.scalars().all()

                recipients = []
                for u in sub_users:
                    if u.subscription and u.subscription.is_valid():
                        if u.get_email_preference('double_signals'):
                            recipients.append({'email': u.email, 'user_id': str(u.id)})
                # Always include admin
                admin_emails = [r['email'] for r in recipients]
                if ADMIN_EMAIL not in admin_emails:
                    recipients.append({'email': ADMIN_EMAIL, 'user_id': None})

                sent = 0
                for recipient in recipients:
                    success = await email_service.send_double_signal_alert(
                        to_email=recipient['email'],
                        new_signals=new_signals,
                        approaching=approaching,
                        market_regime=regime,
                        user_id=recipient['user_id']
                    )
                    if success:
                        sent += 1

                logger.info(f"📧 Double signal alert sent to {sent}/{len(recipients)} recipients")
            else:
                logger.info(f"✅ No new double signals found")
                if approaching:
                    logger.info(f"   👀 {len(approaching)} stocks approaching trigger")

        except Exception as e:
            logger.error(f"❌ Double signal alert check failed: {e}")
            import traceback
            traceback.print_exc()

    async def send_daily_emails(self, target_emails: list = None):
        """
        Send daily summary emails to subscribers

        Runs at 6 PM ET (dinnertime) on trading days.
        Builds ensemble signals (same logic as dashboard) with freshness tracking.

        Args:
            target_emails: If provided, only send to these email addresses (bypasses freshness gate).
        """
        logger.info("📧 Starting daily email job...")

        try:
            # Check if this is a trading day
            now = datetime.now(ET)
            if not self._is_trading_day(now):
                logger.info("📅 Not a trading day, skipping emails")
                return

            # Freshness gate — HOLD emails if data is stale
            # Manual target_emails bypass allows admin testing with stale data
            if not target_emails and not await self._validate_data_freshness("daily_emails"):
                return

            # Read persisted signals from 4 PM scan (guaranteed same as dashboard)
            from app.services.ensemble_signal_service import ensemble_signal_service
            from app.core.database import async_session as email_session

            buy_signals = []
            async with email_session() as sig_db:
                db_signals = await ensemble_signal_service.get_signals_for_date(
                    sig_db, trading_today()
                )
                buy_signals = [
                    {
                        'symbol': s.symbol,
                        'price': s.price,
                        'pct_above_dwap': s.pct_above_dwap,
                        'is_strong': s.is_strong,
                        'momentum_rank': s.momentum_rank,
                        'ensemble_score': s.ensemble_score,
                        'dwap_crossover_date': s.dwap_crossover_date.isoformat() if s.dwap_crossover_date else None,
                        'ensemble_entry_date': s.ensemble_entry_date.isoformat() if s.ensemble_entry_date else None,
                        'days_since_crossover': s.days_since_crossover,
                        'days_since_entry': s.days_since_entry,
                        'is_fresh': s.is_fresh,
                    }
                    for s in db_signals
                ]

            # Fallback: if no persisted signals (first deploy, DB issue), regenerate
            if not buy_signals:
                logger.warning("📧 No persisted signals found, falling back to live scan")
                from app.api.signals import find_dwap_crossover_date, find_ensemble_entry_date, compute_signal_strength, get_signal_strength_label, compute_spy_trend

                # Compute regime-adjusted params for consistency
                regime_effective_params = None
                try:
                    from app.services.market_regime import market_regime_service, get_regime_adjusted_params
                    current_regime = market_regime_service.get_current_regime()
                    if current_regime:
                        regime_effective_params = get_regime_adjusted_params(current_regime)['effective']
                except Exception:
                    pass

                dwap_signals = await scanner_service.scan(refresh_data=False, apply_market_filter=True)
                dwap_by_symbol = {s.symbol: s for s in dwap_signals}
                momentum_rankings = scanner_service.rank_stocks_momentum(
                    apply_market_filter=True,
                    regime_params=regime_effective_params,
                )
                momentum_top_n = 30
                fresh_days = 5
                momentum_by_symbol = {
                    r.symbol: {'rank': i + 1, 'data': r}
                    for i, r in enumerate(momentum_rankings[:momentum_top_n])
                }
                threshold_rank = momentum_top_n // 2
                mom_threshold = momentum_rankings[threshold_rank - 1].composite_score if len(momentum_rankings) >= threshold_rank else 0
                spy_trend = compute_spy_trend()

                for symbol in dwap_by_symbol:
                    if symbol in momentum_by_symbol:
                        dwap = dwap_by_symbol[symbol]
                        mom = momentum_by_symbol[symbol]
                        mom_data = mom['data']
                        mom_rank = mom['rank']
                        crossover_date, days_since = find_dwap_crossover_date(symbol)
                        entry_date = None
                        days_since_entry = None
                        if crossover_date:
                            entry_date = find_ensemble_entry_date(symbol, crossover_date, mom_threshold)
                            if entry_date:
                                import pandas as pd
                                today_et = pd.Timestamp(trading_today())
                                entry_ts = pd.Timestamp(entry_date).normalize()
                                days_since_entry = (today_et - entry_ts).days
                        fresh_by_crossover = days_since is not None and days_since <= fresh_days
                        fresh_by_entry = days_since_entry is not None and days_since_entry <= fresh_days
                        is_fresh = fresh_by_crossover or fresh_by_entry
                        dwap_age = days_since if days_since is not None else 0
                        ensemble_score = compute_signal_strength(
                            volatility=mom_data.volatility,
                            spy_trend=spy_trend,
                            dwap_age=dwap_age,
                            dist_from_high=mom_data.dist_from_50d_high,
                            vol_ratio=dwap.volume_ratio,
                            momentum_score=mom_data.composite_score,
                        )
                        buy_signals.append({
                            'symbol': symbol,
                            'price': float(dwap.price),
                            'pct_above_dwap': float(dwap.pct_above_dwap),
                            'is_strong': bool(dwap.is_strong),
                            'momentum_rank': int(mom_rank),
                            'ensemble_score': round(float(ensemble_score), 1),
                            'signal_strength_label': get_signal_strength_label(ensemble_score),
                            'dwap_crossover_date': crossover_date,
                            'ensemble_entry_date': entry_date,
                            'days_since_crossover': int(days_since) if days_since is not None else None,
                            'days_since_entry': days_since_entry,
                            'is_fresh': bool(is_fresh),
                        })
                buy_signals.sort(key=lambda x: (
                    0 if x['is_fresh'] else 1,
                    x.get('days_since_crossover') or 999,
                    -x['ensemble_score']
                ))
            else:
                logger.info(f"📧 Using {len(buy_signals)} persisted signal(s) from 4 PM scan")

            # Read watchlist + regime + market_context from dashboard cache (same 4 PM data)
            watchlist = []
            regime = {'regime': 'range_bound', 'spy_price': 'N/A', 'vix_level': 'N/A'}
            market_context = None
            try:
                dashboard_data = data_export_service.read_dashboard_json()
                if dashboard_data:
                    watchlist = dashboard_data.get('watchlist', [])
                    market_context = dashboard_data.get('market_context')
                    regime_forecast = dashboard_data.get('regime_forecast')
                    market_stats = dashboard_data.get('market_stats', {})
                    if regime_forecast:
                        regime = {
                            'regime': regime_forecast.get('current_regime', 'range_bound'),
                            'spy_price': market_stats.get('spy_price', 'N/A'),
                            'vix_level': market_stats.get('vix_level', 'N/A'),
                        }
            except Exception as cache_err:
                logger.warning(f"📧 Could not read dashboard cache for watchlist/regime: {cache_err}")

            # Fallback: compute regime from live data if cache failed
            if regime.get('spy_price') == 'N/A':
                try:
                    from app.services.market_regime import market_regime_service
                    spy_df = scanner_service.data_cache.get('SPY')
                    vix_df = scanner_service.data_cache.get('^VIX')
                    if spy_df is not None and len(spy_df) >= 200:
                        regime_obj = market_regime_service.detect_regime(spy_df, scanner_service.data_cache, vix_df)
                        regime = {
                            'regime': regime_obj.regime_type.value,
                            'spy_price': round(float(spy_df['close'].iloc[-1]), 2),
                            'vix_level': round(float(vix_df['close'].iloc[-1]), 1) if vix_df is not None and len(vix_df) > 0 else 'N/A',
                        }
                except Exception:
                    pass

            # Query subscribers with valid subscriptions (trial or active)
            from app.core.database import async_session, User as DBUser, Subscription as DBSub
            from sqlalchemy import select
            from sqlalchemy.orm import selectinload

            target_set = {e.strip().lower() for e in target_emails} if target_emails else None

            async with async_session() as db:
                query = select(DBUser).options(selectinload(DBUser.subscription))
                # Admin target sends: don't filter by is_active (admin may not have active user record)
                if not target_set or not target_set.issubset(ADMIN_EMAILS):
                    query = query.where(DBUser.is_active == True)
                result = await db.execute(query)
                all_users = result.scalars().all()
                logger.warning(f"📧 Found {len(all_users)} users in DB" + (f", filtering for {target_set}" if target_set else ""))

            subscribers = []
            for u in all_users:
                email_lower = (u.email or '').lower()
                if target_set and email_lower not in target_set:
                    continue
                # Admin override: skip subscription/preference checks for admin target sends
                if target_set and email_lower in ADMIN_EMAILS:
                    subscribers.append({'email': u.email, 'name': u.name, 'user_id': str(u.id)})
                    continue
                if u.subscription and u.subscription.is_valid():
                    if not u.get_email_preference('daily_digest'):
                        continue
                    subscribers.append({'email': u.email, 'name': u.name, 'user_id': str(u.id)})

            fresh_count = len([s for s in buy_signals if s.get('is_fresh')])

            if not subscribers:
                logger.warning(
                    f"📧 No active subscribers. Would have sent email with "
                    f"{len(buy_signals)} ensemble signals ({fresh_count} fresh), "
                    f"{len(watchlist)} watchlist"
                )
                return

            logger.warning(f"📧 Sending daily summary to {len(subscribers)} subscriber(s): {[s['email'] for s in subscribers]}")

            # Send emails + push notifications to each subscriber
            sent = 0
            failed = 0
            push_sent = 0
            for sub in subscribers:
                try:
                    success = await email_service.send_daily_summary(
                        to_email=sub['email'],
                        signals=buy_signals,
                        market_regime=regime,
                        watchlist=watchlist,
                        user_id=sub['user_id'],
                        market_context=market_context,
                    )
                    if success:
                        sent += 1
                    else:
                        failed += 1
                except Exception as e:
                    logger.error(f"Failed to send to {sub['email']}: {e}")
                    failed += 1

                # Push notification (never blocks email delivery)
                try:
                    async with email_session() as push_db:
                        count = await push_notification_service.send_daily_summary_push(
                            push_db, sub['user_id'], len(buy_signals), fresh_count
                        )
                        push_sent += count
                except Exception as e:
                    logger.debug(f"Push notification failed for {sub['email']}: {e}")

            logger.info(f"📧 Daily emails complete: {sent}/{len(subscribers)} sent, {failed} failed, {push_sent} push")

        except Exception as e:
            logger.error(f"❌ Daily email job failed: {e}")

    async def _publish_scheduled_posts(self):
        """
        Check for scheduled posts ready to publish.
        Runs every 15 minutes.
        """
        try:
            from app.core.database import async_session
            from app.services.post_scheduler_service import post_scheduler_service

            async with async_session() as db:
                count = await post_scheduler_service.check_and_publish(db)
                if count:
                    logger.info(f"📣 Published {count} scheduled social post(s)")
        except Exception as e:
            logger.error(f"❌ Scheduled post publishing failed: {e}")

    async def _send_post_notifications(self):
        """
        Send T-24h and T-1h notifications for upcoming scheduled posts.
        Runs every hour.
        """
        try:
            from app.core.database import async_session
            from app.services.post_scheduler_service import post_scheduler_service

            async with async_session() as db:
                count = await post_scheduler_service.send_notifications(db)
                if count:
                    logger.info(f"📧 Sent {count} post notification(s)")
        except Exception as e:
            logger.error(f"❌ Post notification check failed: {e}")

    def stop(self):
        """Stop the scheduler"""
        if self.scheduler and self.is_running:
            self.scheduler.shutdown(wait=False)
            self.is_running = False
            logger.info("🛑 Scheduler stopped")

    def get_status(self) -> dict:
        """Get scheduler status"""
        status = {
            "is_running": self.is_running,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "last_run_status": self.last_run_status,
            "run_count": self.run_count,
            "next_runs": []
        }

        if self.scheduler and self.is_running:
            jobs = self.scheduler.get_jobs()
            status["next_runs"] = [
                {
                    "job_id": job.id,
                    "name": job.name,
                    "next_run": job.next_run_time.isoformat() if job.next_run_time else None
                }
                for job in jobs
            ]

        return status

    async def run_now(self):
        """Manually trigger the daily update (for testing)"""
        logger.info("🚀 Manual trigger: running daily update now")
        await self.daily_update()

    async def _export_dashboard_cache(self):
        """
        Pre-compute shared dashboard data and export to S3 for CDN delivery.

        Called after scans and nightly walk-forward so the frontend
        can load dashboard data instantly from CDN.
        """
        try:
            from app.core.database import async_session
            from app.api.signals import compute_shared_dashboard_data

            async with async_session() as db:
                logger.info("📦 Computing shared dashboard data for S3 cache...")
                data = await compute_shared_dashboard_data(db)
                result = data_export_service.export_dashboard_json(data)
                if result.get("success"):
                    logger.info(f"✅ Dashboard cache exported to {result.get('storage', 'storage')}")
                    # Also save a date-keyed snapshot for time-travel
                    today_str = trading_today().isoformat()
                    snap_result = data_export_service.export_snapshot(today_str, data)
                    if snap_result.get("success"):
                        logger.info(f"✅ Snapshot saved for {today_str}")
                    else:
                        logger.warning(f"⚠️ Snapshot export failed: {snap_result.get('message', 'unknown')}")
                else:
                    logger.warning(f"⚠️ Dashboard cache export failed: {result.get('message', 'unknown')}")
        except Exception as e:
            logger.error(f"❌ Dashboard cache export failed: {e}")
            import traceback
            traceback.print_exc()

    async def send_onboarding_drip_emails(self, target_emails: list = None):
        """
        Daily check: send next onboarding email based on signup age.

        Schedule: {1: day 1, 2: day 3, 3: day 5, 4: day 6, 5: day 8}
        Skips: fully unsubscribed users, admins, already-converted (steps 3-5).

        Args:
            target_emails: If provided, only process these email addresses.
        """
        logger.info("📧 Starting onboarding drip check...")

        try:
            from app.core.database import async_session, User as DBUser, Subscription as DBSub
            from sqlalchemy import select
            from sqlalchemy.orm import selectinload

            step_schedule = {1: 1, 2: 3, 3: 5, 4: 6, 5: 8}

            async with async_session() as db:
                query = (
                    select(DBUser)
                    .options(selectinload(DBUser.subscription))
                    .where(DBUser.is_active == True)
                )
                if target_emails:
                    normalized = [e.strip().lower() for e in target_emails]
                    query = query.where(DBUser.email.in_(normalized))
                result = await db.execute(query)
                users = result.scalars().all()

                sent = 0
                skipped = 0

                for user in users:
                    # Skip admins
                    if user.is_admin():
                        continue

                    # Skip if already completed all steps
                    current_step = user.onboarding_step or 0
                    if current_step >= 5:
                        continue

                    # Skip if fully unsubscribed (all prefs false)
                    prefs = user.email_preferences or {}
                    if prefs and all(v is False for v in prefs.values()):
                        skipped += 1
                        continue

                    # Calculate days since signup
                    if not user.created_at:
                        continue
                    days_since = days_since_et(user.created_at)

                    # Find the highest eligible step
                    next_step = None
                    for step, required_days in sorted(step_schedule.items()):
                        if days_since >= required_days and step > current_step:
                            next_step = step

                    if next_step is None:
                        continue

                    # For steps 3-5 (trial urgency / win-back): skip if already converted
                    if next_step >= 3:
                        sub = user.subscription
                        if sub and sub.status == "active":
                            skipped += 1
                            continue

                    # Send the email
                    try:
                        success = await email_service.send_onboarding_email(
                            step=next_step,
                            to_email=user.email,
                            name=user.name or "",
                            user_id=str(user.id),
                        )
                        if success:
                            user.onboarding_step = next_step
                            sent += 1
                            logger.info(f"📧 Onboarding step {next_step} sent to {user.email}")
                        else:
                            logger.warning(f"📧 Onboarding step {next_step} failed for {user.email}")
                    except Exception as e:
                        logger.error(f"📧 Onboarding email error for {user.email}: {e}")

                    # Rate limiting
                    await asyncio.sleep(0.5)

                await db.commit()

                logger.info(f"📧 Onboarding drip complete: {sent} sent, {skipped} skipped")
                return {"sent": sent, "skipped": skipped}

        except Exception as e:
            logger.error(f"❌ Onboarding drip failed: {e}")
            import traceback
            traceback.print_exc()
            return {"sent": 0, "error": str(e)}

    async def _scan_reply_opportunities(self):
        """
        Scan followed accounts for tweets mentioning stocks we've traded.
        Generate contextual reply drafts for admin review.

        Runs every 4 hours at :15 past the hour.
        """
        try:
            from app.core.database import async_session
            from app.services.reply_scanner_service import reply_scanner_service

            async with async_session() as db:
                result = await reply_scanner_service.scan_and_generate(db, since_hours=4)
                if result.get("replies_created"):
                    logger.info(f"🔁 Reply scanner: {result['replies_created']} draft(s) created")
                else:
                    logger.info(f"🔁 Reply scanner: no reply opportunities found "
                               f"({result.get('tweets_found', 0)} tweets scanned)")
        except Exception as e:
            logger.error(f"❌ Reply scanner failed: {e}")

    async def _scan_instagram_comments(self):
        """
        Scan Instagram comments on our posts and generate reply drafts.

        Runs every 4 hours at :30 past the hour.
        """
        try:
            from app.core.database import async_session
            from app.services.instagram_comment_service import instagram_comment_service

            async with async_session() as db:
                result = await instagram_comment_service.scan_and_reply(db, since_hours=4)
                if result.get("replies_created"):
                    logger.info(f"💬 IG comment scanner: {result['replies_created']} reply draft(s) created")
                else:
                    logger.info(f"💬 IG comment scanner: no new comments to reply to "
                               f"({result.get('comments_found', 0)} comments checked)")
        except Exception as e:
            logger.error(f"❌ Instagram comment scanner failed: {e}")

    async def _refresh_threads_token(self):
        """
        Refresh the Threads long-lived access token weekly.

        Long-lived tokens expire after 60 days. Refreshing weekly ensures
        we never get close to expiry.
        """
        try:
            from app.services.social_posting_service import social_posting_service

            result = await social_posting_service.refresh_threads_token()
            if result.get("success"):
                days = result.get("expires_in", 0) // 86400
                logger.info(f"🔑 Threads token refreshed — expires in {days} days")
                if result.get("warning"):
                    logger.warning(f"⚠️ {result['warning']}")
            else:
                logger.error(f"🔑 Threads token refresh failed: {result.get('error')}")
                # Send admin alert
                try:
                    await admin_email_service.send_admin_alert(
                        to_email=ADMIN_EMAIL,
                        subject="Threads Token Refresh Failed",
                        message=f"Automatic Threads token refresh failed: {result.get('error')}\n\n"
                                "Please manually refresh at: https://developers.facebook.com",
                    )
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"❌ Threads token refresh job failed: {e}")

    async def _strategy_auto_analysis(self):
        """
        Biweekly strategy analysis and potential auto-switch.

        This job runs every other Friday to:
        1. Analyze all strategies with 90-day rolling backtest
        2. Check if a switch is recommended
        3. Execute switch if safeguards pass and auto-switch is enabled
        4. Send email notifications
        """
        logger.info("📊 Starting biweekly strategy auto-analysis...")

        try:
            from app.services.auto_switch_service import auto_switch_service
            await auto_switch_service.scheduled_analysis_job()
            logger.info("✅ Strategy auto-analysis complete")
        except Exception as e:
            logger.error(f"❌ Strategy auto-analysis failed: {e}")
            import traceback
            traceback.print_exc()

    async def _send_email_failure_report(self):
        """Send nightly admin report of any email delivery failures."""
        failures = get_email_failures()
        if not failures:
            logger.info("No email failures to report")
            return

        logger.info(f"Sending email failure report: {len(failures)} failures")
        for admin in ADMIN_EMAILS:
            try:
                await admin_email_service.send_email_failure_report(admin, failures)
            except Exception as e:
                logger.error(f"Failed to send failure report to {admin}: {e}")
        clear_email_failures()


    async def _send_weekly_regime_report(self):
        """
        Send the weekly market regime report to all active email subscribers
        and paid users with regime_report preference enabled.
        """
        from app.core.database import async_session, EmailSubscriber, User, Subscription
        from app.services.regime_forecast_service import regime_forecast_service
        from sqlalchemy import select

        logger.info("📊 Starting weekly regime report send...")

        # Freshness gate — relaxed: Friday's data is fine for Monday report
        if not await self._validate_regime_report_freshness():
            return
        sent_count = 0
        error_count = 0

        try:
            async with async_session() as db:
                # Get 30-day regime history
                history = await regime_forecast_service.get_forecast_history(db, days=30)
                if not history:
                    logger.warning("No regime history available — skipping regime report")
                    return

                # 1. Send to free email subscribers
                result = await db.execute(
                    select(EmailSubscriber).where(EmailSubscriber.is_active == True)
                )
                subscribers = result.scalars().all()

                for sub in subscribers:
                    try:
                        html = email_service.generate_regime_report_html(
                            history=history, subscriber_id=sub.id
                        )
                        success = await email_service.send_weekly_regime_report(
                            to_email=sub.email, html=html, subscriber_id=sub.id
                        )
                        if success:
                            sent_count += 1
                        else:
                            error_count += 1
                    except Exception as e:
                        logger.error(f"Failed regime report to subscriber {sub.email}: {e}")
                        error_count += 1

                # 2. Send to paid users with regime_report pref enabled
                result = await db.execute(
                    select(User).join(Subscription, Subscription.user_id == User.id).where(
                        Subscription.status.in_(["active", "trial"]),
                        User.is_active == True,
                    )
                )
                users = result.scalars().all()

                # Exclude users already in subscriber list
                subscriber_emails = {s.email.lower() for s in subscribers}

                for user in users:
                    if user.email.lower() in subscriber_emails:
                        continue
                    if not user.get_email_preference("regime_report"):
                        continue
                    try:
                        html = email_service.generate_regime_report_html(
                            history=history, user_id=str(user.id)
                        )
                        success = await email_service.send_weekly_regime_report(
                            to_email=user.email, html=html, user_id=str(user.id)
                        )
                        if success:
                            sent_count += 1
                        else:
                            error_count += 1
                    except Exception as e:
                        logger.error(f"Failed regime report to user {user.email}: {e}")
                        error_count += 1

        except Exception as e:
            logger.error(f"Weekly regime report failed: {e}")
            import traceback
            traceback.print_exc()

        logger.info(f"📊 Weekly regime report complete: {sent_count} sent, {error_count} errors")


# Singleton instance
scheduler_service = SchedulerService()
