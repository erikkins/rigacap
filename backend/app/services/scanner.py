"""
Scanner Service - Core trading signal generation

Implements the optimized DWAP strategy:
- Buy: Price > DWAP × 1.05
- Stop: 8%
- Target: 20%

Supports full NASDAQ + NYSE universe (~6000 stocks)
"""

import gc
import resource

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, asdict
import asyncio
import logging

try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False

from app.core.config import settings, get_universe, EXCLUDED_SYMBOLS
from app.services.stock_universe import EXCLUDED_PATTERNS

logger = logging.getLogger(__name__)

# Fast set lookup for excluded symbols — union of both lists (single source of truth)
_EXCLUDED_SET = set(EXCLUDED_PATTERNS) | set(EXCLUDED_SYMBOLS)


@dataclass
class SignalData:
    """Trading signal data (legacy DWAP)"""
    symbol: str
    signal_type: str
    price: float
    dwap: float
    pct_above_dwap: float
    volume: int
    volume_ratio: float
    stop_loss: float
    profit_target: float
    ma_50: float
    ma_200: float
    high_52w: float
    is_strong: bool
    timestamp: str
    # New fields for enhanced analysis
    signal_strength: float = 0.0  # 0-100 composite score
    sector: str = ""
    recommendation: str = ""

    def to_dict(self):
        return asdict(self)


@dataclass
class MomentumSignalData:
    """Momentum-based trading signal data (v2 strategy)"""
    symbol: str
    rank: int
    price: float
    short_momentum: float  # 10-day momentum %
    long_momentum: float   # 60-day momentum %
    volatility: float      # Annualized volatility %
    composite_score: float # Weighted score for ranking
    ma_20: float
    ma_50: float
    dist_from_50d_high: float  # % below 50-day high (0 = at high)
    passes_quality_filter: bool
    trailing_stop: float
    timestamp: str
    sector: str = ""
    recommendation: str = ""

    def to_dict(self):
        return asdict(self)


class ScannerService:
    """
    Stock scanner service

    Scans universe for DWAP-based buy signals.
    Supports dynamic universe from NASDAQ + NYSE.
    Auto-loads full universe from S3 cache on startup.
    """

    # Required symbols that are always fetched (for market regime, benchmark, etc.)
    REQUIRED_SYMBOLS = ['SPY', '^VIX']

    def __init__(self):
        # Start with config universe, will be replaced by full universe on load
        self.universe = get_universe()
        self.data_cache: Dict[str, pd.DataFrame] = {}
        self.last_scan: Optional[datetime] = None
        self.signals: List[SignalData] = []
        self.full_universe_loaded = False

    async def load_full_universe(self, max_cache_age_hours: int = 168):
        """
        Load full NASDAQ + NYSE universe from S3 cache or fetch fresh.

        Uses 7-day cache by default since the stock universe doesn't change frequently.
        This replaces the default 80-stock list with all tradeable stocks (~6500).

        Args:
            max_cache_age_hours: Max age of cached universe (default 168 = 7 days)
        """
        try:
            from app.services.stock_universe import stock_universe_service

            # Use ensure_loaded which checks cache first
            symbols = await stock_universe_service.ensure_loaded(max_cache_age_hours=max_cache_age_hours)
            if symbols and len(symbols) > 100:
                self.universe = symbols
                self.full_universe_loaded = True
                logger.info(f"Loaded full universe: {len(self.universe)} symbols")
            else:
                logger.warning(f"Universe load returned only {len(symbols) if symbols else 0} symbols, keeping default")
            return self.universe
        except Exception as e:
            logger.error(f"Failed to load full universe: {e}")
            return self.universe

    async def ensure_universe_loaded(self):
        """
        Ensure the full universe is loaded.
        Called on Lambda cold start.
        """
        if not self.full_universe_loaded or len(self.universe) < 100:
            await self.load_full_universe()
    
    # =========================================================================
    # INDICATORS
    # =========================================================================
    
    @staticmethod
    def dwap(prices: pd.Series, volumes: pd.Series, period: int = 200) -> pd.Series:
        """Daily Weighted Average Price"""
        pv = prices * volumes
        return pv.rolling(period, min_periods=50).sum() / volumes.rolling(period, min_periods=50).sum()
    
    @staticmethod
    def sma(series: pd.Series, period: int) -> pd.Series:
        """Simple Moving Average"""
        return series.rolling(period, min_periods=1).mean()
    
    @staticmethod
    def high_52w(prices: pd.Series) -> pd.Series:
        """52-week rolling high"""
        return prices.rolling(252, min_periods=1).max()

    @staticmethod
    def momentum(prices: pd.Series, period: int) -> pd.Series:
        """Price momentum (% change over period)"""
        return (prices / prices.shift(period) - 1) * 100

    @staticmethod
    def volatility(prices: pd.Series, period: int = 20) -> pd.Series:
        """Annualized volatility"""
        returns = prices.pct_change()
        return returns.rolling(period).std() * np.sqrt(252) * 100

    @staticmethod
    def distance_from_high(prices: pd.Series, period: int = 50) -> pd.Series:
        """% below rolling high (0 = at high, negative = below)"""
        rolling_high = prices.rolling(period, min_periods=1).max()
        return (prices / rolling_high - 1) * 100
    
    # =========================================================================
    # DATA FETCHING
    # =========================================================================

    async def fetch_data(self, symbols: List[str] = None, period: str = "5y") -> Dict[str, pd.DataFrame]:
        """
        Fetch historical data via DualSourceProvider (Alpaca primary, yfinance fallback).
        This fetches FULL historical data - use fetch_incremental() for daily updates.

        Args:
            symbols: List of tickers (default: full universe)
            period: Data period (1y, 2y, 5y, max)

        Returns:
            Dict mapping symbol to DataFrame with indicators
        """
        symbols = symbols or self.universe

        # Always include required symbols (SPY for benchmark, ^VIX for market regime)
        symbols_set = set(symbols)
        for req in self.REQUIRED_SYMBOLS:
            if req not in symbols_set:
                symbols = list(symbols) + [req]
                symbols_set.add(req)

        # Convert period to start_date for provider API
        period_days = {"1y": 365, "2y": 730, "5y": 1825, "max": 7300}
        days = period_days.get(period, 1825)
        start_date = (pd.Timestamp.now() - pd.Timedelta(days=days)).strftime("%Y-%m-%d")

        total = len(symbols)
        print(f"📊 Fetching data for {total} symbols via DualSourceProvider...")

        from app.services.market_data_provider import market_data_provider
        bars = await market_data_provider.fetch_bars(symbols, start_date)
        source = market_data_provider.last_bars_source or "unknown"

        successful = 0
        failed = []

        for symbol in symbols:
            df = bars.get(symbol)
            if df is None or len(df) < 50:
                failed.append(symbol)
                continue

            # Compute indicators
            df['dwap'] = self.dwap(df['close'], df['volume'])
            df['ma_50'] = self.sma(df['close'], 50)
            df['ma_200'] = self.sma(df['close'], 200)
            df['vol_avg'] = self.sma(df['volume'], 200)
            df['high_52w'] = self.high_52w(df['close'])

            self.data_cache[symbol] = df
            successful += 1

        print(f"✅ Loaded {successful}/{total} symbols via {source} ({len(failed)} failed)")

        return self.data_cache

    async def fetch_incremental(self, symbols: List[str] = None, replace_days: int = 0) -> Dict[str, int]:
        """
        Fetch only NEW data since the last cached date for each symbol.
        Uses DualSourceProvider (primary source from config, with automatic fallback).

        Args:
            symbols: List of tickers (default: all symbols in cache)
            replace_days: If > 0, re-fetch and overwrite the last N days for ALL cached
                symbols (not just stale ones). Use this to fix volume data after a
                fallback event where the alternate source returned bad data.

        Returns:
            Dict with counts: {updated: N, failed: N, skipped: N, source: str}
        """
        # Use symbols from cache if not specified
        symbols = symbols or list(self.data_cache.keys())
        if not symbols:
            logger.warning("No symbols to update - cache is empty")
            return {"updated": 0, "failed": 0, "skipped": 0}

        from datetime import timedelta
        from app.services.market_data_provider import market_data_provider

        updated = 0
        failed = 0
        skipped = 0

        today = pd.Timestamp.now().normalize().tz_localize(None)

        # Log memory at start
        rss_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024)
        logger.info(f"📊 Incremental update for {len(symbols)} symbols (RSS: {rss_mb:.0f} MB)"
                     + (f" [replace_days={replace_days}]" if replace_days else ""))

        # Indicator columns to drop — lazy recompute during scan() is more efficient
        INDICATOR_COLS = [
            'dwap', 'ma_50', 'ma_200', 'vol_avg', 'high_52w',
            'short_mom', 'long_mom', 'volatility', 'ma_20', 'dist_from_50d_high',
        ]

        if replace_days > 0:
            # Replace mode: re-fetch last N days for all cached symbols
            cutoff = today - timedelta(days=replace_days)
            symbols_to_update = [s for s in symbols if s in self.data_cache and len(self.data_cache[s]) > 0]
            start_date = (cutoff - timedelta(days=2)).strftime('%Y-%m-%d')
            logger.info(f"🔄 Replace mode: re-fetching last {replace_days} days for {len(symbols_to_update)} symbols from {start_date}")
        else:
            # Normal mode: only fetch new data for stale symbols
            oldest_last_date = today
            symbols_to_update = []
            for symbol in symbols:
                if symbol not in self.data_cache or len(self.data_cache[symbol]) == 0:
                    skipped += 1
                    continue
                last_date = self.data_cache[symbol].index.max()
                if hasattr(last_date, 'tz') and last_date.tz is not None:
                    last_date = last_date.tz_localize(None)
                last_date = pd.Timestamp(last_date).normalize()
                if last_date >= today - timedelta(days=1):
                    skipped += 1
                    continue
                symbols_to_update.append(symbol)
                if last_date < oldest_last_date:
                    oldest_last_date = last_date

            if not symbols_to_update:
                logger.info(f"✅ Incremental update: all {len(symbols)} symbols already up to date")
                return {"updated": 0, "failed": 0, "skipped": skipped}

            # Fetch from oldest_last_date to now (add buffer for safety)
            start_date = (oldest_last_date - timedelta(days=5)).strftime('%Y-%m-%d')

        logger.info(f"📡 Fetching incremental data for {len(symbols_to_update)} symbols from {start_date}...")
        bars = await market_data_provider.fetch_bars(symbols_to_update, start_date)
        source = market_data_provider.last_bars_source or "unknown"

        for symbol in symbols_to_update:
            try:
                new_df = bars.get(symbol)
                if new_df is None or new_df.empty:
                    skipped += 1
                    continue

                # Get existing data
                existing_df = self.data_cache[symbol]

                # Strip tz from new data for consistent comparison
                if hasattr(new_df.index, 'tz') and new_df.index.tz is not None:
                    new_df.index = new_df.index.tz_localize(None)

                # Strip tz from existing data too (pickles may have mixed tz)
                if hasattr(existing_df.index, 'tz') and existing_df.index.tz is not None:
                    existing_df = existing_df.copy()
                    existing_df.index = existing_df.index.tz_localize(None)
                    self.data_cache[symbol] = existing_df

                if replace_days > 0:
                    # Replace mode: drop old rows in the replace window, use fresh data
                    cutoff_ts = today - timedelta(days=replace_days)
                    keep_old = existing_df[existing_df.index < cutoff_ts][['open', 'high', 'low', 'close', 'volume']]
                    new_rows = new_df[new_df.index >= cutoff_ts][['open', 'high', 'low', 'close', 'volume']]
                    combined = pd.concat([keep_old, new_rows])
                else:
                    # Normal mode: only append truly new rows
                    last_cached_date = existing_df.index.max()
                    new_rows = new_df[new_df.index > last_cached_date]
                    if new_rows.empty:
                        skipped += 1
                        continue
                    combined = pd.concat([existing_df[['open', 'high', 'low', 'close', 'volume']],
                                        new_rows[['open', 'high', 'low', 'close', 'volume']]])

                combined = combined[~combined.index.duplicated(keep='last')]
                combined = combined.sort_index()

                # Drop stale indicator columns — recomputed lazily during scan()
                combined = combined.drop(
                    columns=[c for c in INDICATOR_COLS if c in combined.columns],
                    errors='ignore',
                )

                self.data_cache[symbol] = combined
                updated += 1

            except Exception as e:
                logger.warning(f"❌ Failed to update {symbol}: {e}")
                failed += 1

        # Free bulk fetch result and reclaim memory
        del bars
        gc.collect()
        rss_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024)
        logger.info(f"✅ Incremental update complete: {updated} updated, {skipped} skipped, {failed} failed via {source} (RSS: {rss_mb:.0f} MB)")

        # NaN guard: drop last row if close price is NaN or <= 0
        nan_dropped = 0
        for symbol in list(self.data_cache.keys()):
            df = self.data_cache[symbol]
            if df is not None and len(df) > 0:
                last_row = df.iloc[-1]
                if pd.isna(last_row.get('close')) or (last_row.get('close', 0) <= 0):
                    logger.warning(f"{symbol}: Invalid close price {last_row.get('close')}, dropping last row")
                    self.data_cache[symbol] = df.iloc[:-1]
                    nan_dropped += 1
        if nan_dropped:
            logger.warning(f"⚠️ Dropped {nan_dropped} symbols with NaN/invalid close prices")

        return {"updated": updated, "failed": failed, "skipped": skipped, "source": source}

    def validate_data_continuity(self, lookback_days: int = 30) -> Dict[str, list]:
        """
        Detect symbols with missing business days in recent data.
        Returns dict of {symbol: [missing_date, ...]} for symbols with >2 gaps.
        """
        gapped = {}
        cutoff_date = (pd.Timestamp.now().normalize() - pd.Timedelta(days=lookback_days)).date()
        for symbol, df in self.data_cache.items():
            if df is None or df.empty:
                continue
            # Compare on date level to avoid tz-naive/aware mismatch
            dates = [d.date() if hasattr(d, 'date') else d for d in df.index]
            recent_dates = [d for d in dates if d >= cutoff_date]
            if len(recent_dates) < 2:
                continue
            expected = pd.bdate_range(min(recent_dates), max(recent_dates))
            expected_dates = set(d.date() for d in expected)
            actual = set(recent_dates)
            missing = expected_dates - actual
            if len(missing) > 2:  # Allow 1-2 gaps (holidays)
                gapped[symbol] = sorted(str(d) for d in missing)
        return gapped

    # =========================================================================
    # SIGNAL GENERATION
    # =========================================================================
    
    def _ensure_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute indicators if missing from DataFrame (lazy computation)"""
        if 'dwap' not in df.columns:
            df = df.copy()
            df['dwap'] = self.dwap(df['close'], df['volume'])
            df['ma_50'] = self.sma(df['close'], 50)
            df['ma_200'] = self.sma(df['close'], 200)
            df['vol_avg'] = self.sma(df['volume'], 200)
            df['high_52w'] = self.high_52w(df['close'])
        return df

    def _get_signal_universe(self) -> Optional[Set[str]]:
        """Return set of liquid symbols if SIGNAL_UNIVERSE_SIZE is configured, else None (no filter)."""
        size = settings.SIGNAL_UNIVERSE_SIZE
        if size <= 0:
            return None
        from app.services.strategy_analyzer import get_top_liquid_symbols
        symbols = set(get_top_liquid_symbols(max_symbols=size))
        logger.info(f"Signal universe filter active: top {size} liquid symbols ({len(symbols)} found)")
        return symbols

    def _ensure_momentum_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute momentum indicators if missing (lazy computation)"""
        if 'short_mom' not in df.columns:
            df = df.copy()
            df['short_mom'] = self.momentum(df['close'], settings.SHORT_MOMENTUM_DAYS)
            df['long_mom'] = self.momentum(df['close'], settings.LONG_MOMENTUM_DAYS)
            df['volatility'] = self.volatility(df['close'], 20)
            df['ma_20'] = self.sma(df['close'], 20)
            df['ma_50'] = self.sma(df['close'], 50)
            df['dist_from_50d_high'] = self.distance_from_high(df['close'], 50)
        return df

    def rank_stocks_momentum(self, apply_market_filter: bool = True, as_of_date=None, regime_params: dict = None) -> List[MomentumSignalData]:
        """
        Rank all stocks by momentum composite score (v2 strategy)

        Scoring: short_mom * 0.5 + long_mom * 0.3 - volatility * 0.2

        Quality filters:
        - Price > MA20 and MA50 (uptrend)
        - Within 5% of 50-day high (breakout zone)
        - Volume > MIN_VOLUME
        - Price > MIN_PRICE

        Returns:
            List of MomentumSignalData sorted by composite score (highest first)
        """
        # Check market regime if enabled
        if apply_market_filter and settings.MARKET_FILTER_ENABLED:
            try:
                from app.services.market_analysis import market_analysis_service
                market_state = market_analysis_service.get_market_regime()
                if market_state and not market_state.get('spy_above_200ma', True):
                    logger.info("Market filter: SPY below 200MA, returning empty signals")
                    return []
            except Exception as e:
                logger.warning(f"Market filter check failed: {e}")

        candidates = []
        signal_universe = self._get_signal_universe()

        for symbol in self.data_cache:
            if signal_universe is not None and symbol not in signal_universe:
                continue
            if symbol in _EXCLUDED_SET:
                continue

            df = self.data_cache[symbol]
            if len(df) < settings.LONG_MOMENTUM_DAYS + 20:
                continue

            # Ensure momentum indicators are computed
            df = self._ensure_momentum_indicators(df)
            self.data_cache[symbol] = df

            # Time-travel: truncate to as_of_date after indicators computed on full df
            if as_of_date:
                as_of_ts = pd.Timestamp(as_of_date).normalize()
                if hasattr(df.index, 'tz') and df.index.tz is not None:
                    as_of_ts = as_of_ts.tz_localize(df.index.tz)
                df = df[df.index <= as_of_ts]
                if len(df) < settings.LONG_MOMENTUM_DAYS + 20:
                    continue

            row = df.iloc[-1]
            price = row['close']
            volume = row.get('volume', 0)
            short_mom = row.get('short_mom', np.nan)
            long_mom = row.get('long_mom', np.nan)
            vol = row.get('volatility', np.nan)
            ma_20 = row.get('ma_20', 0)
            ma_50 = row.get('ma_50', 0)
            dist_from_high = row.get('dist_from_50d_high', -100)

            # Skip invalid data
            if pd.isna(short_mom) or pd.isna(long_mom) or pd.isna(vol):
                continue

            # Apply basic filters
            if price < settings.MIN_PRICE or volume < settings.MIN_VOLUME:
                continue

            # Quality filter: uptrend (price > MA20 and MA50)
            passes_trend = price > ma_20 > 0 and price > ma_50 > 0

            # Quality filter: near 50-day high (within NEAR_50D_HIGH_PCT)
            near_50d_high = regime_params.get('near_50d_high_pct', settings.NEAR_50D_HIGH_PCT) if regime_params else settings.NEAR_50D_HIGH_PCT
            passes_breakout = dist_from_high >= -near_50d_high

            passes_quality = passes_trend and passes_breakout

            # Calculate composite score
            composite_score = (
                short_mom * settings.SHORT_MOM_WEIGHT +
                long_mom * settings.LONG_MOM_WEIGHT -
                vol * settings.VOLATILITY_PENALTY
            )

            # Calculate trailing stop
            trailing_stop_pct = regime_params.get('trailing_stop_pct', settings.TRAILING_STOP_PCT) if regime_params else settings.TRAILING_STOP_PCT
            trailing_stop = price * (1 - trailing_stop_pct / 100)

            signal_ts = str(as_of_date)[:10] if as_of_date else datetime.now().isoformat()
            candidates.append(MomentumSignalData(
                symbol=symbol,
                rank=0,  # Will be set after sorting
                price=round(price, 2),
                short_momentum=round(short_mom, 2),
                long_momentum=round(long_mom, 2),
                volatility=round(vol, 2),
                composite_score=round(composite_score, 2),
                ma_20=round(ma_20, 2),
                ma_50=round(ma_50, 2),
                dist_from_50d_high=round(dist_from_high, 2),
                passes_quality_filter=passes_quality,
                trailing_stop=round(trailing_stop, 2),
                timestamp=signal_ts
            ))

        # Sort by composite score (highest first), prioritizing quality filter pass
        candidates.sort(key=lambda x: (not x.passes_quality_filter, -x.composite_score))

        # Apply sector cap — max N stocks per sector to prevent concentration
        # Only cap sectors we actually have data for; skip cap for unknown sectors
        from app.services.stock_universe import stock_universe_service
        sector_counts: Dict[str, int] = {}
        capped = []
        for c in candidates:
            info = stock_universe_service.get_symbol_info(c.symbol)
            sector = (info.get('sector', '') if info else '') or ''
            c.sector = sector
            if not sector:
                capped.append(c)
            else:
                count = sector_counts.get(sector, 0)
                if count < settings.MOMENTUM_SECTOR_CAP:
                    capped.append(c)
                    sector_counts[sector] = count + 1
        candidates = capped

        # Assign ranks
        for i, c in enumerate(candidates):
            c.rank = i + 1

        logger.info(f"Momentum ranking complete: {len(candidates)} candidates, "
                   f"{sum(1 for c in candidates if c.passes_quality_filter)} pass quality filter")

        return candidates

    def analyze_stock(self, symbol: str, as_of_date=None) -> Optional[SignalData]:
        """
        Analyze single stock for buy signals

        Buy conditions:
        - Price > DWAP × (1 + threshold)
        - Volume > minimum
        - Price > minimum

        Strong signal (bonus):
        - Volume > avg × spike_mult
        - Price > MA50 > MA200 (healthy trend)
        """
        if symbol not in self.data_cache:
            return None

        df = self.data_cache[symbol]
        if len(df) < 200:
            return None

        # Ensure indicators are computed (lazy computation)
        df = self._ensure_indicators(df)
        self.data_cache[symbol] = df  # Cache the computed indicators

        # Time-travel: truncate to as_of_date after indicators computed on full df
        if as_of_date:
            as_of_ts = pd.Timestamp(as_of_date).normalize()
            if hasattr(df.index, 'tz') and df.index.tz is not None:
                as_of_ts = as_of_ts.tz_localize(df.index.tz)
            df = df[df.index <= as_of_ts]
            if len(df) < 200:
                return None

        # Current values
        row = df.iloc[-1]
        price = row['close']
        volume = row['volume']
        current_dwap = row.get('dwap', np.nan)
        vol_avg = row.get('vol_avg', 1)
        ma_50 = row.get('ma_50', 0)
        ma_200 = row.get('ma_200', 0)
        h_52w = row.get('high_52w', price)
        
        # Skip if DWAP invalid
        if pd.isna(current_dwap) or current_dwap <= 0:
            return None
        
        # Calculate metrics
        pct_above_dwap = (price / current_dwap - 1) * 100
        vol_ratio = volume / vol_avg if vol_avg > 0 else 0
        
        # Check buy conditions
        is_buy = (
            pct_above_dwap >= settings.DWAP_THRESHOLD_PCT and
            volume >= settings.MIN_VOLUME and
            price >= settings.MIN_PRICE
        )
        
        if not is_buy:
            return None
        
        # Strong signal check
        is_strong = (
            vol_ratio >= settings.VOLUME_SPIKE_MULT and
            price > ma_50 > ma_200
        )
        
        # Calculate stops/targets
        stop_loss = price * (1 - settings.STOP_LOSS_PCT / 100)
        profit_target = price * (1 + settings.PROFIT_TARGET_PCT / 100)
        
        signal_ts = str(as_of_date)[:10] if as_of_date else datetime.now().isoformat()
        return SignalData(
            symbol=symbol,
            signal_type='BUY',
            price=round(price, 2),
            dwap=round(current_dwap, 2),
            pct_above_dwap=round(pct_above_dwap, 1),
            volume=int(volume),
            volume_ratio=round(vol_ratio, 2),
            stop_loss=round(stop_loss, 2),
            profit_target=round(profit_target, 2),
            ma_50=round(ma_50, 2),
            ma_200=round(ma_200, 2),
            high_52w=round(h_52w, 2),
            is_strong=is_strong,
            timestamp=signal_ts
        )
    
    async def scan(
        self,
        refresh_data: bool = True,
        apply_market_filter: bool = True,
        min_signal_strength: float = 0,
        as_of_date=None
    ) -> List[SignalData]:
        """
        Run full market scan with market regime awareness

        Args:
            refresh_data: Whether to fetch fresh data
            apply_market_filter: Apply market regime filtering
            min_signal_strength: Minimum signal strength to include (0-100)

        Returns:
            List of SignalData objects sorted by signal strength
        """
        # Time-travel mode: never refresh data (we need historical data intact)
        if as_of_date:
            refresh_data = False

        # In Lambda mode, always try to load from S3 cache first (faster than yfinance)
        import os
        is_lambda = os.environ.get("ENVIRONMENT") == "prod"

        print(f"🔍 Scan called: is_lambda={is_lambda}, data_cache_size={len(self.data_cache)}, refresh_data={refresh_data}")

        if not self.data_cache and is_lambda:
            try:
                from app.services.data_export import data_export_service
                print("📥 Lambda cold start - loading price data from S3...")
                cached_data = data_export_service.import_all()
                if cached_data:
                    self.data_cache = cached_data
                    print(f"✅ Loaded {len(cached_data)} symbols from S3 cache")
                else:
                    print("⚠️ S3 import returned empty data")
            except Exception as e:
                import traceback
                print(f"❌ Failed to load from S3: {e}")
                print(traceback.format_exc())

        # In Lambda mode with S3 data, skip yfinance refresh (use cached data)
        # In local mode or if no S3 data, fetch from yfinance
        should_fetch = (refresh_data and not is_lambda) or not self.data_cache
        if should_fetch:
            await self.fetch_data()

        # Update market analysis and check regime
        market_available = False
        market_favorable = True  # Default to favorable if we can't check

        try:
            from app.services.market_analysis import market_analysis_service
            await market_analysis_service.update_market_state()
            await market_analysis_service.update_sector_strength()
            market_available = True

            # Check if SPY is above 200-day MA (market filter)
            if settings.MARKET_FILTER_ENABLED:
                market_state = market_analysis_service.get_market_regime()
                if market_state:
                    market_favorable = market_state.get('spy_above_200ma', True)
                    if not market_favorable:
                        logger.info("Market filter active: SPY below 200MA, returning empty signals")
                        return []
        except Exception as e:
            logger.warning(f"Market analysis unavailable: {e}")

        self.signals = []
        signal_universe = self._get_signal_universe()

        for symbol in self.data_cache:
            if signal_universe is not None and symbol not in signal_universe:
                continue
            if symbol in _EXCLUDED_SET:
                continue
            signal = self.analyze_stock(symbol, as_of_date=as_of_date)
            if not signal:
                continue

            # Calculate signal strength
            if market_available:
                signal.signal_strength = market_analysis_service.calculate_signal_strength(
                    pct_above_dwap=signal.pct_above_dwap,
                    volume_ratio=signal.volume_ratio,
                    is_strong=signal.is_strong,
                    sector=signal.sector
                )

                # Apply market regime filter
                if apply_market_filter:
                    should_take, reason = market_analysis_service.should_take_signal(signal.signal_strength)
                    signal.recommendation = reason
                    if not should_take:
                        continue
            else:
                # Default strength calculation without market data
                signal.signal_strength = (
                    min(signal.pct_above_dwap * 5, 30) +
                    min((signal.volume_ratio - 1) * 15, 30) +
                    (25 if signal.is_strong else 0)
                )
                signal.recommendation = "Market data unavailable"

            # Apply minimum strength filter
            if signal.signal_strength < min_signal_strength:
                continue

            self.signals.append(signal)

        # Sort by signal strength (highest first)
        self.signals.sort(key=lambda s: -s.signal_strength)

        self.last_scan = datetime.now()

        logger.info(f"Scan complete: {len(self.signals)} signals found")

        return self.signals
    
    def get_strong_signals(self) -> List[SignalData]:
        """Get only strong signals"""
        return [s for s in self.signals if s.is_strong]
    
    def get_watchlist(self, threshold: float = 3.0) -> List[SignalData]:
        """Get stocks approaching DWAP threshold"""
        watchlist = []
        
        for symbol, df in self.data_cache.items():
            if len(df) < 200:
                continue
            
            row = df.iloc[-1]
            price = row['close']
            dwap = row['dwap']
            
            if pd.isna(dwap) or dwap <= 0:
                continue
            
            pct_above = (price / dwap - 1) * 100
            
            # Approaching but not yet at threshold
            if threshold <= pct_above < settings.DWAP_THRESHOLD_PCT:
                watchlist.append({
                    'symbol': symbol,
                    'price': round(price, 2),
                    'dwap': round(dwap, 2),
                    'pct_above_dwap': round(pct_above, 1)
                })
        
        return sorted(watchlist, key=lambda x: -x['pct_above_dwap'])


    def generate_sell_signals(
        self,
        positions: List[dict],
        regime_forecast=None,
        trailing_stop_pct: float = 12.0,
    ) -> List[dict]:
        """
        For each position, determine: HOLD, WARNING, or SELL.

        Args:
            positions: List of position dicts with at least symbol, entry_price, shares,
                       and optionally highest_price (tracked high water mark)
            regime_forecast: RegimeForecast from market_regime.py (optional)
            trailing_stop_pct: Trailing stop percentage (default 12%)

        Returns:
            List of position dicts with added sell guidance fields.
        """
        results = []

        for pos in positions:
            symbol = pos.get('symbol', '')
            entry_price = pos.get('entry_price', 0)
            stored_highest = pos.get('highest_price', entry_price)

            # Look up current price
            current_price = None
            if symbol in self.data_cache and len(self.data_cache[symbol]) > 0:
                current_price = float(self.data_cache[symbol].iloc[-1]['close'])
            else:
                current_price = pos.get('current_price', entry_price)

            # Calculate high water mark
            high_water_mark = max(entry_price, stored_highest or entry_price, current_price or entry_price)

            # Calculate trailing stop
            trailing_stop_level = high_water_mark * (1 - trailing_stop_pct / 100)
            distance_to_stop_pct = (
                (current_price - trailing_stop_level) / trailing_stop_level * 100
                if trailing_stop_level > 0 else 100
            )

            # P&L from entry
            pnl_pct = ((current_price - entry_price) / entry_price * 100) if entry_price > 0 else 0

            # Determine action
            action = "hold"
            action_reason = ""

            # Check regime-based exits first
            if regime_forecast:
                rec = regime_forecast.recommended_action
                if rec == "go_to_cash":
                    action = "sell"
                    action_reason = f"Market regime exit — {regime_forecast.outlook_detail}"
                elif rec == "reduce_exposure":
                    action = "warning"
                    action_reason = f"Regime deteriorating — consider reducing exposure"
                elif rec == "tighten_stops":
                    if action != "sell":
                        action = "warning"
                        action_reason = f"Tighten stops — {regime_forecast.outlook_detail}"

            # Check trailing stop (overrides regime warning if triggered)
            if current_price <= trailing_stop_level:
                action = "sell"
                action_reason = f"Trailing stop hit — price ${current_price:.2f} below stop ${trailing_stop_level:.2f}"

            # Check proximity to trailing stop (warning zone)
            elif distance_to_stop_pct < 3 and action != "sell":
                action = "warning"
                if not action_reason:
                    action_reason = f"Within {distance_to_stop_pct:.1f}% of trailing stop ${trailing_stop_level:.2f}"

            # Default hold reason
            if action == "hold" and not action_reason:
                action_reason = f"Trailing stop at ${trailing_stop_level:.2f} ({distance_to_stop_pct:.0f}% away)"

            result = {
                **pos,
                'current_price': round(current_price, 2),
                'action': action,
                'action_reason': action_reason,
                'trailing_stop_level': round(trailing_stop_level, 2),
                'distance_to_stop_pct': round(distance_to_stop_pct, 1),
                'high_water_mark': round(high_water_mark, 2),
                'pnl_pct': round(pnl_pct, 1),
            }
            results.append(result)

        return results


# Singleton instance
scanner_service = ScannerService()
