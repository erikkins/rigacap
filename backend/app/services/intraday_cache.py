"""Intraday minute-bar cache.

Per the data-provider rule (memory: feedback_data_provider_cache.md):
fetch from Alpaca once, persist to durable storage, never re-fetch.

Storage layout:
    s3://<PRICE_DATA_BUCKET>/intraday/<symbol>/<YYYY-MM-DD>.parquet

Each parquet file holds the FULL trading day's minute bars (regular session,
09:30-16:00 ET). Coverage metadata is embedded in the parquet file's
schema.metadata so cache validation is self-contained.

Public API:
    cache = IntradayBarCache()
    df = await cache.get_or_fetch(symbol, "2024-03-15")

The returned DataFrame is indexed by minute timestamp (UTC) with columns:
open, high, low, close, volume, trade_count, vwap.
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

S3_BUCKET = os.environ.get("PRICE_DATA_BUCKET")
IS_LAMBDA = bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
LOCAL_CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "intraday"

CACHE_SOURCE_TAG = "alpaca-sip"
META_KEY_COMPLETE = b"intraday_complete"
META_KEY_SOURCE = b"intraday_source"
META_KEY_FETCHED_AT = b"intraday_fetched_at"
META_KEY_COVERAGE_START = b"intraday_coverage_start"
META_KEY_COVERAGE_END = b"intraday_coverage_end"


class IntradayBarCache:
    """Idempotent cache for Alpaca minute-bar data, keyed by (symbol, date)."""

    def __init__(self):
        self._s3 = None
        self._alpaca_client = None
        self._alpaca_initialized = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_or_fetch(self, symbol: str, date: str) -> Optional[pd.DataFrame]:
        """Return full-day minute bars for symbol on date.

        Cache-first. If cached file is missing or marked incomplete, fetch
        from Alpaca, write to cache, return cache-canonical form.

        Returns None if Alpaca has no data for that symbol on that date
        (e.g., before IPO, market holiday).
        """
        cached = self._read_cache(symbol, date)
        if cached is not None:
            return cached

        df = await self._fetch_from_alpaca(symbol, date)
        if df is None or df.empty:
            return None

        self._write_cache(symbol, date, df, complete=True)
        # Re-read from cache so callers always get the parquet-canonical form
        # (avoids subtle dtype/precision drift between in-memory and round-trip).
        canonical = self._read_cache(symbol, date)
        return canonical if canonical is not None else df

    def is_cached(self, symbol: str, date: str) -> bool:
        """Cheap existence + completeness check without loading the data."""
        return self._read_cache_metadata(symbol, date) is not None

    # ------------------------------------------------------------------
    # Cache I/O
    # ------------------------------------------------------------------

    def _cache_key(self, symbol: str, date: str) -> str:
        # symbols may contain '.' (e.g. BRK.A); replace for path safety
        safe = symbol.replace("/", "_")
        return f"intraday/{safe}/{date}.parquet"

    def _local_path(self, symbol: str, date: str) -> Path:
        safe = symbol.replace("/", "_")
        return LOCAL_CACHE_DIR / safe / f"{date}.parquet"

    def _read_cache_metadata(self, symbol: str, date: str) -> Optional[dict]:
        """Return metadata dict if cache is complete, else None."""
        try:
            import pyarrow.parquet as pq

            if self._use_s3():
                key = self._cache_key(symbol, date)
                try:
                    obj = self._get_s3().head_object(Bucket=S3_BUCKET, Key=key)
                except Exception:
                    return None
                # Need to read schema metadata; do a lightweight footer read
                resp = self._get_s3().get_object(Bucket=S3_BUCKET, Key=key)
                buf = io.BytesIO(resp["Body"].read())
                pf = pq.ParquetFile(buf)
                meta = dict(pf.schema_arrow.metadata or {})
            else:
                path = self._local_path(symbol, date)
                if not path.exists():
                    return None
                pf = pq.ParquetFile(str(path))
                meta = dict(pf.schema_arrow.metadata or {})

            complete = meta.get(META_KEY_COMPLETE, b"")
            source = meta.get(META_KEY_SOURCE, b"")
            if complete == b"true" and source == CACHE_SOURCE_TAG.encode():
                return {k.decode(): v.decode() for k, v in meta.items()
                        if k.startswith(b"intraday_")}
            return None
        except Exception as e:
            logger.debug(f"cache metadata read failed for {symbol} {date}: {e}")
            return None

    def _read_cache(self, symbol: str, date: str) -> Optional[pd.DataFrame]:
        """Read full DataFrame if cache is complete, else None."""
        if self._read_cache_metadata(symbol, date) is None:
            return None
        try:
            if self._use_s3():
                key = self._cache_key(symbol, date)
                resp = self._get_s3().get_object(Bucket=S3_BUCKET, Key=key)
                buf = io.BytesIO(resp["Body"].read())
                df = pd.read_parquet(buf)
            else:
                path = self._local_path(symbol, date)
                df = pd.read_parquet(str(path))
            return df
        except Exception as e:
            logger.warning(f"cache read failed for {symbol} {date}: {e}")
            return None

    def _write_cache(self, symbol: str, date: str, df: pd.DataFrame, complete: bool):
        """Write DataFrame to cache with embedded coverage metadata."""
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq

            table = pa.Table.from_pandas(df)
            custom_meta = {
                META_KEY_COMPLETE: b"true" if complete else b"false",
                META_KEY_SOURCE: CACHE_SOURCE_TAG.encode(),
                META_KEY_FETCHED_AT: datetime.now(timezone.utc).isoformat().encode(),
                META_KEY_COVERAGE_START: b"09:30",
                META_KEY_COVERAGE_END: b"16:00",
            }
            existing = table.schema.metadata or {}
            new_meta = {**dict(existing), **custom_meta}
            table = table.replace_schema_metadata(new_meta)

            if self._use_s3():
                key = self._cache_key(symbol, date)
                buf = io.BytesIO()
                pq.write_table(table, buf, compression="snappy")
                buf.seek(0)
                self._get_s3().put_object(
                    Bucket=S3_BUCKET,
                    Key=key,
                    Body=buf.getvalue(),
                    ContentType="application/x-parquet",
                )
            else:
                path = self._local_path(symbol, date)
                path.parent.mkdir(parents=True, exist_ok=True)
                pq.write_table(table, str(path), compression="snappy")
        except Exception as e:
            logger.warning(f"cache write failed for {symbol} {date}: {e}")

    def _use_s3(self) -> bool:
        return IS_LAMBDA and S3_BUCKET is not None

    def _get_s3(self):
        if self._s3 is None:
            import boto3
            self._s3 = boto3.client("s3")
        return self._s3

    # ------------------------------------------------------------------
    # Alpaca fetch
    # ------------------------------------------------------------------

    def _ensure_alpaca(self) -> bool:
        if self._alpaca_initialized:
            return self._alpaca_client is not None
        self._alpaca_initialized = True
        try:
            from app.core.config import settings
            from alpaca.data.historical import StockHistoricalDataClient

            if not settings.ALPACA_API_KEY or not settings.ALPACA_SECRET_KEY:
                logger.warning("Alpaca credentials missing")
                return False
            self._alpaca_client = StockHistoricalDataClient(
                api_key=settings.ALPACA_API_KEY,
                secret_key=settings.ALPACA_SECRET_KEY,
            )
            return True
        except Exception as e:
            logger.warning(f"Alpaca init failed: {e}")
            return False

    @staticmethod
    def _to_alpaca_symbol(symbol: str) -> str:
        return symbol.replace("-", ".")

    async def _fetch_from_alpaca(self, symbol: str, date: str) -> Optional[pd.DataFrame]:
        """Fetch full trading day's 1-minute bars (regular session) from Alpaca SIP."""
        if not self._ensure_alpaca():
            return None

        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
        from alpaca.data.enums import DataFeed, Adjustment

        # Window: 13:30 UTC (09:30 ET, regular session start) to 21:00 UTC (17:00 ET, allow buffer)
        # Alpaca filters by trading session, so this captures regular RTH.
        start_dt = datetime.strptime(date, "%Y-%m-%d").replace(hour=13, minute=30, tzinfo=timezone.utc)
        end_dt = datetime.strptime(date, "%Y-%m-%d").replace(hour=21, minute=0, tzinfo=timezone.utc)

        alpaca_sym = self._to_alpaca_symbol(symbol)

        try:
            request = StockBarsRequest(
                symbol_or_symbols=[alpaca_sym],
                timeframe=TimeFrame(1, TimeFrameUnit.Minute),
                start=start_dt,
                end=end_dt,
                feed=DataFeed.SIP,
                adjustment=Adjustment.SPLIT,
            )

            loop = asyncio.get_event_loop()
            bars = await loop.run_in_executor(
                None, self._alpaca_client.get_stock_bars, request
            )

            bar_data = bars.data if hasattr(bars, "data") else {}
            symbol_bars = bar_data.get(alpaca_sym, [])
            if not symbol_bars:
                return None

            rows = [{
                "timestamp": b.timestamp,
                "open": float(b.open),
                "high": float(b.high),
                "low": float(b.low),
                "close": float(b.close),
                "volume": int(b.volume),
                "trade_count": int(b.trade_count) if b.trade_count is not None else 0,
                "vwap": float(b.vwap) if b.vwap is not None else 0.0,
            } for b in symbol_bars]

            df = pd.DataFrame(rows)
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.set_index("timestamp").sort_index()
            df = df[~df.index.duplicated(keep="last")]
            return df

        except Exception as e:
            logger.warning(f"Alpaca minute-bar fetch failed for {symbol} {date}: {e}")
            return None


_cache_singleton: Optional[IntradayBarCache] = None


def get_intraday_cache() -> IntradayBarCache:
    global _cache_singleton
    if _cache_singleton is None:
        _cache_singleton = IntradayBarCache()
    return _cache_singleton
