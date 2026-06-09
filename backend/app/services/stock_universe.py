"""
Stock Universe Service - Fetch all NASDAQ and NYSE symbols

Downloads and maintains a list of all tradeable stocks.
Persists to S3 in Lambda, local filesystem in development.
"""

import pandas as pd
import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set
from pathlib import Path
import json
import logging
import os
import io

logger = logging.getLogger(__name__)

# Check if running in Lambda with S3 bucket configured
S3_BUCKET = os.environ.get("PRICE_DATA_BUCKET")
IS_LAMBDA = bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))

# Local cache directory (for development)
LOCAL_CACHE_DIR = Path(__file__).parent.parent.parent / "data"
LOCAL_CACHE_FILE = LOCAL_CACHE_DIR / "symbols_cache.json"

# S3 key for universe cache
S3_UNIVERSE_KEY = "universe/symbols_cache.json"
# Separate cache for sector/industry data (populated by scripts/backfill_sectors.py;
# refreshed monthly via cron). Kept separate from symbols_cache.json because the
# NASDAQ screener API no longer returns sector fields — sector data has to come
# from yfinance, which is too slow to fold into the per-day symbols refresh.
S3_SECTORS_KEY = "universe/sectors_cache.json"

# Excluded symbols: ALL ETFs, leveraged/inverse products, commodities, bonds
# Individual stocks ONLY — customers pay for stock picks, not "buy SPY"
EXCLUDED_PATTERNS = [
    # Leveraged/Inverse index ETFs (2x/3x products with daily decay)
    'TQQQ', 'SQQQ', 'QLD', 'QID', 'SPXU', 'SPXS', 'UPRO', 'SSO', 'SDS', 'SH',
    'TNA', 'TZA', 'FAS', 'FAZ', 'LABU', 'LABD', 'NUGT', 'DUST', 'JNUG', 'JDST',
    # 1x inverse index ETFs (ProShares Short, etc.)
    'PSQ', 'DOG', 'RWM', 'SBB', 'MYY', 'SEF', 'EUM', 'EFZ',
    # Leveraged/inverse sector & thematic ETFs
    'FNGD', 'FNGU', 'SOXL', 'SOXS', 'TECL', 'TECS', 'CURE', 'PILL',
    'TMF', 'TMV', 'TYD', 'TYO', 'DRN', 'DRV', 'DFEN', 'WEBS',
    'ERX', 'ERY', 'GUSH', 'DRIP', 'NAIL', 'REK',
    # Leveraged/inverse single-stock ETFs (Direxion, GraniteShares, etc.)
    'TSLS', 'TSLQ', 'TSLL', 'NVDL', 'NVDS', 'NVDQ', 'NVD',
    'AAPD', 'AAPU', 'AMZU', 'AMZD', 'MSFU', 'MSFD',
    'METU', 'METD', 'CONL', 'CONY',
    # Commodity ETFs (gold, silver, metals — not equity momentum)
    'GLD', 'IAU', 'GLDM', 'IAUM', 'SGOL', 'OUNZ', 'BAR', 'AAAU',
    'SLV', 'SIVR', 'PSLV', 'PPLT', 'PALL',
    'DBC', 'DBA', 'DBB', 'DBO', 'USO', 'BNO', 'UNG', 'PDBC', 'GSG', 'COMT',
    # Leveraged commodity ETFs (2x/inverse)
    'AGQ', 'ZSL', 'UGL', 'GLL',
    # Bond/Treasury/Fixed-income ETFs (not equity momentum)
    'TLT', 'TLH', 'IEF', 'IEI', 'SHY', 'BIL', 'SPTL', 'SPTI', 'SPTS',
    'AGG', 'BND', 'BNDX', 'LQD', 'HYG', 'JNK', 'MBB', 'VMBS', 'MUB',
    'GOVT', 'VGSH', 'VGIT', 'VGLT', 'VCSH', 'VCIT', 'VCLT',
    'SCHZ', 'SCHQ', 'SCHO', 'SCHR',
    'JAAA', 'VTEB', 'USHY', 'JEPQ',
    # Index/broad market ETFs (customers want stock picks, not "buy SPY")
    'SPY', 'QQQ', 'IWM', 'DIA', 'RSP', 'VTI', 'VOO', 'IVV', 'SPLG',
    'MDY', 'IJR', 'IJH', 'IWB', 'IWF', 'IWD', 'IWN', 'IWO', 'IWP',
    # International ETFs
    'IEFA', 'VWO', 'FXI', 'KWEB', 'ASHR', 'EEM', 'EFA', 'INDA', 'EWZ', 'EWJ',
    # Sector ETFs
    'XLB', 'XLC', 'XLE', 'XLF', 'XLI', 'XLK', 'XLP', 'XLRE', 'XLS', 'XLU', 'XLV', 'XLY',
    'SOXX', 'SMH', 'KRE', 'KBE', 'XBI', 'IBB', 'XOP', 'OIH', 'ITB', 'XHB',
    'GDX', 'GDXJ', 'SILJ',
    # Smart beta / dividend / thematic ETFs
    'SCHD', 'SCHX', 'FNDX', 'ARKK', 'ARKW', 'ARKF', 'ARKQ', 'ARKG',
    'QUAL', 'MTUM', 'VLUE', 'USMV', 'HDV', 'VIG', 'DGRO', 'NOBL',
    # Crypto ETFs (spot — not individual stocks)
    'IBIT', 'FBTC', 'ARKB', 'BITB', 'GBTC', 'ETHE', 'ETHA', 'ETH',
    # Leveraged single-stock ETFs missed earlier
    'MSTX', 'MSTU',
    # Index symbols (not tradeable)
    '^DJI', '^GSPC', '^IXIC',
    # Crypto leveraged ETFs
    'BITX', 'BITU', 'SBIT',
    # Volatility products (contango decay)
    'UVXY', 'SVXY', 'VXX', 'VIXY', 'TVIX',
    # Other problematic symbols
    'DWAC', 'PHUN',
]

# Must-include symbols (major stocks that bypass all filters)
# These are important index components that should never be excluded
MUST_INCLUDE = [
    # Dow 30 components (as of 2025 - WBA went private Dec 2024)
    'AAPL', 'AMGN', 'AXP', 'BA', 'CAT', 'CRM', 'CSCO', 'CVX', 'DIS', 'DOW',
    'GS', 'HD', 'HON', 'IBM', 'INTC', 'JNJ', 'JPM', 'KO', 'MCD', 'MMM',
    'MRK', 'MSFT', 'NKE', 'PG', 'TRV', 'UNH', 'V', 'VZ', 'WMT',
    # Major stocks sometimes filtered (price < $5 or other issues)
    'NIO', 'GRAB', 'SOFI', 'RIVN', 'LCID', 'PLTR', 'HOOD', 'COIN',
    # Block Inc (was SQ, now XYZ as of June 2024)
    'XYZ', 'SQ',
    # Berkshire (handled specially due to dot/dash in symbol)
    'BRK.A', 'BRK.B', 'BRK-A', 'BRK-B',
]

# Minimum requirements for inclusion
MIN_PRICE = 5.0  # Exclude penny stocks
MIN_AVG_VOLUME = 100000  # Minimum average daily volume


class StockUniverseService:
    """
    Manages the universe of tradeable stocks.
    Uses S3 in Lambda, local filesystem in development.
    """

    def __init__(self):
        self.symbols: List[str] = []
        self.symbol_info: Dict[str, dict] = {}
        self.last_updated: Optional[datetime] = None
        self._s3_client = None

        if not IS_LAMBDA:
            self._ensure_local_dir()

    def _get_s3_client(self):
        """Get boto3 S3 client (lazy initialization)"""
        if self._s3_client is None:
            import boto3
            self._s3_client = boto3.client('s3')
        return self._s3_client

    def _ensure_local_dir(self):
        """Create local cache directory if it doesn't exist"""
        LOCAL_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _use_s3(self) -> bool:
        """Check if we should use S3 storage"""
        return IS_LAMBDA and S3_BUCKET is not None

    async def fetch_nasdaq_symbols(self) -> List[dict]:
        """
        Fetch all NASDAQ-listed symbols from NASDAQ's API
        """
        url = "https://api.nasdaq.com/api/screener/stocks"
        params = {
            "tableonly": "true",
            "limit": 10000,
            "exchange": "NASDAQ"
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        rows = data.get("data", {}).get("table", {}).get("rows", [])
                        logger.info(f"Fetched {len(rows)} NASDAQ symbols")
                        return rows
        except Exception as e:
            logger.error(f"Failed to fetch NASDAQ symbols: {e}")

        return []

    async def fetch_nyse_symbols(self) -> List[dict]:
        """
        Fetch all NYSE-listed symbols from NASDAQ's API
        """
        url = "https://api.nasdaq.com/api/screener/stocks"
        params = {
            "tableonly": "true",
            "limit": 10000,
            "exchange": "NYSE"
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        rows = data.get("data", {}).get("table", {}).get("rows", [])
                        logger.info(f"Fetched {len(rows)} NYSE symbols")
                        return rows
        except Exception as e:
            logger.error(f"Failed to fetch NYSE symbols: {e}")

        return []

    async def fetch_all_symbols(self, use_cache: bool = True, max_cache_age_hours: int = 24) -> List[str]:
        """
        Fetch all NASDAQ and NYSE symbols

        Args:
            use_cache: Use cached symbols if available
            max_cache_age_hours: Maximum age of cache in hours (default 24)

        Returns:
            List of stock symbols
        """
        # Check cache first
        if use_cache and self._load_from_cache(max_age_hours=max_cache_age_hours):
            logger.info(f"Loaded {len(self.symbols)} symbols from cache")
            return self.symbols

        logger.info("Fetching fresh stock symbols from NASDAQ API...")

        # Fetch from both exchanges
        nasdaq_stocks, nyse_stocks = await asyncio.gather(
            self.fetch_nasdaq_symbols(),
            self.fetch_nyse_symbols()
        )

        all_stocks = nasdaq_stocks + nyse_stocks

        # Process and filter symbols
        symbols = set()
        must_include_set = set(MUST_INCLUDE)

        for stock in all_stocks:
            symbol = stock.get("symbol", "").strip()

            # Skip empty symbols
            if not symbol:
                continue

            # Check if this is a must-include symbol (bypass most filters)
            is_must_include = symbol in must_include_set

            # Skip symbols longer than 5 chars (unless must-include)
            if len(symbol) > 5 and not is_must_include:
                continue

            # Skip symbols with special characters (unless must-include like BRK.B)
            if any(c in symbol for c in ['^', '/', '-']) and not is_must_include:
                continue
            # Allow dots only for must-include symbols (BRK.B, BRK.A)
            if '.' in symbol and not is_must_include:
                continue

            # Skip excluded symbols (these are never included)
            if symbol in EXCLUDED_PATTERNS:
                continue

            # Parse market cap and volume if available
            try:
                # Get last sale price
                last_sale = stock.get("lastsale", "$0").replace("$", "").replace(",", "")
                price = float(last_sale) if last_sale else 0

                # Skip penny stocks (unless must-include)
                if price < MIN_PRICE and not is_must_include:
                    continue

                # Store symbol info
                self.symbol_info[symbol] = {
                    "name": stock.get("name", ""),
                    "exchange": stock.get("exchange", ""),
                    "sector": stock.get("sector", ""),
                    "industry": stock.get("industry", ""),
                    "market_cap": stock.get("marketCap", ""),
                    "last_price": price
                }

                symbols.add(symbol)

            except (ValueError, TypeError):
                continue

        # Ensure must-include symbols are present even if not in API response
        for symbol in MUST_INCLUDE:
            if symbol not in symbols and symbol not in EXCLUDED_PATTERNS:
                symbols.add(symbol)
                if symbol not in self.symbol_info:
                    self.symbol_info[symbol] = {
                        "name": f"{symbol} (must-include)",
                        "exchange": "",
                        "sector": "",
                        "industry": "",
                        "market_cap": "",
                        "last_price": 0
                    }

        self.symbols = sorted(list(symbols))
        self.last_updated = datetime.now()

        # Save to cache
        self._save_to_cache()

        logger.info(f"Found {len(self.symbols)} valid symbols after filtering (including {len(MUST_INCLUDE)} must-include)")
        return self.symbols

    def _load_from_cache(self, max_age_hours: int = 24) -> bool:
        """Load symbols from cache (S3 or local) if valid"""
        try:
            if self._use_s3():
                return self._load_from_s3(max_age_hours)
            else:
                return self._load_from_local(max_age_hours)
        except Exception as e:
            logger.error(f"Failed to load cache: {e}")
            return False

    def _load_from_s3(self, max_age_hours: int = 24) -> bool:
        """Load symbols from S3 cache"""
        try:
            s3 = self._get_s3_client()
            response = s3.get_object(Bucket=S3_BUCKET, Key=S3_UNIVERSE_KEY)
            data = json.loads(response['Body'].read().decode('utf-8'))

            # Check if cache is still valid
            cached_time = datetime.fromisoformat(data.get("updated", "2000-01-01"))
            if datetime.now() - cached_time > timedelta(hours=max_age_hours):
                logger.info(f"S3 cache expired (age: {datetime.now() - cached_time})")
                return False

            self.symbols = data.get("symbols", [])
            self.symbol_info = data.get("symbol_info", {})
            self.last_updated = cached_time

            logger.info(f"Loaded {len(self.symbols)} symbols from S3 cache")
            return len(self.symbols) > 0

        except self._get_s3_client().exceptions.NoSuchKey:
            logger.info("No S3 universe cache found")
            return False
        except Exception as e:
            logger.error(f"Failed to load S3 cache: {e}")
            return False

    def _load_from_local(self, max_age_hours: int = 24) -> bool:
        """Load symbols from local cache"""
        try:
            if not LOCAL_CACHE_FILE.exists():
                return False

            with open(LOCAL_CACHE_FILE, 'r') as f:
                data = json.load(f)

            # Check if cache is still valid
            cached_time = datetime.fromisoformat(data.get("updated", "2000-01-01"))
            if datetime.now() - cached_time > timedelta(hours=max_age_hours):
                return False

            self.symbols = data.get("symbols", [])
            self.symbol_info = data.get("symbol_info", {})
            self.last_updated = cached_time

            return len(self.symbols) > 0

        except Exception as e:
            logger.error(f"Failed to load local cache: {e}")
            return False

    def _save_to_cache(self):
        """Save symbols to cache (S3 or local)"""
        data = {
            "updated": self.last_updated.isoformat() if self.last_updated else datetime.now().isoformat(),
            "symbols": self.symbols,
            "symbol_info": self.symbol_info,
            "count": len(self.symbols)
        }

        if self._use_s3():
            self._save_to_s3(data)
        else:
            self._save_to_local(data)

    def _save_to_s3(self, data: dict):
        """Save symbols to S3"""
        try:
            s3 = self._get_s3_client()
            s3.put_object(
                Bucket=S3_BUCKET,
                Key=S3_UNIVERSE_KEY,
                Body=json.dumps(data),
                ContentType='application/json'
            )
            logger.info(f"Saved {len(self.symbols)} symbols to S3 cache")
        except Exception as e:
            logger.error(f"Failed to save S3 cache: {e}")

    def _save_to_local(self, data: dict):
        """Save symbols to local cache"""
        try:
            with open(LOCAL_CACHE_FILE, 'w') as f:
                json.dump(data, f)
            logger.info(f"Saved {len(self.symbols)} symbols to local cache")
        except Exception as e:
            logger.error(f"Failed to save local cache: {e}")

    def get_symbols(self,
                    exchange: Optional[str] = None,
                    sector: Optional[str] = None,
                    min_price: float = MIN_PRICE,
                    limit: Optional[int] = None) -> List[str]:
        """
        Get filtered list of symbols

        Args:
            exchange: Filter by exchange (NASDAQ, NYSE)
            sector: Filter by sector
            min_price: Minimum stock price
            limit: Maximum number of symbols to return

        Returns:
            Filtered list of symbols
        """
        filtered = []

        for symbol in self.symbols:
            info = self.symbol_info.get(symbol, {})

            # Apply filters
            if exchange and info.get("exchange") != exchange:
                continue
            if sector and info.get("sector") != sector:
                continue
            if info.get("last_price", 0) < min_price:
                continue

            filtered.append(symbol)

            if limit and len(filtered) >= limit:
                break

        return filtered

    def get_symbol_info(self, symbol: str) -> Optional[dict]:
        """Get info for a specific symbol"""
        return self.symbol_info.get(symbol)

    def get_status(self) -> dict:
        """Get universe status"""
        return {
            "storage": "s3" if self._use_s3() else "local",
            "bucket": S3_BUCKET if self._use_s3() else None,
            "symbols_count": len(self.symbols),
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "sample_symbols": self.symbols[:20] if self.symbols else []
        }

    async def ensure_loaded(self, max_cache_age_hours: int = 168) -> List[str]:
        """
        Ensure universe is loaded, fetching if necessary.

        Uses a longer cache age (7 days default) since the universe
        doesn't change frequently.

        Returns:
            List of stock symbols
        """
        if self.symbols and len(self.symbols) > 100:
            # Even on warm path, make sure sectors are merged once. Cheap.
            self._merge_sectors_cache()
            return self.symbols

        result = await self.fetch_all_symbols(use_cache=True, max_cache_age_hours=max_cache_age_hours)
        self._merge_sectors_cache()
        return result

    def _merge_sectors_cache(self):
        """Fold S3 sectors_cache.json into self.symbol_info if available.

        Called once per ensure_loaded; idempotent. If S3 fetch fails or cache
        is missing, silently no-op — the system continues with empty sector
        fields exactly as before (no regression).
        """
        # Only merge once per process
        if getattr(self, '_sectors_merged', False):
            return
        cache = None
        # Try S3 first. PRICE_DATA_BUCKET is set in Lambda env but typically
        # not in local research scripts — fall back to the well-known prod
        # bucket name so research can use sector data without extra env setup.
        # Production Lambda hits the env var path with IAM role permissions.
        try:
            import boto3
            bucket = S3_BUCKET or "rigacap-prod-price-data-149218244179"
            s3 = boto3.client('s3')
            resp = s3.get_object(Bucket=bucket, Key=S3_SECTORS_KEY)
            cache = json.loads(resp['Body'].read())
            logger.info(f"Sectors cache loaded from s3://{bucket}/{S3_SECTORS_KEY}")
        except Exception as e:
            # Local fallback: /tmp/sectors_cache.json (written by
            # scripts/backfill_sectors.py). Useful when local AWS profile
            # doesn't have access to the prod bucket (different account).
            local_path = "/tmp/sectors_cache.json"
            try:
                with open(local_path) as f:
                    cache = json.load(f)
                logger.info(f"Sectors cache loaded from local fallback {local_path} (S3 error: {type(e).__name__})")
            except Exception:
                logger.info(f"Sectors cache not loaded (S3: {type(e).__name__}; no local fallback); continuing without")
                self._sectors_merged = True
                return

        merged = 0
        for sym, info in cache.items():
            if sym.startswith('_'):  # skip _meta etc.
                continue
            if not isinstance(info, dict):
                continue
            existing = self.symbol_info.setdefault(sym, {})
            sector = info.get('sector')
            if sector and not existing.get('sector'):
                existing['sector'] = sector
                merged += 1
            industry = info.get('industry')
            if industry and not existing.get('industry'):
                existing['industry'] = industry
            country = info.get('country')
            if country and not existing.get('country'):
                existing['country'] = country
        logger.info(f"Sectors cache merged: {merged} symbols now have sector data")
        self._sectors_merged = True

    async def fetch_company_details(self, symbol: str) -> dict:
        """
        Fetch detailed company information from yfinance.

        Returns dict with name, sector, industry, description, website, etc.
        Caches the result in symbol_info.
        """
        import yfinance as yf

        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info or {}

            # Extract relevant fields
            details = {
                "name": info.get("longName") or info.get("shortName", symbol),
                "sector": info.get("sector", ""),
                "industry": info.get("industry", ""),
                "description": info.get("longBusinessSummary", ""),
                "market_cap": str(info.get("marketCap", "")) if info.get("marketCap") else "",
                "exchange": info.get("exchange", ""),
                "website": info.get("website", ""),
                "employees": info.get("fullTimeEmployees"),
                "country": info.get("country", ""),
                "last_price": info.get("regularMarketPrice", 0),
            }

            # Update the cache
            if symbol in self.symbol_info:
                self.symbol_info[symbol].update(details)
            else:
                self.symbol_info[symbol] = details

            return details

        except Exception as e:
            logger.warning(f"Failed to fetch company details for {symbol}: {e}")
            # Return existing cached info or empty dict
            return self.symbol_info.get(symbol, {"name": symbol})


# Singleton instance
stock_universe_service = StockUniverseService()
