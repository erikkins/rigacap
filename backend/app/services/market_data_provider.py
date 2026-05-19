"""
Market Data Provider — Dual-source abstraction layer

Provides:
- AlpacaProvider: Primary source for bars and quotes via SIP (consolidated) feed
- YfinanceProvider: Fallback for bars/quotes + always used for index symbols
- DualSourceProvider: Orchestrator with automatic failover

Alpaca Pro subscription:
- 10k req/min rate limit, SIP consolidated feed (all exchanges)
- Cannot serve index symbols (^VIX, ^GSPC) — yfinance required for those
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Symbols that Alpaca cannot serve (indices use ^ prefix)
INDEX_SYMBOLS = {'^VIX', '^GSPC', '^DJI', '^IXIC', '^RUT', '^TNX'}

# Symbols that Alpaca COULD serve but we deliberately route through yfinance
# because Alpaca's SIP storage has known per-bar corruption for these names.
#
# SPY (May 19, 2026): Alpaca's SPY 2026-02-02 bar reports low=$68.81 across
# all adjustment modes (RAW, SPLIT, ALL); actual market low was ~$687.54.
# The corruption is in Alpaca's underlying daily bar, not our pipeline.
# yfinance returns the correct value. Reported to Alpaca; routing change
# is the durable fix regardless of their response. Also gives us dividend-
# adjusted ("total return") SPY for benchmark consistency — matches the
# 11y canonical pickle that the Apr 28 marketing baseline was built on.
YFINANCE_PREFERRED = {'SPY'}

# Combined: symbols that always route to yfinance, not Alpaca
YFINANCE_ROUTED = INDEX_SYMBOLS | YFINANCE_PREFERRED


def _validate_bar_sanity(symbol: str, df: pd.DataFrame) -> List[str]:
    """Per-bar sanity check for newly-fetched OHLCV data. Returns a list of
    human-readable violation strings (empty list = clean).

    Catches the class of defect that hit SPY 2026-02-02 (Alpaca stored
    low=$68.81 when surrounding open/high/close were ~$690). Trips when:
      - low <= $0 or > high (logical violation)
      - low < 50% of close AND close >= $20 (off-by-decimal in low)
      - high > 2x close (off-by-decimal in high)
      - intraday range (high - low) / close > 0.5 (95th-percentile sanity;
        legit volatile days top out around 10% intraday — 50% is impossible
        for a real bar)

    SPY-specific extra: lows < $50 are always suspect (SPY has never traded
    that low in the modern era; this would have caught the May 4 corruption
    on landing instead of three weeks later).
    """
    violations = []
    if df is None or df.empty:
        return ["empty dataframe"]
    required = {'open', 'high', 'low', 'close'}
    if not required.issubset(df.columns):
        return [f"missing columns: {required - set(df.columns)}"]

    # Logical inversions / non-positive prices
    bad = df[(df['low'] <= 0) | (df['low'] > df['high'])]
    if len(bad):
        violations.append(f"{len(bad)} bar(s) with low<=0 or low>high (e.g. {bad.index[0].date()})")

    # Off-by-decimal in low (low << close on a non-microcap)
    mid_or_large = df[df['close'] >= 20]
    bad_lo = mid_or_large[mid_or_large['low'] < mid_or_large['close'] * 0.5]
    if len(bad_lo):
        d = bad_lo.index[0].date()
        violations.append(
            f"{len(bad_lo)} bar(s) with low < 50% of close (off-by-decimal suspect; "
            f"e.g. {d}: low={bad_lo['low'].iloc[0]:.2f} vs close={bad_lo['close'].iloc[0]:.2f})"
        )

    # Off-by-decimal in high
    bad_hi = df[df['high'] > df['close'] * 2]
    if len(bad_hi):
        violations.append(f"{len(bad_hi)} bar(s) with high > 2x close (e.g. {bad_hi.index[0].date()})")

    # Crazy intraday range
    rng_pct = (df['high'] - df['low']) / df['close'].clip(lower=0.01)
    bad_rng = df[rng_pct > 0.5]
    if len(bad_rng):
        violations.append(f"{len(bad_rng)} bar(s) with intraday range > 50% of close (e.g. {bad_rng.index[0].date()})")

    # SPY-specific floor — would have caught the May 4 corruption on landing
    if symbol == 'SPY':
        bad_spy = df[df['low'] < 50]
        if len(bad_spy):
            violations.append(
                f"SPY-specific: {len(bad_spy)} bar(s) with low < $50 — SPY has never traded that low "
                f"(e.g. {bad_spy.index[0].date()}: low=${bad_spy['low'].iloc[0]:.2f})"
            )

    return violations


@dataclass
class QuoteData:
    """Live quote for a single symbol."""
    symbol: str
    price: float
    prev_close: Optional[float] = None
    change: Optional[float] = None
    change_pct: Optional[float] = None
    day_high: Optional[float] = None
    timestamp: Optional[str] = None
    source: str = ""


@dataclass
class SourceHealth:
    """Health tracking for a data source."""
    consecutive_failures: int = 0
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    total_requests: int = 0
    total_failures: int = 0


class MarketDataProvider(ABC):
    """Abstract base class for market data providers."""

    @abstractmethod
    async def fetch_bars(
        self, symbols: List[str], start_date: str, end_date: Optional[str] = None
    ) -> Dict[str, pd.DataFrame]:
        """Fetch historical daily OHLCV bars.

        Returns dict mapping symbol -> DataFrame with columns:
        open, high, low, close, volume (DatetimeIndex, tz-naive)
        """
        ...

    @abstractmethod
    async def fetch_quotes(self, symbols: List[str]) -> Dict[str, QuoteData]:
        """Fetch live/current quotes for symbols."""
        ...

    def supports_symbol(self, symbol: str) -> bool:
        """Whether this provider can serve data for a given symbol."""
        return True


class AlpacaProvider(MarketDataProvider):
    """Alpaca Markets data provider (REST API).

    Uses alpaca-py SDK for historical bars via SIP (consolidated) feed.
    Cannot serve index symbols (^VIX, ^GSPC, etc).
    """

    # Symbols that need format conversion: yfinance uses hyphens, Alpaca uses dots
    # e.g. BRK-A → BRK.A, BRK-B → BRK.B, BF-B → BF.B
    @staticmethod
    def _to_alpaca_symbol(symbol: str) -> str:
        """Convert yfinance-format symbol to Alpaca format (hyphens → dots)."""
        return symbol.replace('-', '.')

    @staticmethod
    def _from_alpaca_symbol(symbol: str) -> str:
        """Convert Alpaca-format symbol back to yfinance format (dots → hyphens)."""
        return symbol.replace('.', '-')

    def __init__(self):
        self._client = None
        self._initialized = False

    def _ensure_client(self):
        """Lazy-init Alpaca client to avoid import cost on cold start."""
        if self._initialized:
            return self._client is not None

        self._initialized = True
        try:
            from app.core.config import settings
            if not settings.ALPACA_API_KEY or not settings.ALPACA_SECRET_KEY:
                logger.warning("Alpaca credentials not configured")
                return False

            from alpaca.data.historical import StockHistoricalDataClient
            self._client = StockHistoricalDataClient(
                api_key=settings.ALPACA_API_KEY,
                secret_key=settings.ALPACA_SECRET_KEY,
            )
            logger.info("Alpaca client initialized")
            return True
        except ImportError:
            logger.warning("alpaca-py not installed")
            return False
        except Exception as e:
            print(f"❌ Alpaca client init failed: {e}")
            return False

    def supports_symbol(self, symbol: str) -> bool:
        # YFINANCE_ROUTED = INDEX_SYMBOLS ∪ YFINANCE_PREFERRED (currently {SPY}).
        # Indexes are technically unsupported by Alpaca; SPY is supported but
        # routed away due to known per-bar data corruption.
        return symbol not in YFINANCE_ROUTED

    async def fetch_bars(
        self, symbols: List[str], start_date: str, end_date: Optional[str] = None
    ) -> Dict[str, pd.DataFrame]:
        if not self._ensure_client():
            return {}

        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame
        from alpaca.data.enums import DataFeed

        # Filter out unsupported symbols
        alpaca_symbols = [s for s in symbols if self.supports_symbol(s)]
        if not alpaca_symbols:
            return {}

        # Build symbol mapping: alpaca_format → original_format
        sym_map = {}
        for s in alpaca_symbols:
            a = self._to_alpaca_symbol(s)
            sym_map[a] = s
        alpaca_formatted = list(sym_map.keys())

        result: Dict[str, pd.DataFrame] = {}
        BATCH_SIZE = 100  # Alpaca supports large batches

        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d") if end_date else datetime.now()

        for i in range(0, len(alpaca_formatted), BATCH_SIZE):
            batch = alpaca_formatted[i:i + BATCH_SIZE]

            try:
                # Import Adjustment lazily to match existing import pattern
                from alpaca.data.enums import Adjustment
                request = StockBarsRequest(
                    symbol_or_symbols=batch,
                    timeframe=TimeFrame.Day,
                    start=start_dt,
                    end=end_dt,
                    feed=DataFeed.SIP,  # Pro subscription — consolidated volume
                    adjustment=Adjustment.SPLIT,  # Apply split adjustment (was RAW default); prevents artifact trades from unadjusted splits like NVDA 2024-06-10
                )

                loop = asyncio.get_event_loop()
                bars = await loop.run_in_executor(
                    None, self._client.get_stock_bars, request
                )

                # Convert to per-symbol DataFrames
                # BarSet.data is a dict of symbol -> list[Bar] (Alpaca-format keys)
                bar_data = bars.data if hasattr(bars, 'data') else {}
                if i == 0:  # Log first batch for debugging
                    print(f"🔍 Alpaca batch 0: {len(bar_data)} symbols returned")
                for alpaca_sym in batch:
                    try:
                        symbol_bars = bar_data.get(alpaca_sym, [])
                        if not symbol_bars:
                            continue

                        rows = []
                        for bar in symbol_bars:
                            rows.append({
                                'open': float(bar.open),
                                'high': float(bar.high),
                                'low': float(bar.low),
                                'close': float(bar.close),
                                'volume': int(bar.volume),
                                'date': bar.timestamp,
                            })

                        if not rows:
                            continue

                        df = pd.DataFrame(rows)
                        df['date'] = pd.to_datetime(df['date']).dt.tz_localize(None).dt.normalize()
                        df = df.set_index('date').sort_index()
                        # Remove duplicate dates (keep last)
                        df = df[~df.index.duplicated(keep='last')]
                        # Map back to original symbol format
                        original_sym = sym_map.get(alpaca_sym, alpaca_sym)
                        result[original_sym] = df

                    except Exception as e:
                        import traceback
                        print(f"❌ Alpaca parse error for {alpaca_sym}: {e}")
                        traceback.print_exc()

            except Exception as e:
                import traceback
                print(f"❌ Alpaca batch fetch failed ({len(batch)} symbols): {e}")
                traceback.print_exc()

            # Rate limit: 10k req/min (Pro) — minimal delay between batches
            if i + BATCH_SIZE < len(alpaca_formatted):
                await asyncio.sleep(0.1)

        return result

    async def fetch_quotes(self, symbols: List[str]) -> Dict[str, QuoteData]:
        """Fetch latest quotes from Alpaca via SIP (consolidated) feed."""
        if not self._ensure_client():
            return {}

        from alpaca.data.requests import StockLatestQuoteRequest
        from alpaca.data.enums import DataFeed

        alpaca_symbols = [s for s in symbols if self.supports_symbol(s)]
        if not alpaca_symbols:
            return {}

        # Build symbol mapping: alpaca_format → original_format
        sym_map = {}
        for s in alpaca_symbols:
            a = self._to_alpaca_symbol(s)
            sym_map[a] = s
        alpaca_formatted = list(sym_map.keys())

        result: Dict[str, QuoteData] = {}
        try:
            request = StockLatestQuoteRequest(
                symbol_or_symbols=alpaca_formatted,
                feed=DataFeed.SIP,  # Pro subscription — consolidated quotes
            )
            loop = asyncio.get_event_loop()
            quotes = await loop.run_in_executor(
                None, self._client.get_stock_latest_quote, request
            )

            for alpaca_sym in alpaca_formatted:
                try:
                    q = quotes.get(alpaca_sym)
                    if q and q.ask_price and q.ask_price > 0:
                        # Use midpoint of bid/ask as price
                        price = (q.bid_price + q.ask_price) / 2 if q.bid_price else q.ask_price
                        original_sym = sym_map.get(alpaca_sym, alpaca_sym)
                        result[original_sym] = QuoteData(
                            symbol=original_sym,
                            price=round(price, 2),
                            timestamp=str(q.timestamp) if q.timestamp else None,
                            source="alpaca",
                        )
                except Exception as e:
                    logger.debug(f"Alpaca quote parse error for {alpaca_sym}: {e}")

        except Exception as e:
            logger.error(f"Alpaca quotes fetch failed: {e}")

        return result


class YfinanceProvider(MarketDataProvider):
    """yfinance data provider (wraps existing logic)."""

    async def fetch_bars(
        self, symbols: List[str], start_date: str, end_date: Optional[str] = None
    ) -> Dict[str, pd.DataFrame]:
        try:
            import yfinance as yf
        except ImportError:
            logger.error("yfinance not installed")
            return {}

        result: Dict[str, pd.DataFrame] = {}
        BATCH_SIZE = 25
        DELAY = 1.0

        for i in range(0, len(symbols), BATCH_SIZE):
            batch = symbols[i:i + BATCH_SIZE]

            try:
                # auto_adjust=True applies dividend + split back-adjustment to
                # historical OHLC. For index symbols (^VIX, ^GSPC) this is a
                # no-op (they don't pay dividends). For SPY this is essential —
                # it produces the dividend-adjusted ("total return") series that
                # the 11y canonical pickle was built from. Without it, SPY's
                # raw historical closes have small downward gaps every quarter
                # at ex-dividend dates, which produces 4x more spurious 200MA
                # crossings (30 vs 8 over 5y) and -93pp WF return divergence.
                kwargs = {
                    "start": start_date,
                    "progress": False,
                    "threads": True,
                    "timeout": 30,
                    "auto_adjust": True,
                }
                if end_date:
                    kwargs["end"] = end_date

                loop = asyncio.get_event_loop()
                data = await loop.run_in_executor(
                    None, lambda b=batch, k=kwargs: yf.download(b, **k)
                )

                if data.empty:
                    continue

                # Detect if yfinance returned multi-level columns
                has_multi = isinstance(data.columns, pd.MultiIndex)

                for symbol in batch:
                    try:
                        if has_multi:
                            df = pd.DataFrame({
                                'date': data.index,
                                'open': data['Open'][symbol],
                                'high': data['High'][symbol],
                                'low': data['Low'][symbol],
                                'close': data['Close'][symbol],
                                'volume': data['Volume'][symbol],
                            }).dropna()
                        else:
                            df = pd.DataFrame({
                                'date': data.index,
                                'open': data['Open'],
                                'high': data['High'],
                                'low': data['Low'],
                                'close': data['Close'],
                                'volume': data['Volume'],
                            }).dropna()

                        if df.empty:
                            continue

                        df['date'] = pd.to_datetime(df['date'])
                        df = df.set_index('date').sort_index()
                        # Strip timezone and normalize to midnight
                        if hasattr(df.index, 'tz') and df.index.tz is not None:
                            df.index = df.index.tz_localize(None)
                        df.index = df.index.normalize()

                        # Pre-write sanity check for SPY (the benchmark — bad
                        # data here corrupts regime detection for every backtest
                        # and every signal scan). For other symbols we keep the
                        # fast path and rely on the periodic drift-detection
                        # service to catch issues.
                        if symbol in YFINANCE_PREFERRED:
                            violations = _validate_bar_sanity(symbol, df)
                            if violations:
                                print(f"⚠️ Refusing {symbol} fetch — sanity violations: {violations}")
                                continue  # Don't add this symbol to result

                        result[symbol] = df

                    except Exception as e:
                        logger.debug(f"yfinance parse error for {symbol}: {e}")

            except Exception as e:
                logger.error(f"yfinance batch fetch failed ({len(batch)} symbols): {e}")

            if i + BATCH_SIZE < len(symbols):
                await asyncio.sleep(DELAY)

        return result

    async def fetch_quotes(self, symbols: List[str]) -> Dict[str, QuoteData]:
        """Fetch live quotes using yfinance fast_info."""
        try:
            import yfinance as yf
        except ImportError:
            return {}

        result: Dict[str, QuoteData] = {}
        try:
            loop = asyncio.get_event_loop()
            tickers = await loop.run_in_executor(
                None, lambda: yf.Tickers(" ".join(symbols))
            )

            for symbol in symbols:
                try:
                    ticker = tickers.tickers.get(symbol)
                    if not ticker:
                        continue
                    info = ticker.fast_info
                    last_price = info.last_price if hasattr(info, 'last_price') else None
                    prev_close = info.previous_close if hasattr(info, 'previous_close') else None
                    day_high = info.day_high if hasattr(info, 'day_high') else None

                    if last_price:
                        change = last_price - prev_close if prev_close else 0
                        change_pct = (change / prev_close * 100) if prev_close else 0

                        result[symbol] = QuoteData(
                            symbol=symbol,
                            price=round(last_price, 2),
                            prev_close=round(prev_close, 2) if prev_close else None,
                            change=round(change, 2),
                            change_pct=round(change_pct, 2),
                            day_high=round(day_high, 2) if day_high else None,
                            timestamp=datetime.now().isoformat(),
                            source="yfinance",
                        )
                except Exception as e:
                    logger.debug(f"yfinance quote error for {symbol}: {e}")

        except Exception as e:
            logger.error(f"yfinance quotes fetch failed: {e}")

        return result


class DualSourceProvider(MarketDataProvider):
    """Orchestrator: Alpaca (SIP) primary → yfinance fallback.
    Index symbols (^VIX) always via yfinance.
    """

    def __init__(self):
        self.alpaca = AlpacaProvider()
        self.yfinance = YfinanceProvider()
        self.health: Dict[str, SourceHealth] = {
            "alpaca": SourceHealth(),
            "yfinance": SourceHealth(),
        }
        self.force_source: Optional[str] = None  # Override for retry logic
        self._last_bars_source: Optional[str] = None
        self._last_quotes_source: Optional[str] = None

    def _record_success(self, source: str):
        h = self.health[source]
        h.consecutive_failures = 0
        h.last_success = datetime.now()
        h.total_requests += 1

    def _record_failure(self, source: str):
        h = self.health[source]
        h.consecutive_failures += 1
        h.last_failure = datetime.now()
        h.total_requests += 1
        h.total_failures += 1

    @property
    def last_bars_source(self) -> Optional[str]:
        return self._last_bars_source

    @property
    def last_quotes_source(self) -> Optional[str]:
        return self._last_quotes_source

    def get_health_summary(self) -> Dict:
        """Return health status for monitoring."""
        summary = {}
        for name, h in self.health.items():
            if h.consecutive_failures > 5:
                status = "red"
            elif h.consecutive_failures > 0:
                status = "yellow"
            else:
                status = "green"
            summary[name] = {
                "status": status,
                "consecutive_failures": h.consecutive_failures,
                "last_success": h.last_success.isoformat() if h.last_success else None,
                "last_failure": h.last_failure.isoformat() if h.last_failure else None,
                "total_requests": h.total_requests,
                "total_failures": h.total_failures,
            }
        return summary

    def _get_primary_source(self) -> str:
        """Get configured primary source. Defaults to alpaca (Pro/SIP)."""
        try:
            from app.core.config import settings
            return settings.DATA_SOURCE_PRIMARY
        except Exception:
            return "yfinance"

    async def fetch_bars(
        self, symbols: List[str], start_date: str, end_date: Optional[str] = None
    ) -> Dict[str, pd.DataFrame]:
        """Fetch bars: primary source first → fallback on failure.

        Primary source is controlled by DATA_SOURCE_PRIMARY config (default: alpaca).
        Index symbols (^VIX etc) always go through yfinance regardless of primary.
        """
        # Separate index vs stock symbols
        index_syms = [s for s in symbols if s in INDEX_SYMBOLS]
        stock_syms = [s for s in symbols if s not in INDEX_SYMBOLS]

        result: Dict[str, pd.DataFrame] = {}

        # Index symbols: always yfinance
        if index_syms:
            t0 = time.time()
            index_data = await self.yfinance.fetch_bars(index_syms, start_date, end_date)
            elapsed = time.time() - t0
            result.update(index_data)
            if index_data:
                self._record_success("yfinance")
                logger.info(f"[yfinance] Fetched {len(index_data)}/{len(index_syms)} index symbols in {elapsed:.1f}s")
            else:
                self._record_failure("yfinance")
                logger.warning(f"[yfinance] Failed to fetch index symbols")

        if not stock_syms:
            return result

        # Force source override (for retry logic)
        if self.force_source:
            forced = self.force_source
            provider = self.yfinance if forced == "yfinance" else self.alpaca
            t0 = time.time()
            data = await provider.fetch_bars(stock_syms, start_date, end_date)
            elapsed = time.time() - t0
            result.update(data)
            self._last_bars_source = forced
            logger.info(f"[{forced}-forced] Fetched {len(data)}/{len(stock_syms)} symbols in {elapsed:.1f}s")
            return result

        # Determine primary/fallback based on config
        primary_name = self._get_primary_source()
        if primary_name == "alpaca":
            primary, fallback = self.alpaca, self.yfinance
            fallback_name = "yfinance"
        else:
            primary, fallback = self.yfinance, self.alpaca
            fallback_name = "alpaca"

        # Try primary source
        t0 = time.time()
        primary_data = await primary.fetch_bars(stock_syms, start_date, end_date)
        elapsed = time.time() - t0

        if primary_data:
            self._record_success(primary_name)
            result.update(primary_data)
            self._last_bars_source = primary_name
            logger.info(f"[{primary_name}] Fetched {len(primary_data)}/{len(stock_syms)} symbols in {elapsed:.1f}s")

            # Check for missing symbols — fallback for those
            missing = [s for s in stock_syms if s not in primary_data]
            if missing:
                logger.info(f"[{fallback_name}-fallback] Fetching {len(missing)} symbols missing from {primary_name}...")
                t0 = time.time()
                fallback_data = await fallback.fetch_bars(missing, start_date, end_date)
                elapsed = time.time() - t0
                result.update(fallback_data)
                logger.info(f"[{fallback_name}-fallback] Got {len(fallback_data)}/{len(missing)} in {elapsed:.1f}s")
        else:
            # Primary failed entirely — full fallback
            self._record_failure(primary_name)
            logger.warning(f"[{primary_name}] Failed, falling back to {fallback_name} for all {len(stock_syms)} symbols")

            t0 = time.time()
            fallback_data = await fallback.fetch_bars(stock_syms, start_date, end_date)
            elapsed = time.time() - t0

            if fallback_data:
                self._record_success(fallback_name)
                result.update(fallback_data)
                self._last_bars_source = fallback_name
                logger.info(f"[{fallback_name}-fallback] Fetched {len(fallback_data)}/{len(stock_syms)} symbols in {elapsed:.1f}s")
            else:
                self._record_failure(fallback_name)
                logger.error(f"[both] Both {primary_name} and {fallback_name} failed to fetch bars")

        return result

    async def fetch_quotes(self, symbols: List[str]) -> Dict[str, QuoteData]:
        """Fetch live quotes: yfinance primary → Alpaca fallback."""
        # Force source override
        if self.force_source == "alpaca":
            alpaca_data = await self.alpaca.fetch_quotes(symbols)
            self._last_quotes_source = "alpaca"
            return alpaca_data

        # Primary: yfinance (all exchanges)
        t0 = time.time()
        yf_data = await self.yfinance.fetch_quotes(symbols)
        elapsed = time.time() - t0

        if yf_data:
            self._record_success("yfinance")
            self._last_quotes_source = "yfinance"
            logger.debug(f"[yfinance] Fetched {len(yf_data)}/{len(symbols)} quotes in {elapsed:.1f}s")

            # Fill missing from Alpaca
            missing = [s for s in symbols if s not in yf_data and s not in INDEX_SYMBOLS]
            if missing:
                alpaca_quotes = await self.alpaca.fetch_quotes(missing)
                yf_data.update(alpaca_quotes)

            return yf_data
        else:
            # yfinance failed — try Alpaca for non-index symbols
            self._record_failure("yfinance")
            stock_syms = [s for s in symbols if s not in INDEX_SYMBOLS]
            if stock_syms:
                logger.warning(f"[yfinance] Failed, falling back to Alpaca for {len(stock_syms)} quotes")
                alpaca_data = await self.alpaca.fetch_quotes(stock_syms)
                if alpaca_data:
                    self._record_success("alpaca")
                    self._last_quotes_source = "alpaca"
                else:
                    self._record_failure("alpaca")
                return alpaca_data

            return {}


# Singleton instance
market_data_provider = DualSourceProvider()
