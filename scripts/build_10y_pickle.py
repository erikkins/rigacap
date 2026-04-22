#!/usr/bin/env python3
"""
Build 10-year pickle locally using Alpaca Pro API.
Fetches daily bars for all universe symbols, computes indicators, saves pickle.
Then uploads to S3.

Usage:
    cd backend
    python3 ../scripts/build_10y_pickle.py
"""

import asyncio
import gzip
import os
import pickle
import sys
import time
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

# Alpaca credentials
ALPACA_API_KEY = "AKQE37SDE7NOR4JBNVUAZ45UK7"
ALPACA_SECRET_KEY = "HAzrhTGxM2v2Zh4c2g2fvENDtyP7pPodPyofGd2MCRFq"

# Config
START_DATE = datetime(2019, 6, 1)  # ~7y back — gives 1.5y indicator warmup before Feb 2021 WF start
BATCH_SIZE = 100
BATCH_DELAY = 0.15  # seconds between batches (Alpaca Pro: 10k req/min)
OUTPUT_PATH = "/tmp/all_data_7y.pkl.gz"
S3_BUCKET = "rigacap-prod-price-data-149218244179"
S3_KEY = "prices/all_data.pkl.gz"
PROGRESS_INTERVAL = 500  # Print progress every N symbols


def _to_alpaca_symbol(sym: str) -> str:
    return sym.replace("-", ".")


def _from_alpaca_symbol(sym: str) -> str:
    return sym.replace(".", "-")


# Indicator functions (match scanner.py exactly)
def dwap(prices, volumes, period=200):
    pv = prices * volumes
    return pv.rolling(period, min_periods=50).sum() / volumes.rolling(period, min_periods=50).sum()

def sma(series, period):
    return series.rolling(period, min_periods=1).mean()

def high_52w(prices):
    return prices.rolling(252, min_periods=1).max()


async def load_universe():
    """Load universe from local cache or fetch from NASDAQ API."""
    cache_path = os.path.join(os.path.dirname(__file__), '..', 'backend', 'data', 'symbols_cache.json')

    if os.path.exists(cache_path):
        import json
        with open(cache_path) as f:
            data = json.load(f)
        symbols = data.get("symbols", [])
        print(f"Loaded {len(symbols)} symbols from local cache")
        return symbols

    # Fallback: fetch from NASDAQ API
    print("No local cache found, fetching from NASDAQ API...")
    import aiohttp

    all_symbols = []
    for exchange in ["NASDAQ", "NYSE"]:
        url = f"https://api.nasdaq.com/api/screener/stocks?exchange={exchange}&limit=10000"
        headers = {"User-Agent": "Mozilla/5.0"}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                data = await resp.json()
                rows = data.get("data", {}).get("rows", [])
                for row in rows:
                    sym = row.get("symbol", "").strip()
                    if sym and len(sym) <= 5 and not any(c in sym for c in "^/"):
                        all_symbols.append(sym)
        print(f"  {exchange}: {len(rows)} total, {len(all_symbols)} after filter")

    return sorted(set(all_symbols))


async def fetch_bars_alpaca(symbols: list) -> dict:
    """Fetch daily bars from Alpaca for all symbols in batches."""
    from alpaca.data import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame

    client = StockHistoricalDataClient(api_key=ALPACA_API_KEY, secret_key=ALPACA_SECRET_KEY)

    # Filter out index symbols
    index_symbols = {'^VIX', '^GSPC', '^DJI', '^IXIC', '^RUT', '^TNX'}
    stock_symbols = [s for s in symbols if s not in index_symbols]
    idx_symbols = [s for s in symbols if s in index_symbols]

    results = {}
    total = len(stock_symbols)
    batches = (total + BATCH_SIZE - 1) // BATCH_SIZE

    print(f"\nFetching {total} symbols from Alpaca ({batches} batches of {BATCH_SIZE})...")
    print(f"Start date: {START_DATE}")

    failed_symbols = []

    for i in range(0, total, BATCH_SIZE):
        batch = stock_symbols[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1

        # Convert to Alpaca format
        sym_map = {}
        alpaca_syms = []
        for s in batch:
            a = _to_alpaca_symbol(s)
            sym_map[a] = s
            alpaca_syms.append(a)

        try:
            request = StockBarsRequest(
                symbol_or_symbols=alpaca_syms,
                timeframe=TimeFrame.Day,
                start=START_DATE,
                feed="sip",
            )

            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            bars_response = await loop.run_in_executor(None, client.get_stock_bars, request)

            # Parse response
            for alpaca_sym, bar_list in bars_response.data.items():
                orig_sym = sym_map.get(str(alpaca_sym), str(alpaca_sym))
                orig_sym = _from_alpaca_symbol(orig_sym)

                rows = []
                for bar in bar_list:
                    rows.append({
                        'date': pd.Timestamp(bar.timestamp).tz_localize(None).normalize(),
                        'open': float(bar.open),
                        'high': float(bar.high),
                        'low': float(bar.low),
                        'close': float(bar.close),
                        'volume': int(bar.volume),
                    })

                if rows:
                    df = pd.DataFrame(rows)
                    df = df.set_index('date').sort_index()
                    df = df[~df.index.duplicated(keep='last')]
                    results[orig_sym] = df

        except Exception as e:
            print(f"  Batch {batch_num} FAILED: {e}")
            failed_symbols.extend(batch)

        # Progress
        fetched_so_far = len(results)
        if batch_num % 5 == 0 or batch_num == batches:
            print(f"  Batch {batch_num}/{batches}: {fetched_so_far} symbols fetched so far")

        # Rate limit
        if i + BATCH_SIZE < total:
            await asyncio.sleep(BATCH_DELAY)

    # Fetch index symbols via yfinance
    if idx_symbols:
        print(f"\nFetching {len(idx_symbols)} index symbols via yfinance...")
        import yfinance as yf
        for sym in idx_symbols:
            try:
                start_str = START_DATE.strftime("%Y-%m-%d") if isinstance(START_DATE, datetime) else START_DATE
                df = yf.download(sym, start=start_str, progress=False)
                if df is not None and len(df) > 0:
                    # Handle MultiIndex columns from yfinance
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = [c[0].lower() if isinstance(c, tuple) else c.lower() for c in df.columns]
                    else:
                        df.columns = [c.lower() for c in df.columns]
                    if 'adj close' in df.columns:
                        df = df.drop(columns=['adj close'])
                    results[sym] = df
                    print(f"  {sym}: {len(df)} bars")
            except Exception as e:
                print(f"  {sym} FAILED: {e}")

    print(f"\nTotal: {len(results)} symbols fetched, {len(failed_symbols)} failed")
    if failed_symbols[:20]:
        print(f"Failed (first 20): {failed_symbols[:20]}")

    return results


def compute_indicators(data_cache: dict) -> dict:
    """Compute indicators for all symbols (matching scanner.py exactly)."""
    print(f"\nComputing indicators for {len(data_cache)} symbols...")

    count = 0
    dropped = 0

    for symbol, df in list(data_cache.items()):
        if len(df) < 50:
            del data_cache[symbol]
            dropped += 1
            continue

        df['dwap'] = dwap(df['close'], df['volume'])
        df['ma_50'] = sma(df['close'], 50)
        df['ma_200'] = sma(df['close'], 200)
        df['vol_avg'] = sma(df['volume'], 200)
        df['high_52w'] = high_52w(df['close'])

        count += 1
        if count % PROGRESS_INTERVAL == 0:
            print(f"  {count}/{len(data_cache)} indicators computed...")

    print(f"  Done: {count} symbols with indicators, {dropped} dropped (<50 bars)")
    return data_cache


def save_pickle(data_cache: dict, path: str):
    """Save data cache as compressed pickle."""
    print(f"\nSaving pickle to {path}...")
    raw = pickle.dumps(data_cache, protocol=pickle.HIGHEST_PROTOCOL)
    print(f"  Raw size: {len(raw) / 1024 / 1024:.1f} MB")

    compressed = gzip.compress(raw, compresslevel=6)
    print(f"  Compressed size: {len(compressed) / 1024 / 1024:.1f} MB")

    with open(path, 'wb') as f:
        f.write(compressed)

    print(f"  Saved to {path}")
    return len(compressed)


def upload_to_s3(local_path: str, bucket: str, key: str):
    """Upload pickle to S3."""
    import boto3

    file_size = os.path.getsize(local_path)
    print(f"\nUploading {file_size / 1024 / 1024:.1f} MB to s3://{bucket}/{key}...")

    session = boto3.Session(profile_name='rigacap')
    s3 = session.client('s3', region_name='us-east-1')

    # Use multipart upload for large files
    from boto3.s3.transfer import TransferConfig
    config = TransferConfig(
        multipart_threshold=50 * 1024 * 1024,  # 50 MB
        max_concurrency=10,
        multipart_chunksize=50 * 1024 * 1024,
    )

    s3.upload_file(local_path, bucket, key, Config=config)
    print(f"  Uploaded successfully!")


async def main():
    start_time = time.time()

    print("=" * 60)
    print("Building 10-year pickle for RigaCap")
    print("=" * 60)

    # 1. Load universe
    symbols = await load_universe()

    # Always include required symbols
    for req in ['SPY', '^VIX', '^GSPC']:
        if req not in symbols:
            symbols.append(req)

    print(f"\nUniverse: {len(symbols)} symbols")

    # 2. Fetch bars
    data_cache = await fetch_bars_alpaca(symbols)

    # 3. Compute indicators
    data_cache = compute_indicators(data_cache)

    # 4. Stats
    total_bars = sum(len(df) for df in data_cache.values())
    avg_bars = total_bars / len(data_cache) if data_cache else 0
    min_date = min(df.index.min() for df in data_cache.values() if len(df) > 0)
    max_date = max(df.index.max() for df in data_cache.values() if len(df) > 0)

    print(f"\n{'=' * 60}")
    print(f"Pickle stats:")
    print(f"  Symbols: {len(data_cache)}")
    print(f"  Total bars: {total_bars:,}")
    print(f"  Avg bars/symbol: {avg_bars:.0f}")
    print(f"  Date range: {min_date.date()} to {max_date.date()}")
    print(f"{'=' * 60}")

    # 5. GUARDRAIL: refuse to save if too few symbols (prevents overwriting prod with bad data)
    MIN_SYMBOLS = 3000
    if len(data_cache) < MIN_SYMBOLS:
        print(f"\n❌ ABORTING: Only {len(data_cache)} symbols fetched (minimum {MIN_SYMBOLS}). NOT saving or uploading.")
        print(f"   This prevents overwriting production with an incomplete pickle.")
        sys.exit(1)

    # 6. Save pickle
    compressed_size = save_pickle(data_cache, OUTPUT_PATH)

    # 7. Upload to S3 — NEVER to the production key directly
    #    Upload to a staging key, then manually promote after verification.
    staging_key = S3_KEY.replace("all_data.pkl.gz", "all_data_STAGING.pkl.gz")
    print(f"\n⚠️  Uploading to STAGING key: {staging_key}")
    print(f"   To promote to production, run:")
    print(f"   aws s3 cp s3://{S3_BUCKET}/{staging_key} s3://{S3_BUCKET}/{S3_KEY} --profile rigacap")
    upload_to_s3(OUTPUT_PATH, S3_BUCKET, staging_key)

    elapsed = time.time() - start_time
    print(f"\nTotal time: {elapsed / 60:.1f} minutes")
    print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
