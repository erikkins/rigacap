"""
EC2 Walk-Forward Runner — builds 10y dataset and runs walk-forward simulation.

Runs inside the production Docker container on EC2 with --entrypoint python3.
All app imports resolve because the container has the full Lambda image.

Env vars (set by ec2-spot-walkforward.sh):
  DATABASE_URL, ALPACA_API_KEY, ALPACA_SECRET_KEY, PRICE_DATA_BUCKET
  SKIP_BUILD=1         — skip data fetch, load existing 10y pickle from S3
  WF_START_DATE        — simulation start (default: 2016-02-01)
  WF_END_DATE          — simulation end (default: 2026-02-01)
  WF_MAX_SYMBOLS       — top N liquid symbols per period (default: 500)
  WF_CARRY_POSITIONS   — carry positions across periods (default: true)
  WF_ENABLE_AI         — enable AI optimization (default: false)
"""

import os
import sys

# Lambda container installs packages to /var/task — add to path
sys.path.insert(0, "/var/task")

import time
import asyncio
import gzip
import pickle
import tempfile
from datetime import datetime

import numpy as np
import pandas as pd


# ─────────────────────────────────────────────────────────────
# Phase 1: Build or load 10-year dataset
# ─────────────────────────────────────────────────────────────

async def build_10y_dataset() -> dict:
    """Fetch 10 years of daily bars for ~7000 symbols and compute indicators."""
    from app.services.scanner import ScannerService
    from app.services.stock_universe import stock_universe_service
    from app.services.market_data_provider import market_data_provider

    print("=" * 60)
    print("PHASE 1: Building 10-year dataset")
    print("=" * 60)

    # Load full universe
    print("[DATA] Loading stock universe...")
    symbols = await stock_universe_service.ensure_loaded()
    print(f"[DATA] Universe: {len(symbols)} symbols")

    # Always include SPY and ^VIX
    required = ['SPY', '^VIX']
    symbols_set = set(symbols)
    for req in required:
        if req not in symbols_set:
            symbols.append(req)
            symbols_set.add(req)

    # Fetch data starting 11 years back (extra year for 200-day indicator warmup)
    # The WF sim starts at WF_START_DATE (default 2016-02-01), and indicators need
    # ~200 trading days of prior data to be valid.
    wf_start = os.environ.get("WF_START_DATE", "2016-02-01")
    warmup_start = pd.Timestamp(wf_start) - pd.Timedelta(days=400)  # 400 cal days ~ 280 trading days
    start_date = warmup_start.strftime("%Y-%m-%d")
    total = len(symbols)
    print(f"[DATA] Fetching bars from {start_date} (warmup for WF start {wf_start}) for {total} symbols...")

    t0 = time.time()
    bars = await market_data_provider.fetch_bars(symbols, start_date)
    source = market_data_provider.last_bars_source or "unknown"
    elapsed = time.time() - t0
    print(f"[DATA] Fetch complete in {elapsed:.0f}s via {source}: {len(bars)} symbols returned")

    # Compute indicators (same as ScannerService.fetch_data)
    print("[DATA] Computing indicators (DWAP, MA50, MA200, vol_avg, high_52w)...")
    data_cache = {}
    failed = []

    for symbol in symbols:
        df = bars.get(symbol)
        if df is None or len(df) < 50:
            failed.append(symbol)
            continue

        df['dwap'] = ScannerService.dwap(df['close'], df['volume'])
        df['ma_50'] = ScannerService.sma(df['close'], 50)
        df['ma_200'] = ScannerService.sma(df['close'], 200)
        df['vol_avg'] = ScannerService.sma(df['volume'], 200)
        df['high_52w'] = ScannerService.high_52w(df['close'])

        data_cache[symbol] = df

    print(f"[DATA] Built dataset: {len(data_cache)} symbols ({len(failed)} failed)")
    if failed[:20]:
        print(f"[DATA] Sample failures: {failed[:20]}")

    return data_cache


def load_10y_pickle() -> dict:
    """Load existing 10y pickle from S3."""
    import boto3

    print("=" * 60)
    print("PHASE 1: Loading existing 10y pickle from S3 (SKIP_BUILD=1)")
    print("=" * 60)

    bucket = os.environ.get("PRICE_DATA_BUCKET", "rigacap-prod-price-data-149218244179")
    key = "prices/all_data_10y.pkl.gz"

    s3 = boto3.client("s3")
    tmp_path = os.path.join(tempfile.gettempdir(), "all_data_10y.pkl.gz")

    print(f"[DATA] Downloading s3://{bucket}/{key} ...")
    t0 = time.time()
    s3.download_file(bucket, key, tmp_path)
    size_mb = os.path.getsize(tmp_path) / (1024 * 1024)
    print(f"[DATA] Downloaded {size_mb:.0f} MB in {time.time() - t0:.0f}s")

    print("[DATA] Decompressing + deserializing...")
    t0 = time.time()
    with gzip.open(tmp_path, "rb") as f:
        data_cache = pickle.load(f)
    print(f"[DATA] Loaded {len(data_cache)} symbols in {time.time() - t0:.0f}s")

    os.remove(tmp_path)
    return data_cache


# ─────────────────────────────────────────────────────────────
# Phase 3: Save 10y pickle to S3
# ─────────────────────────────────────────────────────────────

def save_10y_pickle(data_cache: dict):
    """Save 10y dataset to S3 as prices/all_data_10y.pkl.gz (NOT production key)."""
    import boto3

    print("=" * 60)
    print("PHASE 3: Saving 10y pickle to S3")
    print("=" * 60)

    bucket = os.environ.get("PRICE_DATA_BUCKET", "rigacap-prod-price-data-149218244179")
    key = "prices/all_data_10y.pkl.gz"
    tmp_path = os.path.join(tempfile.gettempdir(), "all_data_10y.pkl.gz")

    print(f"[SAVE] Serializing {len(data_cache)} symbols...")
    t0 = time.time()
    with gzip.open(tmp_path, "wb", compresslevel=6) as f:
        pickle.dump(data_cache, f, protocol=pickle.HIGHEST_PROTOCOL)
    size_mb = os.path.getsize(tmp_path) / (1024 * 1024)
    print(f"[SAVE] Compressed to {size_mb:.0f} MB in {time.time() - t0:.0f}s")

    print(f"[SAVE] Uploading to s3://{bucket}/{key} ...")
    t0 = time.time()
    s3 = boto3.client("s3")
    s3.upload_file(tmp_path, bucket, key)
    print(f"[SAVE] Upload complete in {time.time() - t0:.0f}s")

    os.remove(tmp_path)
    print(f"[SAVE] Production pickle (prices/all_data.pkl.gz) NOT touched.")


# ─────────────────────────────────────────────────────────────
# Phase 4: Run walk-forward simulation
# ─────────────────────────────────────────────────────────────

async def run_simulation(data_cache: dict):
    """Run the walk-forward simulation using the existing service."""
    from app.services.scanner import scanner_service
    from app.services.walk_forward_service import walk_forward_service
    from app.core.database import async_session

    print("=" * 60)
    print("PHASE 4: Running walk-forward simulation")
    print("=" * 60)

    # Inject data into scanner service (bypass S3 pickle load)
    scanner_service.data_cache = data_cache
    scanner_service.universe = list(data_cache.keys())
    scanner_service.full_universe_loaded = True
    print(f"[SIM] Injected {len(data_cache)} symbols into scanner_service.data_cache")

    # Parse config from env vars
    start_date_str = os.environ.get("WF_START_DATE", "2016-02-01")
    end_date_str = os.environ.get("WF_END_DATE", "2026-02-01")
    max_symbols = int(os.environ.get("WF_MAX_SYMBOLS", "500"))
    carry_positions = os.environ.get("WF_CARRY_POSITIONS", "true").lower() == "true"
    enable_ai = os.environ.get("WF_ENABLE_AI", "false").lower() == "true"

    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")

    print(f"[SIM] Config:")
    print(f"  Start:           {start_date_str}")
    print(f"  End:             {end_date_str}")
    print(f"  Max symbols:     {max_symbols}")
    print(f"  Carry positions: {carry_positions}")
    print(f"  Enable AI:       {enable_ai}")
    print(f"  Frequency:       biweekly")

    # Run simulation
    t0 = time.time()
    async with async_session() as db:
        result = await walk_forward_service.run_walk_forward_simulation(
            db=db,
            start_date=start_date,
            end_date=end_date,
            reoptimization_frequency="biweekly",
            min_score_diff=10.0,
            lookback_days=60,
            enable_ai_optimization=enable_ai,
            max_symbols=max_symbols,
            carry_positions=carry_positions,
            periods_limit=0,  # No chunking on EC2 — run all periods
            fixed_strategy_id=5,  # Ensemble
        )

    elapsed = time.time() - t0

    # ─────────────────────────────────────────────────────────
    # Phase 5: Print summary
    # ─────────────────────────────────────────────────────────
    print("")
    print("=" * 60)
    print("RESULTS: 10-Year Walk-Forward Simulation")
    print("=" * 60)
    print(f"  Period:          {result.start_date} → {result.end_date}")
    print(f"  Total Return:    {result.total_return_pct:+.1f}%")
    print(f"  Sharpe Ratio:    {result.sharpe_ratio:.2f}")
    print(f"  Max Drawdown:    {result.max_drawdown_pct:.1f}%")
    print(f"  Benchmark (SPY): {result.benchmark_return_pct:+.1f}%")
    print(f"  Strategy Switches: {result.num_strategy_switches}")
    print(f"  Total Trades:    {len(result.trades)}")
    print(f"  Sim Time:        {elapsed:.0f}s ({elapsed/60:.1f} min)")

    if result.errors:
        print(f"  Errors:          {len(result.errors)}")
        for err in result.errors[:5]:
            print(f"    - {err}")

    print("")
    print("Results saved to walk_forward_simulations table.")
    print("View in admin: Strategies > Walk-Forward History")
    print("=" * 60)

    return result


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────

async def main():
    skip_build = os.environ.get("SKIP_BUILD", "0") == "1"

    print("=" * 60)
    print("RigaCap 10-Year Walk-Forward Simulation (EC2)")
    print(f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print(f"Skip build: {skip_build}")
    print("=" * 60)
    print("")

    total_t0 = time.time()

    # Phase 1: Build or load data
    if skip_build:
        data_cache = load_10y_pickle()
    else:
        data_cache = await build_10y_dataset()

    # Phase 3: Save pickle (only if we built fresh data)
    if not skip_build:
        save_10y_pickle(data_cache)

    # Phase 4+5: Run simulation and print results
    await run_simulation(data_cache)

    total_elapsed = time.time() - total_t0
    print(f"\nTotal runtime: {total_elapsed:.0f}s ({total_elapsed/60:.1f} min)")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        import traceback
        print(f"\n{'=' * 60}")
        print(f"FATAL ERROR: {e}")
        print('=' * 60)
        traceback.print_exc()
        sys.exit(1)
