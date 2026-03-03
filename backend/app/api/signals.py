"""
Signals API - Trading signal endpoints
"""

import os

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

from app.core.database import get_db, Signal, Position, User, EmailSubscriber
from app.core.security import get_current_user_optional, get_admin_user, require_valid_subscription
from app.services.scanner import scanner_service, SignalData
from app.services.stock_universe import stock_universe_service
from app.services.data_export import data_export_service

router = APIRouter()
public_router = APIRouter()


# ============================================================================
# "What If You Followed Us" — Subscriber-facing calculator
# ============================================================================

@router.get("/what-if")
async def subscriber_what_if(
    capital: float = 10000,
    user: User = Depends(require_valid_subscription),
    db: AsyncSession = Depends(get_db),
):
    """Calculate personalized returns from user's signup date."""
    from app.services.model_portfolio_service import model_portfolio_service

    if not user.created_at:
        return {"error": "No signup date found"}

    start_date = user.created_at.strftime("%Y-%m-%d")
    return await model_portfolio_service.calculate_what_if(db, start_date, capital)


# Pydantic models for API
class SignalResponse(BaseModel):
    id: Optional[int] = None
    symbol: str
    signal_type: str
    price: float
    dwap: float
    pct_above_dwap: float
    volume: int
    volume_ratio: float
    stop_loss: float
    profit_target: float
    ma_50: float = 0.0
    ma_200: float = 0.0
    high_52w: float = 0.0
    is_strong: bool
    signal_strength: float = 0.0
    sector: str = ""
    recommendation: str = ""
    timestamp: str

    class Config:
        from_attributes = True


class ScanResponse(BaseModel):
    timestamp: str
    total_signals: int
    strong_signals: int
    signals: List[SignalResponse]


class WatchlistItem(BaseModel):
    symbol: str
    price: float
    dwap: float
    pct_above_dwap: float


# Endpoints
@router.get("/scan", response_model=ScanResponse)
async def run_scan(
    refresh: bool = True,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_valid_subscription),
):
    """
    Run market scan for buy signals
    
    - **refresh**: If true, fetch fresh data from Yahoo Finance
    """
    try:
        signals = await scanner_service.scan(refresh_data=refresh)
        
        # Store signals in database
        for sig in signals:
            db_signal = Signal(
                symbol=sig.symbol,
                signal_type=sig.signal_type,
                price=sig.price,
                dwap=sig.dwap,
                pct_above_dwap=sig.pct_above_dwap,
                volume=sig.volume,
                volume_ratio=sig.volume_ratio,
                stop_loss=sig.stop_loss,
                profit_target=sig.profit_target,
                is_strong=sig.is_strong,
                status="active"
            )
            db.add(db_signal)
        
        await db.commit()
        
        return ScanResponse(
            timestamp=datetime.now().isoformat(),
            total_signals=len(signals),
            strong_signals=len([s for s in signals if s.is_strong]),
            signals=[SignalResponse(**s.to_dict()) for s in signals]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/latest", response_model=ScanResponse)
async def get_latest_signals(
    limit: int = 20,
    strong_only: bool = False,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_valid_subscription),
):
    """
    Get latest signals from database
    
    - **limit**: Maximum number of signals to return
    - **strong_only**: If true, only return strong signals
    """
    query = select(Signal).order_by(desc(Signal.created_at)).limit(limit)
    
    if strong_only:
        query = query.where(Signal.is_strong == True)
    
    result = await db.execute(query)
    signals = result.scalars().all()
    
    return ScanResponse(
        timestamp=datetime.now().isoformat(),
        total_signals=len(signals),
        strong_signals=len([s for s in signals if s.is_strong]),
        signals=[SignalResponse(
            id=s.id,
            symbol=s.symbol,
            signal_type=s.signal_type,
            price=s.price,
            dwap=s.dwap,
            pct_above_dwap=s.pct_above_dwap,
            volume=int(s.volume),
            volume_ratio=s.volume_ratio,
            stop_loss=s.stop_loss,
            profit_target=s.profit_target,
            is_strong=s.is_strong,
            timestamp=s.created_at.isoformat()
        ) for s in signals]
    )


@router.get("/watchlist", response_model=List[WatchlistItem])
async def get_watchlist(threshold: float = 3.0, user: User = Depends(require_valid_subscription)):
    """
    Get stocks approaching DWAP threshold (watchlist)

    - **threshold**: Minimum % above DWAP to include
    """
    watchlist = scanner_service.get_watchlist(threshold)
    return [WatchlistItem(**item) for item in watchlist]


@router.get("/memory-scan", response_model=ScanResponse)
async def run_memory_scan(
    refresh: bool = False,
    apply_market_filter: bool = True,
    min_strength: float = 0,
    export_to_cdn: bool = True,
    admin: User = Depends(get_admin_user),
):
    """
    Run market scan without database (memory only).
    Worker Lambda only — requires pickle data that exceeds API Lambda memory.
    """
    if os.environ.get("LAMBDA_ROLE") == "api":
        raise HTTPException(
            status_code=400,
            detail="memory-scan requires the worker Lambda. Use the worker invoke or wait for the daily scan.",
        )
    try:
        signals = await scanner_service.scan(
            refresh_data=refresh,
            apply_market_filter=apply_market_filter,
            min_signal_strength=min_strength
        )

        # Export signals to S3 for CDN delivery
        if export_to_cdn and signals:
            data_export_service.export_signals_json(signals)

        return ScanResponse(
            timestamp=datetime.now().isoformat(),
            total_signals=len(signals),
            strong_signals=len([s for s in signals if s.is_strong]),
            signals=[SignalResponse(**s.to_dict()) for s in signals]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/cdn-url")
async def get_signals_cdn_url(admin: User = Depends(get_admin_user)):
    """
    Get the CDN URL for the latest signals JSON.

    Frontend should fetch signals from this URL for instant loading.
    """
    return {
        "url": data_export_service.get_signals_url(),
        "cache_max_age": 300,  # 5 minutes
        "description": "Fetch signals from this URL for instant loading"
    }


@router.get("/symbol/{symbol}", response_model=SignalResponse)
async def get_signal_for_symbol(symbol: str, user: User = Depends(require_valid_subscription)):
    """
    Get current signal analysis for a specific symbol
    """
    if symbol.upper() not in scanner_service.data_cache:
        # Try to fetch data
        await scanner_service.fetch_data([symbol.upper()])

    signal = scanner_service.analyze_stock(symbol.upper())

    if not signal:
        raise HTTPException(status_code=404, detail=f"No signal for {symbol}")

    return SignalResponse(**signal.to_dict())


class MissedOpportunity(BaseModel):
    symbol: str
    entry_date: str
    entry_price: float
    sell_date: str  # When it hit +20% profit target
    sell_price: float
    would_be_return: float
    would_be_pnl: float
    days_held: int = 0
    sector: str = ""


@router.get("/missed", response_model=List[MissedOpportunity])
async def get_missed_opportunities(
    days: int = 90,
    limit: int = 10,
    user: User = Depends(require_valid_subscription),
    db: AsyncSession = Depends(get_db),
):
    """
    Get missed opportunities - profitable trades from a backtest of the past N days.
    Shows what returns users could have achieved using our momentum strategy.

    - **days**: Look back period (default 90 days)
    - **limit**: Maximum results to return (default 10)
    """
    from app.services.backtester import backtester_service

    # Run backtest for the specified period
    try:
        result = backtester_service.run_backtest(
            lookback_days=days,
            use_momentum_strategy=True
        )
    except Exception as e:
        print(f"[MISSED] Backtest failed: {e}")
        return []

    # Filter to only profitable closed trades (winners)
    opportunities = []
    for trade in result.trades:
        # Only show profitable trades
        if trade.pnl_pct <= 0:
            continue

        # Get sector info
        sector = ""
        info = stock_universe_service.symbol_info.get(trade.symbol, {})
        sector = info.get("sector", "")

        opportunities.append(MissedOpportunity(
            symbol=trade.symbol,
            entry_date=trade.entry_date,
            entry_price=round(trade.entry_price, 2),
            sell_date=trade.exit_date,
            sell_price=round(trade.exit_price, 2),
            would_be_return=round(trade.pnl_pct, 1),
            would_be_pnl=round(trade.pnl, 2),
            days_held=trade.days_held,
            sector=sector
        ))

    # Sort by highest return first (most impressive opportunities)
    opportunities.sort(key=lambda x: x.would_be_return, reverse=True)
    return opportunities[:limit]


@router.post("/backfill")
async def backfill_historical_signals(
    days: int = 90,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Backfill historical signals by scanning past price data.

    This simulates what signals would have been generated over the past N days.
    Used to populate the "missed opportunities" section.

    - **days**: How many days back to scan (default 90)
    """
    import pandas as pd
    import numpy as np
    from datetime import timedelta
    from app.core.config import settings

    if not scanner_service.data_cache:
        raise HTTPException(status_code=400, detail="No price data loaded")

    # Settings for signal detection
    DWAP_THRESHOLD = settings.DWAP_THRESHOLD_PCT / 100  # 5%
    MIN_VOLUME = settings.MIN_VOLUME
    MIN_PRICE = settings.MIN_PRICE
    VOLUME_SPIKE = settings.VOLUME_SPIKE_MULT
    STOP_LOSS_PCT = settings.STOP_LOSS_PCT
    PROFIT_TARGET_PCT = settings.PROFIT_TARGET_PCT

    # Date range to scan
    end_date = datetime.now() - timedelta(days=1)  # Yesterday
    start_date = end_date - timedelta(days=days)

    signals_created = 0
    days_scanned = 0

    # Get trading days from one of the symbols
    sample_symbol = list(scanner_service.data_cache.keys())[0]
    sample_df = scanner_service.data_cache[sample_symbol]

    # Filter to our date range - normalize dates for comparison
    start_ts = pd.Timestamp(start_date).normalize()
    end_ts = pd.Timestamp(end_date).normalize()

    trading_days = [
        d for d in sample_df.index
        if start_ts <= pd.Timestamp(d).normalize() <= end_ts
    ]

    # Process each trading day
    for trade_date in trading_days:
        days_scanned += 1
        trade_date_normalized = pd.Timestamp(trade_date).normalize()

        # Check each symbol for signals on this date
        for symbol, df in scanner_service.data_cache.items():
            try:
                # Find the closest date in this symbol's data
                date_matches = [d for d in df.index if pd.Timestamp(d).normalize() == trade_date_normalized]
                if not date_matches:
                    continue

                actual_date = date_matches[0]
                idx = df.index.get_loc(actual_date)
                if idx < 200:  # Need enough history for DWAP
                    continue

                row = df.loc[actual_date]
                price = row['close']
                volume = row['volume']
                dwap = row.get('dwap', np.nan)
                vol_avg = row.get('vol_avg', np.nan)
                ma_50 = row.get('ma_50', np.nan)
                ma_200 = row.get('ma_200', np.nan)

                if pd.isna(dwap) or dwap <= 0:
                    continue

                pct_above_dwap = (price / dwap - 1)

                # Check buy conditions
                if (pct_above_dwap >= DWAP_THRESHOLD and
                    volume >= MIN_VOLUME and
                    price >= MIN_PRICE):

                    vol_ratio = volume / vol_avg if vol_avg and vol_avg > 0 else 0

                    # Strong signal check
                    is_strong = (
                        vol_ratio >= VOLUME_SPIKE and
                        not pd.isna(ma_50) and not pd.isna(ma_200) and
                        price > ma_50 > ma_200
                    )

                    # Check if signal already exists for this symbol on this date
                    check_start = trade_date_normalized.to_pydatetime()
                    check_end = check_start + timedelta(days=1)
                    existing = await db.execute(
                        select(Signal).where(
                            Signal.symbol == symbol,
                            Signal.created_at >= check_start,
                            Signal.created_at < check_end
                        )
                    )
                    if existing.scalar_one_or_none():
                        continue  # Already have this signal

                    # Create the signal
                    stop_loss = price * (1 - STOP_LOSS_PCT / 100)
                    profit_target = price * (1 + PROFIT_TARGET_PCT / 100)

                    signal = Signal(
                        symbol=symbol,
                        signal_type='BUY',
                        price=round(float(price), 2),
                        dwap=round(float(dwap), 2),
                        pct_above_dwap=round(float(pct_above_dwap) * 100, 1),
                        volume=int(volume),
                        volume_ratio=round(float(vol_ratio), 2),
                        stop_loss=round(float(stop_loss), 2),
                        profit_target=round(float(profit_target), 2),
                        is_strong=bool(is_strong),
                        status='historical'
                    )
                    # Set created_at to the historical date
                    signal.created_at = trade_date_normalized.to_pydatetime()

                    db.add(signal)
                    signals_created += 1

            except Exception as e:
                continue  # Skip symbols with issues

        # Commit in batches
        if days_scanned % 10 == 0:
            await db.commit()

    # Final commit
    await db.commit()

    return {
        "success": True,
        "days_scanned": days_scanned,
        "signals_created": signals_created,
        "date_range": {
            "start": start_date.strftime('%Y-%m-%d'),
            "end": end_date.strftime('%Y-%m-%d')
        }
    }


@router.get("/info/{symbol}")
async def get_stock_info(symbol: str, user: User = Depends(require_valid_subscription)):
    """
    Get company information for a stock symbol

    Returns name, sector, industry, description, market cap, etc.
    Fetches from yfinance if sector/description not already cached.
    """
    symbol = symbol.upper()

    # Load cache if needed
    if not stock_universe_service.symbol_info:
        stock_universe_service._load_from_cache()

    # Get basic info from cache
    info = stock_universe_service.symbol_info.get(symbol, {})

    # Fetch detailed info (sector, description) from yfinance if not cached
    if not info.get('sector') or not info.get('description'):
        try:
            info = await stock_universe_service.fetch_company_details(symbol)
        except Exception:
            pass  # Use whatever info we have

    # Get current price and technical data if available
    current_data = {}
    if symbol in scanner_service.data_cache:
        df = scanner_service.data_cache[symbol]
        if len(df) > 0:
            import pandas as pd
            row = df.iloc[-1]
            current_data = {
                "current_price": round(float(row['close']), 2),
                "dwap": round(float(row['dwap']), 2) if pd.notna(row.get('dwap')) else None,
                "ma_50": round(float(row['ma_50']), 2) if pd.notna(row.get('ma_50')) else None,
                "ma_200": round(float(row['ma_200']), 2) if pd.notna(row.get('ma_200')) else None,
                "high_52w": round(float(row['high_52w']), 2) if pd.notna(row.get('high_52w')) else None,
                "volume": int(row['volume']) if pd.notna(row.get('volume')) else 0,
                "avg_volume": int(row['vol_avg']) if pd.notna(row.get('vol_avg')) else None,
            }

    return {
        "symbol": symbol,
        "name": info.get("name", symbol),
        "sector": info.get("sector", ""),
        "industry": info.get("industry", ""),
        "description": info.get("description", ""),
        "market_cap": info.get("market_cap", ""),
        "exchange": info.get("exchange", ""),
        "website": info.get("website", ""),
        "employees": info.get("employees"),
        **current_data
    }


class DashboardResponse(BaseModel):
    """Unified dashboard response — one call, everything the frontend needs."""
    regime_forecast: Optional[dict] = None
    buy_signals: List[dict] = []
    positions_with_guidance: List[dict] = []
    watchlist: List[dict] = []
    market_stats: dict = {}
    recent_signals: List[dict] = []
    missed_opportunities: List[dict] = []
    generated_at: str


async def compute_shared_dashboard_data(db: AsyncSession, momentum_top_n: int = 30, fresh_days: int = 5) -> dict:
    """
    Compute the shared (non-user-specific) dashboard data.

    This is called by the scheduler to pre-compute and cache to S3,
    and as a fallback when the S3 cache is missing.

    Returns dict with: regime_forecast, buy_signals, watchlist,
    market_stats, missed_opportunities, recent_signals.
    """
    from app.core.config import settings
    from app.services.market_regime import market_regime_service
    import pandas as pd

    if not scanner_service.data_cache:
        return {'error': 'Price data not loaded', 'generated_at': datetime.now().isoformat()}

    # --- Regime forecast ---
    regime_forecast_data = None
    regime_forecast_obj = None
    try:
        spy_df = scanner_service.data_cache.get('SPY')
        vix_df = scanner_service.data_cache.get('^VIX')
        if spy_df is not None and len(spy_df) >= 200:
            regime_forecast_obj = market_regime_service.predict_transitions(
                spy_df=spy_df,
                universe_dfs=scanner_service.data_cache,
                vix_df=vix_df,
            )
            regime_forecast_data = regime_forecast_obj.to_dict()
    except Exception as e:
        import traceback
        print(f"Regime forecast error: {e}")
        traceback.print_exc()

    # --- Buy signals + Watchlist (single momentum ranking call) ---
    buy_signals = []
    watchlist = []
    try:
        dwap_signals = await scanner_service.scan(refresh_data=False, apply_market_filter=True)
        dwap_by_symbol = {s.symbol: s for s in dwap_signals}

        # Single momentum ranking call — reused for both buy signals and watchlist
        momentum_rankings = scanner_service.rank_stocks_momentum(apply_market_filter=True)
        momentum_by_symbol = {
            r.symbol: {'rank': i + 1, 'data': r}
            for i, r in enumerate(momentum_rankings[:momentum_top_n])
        }

        # Threshold for ensemble entry date
        threshold_rank = momentum_top_n // 2
        mom_threshold = momentum_rankings[threshold_rank - 1].composite_score if len(momentum_rankings) >= threshold_rank else 0

        # Compute SPY trend once for all signals
        spy_trend = compute_spy_trend()

        # Build buy signals (ensemble)
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
                        from app.core.timezone import trading_today
                        today_et = pd.Timestamp(trading_today())
                        entry_ts = pd.Timestamp(entry_date).normalize()
                        days_since_entry = (today_et - entry_ts).days

                fresh_by_crossover = days_since is not None and days_since <= fresh_days
                fresh_by_entry = days_since_entry is not None and days_since_entry <= fresh_days
                is_fresh = fresh_by_crossover or fresh_by_entry

                # Signal strength score (data-backed, replaces old ensemble_score)
                dwap_age = days_since if days_since is not None else 0
                ensemble_score = compute_signal_strength(
                    volatility=mom_data.volatility,
                    spy_trend=spy_trend,
                    dwap_age=dwap_age,
                    dist_from_high=mom_data.dist_from_50d_high,
                    vol_ratio=dwap.volume_ratio,
                    momentum_score=mom_data.composite_score,
                )

                info = stock_universe_service.symbol_info.get(symbol, {})
                sector = info.get('sector', '')

                buy_signals.append({
                    'symbol': symbol,
                    'price': float(dwap.price),
                    'dwap': float(dwap.dwap),
                    'pct_above_dwap': float(dwap.pct_above_dwap),
                    'volume': int(dwap.volume),
                    'volume_ratio': float(dwap.volume_ratio),
                    'is_strong': bool(dwap.is_strong),
                    'momentum_rank': int(mom_rank),
                    'momentum_score': round(float(mom_data.composite_score), 2),
                    'short_momentum': round(float(mom_data.short_momentum), 2),
                    'long_momentum': round(float(mom_data.long_momentum), 2),
                    'ensemble_score': round(float(ensemble_score), 1),
                    'signal_strength_label': get_signal_strength_label(ensemble_score),
                    'dwap_crossover_date': crossover_date,
                    'ensemble_entry_date': entry_date,
                    'days_since_crossover': int(days_since) if days_since is not None else None,
                    'days_since_entry': int(days_since_entry) if days_since_entry is not None else None,
                    'is_fresh': bool(is_fresh),
                    'sector': sector,
                })

        buy_signals.sort(key=lambda x: (
            0 if (x.get('days_since_entry') or 999) == 0 else 1,  # BUY NOW first
            0 if x['is_fresh'] else 1,
            x.get('days_since_entry') if x.get('days_since_entry') is not None else 999,
            -x['ensemble_score']
        ))

        # Enrich signals with missing sector data from yfinance
        missing_sector_symbols = [s['symbol'] for s in buy_signals if not s.get('sector')]
        if missing_sector_symbols:
            import yfinance as yf
            for symbol in missing_sector_symbols:
                try:
                    ticker = yf.Ticker(symbol)
                    info = ticker.info or {}
                    sector = info.get('sector', '')
                    if sector:
                        # Update signal and universe cache
                        for s in buy_signals:
                            if s['symbol'] == symbol:
                                s['sector'] = sector
                        if symbol in stock_universe_service.symbol_info:
                            stock_universe_service.symbol_info[symbol]['sector'] = sector
                except Exception:
                    pass

        # Build watchlist from same momentum rankings (no second call)
        for symbol, mom in momentum_by_symbol.items():
            df = scanner_service.data_cache.get(symbol)
            if df is None or len(df) < 1:
                continue

            row = df.iloc[-1]
            price = row['close']
            dwap_val = row.get('dwap')

            if pd.isna(dwap_val) or dwap_val <= 0:
                continue

            pct_above = (price / dwap_val - 1) * 100

            if 3.0 <= pct_above < 5.0:
                mom_data = mom['data']
                info = stock_universe_service.symbol_info.get(symbol, {})
                watchlist.append({
                    'symbol': symbol,
                    'price': round(float(price), 2),
                    'dwap': round(float(dwap_val), 2),
                    'pct_above_dwap': round(float(pct_above), 2),
                    'distance_to_trigger': round(float(5.0 - pct_above), 2),
                    'momentum_rank': int(mom['rank']),
                    'momentum_score': round(float(mom_data.composite_score), 2),
                    'sector': info.get('sector', ''),
                })

        watchlist.sort(key=lambda x: x['distance_to_trigger'])
        watchlist = watchlist[:5]
    except Exception as e:
        print(f"Buy signals/watchlist error: {e}")

    # --- Market stats ---
    market_stats = {}
    try:
        spy_df = scanner_service.data_cache.get('SPY')
        vix_df = scanner_service.data_cache.get('^VIX')
        if spy_df is not None and len(spy_df) > 0:
            market_stats['spy_price'] = round(float(spy_df.iloc[-1]['close']), 2)
            if len(spy_df) >= 2:
                prev_close = float(spy_df.iloc[-2]['close'])
                if prev_close > 0:
                    market_stats['spy_change_pct'] = round((market_stats['spy_price'] / prev_close - 1) * 100, 2)
        if vix_df is not None and len(vix_df) > 0:
            market_stats['vix_level'] = round(float(vix_df.iloc[-1]['close']), 2)
        if regime_forecast_data:
            market_stats['regime_name'] = regime_forecast_data.get('current_regime_name', '')
            market_stats['regime'] = regime_forecast_data.get('current_regime', '')
        market_stats['signal_count'] = len(buy_signals)
        market_stats['fresh_count'] = len([s for s in buy_signals if s.get('is_fresh')])
    except Exception as e:
        print(f"Market stats error: {e}")

    # --- Missed opportunities ---
    missed_opportunities = []
    TRAILING_STOP_PCT = 0.12
    try:
        from app.core.database import WalkForwardSimulation
        import json as _json

        nightly_result = await db.execute(
            select(WalkForwardSimulation)
            .where(WalkForwardSimulation.is_nightly_missed_opps == True)
            .where(WalkForwardSimulation.status == "completed")
            .order_by(desc(WalkForwardSimulation.simulation_date))
            .limit(1)
        )
        nightly_sim = nightly_result.scalar_one_or_none()

        if nightly_sim and nightly_sim.trades_json:
            trades = _json.loads(nightly_sim.trades_json)

            for trade in trades:
                symbol = trade.get('symbol', '')
                exit_reason = trade.get('exit_reason', '')
                entry_price = float(trade.get('entry_price', 0))
                entry_date_str = str(trade.get('entry_date', ''))[:10]

                if exit_reason == 'rebalance_exit':
                    df = scanner_service.data_cache.get(symbol)
                    if df is None or len(df) < 50 or entry_price <= 0:
                        continue

                    entry_ts = pd.Timestamp(entry_date_str)
                    if hasattr(df.index, 'tz') and df.index.tz is not None and entry_ts.tz is None:
                        entry_ts = entry_ts.tz_localize(df.index.tz)
                    mask = df.index >= entry_ts
                    if not mask.any():
                        continue
                    post_entry = df.loc[mask]

                    high_water = entry_price
                    sell_price = None
                    sell_date = None
                    for idx, row in post_entry.iterrows():
                        price_j = float(row['close'])
                        high_water = max(high_water, price_j)
                        trailing_stop = high_water * (1 - TRAILING_STOP_PCT)
                        if price_j <= trailing_stop:
                            sell_price = price_j
                            sell_date = idx
                            break

                    if sell_price is None:
                        current_price = float(post_entry.iloc[-1]['close'])
                        pnl_pct = (current_price / entry_price - 1) * 100
                        if pnl_pct <= 5.0:
                            continue
                        last_date = post_entry.index[-1]
                        days_held = (last_date - entry_ts).days
                        missed_opportunities.append({
                            'symbol': symbol,
                            'entry_date': entry_date_str,
                            'entry_price': round(entry_price, 2),
                            'sell_date': last_date.strftime('%Y-%m-%d') if hasattr(last_date, 'strftime') else str(last_date)[:10],
                            'sell_price': round(current_price, 2),
                            'would_be_return': round(pnl_pct, 1),
                            'would_be_pnl': round((current_price - entry_price) * 100, 0),
                            'days_held': int(days_held),
                            'strategy_name': trade.get('strategy_name', 'Ensemble'),
                            'exit_reason': 'still_open',
                        })
                        continue

                    pnl_pct = (sell_price / entry_price - 1) * 100
                    if pnl_pct <= 5.0:
                        continue

                    days_held = (sell_date - entry_ts).days

                    missed_opportunities.append({
                        'symbol': symbol,
                        'entry_date': entry_date_str,
                        'entry_price': round(entry_price, 2),
                        'sell_date': sell_date.strftime('%Y-%m-%d') if hasattr(sell_date, 'strftime') else str(sell_date)[:10],
                        'sell_price': round(sell_price, 2),
                        'would_be_return': round(pnl_pct, 1),
                        'would_be_pnl': round((sell_price - entry_price) * 100, 0),
                        'days_held': int(days_held),
                        'strategy_name': trade.get('strategy_name', 'Ensemble'),
                        'exit_reason': 'trailing_stop',
                    })
                else:
                    pnl_pct = trade.get('pnl_pct', 0)
                    if pnl_pct <= 5.0:
                        continue

                    exit_date = trade.get('exit_date', '')
                    exit_price = trade.get('exit_price', 0)
                    days_held = trade.get('days_held', 0)

                    missed_opportunities.append({
                        'symbol': symbol,
                        'entry_date': entry_date_str,
                        'entry_price': round(float(entry_price), 2),
                        'sell_date': str(exit_date)[:10],
                        'sell_price': round(float(exit_price), 2),
                        'would_be_return': round(float(pnl_pct), 1),
                        'would_be_pnl': round((float(exit_price) - float(entry_price)) * 100, 0),
                        'days_held': int(days_held),
                        'strategy_name': trade.get('strategy_name', 'Ensemble'),
                        'exit_reason': exit_reason,
                    })

            missed_opportunities.sort(key=lambda x: x['would_be_return'], reverse=True)
            missed_opportunities = missed_opportunities[:5]
        else:
            # Fallback: compute on-the-fly from price data
            lookback = 90
            min_price = settings.MIN_PRICE
            min_volume = settings.MIN_VOLUME

            for symbol, df in scanner_service.data_cache.items():
                if df is None or len(df) < 250 or symbol in ('SPY', '^VIX'):
                    continue
                if 'dwap' not in df.columns:
                    continue

                recent = df.tail(lookback + 60)
                if len(recent) < lookback:
                    continue

                closes = recent['close'].values
                volumes = recent['volume'].values if 'volume' in recent.columns else None
                dwaps = recent['dwap'].values
                dates = recent.index

                for i in range(1, min(lookback, len(recent) - 1)):
                    if dwaps[i] <= 0 or pd.isna(dwaps[i]) or dwaps[i-1] <= 0 or pd.isna(dwaps[i-1]):
                        continue
                    if closes[i] < min_price:
                        continue
                    if volumes is not None and volumes[i] < min_volume:
                        continue

                    prev_pct = (closes[i-1] / dwaps[i-1] - 1)
                    curr_pct = (closes[i] / dwaps[i] - 1)

                    if prev_pct < 0.05 and curr_pct >= 0.05:
                        entry_price = float(closes[i])
                        entry_date = dates[i]

                        high_water = entry_price
                        sell_price = None
                        sell_date = None

                        for j in range(i + 1, len(recent)):
                            price_j = float(closes[j])
                            high_water = max(high_water, price_j)
                            trailing_stop = high_water * (1 - TRAILING_STOP_PCT)
                            if price_j <= trailing_stop:
                                sell_price = price_j
                                sell_date = dates[j]
                                break

                        if sell_price is None:
                            current_price = float(closes[-1])
                            pnl_pct = (current_price / entry_price - 1) * 100
                            if pnl_pct > 5.0:
                                missed_opportunities.append({
                                    'symbol': symbol,
                                    'entry_date': entry_date.strftime('%Y-%m-%d') if hasattr(entry_date, 'strftime') else str(entry_date)[:10],
                                    'entry_price': round(entry_price, 2),
                                    'sell_date': dates[-1].strftime('%Y-%m-%d') if hasattr(dates[-1], 'strftime') else str(dates[-1])[:10],
                                    'sell_price': round(current_price, 2),
                                    'would_be_return': round(pnl_pct, 1),
                                    'would_be_pnl': round((current_price - entry_price) * 100, 0),
                                    'days_held': int((dates[-1] - entry_date).days),
                                    'exit_reason': 'still_open',
                                })
                            break

                        pnl_pct = (sell_price / entry_price - 1) * 100
                        days_held = (sell_date - entry_date).days

                        if pnl_pct > 5.0:
                            missed_opportunities.append({
                                'symbol': symbol,
                                'entry_date': entry_date.strftime('%Y-%m-%d') if hasattr(entry_date, 'strftime') else str(entry_date)[:10],
                                'entry_price': round(entry_price, 2),
                                'sell_date': sell_date.strftime('%Y-%m-%d') if hasattr(sell_date, 'strftime') else str(sell_date)[:10],
                                'sell_price': round(sell_price, 2),
                                'would_be_return': round(pnl_pct, 1),
                                'would_be_pnl': round((sell_price - entry_price) * 100, 0),
                                'days_held': int(days_held),
                            })
                        break

            missed_opportunities.sort(key=lambda x: x['would_be_return'], reverse=True)
            missed_opportunities = missed_opportunities[:5]
    except Exception as e:
        print(f"Missed opportunities error: {e}")

    # --- Recent signals with performance ---
    recent_signals = []
    try:
        result = await db.execute(
            select(Signal).where(Signal.signal_type == 'BUY')
            .order_by(desc(Signal.created_at)).limit(5)
        )
        for sig in result.scalars().all():
            current_price = None
            df = scanner_service.data_cache.get(sig.symbol)
            if df is not None and len(df) > 0:
                current_price = round(float(df.iloc[-1]['close']), 2)
            perf_pct = round((current_price / sig.price - 1) * 100, 1) if current_price and sig.price > 0 else None
            recent_signals.append({
                'symbol': sig.symbol,
                'signal_date': sig.created_at.strftime('%Y-%m-%d'),
                'signal_price': round(float(sig.price), 2),
                'current_price': current_price,
                'performance_pct': perf_pct,
            })
    except Exception as e:
        print(f"Recent signals error: {e}")

    # --- Last ensemble entry date (from persisted signals, survives top-N churn) ---
    last_ensemble_entry_date = None
    try:
        from app.core.database import EnsembleSignal
        result = await db.execute(
            select(EnsembleSignal.ensemble_entry_date)
            .where(EnsembleSignal.ensemble_entry_date.isnot(None))
            .order_by(desc(EnsembleSignal.ensemble_entry_date))
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if row:
            last_ensemble_entry_date = str(row)
    except Exception as e:
        print(f"Last ensemble entry date error: {e}")

    # --- Fetch top headlines for world-event awareness ---
    top_headlines = []
    try:
        import httpx
        import xml.etree.ElementTree as ET
        resp = httpx.get(
            "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en",
            timeout=3,
            follow_redirects=True,
        )
        if resp.status_code == 200:
            root = ET.fromstring(resp.text)
            for item in root.findall(".//item")[:5]:
                title = item.findtext("title", "")
                if title:
                    top_headlines.append(title)
            if top_headlines:
                print(f"📰 Headlines: {top_headlines}")
    except Exception as hl_err:
        print(f"⚠️ Headline fetch failed (non-fatal): {hl_err}")

    # --- Market context (AI-generated daily briefing) ---
    # Reuse today's cached context if it exists (generate once per day, not per call)
    market_context = None
    try:
        from datetime import date, timedelta
        from app.services.data_export import data_export_service

        existing_dashboard = data_export_service.read_dashboard_json()
        if existing_dashboard and existing_dashboard.get('market_context'):
            generated = existing_dashboard.get('generated_at', '')
            if date.today().isoformat() in generated:
                market_context = existing_dashboard['market_context']
                print(f"📝 Market context (cached): {market_context}")

        # Only generate if not already cached for today
        if not market_context:
            # Load previous snapshot for comparison
            prev_snap = None
            for days_back in range(1, 4):
                prev_date = (date.today() - timedelta(days=days_back)).strftime("%Y-%m-%d")
                prev_snap = data_export_service.read_snapshot(prev_date)
                if prev_snap:
                    break

            # Gather context data
            today_count = len(buy_signals)
            fresh_signals = [s for s in buy_signals if s.get('is_fresh')]
            fresh_count = len(fresh_signals)
            spy_price = market_stats.get('spy_price', '?')
            vix_level = market_stats.get('vix_level', '?')
            regime_name = market_stats.get('regime_name', market_stats.get('regime', '?'))

            # Previous day comparison
            prev_count = 0
            delta = 0
            dropped = set()
            added = set()
            prev_regime = None
            if prev_snap:
                prev_signals_list = prev_snap.get('buy_signals', [])
                prev_count = len(prev_signals_list)
                delta = today_count - prev_count
                prev_symbols = {s['symbol'] for s in prev_signals_list}
                today_symbols = {s['symbol'] for s in buy_signals}
                dropped = prev_symbols - today_symbols
                added = today_symbols - prev_symbols
                prev_regime = prev_snap.get('regime_forecast', {}).get('current_regime')

            # Top momentum names for color
            top5 = [s['symbol'] for s in buy_signals[:5]] if buy_signals else []

            # Sector themes from fresh entries
            fresh_names = [s['symbol'] for s in fresh_signals[:5]]

            # Build the AI prompt — pre-compute parts to avoid nested f-string issues
            delta_sign = "+" if delta > 0 else ""
            change_note = f" (was {prev_count} yesterday, {delta_sign}{delta} change)" if prev_snap else " (no prior day to compare)"
            fresh_note = f" — {', '.join(fresh_names)}" if fresh_names else ""
            dropped_list = ", ".join(sorted(dropped)[:8]) if dropped else "none"
            dropped_extra = f" (+{len(dropped)-8} more)" if len(dropped) > 8 else ""
            added_list = ", ".join(sorted(added)[:8]) if added else "none"
            added_extra = f" (+{len(added)-8} more)" if len(added) > 8 else ""
            regime_change = ""
            if prev_regime and prev_regime != market_stats.get("regime"):
                regime_change = f" (was {prev_regime.replace('_', ' ')})"

            context_block = (
                f"Signal count: {today_count} ensemble signals{change_note}\n"
                f"Fresh entries today: {fresh_count}{fresh_note}\n"
                f"Dropped since yesterday: {dropped_list}{dropped_extra}\n"
                f"New since yesterday: {added_list}{added_extra}\n"
                f"Top 5 momentum: {', '.join(top5)}\n"
                f"S&P 500: ${spy_price} | Market Fear: {vix_level} (VIX)\n"
                f"Regime: {regime_name}{regime_change}\n"
            )

            # Add headlines if available
            if top_headlines:
                headlines_block = "Today's top headlines:\n" + "\n".join(f"- {h}" for h in top_headlines)
            else:
                headlines_block = ""

            # Classify the day for tone guidance
            if prev_snap and abs(delta) >= 5:
                day_type = "big_move"
            elif fresh_count >= 3:
                day_type = "active"
            elif prev_snap and delta == 0 and not added:
                day_type = "quiet"
            else:
                day_type = "normal"

            system_prompt = (
                "You write daily market context for RigaCap, an AI-powered stock signal service. "
                "Your tone: witty, confident, data-driven. You talk like a sharp analyst friend — "
                "not a robot, not a hype machine. You're briefing someone who trusts your system.\n\n"
                "Rules:\n"
                "- Write exactly 1-2 sentences. Max 280 characters.\n"
                "- Plain text only. No markdown, no bold, no bullets, no emoji.\n"
                "- Never say 'our algorithm' or 'our model' — say 'the ensemble' or 'our signals'.\n"
                "- Never give financial advice or say 'buy' / 'sell'.\n"
                "- Reference specific tickers, regimes, or data points when interesting.\n"
                "- Vary your phrasing. Don't start every sentence the same way.\n"
                "- If signals dropped hard, be matter-of-fact, not alarming.\n"
                "- If it's a quiet day, keep it brief and confident.\n"
                "- NEVER use the term 'VIX' — our audience is everyday investors. Say 'market fear' instead. "
                "Example: 'market fear elevated at 28' not 'VIX at 28'.\n"
                "- You may receive today's top news headlines. If there is an extraordinary world event "
                "(war, pandemic, historic crisis, major geopolitical escalation) that would rattle global markets, "
                "open with ONE brief factual sentence connecting it to what the data shows. "
                "Ignore routine finance news (earnings, Fed meetings, jobs reports, analyst upgrades) — "
                "we are a technical signals service, not a news desk. Only acknowledge the elephant in the room.\n"
            )

            tone_hints = {
                "big_move": "This is a significant signal shift — lead with the change and what drove it. Be direct.",
                "active": "Fresh entries are coming in — highlight what's new and why the ensemble is finding opportunities.",
                "quiet": "Nothing dramatic today. One concise sentence is fine. Confidence, not filler.",
                "normal": "Moderate activity. Note what's interesting without overstating it.",
            }

            headlines_section = f"\n\n{headlines_block}" if headlines_block else ""
            user_prompt = (
                f"{tone_hints[day_type]}\n\n"
                f"Today's data:\n{context_block}"
                f"{headlines_section}"
            )

            # Try Claude API (raw HTTP — anthropic SDK not in Lambda)
            try:
                import httpx
                from app.core.config import settings
                if settings.ANTHROPIC_API_KEY:
                    headers = {
                        "x-api-key": settings.ANTHROPIC_API_KEY,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    }
                    payload = {
                        "model": "claude-haiku-4-5-20251001",
                        "max_tokens": 150,
                        "system": system_prompt,
                        "messages": [{"role": "user", "content": user_prompt}],
                    }
                    resp = httpx.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload, timeout=15)
                    if resp.status_code == 200:
                        content = resp.json().get("content", [])
                        if content and content[0].get("type") == "text":
                            market_context = content[0]["text"].strip().strip('"')
                            print(f"📝 Market context ({day_type}): {market_context}")
                    else:
                        print(f"⚠️ Claude API {resp.status_code}: {resp.text[:200]}")
            except Exception as ai_err:
                print(f"⚠️ AI market context failed, using fallback: {ai_err}")

            # Fallback if AI unavailable
            if not market_context:
                if prev_snap and abs(delta) >= 3:
                    if delta < 0:
                        market_context = (
                            f"Ensemble narrowed from {prev_count} to {today_count} signals after today's session. "
                            f"S&P 500 ${spy_price}, market fear at {vix_level}."
                        )
                    else:
                        market_context = (
                            f"Ensemble expanded to {today_count} signals from {prev_count}. "
                            f"{len(added)} new name{'s' if len(added) != 1 else ''} entered."
                        )
                elif today_count > 0:
                    market_context = (
                        f"Tracking {today_count} ensemble signals in {regime_name.lower()} regime. "
                        f"S&P 500 ${spy_price}, market fear at {vix_level}."
                    )
    except Exception as ctx_err:
        print(f"⚠️ Market context generation failed (non-fatal): {ctx_err}")

    return {
        'regime_forecast': regime_forecast_data,
        'buy_signals': buy_signals,
        'watchlist': watchlist,
        'market_stats': market_stats,
        'missed_opportunities': missed_opportunities,
        'recent_signals': recent_signals,
        'last_ensemble_entry_date': last_ensemble_entry_date,
        'market_context': market_context,
        'generated_at': datetime.now().isoformat(),
    }


async def _get_positions_with_guidance(db: AsyncSession, user, regime_forecast_data: dict):
    """Get user-specific positions with sell guidance (~200ms)."""
    from app.services.market_regime import market_regime_service, RegimeForecast

    positions_with_guidance = []
    try:
        if user is None:
            return []

        result = await db.execute(
            select(Position).where(Position.status == 'open', Position.user_id == user.id)
        )
        open_positions = result.scalars().all()

        pos_dicts = []
        for p in open_positions:
            current_price = p.entry_price
            df = scanner_service.data_cache.get(p.symbol)
            if df is not None and len(df) > 0:
                current_price = float(df.iloc[-1]['close'])
            pos_dicts.append({
                'id': p.id,
                'symbol': p.symbol,
                'shares': float(p.shares),
                'entry_price': float(p.entry_price),
                'entry_date': p.created_at.strftime('%Y-%m-%d') if p.created_at else None,
                'current_price': current_price,
                'highest_price': float(getattr(p, 'highest_price', None) or p.entry_price),
                'sector': getattr(p, 'sector', '') or '',
            })

        if pos_dicts:
            # Reconstruct regime forecast object for sell guidance
            regime_forecast_obj = None
            if regime_forecast_data:
                try:
                    spy_df = scanner_service.data_cache.get('SPY')
                    vix_df = scanner_service.data_cache.get('^VIX')
                    if spy_df is not None and len(spy_df) >= 200:
                        regime_forecast_obj = market_regime_service.predict_transitions(
                            spy_df=spy_df,
                            universe_dfs=scanner_service.data_cache,
                            vix_df=vix_df,
                        )
                except Exception:
                    pass

            positions_with_guidance = scanner_service.generate_sell_signals(
                positions=pos_dicts,
                regime_forecast=regime_forecast_obj,
            )
    except Exception as e:
        print(f"Positions guidance error: {e}")

    return positions_with_guidance


@router.get("/dashboard")
async def get_dashboard_data(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_optional),
    momentum_top_n: int = 30,
    fresh_days: int = 5,
    as_of_date: Optional[str] = None,
):
    """
    Unified dashboard endpoint.

    Normal mode: reads pre-computed data from S3 cache (instant),
    adds user-specific positions with sell guidance (~200ms).

    Time-travel mode (admin-only): computes everything live.

    Subscription enforcement: unauthenticated or expired users see a teaser
    (regime, market stats, signal count) but not actual buy signals.
    """
    import pandas as pd
    from sqlalchemy.orm import selectinload
    from app.core.database import Subscription

    # --- Check subscription status ---
    has_valid_sub = False
    if user:
        if user.is_admin():
            has_valid_sub = True
        else:
            # Load subscription if not already loaded
            sub_result = await db.execute(
                select(Subscription).where(Subscription.user_id == user.id)
            )
            subscription = sub_result.scalar_one_or_none()
            has_valid_sub = subscription is not None and subscription.is_valid()

    # --- Time-travel mode (admin only) — always compute live ---
    if as_of_date:
        if not user or not user.is_admin():
            raise HTTPException(status_code=403, detail="Admin only")
        return await _compute_dashboard_live(db, user, momentum_top_n, fresh_days, as_of_date)

    # --- Normal mode: read pre-computed cache from S3 ---
    # (API Lambda doesn't load the full pickle — dashboard.json is pre-computed by worker)
    cached = data_export_service.read_dashboard_json()

    if cached is None and not scanner_service.data_cache:
        raise HTTPException(status_code=503, detail="Price data not loaded")
    elif cached is None:
        # Fallback: compute live if S3 cache missing but data is loaded
        cached = await compute_shared_dashboard_data(db, momentum_top_n, fresh_days)

    # --- Subscription gating ---
    if not has_valid_sub:
        # Teaser: show regime, market stats, signal count, but no actual signals
        return {
            'regime_forecast': cached.get('regime_forecast'),
            'buy_signals': [],
            'positions_with_guidance': [],
            'watchlist': [],
            'market_stats': cached.get('market_stats', {}),
            'recent_signals': [],
            'missed_opportunities': [],
            'generated_at': cached.get('generated_at', datetime.now().isoformat()),
            'subscription_required': True,
        }

    # Add user-specific positions with sell guidance (~200ms)
    positions_with_guidance = await _get_positions_with_guidance(
        db, user, cached.get('regime_forecast')
    )

    # Capture unfiltered fresh signal metadata before position filtering
    all_buy_signals = cached.get('buy_signals', [])
    fresh_signal_dates = [
        s.get('ensemble_entry_date') or s.get('crossover_date')
        for s in all_buy_signals if s.get('is_fresh')
    ]
    fresh_signal_dates = [d for d in fresh_signal_dates if d]  # remove None
    total_fresh_count = sum(1 for s in all_buy_signals if s.get('is_fresh'))

    # Filter buy signals by user's open positions
    open_syms = {p.get('symbol', '') for p in positions_with_guidance}
    buy_signals = [s for s in all_buy_signals if s['symbol'] not in open_syms]

    # Filter missed opportunities by user's open positions
    missed_opportunities = [
        m for m in cached.get('missed_opportunities', [])
        if m.get('symbol', '') not in open_syms
    ]

    return {
        'regime_forecast': cached.get('regime_forecast'),
        'buy_signals': buy_signals,
        'positions_with_guidance': positions_with_guidance,
        'watchlist': cached.get('watchlist', []),
        'market_stats': cached.get('market_stats', {}),
        'recent_signals': cached.get('recent_signals', []),
        'missed_opportunities': missed_opportunities,
        'generated_at': cached.get('generated_at', datetime.now().isoformat()),
        'last_ensemble_entry_date': cached.get('last_ensemble_entry_date'),
        'fresh_signal_dates': fresh_signal_dates,
        'total_fresh_count': total_fresh_count,
    }


async def _compute_dashboard_live(
    db: AsyncSession, user, momentum_top_n: int, fresh_days: int, as_of_date: str
) -> dict:
    """Full live computation for time-travel mode (admin only). Unchanged logic."""
    from app.core.config import settings
    from app.services.market_regime import market_regime_service
    import pandas as pd

    # Try snapshot first — instant, no memory/timeout issues
    snapshot = data_export_service.read_snapshot(as_of_date)
    if snapshot:
        print(f"Time-travel {as_of_date}: loaded from snapshot")
        return snapshot

    effective_date = pd.Timestamp(as_of_date).normalize()

    if not scanner_service.data_cache:
        raise HTTPException(status_code=503, detail="Price data not loaded")

    def _truncate_df(df, ts):
        if hasattr(df.index, 'tz') and df.index.tz is not None and ts.tz is None:
            ts = ts.tz_localize(df.index.tz)
        return df[df.index <= ts]

    # Regime forecast
    regime_forecast_data = None
    try:
        spy_df = scanner_service.data_cache.get('SPY')
        vix_df = scanner_service.data_cache.get('^VIX')
        if spy_df is not None and len(spy_df) >= 200:
            regime_forecast_obj = market_regime_service.predict_transitions(
                spy_df=spy_df,
                universe_dfs=scanner_service.data_cache,
                vix_df=vix_df,
                as_of_date=effective_date,
            )
            regime_forecast_data = regime_forecast_obj.to_dict()
    except Exception as e:
        import traceback
        print(f"Regime forecast error: {e}")
        traceback.print_exc()

    # Buy signals (time-travel)
    buy_signals = []
    try:
        dwap_signals = await scanner_service.scan(refresh_data=False, apply_market_filter=False, as_of_date=effective_date)
        dwap_by_symbol = {s.symbol: s for s in dwap_signals}

        momentum_rankings = scanner_service.rank_stocks_momentum(apply_market_filter=False, as_of_date=effective_date)
        momentum_by_symbol = {
            r.symbol: {'rank': i + 1, 'data': r}
            for i, r in enumerate(momentum_rankings[:momentum_top_n])
        }

        threshold_rank = momentum_top_n // 2
        mom_threshold = momentum_rankings[threshold_rank - 1].composite_score if len(momentum_rankings) >= threshold_rank else 0

        spy_trend = compute_spy_trend(as_of_date=effective_date)

        for symbol in dwap_by_symbol:
            if symbol in momentum_by_symbol:
                dwap = dwap_by_symbol[symbol]
                mom = momentum_by_symbol[symbol]
                mom_data = mom['data']
                mom_rank = mom['rank']

                crossover_date, days_since = find_dwap_crossover_date(symbol, as_of_date=effective_date)

                entry_date = None
                days_since_entry = None
                if crossover_date:
                    entry_date = find_ensemble_entry_date(symbol, crossover_date, mom_threshold, as_of_date=effective_date)
                    if entry_date:
                        entry_ts = pd.Timestamp(entry_date).normalize()
                        days_since_entry = (effective_date - entry_ts).days

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

                info = stock_universe_service.symbol_info.get(symbol, {})

                buy_signals.append({
                    'symbol': symbol,
                    'price': float(dwap.price),
                    'dwap': float(dwap.dwap),
                    'pct_above_dwap': float(dwap.pct_above_dwap),
                    'volume': int(dwap.volume),
                    'volume_ratio': float(dwap.volume_ratio),
                    'is_strong': bool(dwap.is_strong),
                    'momentum_rank': int(mom_rank),
                    'momentum_score': round(float(mom_data.composite_score), 2),
                    'short_momentum': round(float(mom_data.short_momentum), 2),
                    'long_momentum': round(float(mom_data.long_momentum), 2),
                    'ensemble_score': round(float(ensemble_score), 1),
                    'signal_strength_label': get_signal_strength_label(ensemble_score),
                    'dwap_crossover_date': crossover_date,
                    'ensemble_entry_date': entry_date,
                    'days_since_crossover': int(days_since) if days_since is not None else None,
                    'days_since_entry': int(days_since_entry) if days_since_entry is not None else None,
                    'is_fresh': bool(is_fresh),
                    'sector': info.get('sector', ''),
                })

        # Time-travel: only show fresh signals
        buy_signals = [s for s in buy_signals if s['is_fresh']]

        buy_signals.sort(key=lambda x: (
            0 if (x.get('days_since_entry') or 999) == 0 else 1,  # BUY NOW first
            0 if x['is_fresh'] else 1,
            x.get('days_since_entry') if x.get('days_since_entry') is not None else 999,
            -x['ensemble_score']
        ))
    except Exception as e:
        print(f"Buy signals error: {e}")

    # Watchlist (time-travel)
    watchlist = []
    try:
        # Reuse momentum_rankings from above (already computed for time-travel)
        top_momentum = {
            r.symbol: {'rank': i + 1, 'data': r}
            for i, r in enumerate(momentum_rankings[:momentum_top_n])
        }

        for symbol, mom in top_momentum.items():
            df = scanner_service.data_cache.get(symbol)
            if df is None or len(df) < 1:
                continue

            df = _truncate_df(df, effective_date)
            if len(df) < 1:
                continue

            row = df.iloc[-1]
            price = row['close']
            dwap_val = row.get('dwap')

            if pd.isna(dwap_val) or dwap_val <= 0:
                continue

            pct_above = (price / dwap_val - 1) * 100

            if 3.0 <= pct_above < 5.0:
                mom_data = mom['data']
                info = stock_universe_service.symbol_info.get(symbol, {})
                watchlist.append({
                    'symbol': symbol,
                    'price': round(float(price), 2),
                    'dwap': round(float(dwap_val), 2),
                    'pct_above_dwap': round(float(pct_above), 2),
                    'distance_to_trigger': round(float(5.0 - pct_above), 2),
                    'momentum_rank': int(mom['rank']),
                    'momentum_score': round(float(mom_data.composite_score), 2),
                    'sector': info.get('sector', ''),
                })

        watchlist.sort(key=lambda x: x['distance_to_trigger'])
        watchlist = watchlist[:5]
    except Exception as e:
        print(f"Watchlist error: {e}")

    # Market stats (time-travel)
    market_stats = {}
    try:
        spy_df = scanner_service.data_cache.get('SPY')
        vix_df = scanner_service.data_cache.get('^VIX')
        if spy_df is not None:
            spy_df = _truncate_df(spy_df, effective_date)
        if vix_df is not None:
            vix_df = _truncate_df(vix_df, effective_date)
        if spy_df is not None and len(spy_df) > 0:
            market_stats['spy_price'] = round(float(spy_df.iloc[-1]['close']), 2)
            if len(spy_df) >= 2:
                prev_close = float(spy_df.iloc[-2]['close'])
                if prev_close > 0:
                    market_stats['spy_change_pct'] = round((market_stats['spy_price'] / prev_close - 1) * 100, 2)
        if vix_df is not None and len(vix_df) > 0:
            market_stats['vix_level'] = round(float(vix_df.iloc[-1]['close']), 2)
        if regime_forecast_data:
            market_stats['regime_name'] = regime_forecast_data.get('current_regime_name', '')
            market_stats['regime'] = regime_forecast_data.get('current_regime', '')
        market_stats['signal_count'] = len(buy_signals)
        market_stats['fresh_count'] = len([s for s in buy_signals if s.get('is_fresh')])
    except Exception as e:
        print(f"Market stats error: {e}")

    return {
        'regime_forecast': regime_forecast_data,
        'buy_signals': buy_signals,
        'positions_with_guidance': [],
        'watchlist': watchlist,
        'market_stats': market_stats,
        'recent_signals': [],
        'missed_opportunities': [],
        'as_of_date': as_of_date,
        'generated_at': datetime.now().isoformat(),
    }


class MomentumRankingItem(BaseModel):
    rank: int
    symbol: str
    price: float
    momentum_score: float
    short_momentum: float
    long_momentum: float
    volatility: float
    near_50d_high: float
    passes_quality: bool


class MomentumRankingsResponse(BaseModel):
    rankings: List[MomentumRankingItem]
    market_filter_active: bool
    generated_at: str


@router.get("/momentum-rankings", response_model=MomentumRankingsResponse)
async def get_momentum_rankings(
    top_n: int = 20,
    user: User = Depends(require_valid_subscription),
):
    """
    Get current top stocks by momentum score.

    Returns the top N stocks ranked by the momentum scoring formula:
    score = short_momentum * 0.5 + long_momentum * 0.3 - volatility * 0.2

    Stocks must pass quality filters:
    - Price > MA20 and MA50 (uptrend)
    - Within 5% of 50-day high (breakout potential)
    - Volume > 500,000
    - Price > $20

    These are the same stocks that the momentum strategy would consider buying.
    """
    from app.core.config import settings

    if not scanner_service.data_cache:
        raise HTTPException(status_code=503, detail="Price data not loaded")

    rankings = scanner_service.rank_stocks_momentum(apply_market_filter=True)

    if not rankings:
        # Market filter might have blocked all signals
        return MomentumRankingsResponse(
            rankings=[],
            market_filter_active=settings.MARKET_FILTER_ENABLED,
            generated_at=datetime.now().isoformat()
        )

    return MomentumRankingsResponse(
        rankings=[
            MomentumRankingItem(
                rank=i + 1,
                symbol=r.symbol,
                price=r.price,
                momentum_score=round(r.composite_score, 2),
                short_momentum=round(r.short_momentum, 2),
                long_momentum=round(r.long_momentum, 2),
                volatility=round(r.volatility, 2),
                near_50d_high=round(r.dist_from_50d_high, 2),
                passes_quality=r.passes_quality_filter
            )
            for i, r in enumerate(rankings[:top_n])
        ],
        market_filter_active=settings.MARKET_FILTER_ENABLED,
        generated_at=datetime.now().isoformat()
    )


class DoubleSignalItem(BaseModel):
    """A stock with both DWAP trigger AND top momentum ranking."""
    symbol: str
    price: float
    # DWAP data
    dwap: float
    pct_above_dwap: float
    volume: int
    volume_ratio: float
    is_strong: bool
    # Momentum data
    momentum_rank: int
    momentum_score: float
    short_momentum: float
    long_momentum: float
    # Signal strength score (0-100, data-backed)
    ensemble_score: float
    signal_strength_label: str = ""
    # Crossover tracking
    dwap_crossover_date: Optional[str] = None  # When stock first crossed DWAP +5%
    days_since_crossover: Optional[int] = None  # Days since the crossover
    is_fresh: bool = False  # True if crossover was recent (actionable buy signal)


class DoubleSignalsResponse(BaseModel):
    signals: List[DoubleSignalItem]
    fresh_signals: List[DoubleSignalItem]  # Only fresh (recent crossover) signals
    dwap_only_count: int
    momentum_only_count: int
    fresh_count: int  # Number of actionable fresh signals
    stale_count: int  # Number of stale (old crossover) signals
    fresh_threshold_days: int  # Days threshold for "fresh" (e.g., 5)
    market_filter_active: bool
    generated_at: str


def find_ensemble_entry_date(symbol: str, dwap_crossover_date_str: str, momentum_threshold: float, as_of_date=None) -> Optional[str]:
    """
    Find when a stock first qualified for the ensemble (DWAP +5% AND momentum top-N).
    Walks forward from DWAP crossover date checking composite score against threshold.
    Returns date string or None.
    """
    import pandas as pd
    from app.core.config import settings

    df = scanner_service.data_cache.get(symbol)
    if df is None or len(df) < 200:
        return None

    # Ensure momentum indicators exist
    df = scanner_service._ensure_momentum_indicators(df)

    # Truncate for time-travel
    if as_of_date:
        as_of_ts = pd.Timestamp(as_of_date).normalize()
        if hasattr(df.index, 'tz') and df.index.tz is not None:
            as_of_ts = as_of_ts.tz_localize(df.index.tz)
        df = df[df.index <= as_of_ts]

    # Start from DWAP crossover date
    start_ts = pd.Timestamp(dwap_crossover_date_str).normalize()
    if hasattr(df.index, 'tz') and df.index.tz is not None:
        start_ts = start_ts.tz_localize(df.index.tz)

    subset = df[df.index >= start_ts]
    if len(subset) == 0:
        return None

    for idx in range(len(subset)):
        row = subset.iloc[idx]
        price = row['close']
        volume = row.get('volume', 0)
        dwap = row.get('dwap', 0)
        if pd.isna(dwap) or dwap <= 0:
            continue

        # Check volume and price filters (must match scan/ranking filters)
        if price < settings.MIN_PRICE or volume < settings.MIN_VOLUME:
            continue

        # Check DWAP +5%
        pct_above = (price / dwap - 1) * 100
        if pct_above < 5.0:
            continue

        # Check momentum quality filters
        ma_20 = row.get('ma_20', 0)
        ma_50 = row.get('ma_50', 0)
        dist_from_high = row.get('dist_from_50d_high', -100)
        if not (price > ma_20 > 0 and price > ma_50 > 0):
            continue
        if dist_from_high < -settings.NEAR_50D_HIGH_PCT:
            continue

        # Check composite score against threshold
        short_mom = row.get('short_mom', 0)
        long_mom = row.get('long_mom', 0)
        vol = row.get('volatility', 0)
        if pd.isna(short_mom) or pd.isna(long_mom) or pd.isna(vol):
            continue
        composite = (
            short_mom * settings.SHORT_MOM_WEIGHT +
            long_mom * settings.LONG_MOM_WEIGHT -
            vol * settings.VOLATILITY_PENALTY
        )
        if composite >= momentum_threshold:
            entry_date = subset.index[idx]
            if hasattr(entry_date, 'tz') and entry_date.tz is not None:
                entry_date = entry_date.tz_localize(None)
            return entry_date.strftime('%Y-%m-%d')

    return None


def compute_signal_strength(volatility: float, spy_trend: float, dwap_age: int,
                            dist_from_high: float, vol_ratio: float,
                            momentum_score: float) -> int:
    """
    Data-backed signal strength score (0-100).

    Formula B (Penalty/Bonus) — validated on 710 walk-forward trades (2021-2026).
    Uses 5 factors: volatility (monotonic ↑), spy_trend (6-9% sweet spot),
    dwap_age (stale better), dist_from_high (-3 to -1 sweet spot),
    vol_ratio × momentum interaction.

    Validation: Pearson r=+0.083 (p=0.027), Q5-Q1 spread=+2.39%,
    4/5 leave-one-year-out CV pass.
    """
    base = 60
    vol_bonus = min((volatility - 20) * 0.3, 15)
    if 6 <= spy_trend <= 9:
        spy_bonus = 10
    elif spy_trend > 3:
        spy_bonus = 5
    else:
        spy_bonus = -5
    age_bonus = min(dwap_age / 15, 10)
    dfh_bonus = 8 if -3 < dist_from_high < -1 else 0
    combo_bonus = 8 if vol_ratio > 1.3 and momentum_score > 5 else 0
    return max(0, min(100, round(base + vol_bonus + spy_bonus + age_bonus + dfh_bonus + combo_bonus)))


def get_signal_strength_label(score: int) -> str:
    """Convert signal strength score to human-readable label."""
    if score >= 88:
        return "Very Strong"
    elif score >= 75:
        return "Strong"
    elif score >= 61:
        return "Moderate"
    else:
        return "Weak"


def compute_spy_trend(as_of_date=None) -> float:
    """
    Return SPY's % above its 200-day MA. Positive = bullish, negative = bearish.
    """
    import numpy as np

    spy_df = scanner_service.data_cache.get('SPY')
    if spy_df is None or len(spy_df) < 200:
        return 0.0

    if as_of_date is not None:
        import pandas as pd
        as_of_ts = pd.Timestamp(as_of_date).normalize()
        if hasattr(spy_df.index, 'tz') and spy_df.index.tz is not None:
            as_of_ts = as_of_ts.tz_localize(spy_df.index.tz)
        spy_df = spy_df[spy_df.index <= as_of_ts]
        if len(spy_df) < 200:
            return 0.0

    row = spy_df.iloc[-1]
    spy_price = row['close']
    spy_ma200 = row.get('ma_200', np.nan)
    if np.isnan(spy_ma200) or spy_ma200 <= 0:
        return 0.0
    return round((spy_price / spy_ma200 - 1) * 100, 2)


def find_dwap_crossover_date(symbol: str, threshold_pct: float = 5.0, lookback_days: int = 60, as_of_date=None) -> tuple:
    """
    Find when a stock first crossed above DWAP threshold in recent history.
    Returns (crossover_date, days_since) or (None, None) if not found.
    """
    import pandas as pd

    df = scanner_service.data_cache.get(symbol)
    if df is None or len(df) < 200:
        return None, None

    # Time-travel: truncate to as_of_date
    if as_of_date:
        as_of_ts = pd.Timestamp(as_of_date).normalize()
        if hasattr(df.index, 'tz') and df.index.tz is not None:
            as_of_ts = as_of_ts.tz_localize(df.index.tz)
        df = df[df.index <= as_of_ts]
        if len(df) < 200:
            return None, None

    # Look at recent history (last N trading days)
    recent = df.tail(lookback_days)
    if len(recent) < 2:
        return None, None

    crossover_date = None

    # Scan from oldest to newest to find first crossover
    for i in range(1, len(recent)):
        prev_row = recent.iloc[i - 1]
        curr_row = recent.iloc[i]

        prev_dwap = prev_row.get('dwap')
        curr_dwap = curr_row.get('dwap')
        prev_close = prev_row['close']
        curr_close = curr_row['close']

        if pd.isna(prev_dwap) or pd.isna(curr_dwap) or prev_dwap <= 0 or curr_dwap <= 0:
            continue

        prev_pct = (prev_close / prev_dwap - 1) * 100
        curr_pct = (curr_close / curr_dwap - 1) * 100

        # Check for crossover: was below threshold, now above
        if prev_pct < threshold_pct and curr_pct >= threshold_pct:
            crossover_date = curr_row.name
            break

    if crossover_date is None:
        # Stock may have been above threshold for the entire lookback period
        # Check if first day was already above threshold
        first_row = recent.iloc[0]
        first_dwap = first_row.get('dwap')
        if first_dwap and first_dwap > 0:
            first_pct = (first_row['close'] / first_dwap - 1) * 100
            if first_pct >= threshold_pct:
                crossover_date = first_row.name

    if crossover_date is not None:
        # Calculate days since crossover
        today = df.index[-1]
        if hasattr(crossover_date, 'tz') and crossover_date.tz is not None:
            crossover_date = crossover_date.tz_localize(None)
        if hasattr(today, 'tz') and today.tz is not None:
            today = today.tz_localize(None)
        days_since = (today - crossover_date).days
        date_str = crossover_date.strftime('%Y-%m-%d')
        return date_str, days_since

    return None, None


class ApproachingTriggerItem(BaseModel):
    """A momentum stock approaching the DWAP +5% trigger."""
    symbol: str
    price: float
    dwap: float
    pct_above_dwap: float
    distance_to_trigger: float  # How far from +5% (e.g., 1.5 means +1.5% to go)
    momentum_rank: int
    momentum_score: float
    short_momentum: float
    long_momentum: float


class ApproachingTriggerResponse(BaseModel):
    approaching: List[ApproachingTriggerItem]
    market_filter_active: bool
    trigger_threshold: float  # The threshold they're approaching (e.g., 5.0)
    generated_at: str



@router.get("/approaching-trigger", response_model=ApproachingTriggerResponse)
async def get_approaching_trigger(
    momentum_top_n: int = 30,
    min_pct: float = 3.0,
    max_pct: float = 5.0,
    user: User = Depends(require_valid_subscription),
):
    """
    Get momentum stocks approaching the DWAP +5% trigger.

    Shows stocks in the top momentum rankings that are at +3-4% above DWAP,
    meaning they're close to triggering a double signal but haven't yet.

    These are "watch list" stocks - if they push up another 1-2%, they'll
    become actionable double signals.

    - **momentum_top_n**: Consider top N momentum stocks (default 20)
    - **min_pct**: Minimum % above DWAP to include (default 3.0)
    - **max_pct**: Maximum % above DWAP (default 5.0 - the trigger threshold)
    """
    from app.core.config import settings
    import pandas as pd

    if not scanner_service.data_cache:
        raise HTTPException(status_code=503, detail="Price data not loaded")

    # Get momentum rankings
    momentum_rankings = scanner_service.rank_stocks_momentum(apply_market_filter=True)
    top_momentum = {
        r.symbol: {'rank': i + 1, 'data': r}
        for i, r in enumerate(momentum_rankings[:momentum_top_n])
    }

    approaching = []

    for symbol, mom in top_momentum.items():
        df = scanner_service.data_cache.get(symbol)
        if df is None or len(df) < 1:
            continue

        row = df.iloc[-1]
        price = row['close']
        dwap = row.get('dwap')

        if pd.isna(dwap) or dwap <= 0:
            continue

        pct_above = (price / dwap - 1) * 100  # Convert to percentage

        # Check if in the "approaching" range (3-5%)
        if min_pct <= pct_above < max_pct:
            distance_to_trigger = max_pct - pct_above
            mom_data = mom['data']

            approaching.append(ApproachingTriggerItem(
                symbol=symbol,
                price=round(float(price), 2),
                dwap=round(float(dwap), 2),
                pct_above_dwap=round(pct_above, 2),
                distance_to_trigger=round(distance_to_trigger, 2),
                momentum_rank=mom['rank'],
                momentum_score=round(mom_data.composite_score, 2),
                short_momentum=round(mom_data.short_momentum, 2),
                long_momentum=round(mom_data.long_momentum, 2)
            ))

    # Sort by closest to trigger (smallest distance first)
    approaching.sort(key=lambda x: x.distance_to_trigger)

    return ApproachingTriggerResponse(
        approaching=approaching,
        market_filter_active=settings.MARKET_FILTER_ENABLED,
        trigger_threshold=max_pct,
        generated_at=datetime.now().isoformat()
    )


@router.get("/double-signals", response_model=DoubleSignalsResponse)
async def get_double_signals(
    momentum_top_n: int = 30,
    fresh_days: int = 5,
    user: User = Depends(require_valid_subscription),
):
    """
    Get stocks with BOTH DWAP trigger (+5% above DWAP) AND top momentum ranking.

    These "double signals" have historically shown 2.5x higher returns than
    DWAP-only signals (2.91% vs 1.16% at 20 days).

    **Fresh vs Stale Signals:**
    - **Fresh**: Crossed DWAP +5% within the last `fresh_days` (default 5) - actionable BUY
    - **Stale**: Crossed longer ago - may have missed the optimal entry

    DWAP typically crosses before momentum picks up, so fresh crossovers are
    the ideal entry points for the ensemble strategy.

    - **momentum_top_n**: Consider top N momentum stocks (default 20)
    - **fresh_days**: Days threshold for "fresh" signals (default 5)
    """
    from app.core.config import settings

    if not scanner_service.data_cache:
        raise HTTPException(status_code=503, detail="Price data not loaded")

    # Get current DWAP signals
    dwap_signals = await scanner_service.scan(refresh_data=False, apply_market_filter=True)
    dwap_by_symbol = {s.symbol: s for s in dwap_signals}

    # Get momentum rankings
    momentum_rankings = scanner_service.rank_stocks_momentum(apply_market_filter=True)
    momentum_by_symbol = {
        r.symbol: {'rank': i + 1, 'data': r}
        for i, r in enumerate(momentum_rankings[:momentum_top_n])
    }

    # Find intersection (double signals)
    double_signals = []
    fresh_signals = []
    spy_trend = compute_spy_trend()

    for symbol in dwap_by_symbol:
        if symbol in momentum_by_symbol:
            dwap = dwap_by_symbol[symbol]
            mom = momentum_by_symbol[symbol]
            mom_data = mom['data']
            mom_rank = mom['rank']

            # Find when the DWAP crossover occurred
            crossover_date, days_since = find_dwap_crossover_date(symbol)

            # Determine if this is a fresh signal (actionable buy)
            is_fresh = days_since is not None and days_since <= fresh_days

            # Signal strength score (data-backed)
            dwap_age = days_since if days_since is not None else 0
            ensemble_score = compute_signal_strength(
                volatility=mom_data.volatility,
                spy_trend=spy_trend,
                dwap_age=dwap_age,
                dist_from_high=mom_data.dist_from_50d_high,
                vol_ratio=dwap.volume_ratio,
                momentum_score=mom_data.composite_score,
            )

            signal = DoubleSignalItem(
                symbol=symbol,
                price=dwap.price,
                dwap=dwap.dwap,
                pct_above_dwap=dwap.pct_above_dwap,
                volume=dwap.volume,
                volume_ratio=dwap.volume_ratio,
                is_strong=dwap.is_strong,
                momentum_rank=mom_rank,
                momentum_score=round(mom_data.composite_score, 2),
                short_momentum=round(mom_data.short_momentum, 2),
                long_momentum=round(mom_data.long_momentum, 2),
                ensemble_score=round(ensemble_score, 1),
                signal_strength_label=get_signal_strength_label(ensemble_score),
                dwap_crossover_date=crossover_date,
                days_since_crossover=days_since,
                is_fresh=is_fresh
            )

            double_signals.append(signal)
            if is_fresh:
                fresh_signals.append(signal)

    # Sort: fresh signals first (by recency), then stale by ensemble score
    double_signals.sort(key=lambda x: (
        0 if x.is_fresh else 1,  # Fresh first
        x.days_since_crossover if x.days_since_crossover else 999,  # Then by recency
        -x.ensemble_score  # Then by score
    ))

    # Sort fresh signals by recency then score
    fresh_signals.sort(key=lambda x: (
        x.days_since_crossover if x.days_since_crossover else 0,
        -x.ensemble_score
    ))

    return DoubleSignalsResponse(
        signals=double_signals,
        fresh_signals=fresh_signals,
        dwap_only_count=len(dwap_by_symbol) - len(double_signals),
        momentum_only_count=len(momentum_by_symbol) - len(double_signals),
        fresh_count=len(fresh_signals),
        stale_count=len(double_signals) - len(fresh_signals),
        fresh_threshold_days=fresh_days,
        market_filter_active=settings.MARKET_FILTER_ENABLED,
        generated_at=datetime.now().isoformat()
    )


@router.get("/ensemble/history")
async def get_ensemble_signal_history(
    symbol: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_optional),
):
    """
    Query persisted ensemble signal history. Admin-only.

    Returns full audit trail of signals: when they fired, their scores,
    and whether they were later invalidated.

    Example: /ensemble/history?symbol=ADI&status=invalidated
    """
    from datetime import date as date_type
    from app.services.ensemble_signal_service import ensemble_signal_service

    if not user or not user.is_admin():
        raise HTTPException(status_code=403, detail="Admin only")

    parsed_start = None
    parsed_end = None
    if start_date:
        try:
            parsed_start = date_type.fromisoformat(start_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_date format (YYYY-MM-DD)")
    if end_date:
        try:
            parsed_end = date_type.fromisoformat(end_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end_date format (YYYY-MM-DD)")

    signals = await ensemble_signal_service.query_signals(
        db,
        symbol=symbol,
        start_date=parsed_start,
        end_date=parsed_end,
        status=status,
        limit=min(limit, 500),
    )

    return {
        "count": len(signals),
        "signals": [
            {
                "id": s.id,
                "signal_date": s.signal_date.isoformat(),
                "symbol": s.symbol,
                "price": s.price,
                "dwap": s.dwap,
                "pct_above_dwap": s.pct_above_dwap,
                "momentum_rank": s.momentum_rank,
                "momentum_score": s.momentum_score,
                "ensemble_score": s.ensemble_score,
                "dwap_crossover_date": s.dwap_crossover_date.isoformat() if s.dwap_crossover_date else None,
                "ensemble_entry_date": s.ensemble_entry_date.isoformat() if s.ensemble_entry_date else None,
                "days_since_crossover": s.days_since_crossover,
                "days_since_entry": s.days_since_entry,
                "is_fresh": s.is_fresh,
                "is_strong": s.is_strong,
                "sector": s.sector,
                "status": s.status,
                "invalidated_at": s.invalidated_at.isoformat() if s.invalidated_at else None,
                "invalidation_reason": s.invalidation_reason,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in signals
        ],
    }


@router.get("/simulate-intraday-crossover")
async def simulate_intraday_crossover(
    as_of_date: str,
    send_email: bool = False,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_optional),
):
    """
    Simulate intraday DWAP crossover detection for a historical date.

    Shows what the intraday monitor would have detected and emailed.

    - Computes the watchlist as of the previous trading day
    - Checks which watchlist stocks crossed DWAP +5% on as_of_date
    - Optionally sends the intraday alert email to the requesting user

    Admin-only. Example: /simulate-intraday-crossover?as_of_date=2026-01-28
    """
    import pandas as pd

    if not user or not user.is_admin():
        raise HTTPException(status_code=403, detail="Admin only")

    if not scanner_service.data_cache:
        raise HTTPException(status_code=503, detail="Price data not loaded")

    effective_date = pd.Timestamp(as_of_date).normalize()

    def _truncate_df(df, ts):
        if hasattr(df.index, 'tz') and df.index.tz is not None and ts.tz is None:
            ts = ts.tz_localize(df.index.tz)
        return df[df.index <= ts]

    # Find previous trading day
    spy_df = scanner_service.data_cache.get('SPY')
    if spy_df is None:
        raise HTTPException(status_code=503, detail="SPY data not available")

    spy_trunc = _truncate_df(spy_df, effective_date)
    if len(spy_trunc) < 2:
        raise HTTPException(status_code=400, detail="Not enough data for this date")

    prev_trading_day = spy_trunc.index[-2]
    prev_date_ts = prev_trading_day.tz_localize(None) if hasattr(prev_trading_day, 'tz') and prev_trading_day.tz else prev_trading_day

    # Step 1: Compute watchlist as of previous trading day
    # (stocks 3-5% above DWAP in top-30 momentum)
    momentum_top_n = 30
    momentum_rankings = scanner_service.rank_stocks_momentum(
        apply_market_filter=True, as_of_date=prev_date_ts
    )
    top_momentum = {
        r.symbol: {'rank': i + 1, 'data': r}
        for i, r in enumerate(momentum_rankings[:momentum_top_n])
    }

    prev_watchlist = []
    for symbol, mom in top_momentum.items():
        df = scanner_service.data_cache.get(symbol)
        if df is None or len(df) < 200:
            continue

        df_prev = _truncate_df(df, prev_date_ts)
        if len(df_prev) < 1:
            continue

        row = df_prev.iloc[-1]
        price = row['close']
        dwap_val = row.get('dwap')
        if pd.isna(dwap_val) or dwap_val <= 0:
            continue

        pct_above = (price / dwap_val - 1) * 100
        if 3.0 <= pct_above < 5.0:
            prev_watchlist.append({
                'symbol': symbol,
                'prev_day_price': round(float(price), 2),
                'dwap': round(float(dwap_val), 2),
                'prev_day_pct_above': round(float(pct_above), 2),
                'distance_to_trigger': round(float(5.0 - pct_above), 2),
                'momentum_rank': mom['rank'],
            })

    prev_watchlist.sort(key=lambda x: x['distance_to_trigger'])
    prev_watchlist = prev_watchlist[:5]

    # Step 2: Check which watchlist stocks crossed +5% on as_of_date
    crossovers = []
    for w in prev_watchlist:
        symbol = w['symbol']
        df = scanner_service.data_cache.get(symbol)
        if df is None:
            continue

        df_today = _truncate_df(df, effective_date)
        if len(df_today) < 1:
            continue

        today_row = df_today.iloc[-1]
        today_price = float(today_row['close'])
        dwap_val = w['dwap']

        # Use the as_of_date DWAP (it changes daily)
        today_dwap = today_row.get('dwap')
        if pd.isna(today_dwap) or today_dwap <= 0:
            today_dwap = dwap_val  # fallback to prev day DWAP

        pct_above = (today_price / float(today_dwap) - 1) * 100
        crossed = pct_above >= 5.0

        info = stock_universe_service.symbol_info.get(symbol, {})
        sector = info.get('sector', '')

        crossovers.append({
            'symbol': symbol,
            'prev_day_price': w['prev_day_price'],
            'prev_day_pct_above': w['prev_day_pct_above'],
            'as_of_date_price': round(today_price, 2),
            'as_of_date_dwap': round(float(today_dwap), 2),
            'as_of_date_pct_above': round(pct_above, 2),
            'crossed': crossed,
            'momentum_rank': w['momentum_rank'],
            'sector': sector,
        })

    triggered = [c for c in crossovers if c['crossed']]

    # Step 3: Optionally send the intraday alert email
    emails_sent = []
    if send_email and triggered and user:
        from app.services.email_service import email_service

        for sig in triggered:
            success = await email_service.send_intraday_signal_alert(
                to_email=user.email,
                user_name=user.name or "",
                symbol=sig['symbol'],
                live_price=sig['as_of_date_price'],
                dwap=sig['as_of_date_dwap'],
                pct_above_dwap=sig['as_of_date_pct_above'],
                momentum_rank=sig['momentum_rank'],
                sector=sig['sector'],
                user_id=str(user.id),
            )
            emails_sent.append({
                'symbol': sig['symbol'],
                'sent_to': user.email,
                'success': success,
            })

    # Step 4: Show what the dashboard update would contain
    dashboard_additions = []
    for sig in triggered:
        dashboard_additions.append({
            'symbol': sig['symbol'],
            'price': sig['as_of_date_price'],
            'dwap': sig['as_of_date_dwap'],
            'pct_above_dwap': sig['as_of_date_pct_above'],
            'momentum_rank': sig['momentum_rank'],
            'sector': sig['sector'],
            'is_fresh': True,
            'is_intraday': True,
            'days_since_crossover': 0,
            'ensemble_score': 0,
        })

    return {
        'simulation_date': as_of_date,
        'prev_trading_day': prev_date_ts.strftime('%Y-%m-%d'),
        'watchlist_prev_day': prev_watchlist,
        'crossover_results': crossovers,
        'triggered_count': len(triggered),
        'dashboard_additions': dashboard_additions,
        'emails_sent': emails_sent if emails_sent else None,
        'note': (
            'This simulates what the intraday monitor would have detected. '
            'The prev_trading_day watchlist shows stocks that were 3-5% above DWAP. '
            'crossover_results shows whether each crossed +5% on the simulation date. '
            'Add ?send_email=true to receive the actual alert email.'
        ),
    }


# ============================================================================
# Public endpoints (no auth required) — for /market-regime page + email signup
# ============================================================================

REGIME_COLORS = {
    'strong_bull': {'color': '#10B981', 'bg': '#d1fae5', 'name': 'Strong Bull'},
    'weak_bull': {'color': '#84CC16', 'bg': '#ecfdf5', 'name': 'Weak Bull'},
    'rotating_bull': {'color': '#8B5CF6', 'bg': '#ede9fe', 'name': 'Rotating Bull'},
    'range_bound': {'color': '#F59E0B', 'bg': '#fef3c7', 'name': 'Range-Bound'},
    'weak_bear': {'color': '#F97316', 'bg': '#fff7ed', 'name': 'Weak Bear'},
    'panic_crash': {'color': '#EF4444', 'bg': '#fee2e2', 'name': 'Panic/Crash'},
    'recovery': {'color': '#06B6D4', 'bg': '#cffafe', 'name': 'Recovery'},
}


@public_router.get("/track-record")
async def get_public_track_record(db: AsyncSession = Depends(get_db)):
    """
    Public track record data — no auth required.
    Returns stitched equity curve from canonical 5-year walk-forward sims + regime periods.
    """
    from app.core.config import settings
    from app.core.database import WalkForwardSimulation, RegimeHistory
    from app.services.regime_forecast_service import regime_forecast_service
    from fastapi.responses import JSONResponse
    import json

    sim_ids = settings.TRACK_RECORD_SIM_IDS

    # Fetch canonical sims
    result = await db.execute(
        select(WalkForwardSimulation).where(
            WalkForwardSimulation.id.in_(sim_ids)
        )
    )
    sims = result.scalars().all()

    if not sims:
        raise HTTPException(status_code=404, detail="Track record data not available")

    # Sort sims by start_date to stitch in order
    sims_by_id = {s.id: s for s in sims}
    ordered_sims = [sims_by_id[sid] for sid in sim_ids if sid in sims_by_id]

    # Stitch equity curves: Year 1 starts at $100k, each subsequent year
    # starts where the previous ended (scale all values proportionally)
    stitched = []
    scale_factor = 1.0
    spy_scale_factor = 1.0

    for i, sim in enumerate(ordered_sims):
        if not sim.equity_curve_json:
            continue

        curve = json.loads(sim.equity_curve_json)
        if not curve:
            continue

        # For first sim, no scaling needed (starts at 100k)
        if i == 0:
            for point in curve:
                stitched.append({
                    "date": point["date"],
                    "equity": round(point["equity"], 2),
                    "spy_equity": round(point.get("spy_equity", 100000), 2),
                })
            if stitched:
                last_equity = stitched[-1]["equity"]
                last_spy = stitched[-1]["spy_equity"]
                scale_factor = last_equity / 100000
                spy_scale_factor = last_spy / 100000
        else:
            # Scale this year's curve so it starts where previous ended
            first_equity = curve[0]["equity"]
            first_spy = curve[0].get("spy_equity", 100000)
            year_equity_scale = (scale_factor * 100000) / first_equity if first_equity else 1
            year_spy_scale = (spy_scale_factor * 100000) / first_spy if first_spy else 1

            # Skip first point (overlap with previous year's last point)
            for point in curve[1:]:
                stitched.append({
                    "date": point["date"],
                    "equity": round(point["equity"] * year_equity_scale, 2),
                    "spy_equity": round(point.get("spy_equity", 100000) * year_spy_scale, 2),
                })

            if stitched:
                last_equity = stitched[-1]["equity"]
                last_spy = stitched[-1]["spy_equity"]
                scale_factor = last_equity / 100000
                spy_scale_factor = last_spy / 100000

    # Get regime periods for the same date range
    regime_data = await regime_forecast_service.get_regime_periods_from_db(
        db, start_date="2021-02-01", end_date="2026-02-01"
    )
    regime_periods = regime_data.get("periods", []) if regime_data else []

    # Compute final metrics from stitched curve
    total_return = 0
    benchmark_return = 0
    if stitched:
        total_return = round((stitched[-1]["equity"] / stitched[0]["equity"] - 1) * 100, 1)
        benchmark_return = round((stitched[-1]["spy_equity"] / stitched[0]["spy_equity"] - 1) * 100, 1)

    response_data = {
        "equity_curve": stitched,
        "regime_periods": regime_periods,
        "metrics": {
            "total_return_pct": total_return,
            "benchmark_return_pct": benchmark_return,
            "sharpe_median": 1.02,
            "max_drawdown_pct": -15.1,
            "win_rate": 80,
        },
    }

    response = JSONResponse(content=response_data)
    response.headers["Cache-Control"] = "public, max-age=86400"
    return response


@public_router.get("/regime-report")
async def get_public_regime_report(db: AsyncSession = Depends(get_db)):
    """
    Public regime report data — no auth required.
    Serves the /market-regime page with regime status, history, and forecast.
    """
    from app.services.regime_forecast_service import regime_forecast_service
    import json

    # get_forecast_history returns ascending order (oldest first)
    history = await regime_forecast_service.get_forecast_history(db, days=30)

    if not history:
        return {
            'current': None,
            'history': [],
            'week_over_week': None,
            'transition_probabilities': [],
        }

    # Current regime (most recent snapshot — last element in ascending list)
    latest = history[-1]
    regime_key = latest.get('regime', 'range_bound')
    regime_meta = REGIME_COLORS.get(regime_key, REGIME_COLORS['range_bound'])

    # Week-over-week comparison (7 days back from end)
    week_ago_idx = max(0, len(history) - 7)
    week_ago = history[week_ago_idx]
    wow_change = None
    if week_ago:
        prev_regime = week_ago.get('regime', '')
        if prev_regime == regime_key:
            wow_change = f"Held at {regime_meta['name']}"
        else:
            prev_meta = REGIME_COLORS.get(prev_regime, {})
            wow_change = f"Shifted: {prev_meta.get('name', prev_regime)} → {regime_meta['name']}"

    # Days in current regime — query ALL snapshots (not just 30-day window)
    # to find the true duration since the last regime change
    full_history = await regime_forecast_service.get_forecast_history(db, days=730)
    days_in_regime = 1
    prior_regime = None
    for snap in reversed(full_history[:-1]):
        if snap.get('regime') == regime_key:
            days_in_regime += 1
        else:
            prior_regime_key = snap.get('regime', '')
            prior_meta = REGIME_COLORS.get(prior_regime_key, {})
            prior_regime = {
                'regime': prior_regime_key,
                'name': prior_meta.get('name', prior_regime_key),
                'color': prior_meta.get('color', '#6b7280'),
                'date': snap.get('date', ''),
            }
            break

    # Parse transition probabilities from latest snapshot
    transition_probs = []
    probs_raw = latest.get('probabilities')
    if probs_raw:
        probs = probs_raw if isinstance(probs_raw, dict) else json.loads(probs_raw) if isinstance(probs_raw, str) else {}
        for regime, prob in sorted(probs.items(), key=lambda x: -x[1]):
            meta = REGIME_COLORS.get(regime, {})
            transition_probs.append({
                'regime': regime,
                'name': meta.get('name', regime),
                'color': meta.get('color', '#6b7280'),
                'probability': round(prob, 1),
            })

    # Build history timeline (already ascending = oldest→newest, left→right)
    timeline = []
    for snap in history:
        r = snap.get('regime', 'range_bound')
        meta = REGIME_COLORS.get(r, REGIME_COLORS['range_bound'])
        timeline.append({
            'date': snap.get('date', ''),
            'regime': r,
            'name': meta['name'],
            'color': meta['color'],
            'spy_close': snap.get('spy_close'),
            'vix_close': snap.get('vix_close'),
        })

    return {
        'current': {
            'regime': regime_key,
            'name': regime_meta['name'],
            'color': regime_meta['color'],
            'bg': regime_meta['bg'],
            'outlook': latest.get('outlook', ''),
            'recommended_action': latest.get('recommended_action', ''),
            'risk_change': latest.get('risk_change', ''),
            'spy_close': latest.get('spy_close'),
            'vix_close': latest.get('vix_close'),
            'days_in_regime': days_in_regime,
        },
        'week_over_week': wow_change,
        'prior_regime': prior_regime,
        'transition_probabilities': transition_probs[:5],
        'history': timeline,
    }


class SubscribeRequest(BaseModel):
    email: str
    turnstile_token: str
    source: str = "regime_report"


@public_router.post("/subscribe")
async def public_subscribe(
    req: SubscribeRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Subscribe an email to the free weekly regime report. No account needed.
    """
    from app.services.turnstile import verify_turnstile
    import re

    # Basic email validation
    if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', req.email):
        raise HTTPException(status_code=400, detail="Invalid email address")

    # Verify Turnstile
    turnstile_ok = await verify_turnstile(req.turnstile_token)
    if not turnstile_ok:
        raise HTTPException(status_code=400, detail="Verification failed. Please try again.")

    email_lower = req.email.strip().lower()

    # Check if already exists
    result = await db.execute(
        select(EmailSubscriber).where(EmailSubscriber.email == email_lower)
    )
    existing = result.scalar_one_or_none()

    if existing:
        if existing.is_active:
            return {"success": True, "message": "You're already subscribed!"}
        # Reactivate
        existing.is_active = True
        existing.unsubscribed_at = None
        await db.commit()
        return {"success": True, "message": "Welcome back! You've been resubscribed."}

    # New subscriber
    subscriber = EmailSubscriber(
        email=email_lower,
        source=req.source,
    )
    db.add(subscriber)
    await db.commit()
    return {"success": True, "message": "You're in! Watch for your first report on Monday."}


@public_router.get("/unsubscribe")
async def public_unsubscribe(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Unsubscribe from the regime report via JWT-signed link.
    Returns a simple HTML page.
    """
    from jose import jwt as jose_jwt, JWTError
    from app.core.config import settings
    from fastapi.responses import HTMLResponse

    try:
        payload = jose_jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        subscriber_id = payload.get("sub")
        purpose = payload.get("purpose")
        if purpose != "regime_unsubscribe" or not subscriber_id:
            raise JWTError("Invalid token")
    except JWTError:
        return HTMLResponse(
            content='<html><body style="font-family:sans-serif;text-align:center;padding:60px;background:#0f172a;color:#e2e8f0;">'
            '<h2>Invalid or expired link</h2><p>Please contact support@rigacap.com</p></body></html>',
            status_code=400,
        )

    result = await db.execute(
        select(EmailSubscriber).where(EmailSubscriber.id == int(subscriber_id))
    )
    subscriber = result.scalar_one_or_none()

    if subscriber and subscriber.is_active:
        subscriber.is_active = False
        subscriber.unsubscribed_at = datetime.utcnow()
        await db.commit()

    return HTMLResponse(
        content='<html><body style="font-family:sans-serif;text-align:center;padding:60px;background:#0f172a;color:#e2e8f0;">'
        '<h2 style="color:#f59e0b;">Unsubscribed</h2>'
        '<p>You\'ve been removed from the weekly regime report.</p>'
        '<p style="margin-top:24px;"><a href="https://rigacap.com" style="color:#818cf8;">Back to RigaCap</a></p>'
        '</body></html>',
    )
