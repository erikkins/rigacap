"""
Data Export Service - Persist historical price data to S3 or local files

Exports scanner data cache to Parquet files for:
- Permanent storage of historical prices (never need to re-fetch)
- Fast loading on startup
- Database seeding for new deployments

In Lambda: Uses S3 bucket for persistent storage
Locally: Uses backend/data/prices directory
"""

import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import logging
import json
import os
import io
import gzip

logger = logging.getLogger(__name__)

# Check if running in Lambda with S3 bucket configured
S3_BUCKET = os.environ.get("PRICE_DATA_BUCKET")
IS_LAMBDA = bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))

# Local data directory (for development)
LOCAL_DATA_DIR = Path(__file__).parent.parent.parent / "data" / "prices"


class DataExportService:
    """
    Manages export and import of historical price data.
    Uses S3 in Lambda, local filesystem in development.
    """

    def __init__(self):
        self.last_export: Optional[datetime] = None
        self.exported_symbols: List[str] = []
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
        """Create local data directory if it doesn't exist"""
        LOCAL_DATA_DIR.mkdir(parents=True, exist_ok=True)

    def _use_s3(self) -> bool:
        """Check if we should use S3 storage"""
        return IS_LAMBDA and S3_BUCKET is not None

    def export_all(self, data_cache: Dict[str, pd.DataFrame]) -> Dict:
        """
        Export all cached data to Parquet files (S3 or local)

        Args:
            data_cache: Scanner's data cache (symbol -> DataFrame)

        Returns:
            Export summary with file count and size
        """
        if not data_cache:
            return {"success": False, "message": "No data to export", "count": 0}

        exported = 0
        total_size = 0
        failed = []

        for symbol, df in data_cache.items():
            try:
                if len(df) < 50:  # Skip if not enough data
                    continue

                # Reset index to include date as column
                df_export = df.reset_index()

                # Normalize date column name (some DataFrames use 'index' or other names)
                if 'date' not in df_export.columns and 'Date' not in df_export.columns:
                    for col in ['index', 'Index']:
                        if col in df_export.columns:
                            df_export = df_export.rename(columns={col: 'date'})
                            break

                # Ensure date column is proper datetime
                if 'date' in df_export.columns:
                    df_export['date'] = pd.to_datetime(df_export['date'])

                if self._use_s3():
                    # Export to S3 as CSV (pyarrow not available in Lambda)
                    buffer = io.StringIO()
                    df_export.to_csv(buffer, index=False)
                    csv_bytes = buffer.getvalue().encode('utf-8')

                    s3 = self._get_s3_client()
                    s3.put_object(
                        Bucket=S3_BUCKET,
                        Key=f"prices/{symbol}.csv",
                        Body=csv_bytes,
                        ContentType='text/csv'
                    )
                    file_size = len(csv_bytes)
                else:
                    # Export to local file as parquet (pyarrow available locally)
                    filepath = LOCAL_DATA_DIR / f"{symbol}.parquet"
                    df_export.to_parquet(filepath, index=False, compression='snappy')
                    file_size = filepath.stat().st_size

                total_size += file_size
                exported += 1

            except Exception as e:
                logger.error(f"Failed to export {symbol}: {e}")
                failed.append(symbol)

        # Save metadata
        self.last_export = datetime.now()
        self.exported_symbols = list(data_cache.keys())
        self._save_metadata()

        storage_type = "S3" if self._use_s3() else "local"
        logger.info(f"Exported {exported} symbols to {storage_type} ({total_size / 1024 / 1024:.1f} MB)")

        return {
            "success": True,
            "count": exported,
            "total_size_mb": round(total_size / 1024 / 1024, 2),
            "failed": failed,
            "storage": storage_type,
            "bucket": S3_BUCKET if self._use_s3() else None,
            "timestamp": self.last_export.isoformat()
        }

    def import_all(self) -> Dict[str, pd.DataFrame]:
        """
        Import all Parquet files into memory (from S3 or local)

        Returns:
            Dict mapping symbol to DataFrame
        """
        data_cache = {}

        if self._use_s3():
            data_cache = self._import_from_s3()
        else:
            data_cache = self._import_from_local()

        return data_cache

    def import_symbols(self, symbols: List[str]) -> Dict[str, pd.DataFrame]:
        """
        Import specific symbols from individual S3 CSVs (~250KB each).

        Used by the API Lambda to load only the data needed for a request,
        avoiding the full pickle download that would OOM on 1024 MB.

        Args:
            symbols: List of ticker symbols to load

        Returns:
            Dict mapping symbol to DataFrame (date-indexed)
        """
        data_cache = {}

        if self._use_s3():
            s3 = self._get_s3_client()
            for symbol in symbols:
                try:
                    response = s3.get_object(
                        Bucket=S3_BUCKET,
                        Key=f"prices/{symbol}.csv"
                    )
                    csv_content = response['Body'].read().decode('utf-8')
                    df = pd.read_csv(io.StringIO(csv_content))

                    # Set date as index (CSVs may use 'date', 'Date', or 'index' as column name)
                    if 'date' in df.columns:
                        df['date'] = pd.to_datetime(df['date'])
                        df = df.set_index('date').sort_index()
                    elif 'Date' in df.columns:
                        df['Date'] = pd.to_datetime(df['Date'])
                        df = df.set_index('Date').sort_index()
                        df.index.name = 'date'
                    elif 'index' in df.columns:
                        df['index'] = pd.to_datetime(df['index'])
                        df = df.set_index('index').sort_index()
                        df.index.name = 'date'

                    # Strip timezone if present
                    if df.index.tz is not None:
                        df.index = df.index.tz_localize(None)

                    data_cache[symbol] = df
                    logger.info(f"Loaded {symbol} from S3 CSV ({len(df)} rows)")

                except Exception as e:
                    if 'NoSuchKey' in str(e):
                        logger.debug(f"No S3 CSV for {symbol}")
                    else:
                        logger.error(f"Failed to load {symbol} from S3: {e}")
        else:
            # Local dev: load from parquet files
            for symbol in symbols:
                filepath = LOCAL_DATA_DIR / f"{symbol}.parquet"
                if filepath.exists():
                    try:
                        df = pd.read_parquet(filepath)
                        if 'date' in df.columns:
                            df['date'] = pd.to_datetime(df['date'])
                            df = df.set_index('date').sort_index()
                        if 'dwap' not in df.columns:
                            df = self._compute_indicators(df)
                        data_cache[symbol] = df
                        logger.info(f"Loaded {symbol} from local parquet ({len(df)} rows)")
                    except Exception as e:
                        logger.error(f"Failed to load {symbol} from local: {e}")

        return data_cache

    def _compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute technical indicators on a price DataFrame"""
        if len(df) < 50:
            return df

        # DWAP - Daily Weighted Average Price (200-day)
        pv = df['close'] * df['volume']
        df['dwap'] = pv.rolling(200, min_periods=50).sum() / df['volume'].rolling(200, min_periods=50).sum()

        # Moving Averages
        df['ma_50'] = df['close'].rolling(50, min_periods=1).mean()
        df['ma_200'] = df['close'].rolling(200, min_periods=1).mean()

        # Volume Average
        df['vol_avg'] = df['volume'].rolling(200, min_periods=1).mean()

        # 52-week High
        df['high_52w'] = df['close'].rolling(252, min_periods=1).max()

        return df

    def _import_from_s3(self) -> Dict[str, pd.DataFrame]:
        """Import price data from S3 - uses pickle file for speed"""
        data_cache = {}

        try:
            s3 = self._get_s3_client()
            print(f"📥 S3 import starting. Bucket={S3_BUCKET}")

            # Try pickle file first (fastest - no parsing/splitting needed).
            # PRICE_DATA_PICKLE_KEY env var can override the S3 key (used for
            # research jobs needing a longer-history pickle, e.g. all_data_11y_STAGING.pkl.gz).
            # Default = production 7y pickle.
            pickle_key = os.environ.get("PRICE_DATA_PICKLE_KEY") or "prices/all_data.pkl.gz"
            try:
                print(f"📦 Loading pickle data from S3 (key={pickle_key})...")
                import pickle
                response = s3.get_object(Bucket=S3_BUCKET, Key=pickle_key)
                print(f"📦 Got S3 response, reading body...")
                raw_bytes = response['Body'].read()
                print(f"📦 Read {len(raw_bytes)} bytes, decompressing...")
                pkl_bytes = gzip.decompress(raw_bytes)
                print(f"📦 Decompressed to {len(pkl_bytes)} bytes, unpickling...")
                data_cache = pickle.loads(pkl_bytes)
                # Normalize index name across all symbol DataFrames. Pickle
                # historically contained inconsistent index naming (notably
                # ^VIX / ^GSPC carried index.name=None or 'Date' from a
                # yf.download path that skipped set_index('date'); everywhere
                # else it was 'date'). Parquet's import_parquet ALWAYS sets
                # index.name='date' on read, so any pickle-side inconsistency
                # shows up as a spurious column_set_diff. Normalizing here
                # gives every consumer of data_cache a single canonical
                # shape — which is also what parquet-primary will deliver
                # post-cutover. Skip silently if df.index isn't a
                # DatetimeIndex (defensive, shouldn't happen).
                for _sym, _df in data_cache.items():
                    if isinstance(_df, pd.DataFrame) and _df.index.name != 'date':
                        _df.index.name = 'date'
                print(f"✅ Loaded {len(data_cache)} symbols from pickle file")
                # Update metadata with correct count
                self.exported_symbols = list(data_cache.keys())
                self.last_export = datetime.now()
                self._save_metadata()
                return data_cache
            except Exception as e:
                error_code = getattr(getattr(e, 'response', {}), 'get', lambda *a: None)('Error', {}).get('Code')
                if error_code == 'NoSuchKey' or 'NoSuchKey' in str(e):
                    print("📦 No pickle file found, trying parquet...")
                else:
                    print(f"⚠️ Pickle load failed: {e}, trying parquet...")

            # Fallback 1: Parquet via DuckDB httpfs (AL2023 native, no /tmp)
            if not data_cache:
                try:
                    # NOTE: os is already imported at module level. Importing
                    # it AGAIN here makes os a local-to-this-function variable,
                    # which collides with the os.environ.get() reads earlier
                    # in this function (UnboundLocalError). Same Python scoping
                    # pitfall as the scanner_service incident May 2 2026.
                    import duckdb
                    print("📦 Loading from parquet via DuckDB httpfs...")
                    conn = duckdb.connect(':memory:')
                    conn.execute("SET home_directory='/tmp';")
                    conn.execute("SET extension_directory='/tmp/duckdb_extensions';")
                    region = os.environ.get('AWS_REGION', 'us-east-1')
                    conn.execute("INSTALL httpfs; LOAD httpfs;")
                    conn.execute(f"SET s3_region = '{region}';")
                    conn.execute("CREATE SECRET aws_creds (TYPE S3, PROVIDER CREDENTIAL_CHAIN);")
                    s3_url = f"s3://{S3_BUCKET}/prices/all_data.parquet"
                    df_all = conn.execute(f"SELECT * FROM '{s3_url}'").df()
                    conn.close()
                    print(f"📦 Read {len(df_all)} rows from parquet, splitting by symbol...")
                    df_all['date'] = pd.to_datetime(df_all['date'])
                    for symbol, group in df_all.groupby('symbol'):
                        data_cache[symbol] = group.drop('symbol', axis=1).set_index('date').sort_index()
                    print(f"✅ Loaded {len(data_cache)} symbols from parquet (fallback)")
                    self.exported_symbols = list(data_cache.keys())
                    self.last_export = datetime.now()
                    self._save_metadata()
                    return data_cache
                except Exception as pq_err:
                    print(f"⚠️ Parquet fallback failed: {pq_err}, trying CSV...")

            # Fallback 2: CSV (slowest)
            try:
                print("📦 Loading CSV data from S3...")
                response = s3.get_object(Bucket=S3_BUCKET, Key='prices/all_prices.csv.gz')
                print(f"📦 Got S3 response, reading body...")
                raw_bytes = response['Body'].read()
                print(f"📦 Read {len(raw_bytes)} bytes, decompressing...")
                csv_bytes = gzip.decompress(raw_bytes)
                print(f"📦 Decompressed to {len(csv_bytes)} bytes, parsing CSV...")
                csv_content = csv_bytes.decode('utf-8')
                buffer = io.StringIO(csv_content)

                # Read the consolidated CSV with symbol column
                df_all = pd.read_csv(buffer)
                df_all['date'] = pd.to_datetime(df_all['date'])
                print(f"📦 Parsed CSV with {len(df_all)} rows, splitting by symbol...")

                # Faster split: set multi-index and group
                df_all = df_all.set_index(['symbol', 'date']).sort_index()
                for symbol in df_all.index.get_level_values('symbol').unique():
                    data_cache[symbol] = df_all.loc[symbol]

                print(f"✅ Loaded {len(data_cache)} symbols from CSV file")
                return data_cache

            except Exception as e:
                import traceback
                print(f"⚠️ CSV load failed: {e}")
                print(traceback.format_exc())
                print("Falling back to individual files...")

            # Fallback: load individual CSV files
            paginator = s3.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=S3_BUCKET, Prefix='prices/')

            csv_keys = []
            for page in pages:
                for obj in page.get('Contents', []):
                    if obj['Key'].endswith('.csv') and not obj['Key'].endswith('all_prices.csv.gz'):
                        csv_keys.append(obj['Key'])

            logger.info(f"Found {len(csv_keys)} CSV files in S3")

            for key in csv_keys:
                try:
                    symbol = key.split('/')[-1].replace('.csv', '')

                    response = s3.get_object(Bucket=S3_BUCKET, Key=key)
                    csv_content = response['Body'].read().decode('utf-8')
                    buffer = io.StringIO(csv_content)

                    df = pd.read_csv(buffer)

                    # Set date as index
                    if 'date' in df.columns:
                        df['date'] = pd.to_datetime(df['date'])
                        df = df.set_index('date').sort_index()

                    data_cache[symbol] = df

                except Exception as e:
                    logger.error(f"Failed to import {key} from S3: {e}")

            logger.info(f"Imported {len(data_cache)} symbols from S3")

        except Exception as e:
            logger.error(f"Failed to list S3 objects: {e}")

        return data_cache

    def export_pickle(self, data_cache: Dict[str, pd.DataFrame]) -> Dict:
        """
        Export all cached data to a single gzipped pickle file.
        This is the fastest format to load (no parsing/splitting needed).

        GUARDRAILS:
        - Refuses to overwrite if new pickle is >20% smaller than existing (data loss protection)
        - Auto-archives existing pickle before overwrite (weekly rotation)
        - Logs size comparison for monitoring
        """
        if not data_cache:
            return {"success": False, "message": "No data to export", "count": 0}

        try:
            import pickle

            # Canonicalize each symbol's DataFrame at the storage boundary:
            #   1. Filter out short-history (< 50 rows) — same as before
            #   2. index.name == 'date' — historically a yf.download path for
            #      ^VIX/^GSPC left this as 'Date' or None
            #   3. All EXPECTED_INDICATORS columns present — without this, a
            #      symbol that gets added/updated by a non-scan path (e.g.
            #      nightly data hygiene split-refetch) can land in the
            #      pickle with bare OHLCV. Parquet's strict-schema concat
            #      union fills those NaN, so the diff harness sees
            #      column_set_diff.
            #
            # CRITICAL: canonicalization writes back to the input data_cache
            # in-place. The diff harness `compare_pickle_to_parquet()` reads
            # the live data_cache, not the S3 pickle — so without in-place
            # mutation, the disk-pickle is canonical but the cache (and thus
            # the diff harness) still sees stale state. May 13-14 5-event
            # regression was exactly this: pickle on disk was clean, but the
            # diff harness reported divergence because it inspected the
            # un-canonicalized in-memory dict.
            from app.services.scanner import scanner_service
            expected_indicators = set(scanner_service.EXPECTED_INDICATORS)
            clean_cache = {}
            for symbol, df in data_cache.items():
                if df is None or len(df) < 50:
                    continue
                mutated = False
                # Index name normalization
                if df.index.name != 'date':
                    df = df.copy()
                    df.index.name = 'date'
                    mutated = True
                # Indicator canonicalization
                if any(c not in df.columns for c in expected_indicators):
                    df = scanner_service._ensure_indicators(df)
                    mutated = True
                if mutated:
                    # Write back to live cache so downstream consumers see
                    # the canonical schema. Safe — we're replacing dict
                    # values, not keys, mid-iteration.
                    data_cache[symbol] = df
                clean_cache[symbol] = df

            if not clean_cache:
                return {"success": False, "message": "No valid data to export", "count": 0}

            num_symbols = len(clean_cache)
            symbol_names = list(clean_cache.keys())

            # Stream pickle to disk first to avoid holding ~1 GB in RAM
            import tempfile, os
            tmp_path = os.path.join(tempfile.gettempdir(), "all_data.pkl.gz")
            with gzip.open(tmp_path, 'wb') as f:
                pickle.dump(clean_cache, f)
            del clean_cache
            new_size = os.path.getsize(tmp_path)
            new_size_mb = new_size / 1024 / 1024

            if self._use_s3():
                s3 = self._get_s3_client()
                pickle_key = 'prices/all_data.pkl.gz'

                # GUARDRAIL: Check existing pickle size before overwriting
                existing_size = 0
                try:
                    head = s3.head_object(Bucket=S3_BUCKET, Key=pickle_key)
                    existing_size = head['ContentLength']
                except Exception:
                    pass  # No existing pickle, OK to write

                existing_size_mb = existing_size / 1024 / 1024
                shrink_pct = ((existing_size - new_size) / existing_size * 100) if existing_size > 0 else 0

                print(f"📦 Pickle size check: new={new_size_mb:.1f} MB, existing={existing_size_mb:.1f} MB, shrink={shrink_pct:.1f}%")

                # Block if new pickle is >20% smaller (likely data loss)
                if existing_size > 0 and shrink_pct > 20:
                    print(f"🚫 PICKLE GUARDRAIL: Refusing to overwrite! New pickle ({new_size_mb:.1f} MB) is "
                          f"{shrink_pct:.0f}% smaller than existing ({existing_size_mb:.1f} MB). "
                          f"This likely means historical data was lost during incremental update.")
                    os.remove(tmp_path)
                    return {
                        "success": False,
                        "message": f"Guardrail blocked: new pickle {shrink_pct:.0f}% smaller ({new_size_mb:.1f} vs {existing_size_mb:.1f} MB)",
                        "count": num_symbols,
                        "guardrail": True,
                    }

                # Auto-archive: save weekly backup (once per week, keyed by ISO week)
                try:
                    week_key = datetime.now().strftime("%Y-W%W")
                    archive_key = f"prices/backups/weekly_{week_key}.pkl.gz"
                    # Only archive if no backup exists for this week yet
                    try:
                        s3.head_object(Bucket=S3_BUCKET, Key=archive_key)
                    except Exception:
                        # No backup for this week — create one from existing pickle
                        if existing_size > 0:
                            s3.copy_object(
                                Bucket=S3_BUCKET,
                                CopySource={'Bucket': S3_BUCKET, 'Key': pickle_key},
                                Key=archive_key,
                            )
                            print(f"📦 Weekly pickle archived: {archive_key} ({existing_size_mb:.1f} MB)")
                except Exception as arch_err:
                    print(f"⚠️ Weekly archive failed (non-fatal): {arch_err}")

                # Write new pickle
                with open(tmp_path, 'rb') as f:
                    s3.put_object(
                        Bucket=S3_BUCKET,
                        Key=pickle_key,
                        Body=f,
                        ContentType='application/octet-stream'
                    )
                storage_type = "S3"
            else:
                import shutil
                filepath = LOCAL_DATA_DIR / "all_data.pkl.gz"
                shutil.move(tmp_path, str(filepath))
                storage_type = "local"

            # Clean up temp file
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

            self.last_export = datetime.now()
            self.exported_symbols = symbol_names

            print(f"✅ Exported pickle with {num_symbols} symbols ({new_size_mb:.1f} MB)")

            return {
                "success": True,
                "count": num_symbols,
                "total_size_mb": round(new_size_mb, 2),
                "storage": storage_type,
                "bucket": S3_BUCKET if self._use_s3() else None,
                "timestamp": self.last_export.isoformat()
            }

        except Exception as e:
            import traceback
            print(f"❌ Failed to export pickle: {e}")
            print(traceback.format_exc())
            return {"success": False, "message": str(e), "count": 0}

    def export_parquet(self, data_cache: Dict[str, pd.DataFrame]) -> Dict:
        """
        Export all cached data to a single consolidated Parquet file.

        Parquet advantages over pickle (Apr 2026 migration):
        - Columnar compression (typically 30-50% smaller than gzipped pickle)
        - Strict schema (pyarrow catches NaN-tail bugs, type drift, etc.)
        - Fast partial reads — can query one symbol without loading full file
        - Cross-language compatible (DuckDB, Spark, BigQuery can read directly)
        - Atomic per-symbol updates (when partitioned) vs pickle's all-or-nothing

        This is a SHADOW write — runs alongside export_pickle during the
        migration. Once parquet read path is validated on all consumers,
        the pickle path can be retired.

        Storage layout: single file at s3://<bucket>/prices/all_data.parquet
        with rows concatenated across symbols, 'symbol' column added for
        grouping on read.
        """
        if not data_cache:
            return {"success": False, "message": "No data to export", "count": 0}

        try:
            import tempfile, os

            # Filter small dataframes, build concatenated DataFrame with symbol col
            frames = []
            for symbol, df in data_cache.items():
                if df is None or len(df) < 50:
                    continue
                df_copy = df.copy()
                df_copy['symbol'] = symbol
                # Reset index to expose date as a column (parquet prefers explicit cols)
                df_copy = df_copy.reset_index()
                # Normalize index column name to 'date'
                if 'date' not in df_copy.columns:
                    for candidate in ['index', 'Index', 'Date']:
                        if candidate in df_copy.columns:
                            df_copy = df_copy.rename(columns={candidate: 'date'})
                            break
                # Ensure tz-naive datetime for parquet compatibility
                if 'date' in df_copy.columns:
                    df_copy['date'] = pd.to_datetime(df_copy['date']).dt.tz_localize(None) \
                        if getattr(pd.to_datetime(df_copy['date']).dt, 'tz', None) is not None \
                        else pd.to_datetime(df_copy['date'])
                frames.append(df_copy)

            if not frames:
                return {"success": False, "message": "No valid data to export", "count": 0}

            combined = pd.concat(frames, ignore_index=True)
            num_symbols = combined['symbol'].nunique()

            # Stream parquet to disk first
            tmp_path = os.path.join(tempfile.gettempdir(), "all_data.parquet")
            # zstd has best compression for float-heavy financial data
            combined.to_parquet(tmp_path, index=False, compression='zstd')
            new_size = os.path.getsize(tmp_path)
            new_size_mb = new_size / 1024 / 1024

            if self._use_s3():
                s3 = self._get_s3_client()
                parquet_key = 'prices/all_data.parquet'
                # upload_file auto-multiparts large files and streams from disk
                # rather than loading the whole file into a single in-memory
                # buffer. The previous put_object(Body=f.read()) approach hit
                # `[Errno 14] Bad address` (EFAULT) on the May 8 daily scan
                # when the parquet was 351 MB — Lambda's /tmp is on a backing
                # store that mmap-style large reads can fault on. The
                # downstream consequence was worse than the failed write
                # itself: the parallel-read diff harness ran against the
                # *previous day's* parquet still in S3 and false-positived
                # 4500+ row_count_diff events.
                s3.upload_file(
                    tmp_path,
                    S3_BUCKET,
                    parquet_key,
                    ExtraArgs={'ContentType': 'application/vnd.apache.parquet'},
                )
                os.remove(tmp_path)
                storage = "S3"
                location = f"s3://{S3_BUCKET}/{parquet_key}"
            else:
                local_path = LOCAL_DATA_DIR / "all_data.parquet"
                import shutil
                shutil.move(tmp_path, local_path)
                storage = "local"
                location = str(local_path)

            logger.info(f"✅ Exported parquet: {num_symbols} symbols, {new_size_mb:.1f} MB → {location}")
            return {
                "success": True,
                "count": num_symbols,
                "total_rows": len(combined),
                "size_mb": round(new_size_mb, 2),
                "storage": storage,
                "location": location,
            }

        except Exception as e:
            import traceback
            print(f"❌ Failed to export parquet: {e}")
            print(traceback.format_exc())
            return {"success": False, "message": str(e), "count": 0}

    def import_parquet(self, symbols: Optional[List[str]] = None) -> Dict[str, pd.DataFrame]:
        """
        Import cached data from the consolidated Parquet file.

        Args:
            symbols: Optional list of specific symbols to import. If None,
                imports all symbols (equivalent to pickle's bulk load).
                When provided, uses parquet's columnar read to fetch ONLY
                those symbols — no need to load the full file.

        Returns:
            Dict mapping symbol -> DataFrame (same shape as import_all's
            pickle path).

        This is the Parquet counterpart to pickle's _import_from_s3. Same
        API, different underlying storage.
        """
        try:
            import tempfile, os
            data_cache: Dict[str, pd.DataFrame] = {}

            if self._use_s3():
                s3 = self._get_s3_client()
                parquet_key = 'prices/all_data.parquet'
                # Stream to disk — large files OOM if fully buffered
                tmp_path = os.path.join(tempfile.gettempdir(), "import_all_data.parquet")
                with open(tmp_path, 'wb') as f:
                    obj = s3.get_object(Bucket=S3_BUCKET, Key=parquet_key)
                    for chunk in obj['Body'].iter_chunks(chunk_size=8 * 1024 * 1024):
                        f.write(chunk)
                source = tmp_path
            else:
                source = str(LOCAL_DATA_DIR / "all_data.parquet")

            # Use pyarrow for filtered reads if a symbol subset is requested
            if symbols:
                filters = [('symbol', 'in', symbols)]
                df = pd.read_parquet(source, filters=filters)
            else:
                df = pd.read_parquet(source)

            if self._use_s3() and os.path.exists(source):
                os.remove(source)

            # Split back into per-symbol DataFrames, restoring the date index
            for sym, group in df.groupby('symbol'):
                group = group.drop(columns=['symbol']).set_index('date').sort_index()
                data_cache[sym] = group

            logger.info(f"📦 Imported {len(data_cache)} symbols from parquet")
            return data_cache

        except Exception as e:
            import traceback
            print(f"❌ Failed to import parquet: {e}")
            print(traceback.format_exc())
            return {}

    def query_parquet(self, sql: str) -> pd.DataFrame:
        """
        Execute an arbitrary SQL query against the S3 parquet file using DuckDB.
        Returns a pandas DataFrame.

        Within the SQL, reference the parquet file as 'prices' — the method
        sets up a DuckDB view that points to the S3 file automatically.

        Example:
            df = svc.query_parquet('''
                SELECT symbol, date, close
                FROM prices
                WHERE symbol = 'NVDA' AND date >= '2024-01-01'
                ORDER BY date
            ''')

        Use cases:
        - Admin diagnostics ('which symbols had >10% moves yesterday?')
        - Cross-symbol analysis ('correlate AAPL and MSFT returns')
        - Data quality checks without loading full cache
        """
        try:
            import duckdb
        except ImportError:
            raise RuntimeError("duckdb not installed — add to requirements.txt")

        conn = duckdb.connect(':memory:')
        try:
            # Set DuckDB home to /tmp on Lambda (no writable home dir)
            conn.execute("SET home_directory='/tmp';")
            conn.execute("SET extension_directory='/tmp/duckdb_extensions';")

            if self._use_s3():
                # AL2023 (glibc 2.34) supports DuckDB httpfs natively.
                # Query parquet directly on S3 — no /tmp download needed.
                import os
                region = os.environ.get('AWS_REGION', 'us-east-1')
                conn.execute("INSTALL httpfs; LOAD httpfs;")
                conn.execute(f"SET s3_region = '{region}';")
                conn.execute("CREATE SECRET aws_creds (TYPE S3, PROVIDER CREDENTIAL_CHAIN);")
                s3_url = f"s3://{S3_BUCKET}/prices/all_data.parquet"
                conn.execute(f"CREATE VIEW prices AS SELECT * FROM '{s3_url}';")
                return conn.execute(sql).df()
            else:
                url = str(LOCAL_DATA_DIR / "all_data.parquet")
                conn.execute(f"CREATE VIEW prices AS SELECT * FROM '{url}';")
                return conn.execute(sql).df()
        finally:
            conn.close()

    def snapshot_universe_history(self, snapshot_date: Optional[str] = None) -> Dict:
        """
        Persist a full daily snapshot of the scan universe ranking to S3.

        Captures, for a given snapshot date:
          - Full ranked list: every eligible symbol with 60-day avg volume
            up to and including snapshot_date (survivorship-bias-free)
          - The exclusion set in effect at write time
          - Snapshot timestamp + universe size hint

        Files are append-only at signals/universe-history/{date}.json. Never
        overwritten without explicit force; idempotent on re-invocation for
        the same date (returns existing summary).

        Use case: future audits of "where did rank N go" don't need to
        reconstruct from the current pickle — they read the historical
        snapshot directly. Closes the gap surfaced by the May 17 2026
        SIGNAL_UNIVERSE_SIZE 100→500 investigation, where rank attribution
        relied on reconstruction.

        Args:
            snapshot_date: ISO YYYY-MM-DD. Defaults to today (UTC).
        """
        from app.services.scanner import scanner_service, _EXCLUDED_SET
        from datetime import datetime as _dt, date as _date

        if snapshot_date is None:
            snapshot_date = _date.today().isoformat()
        snap_ts = pd.Timestamp(snapshot_date)
        key = f"signals/universe-history/{snapshot_date}.json"

        # Skip if already exists (idempotent — never overwrite history)
        if self._use_s3():
            try:
                s3 = self._get_s3_client()
                s3.head_object(Bucket=S3_BUCKET, Key=key)
                return {"status": "exists", "key": key, "snapshot_date": snapshot_date}
            except Exception:
                pass  # NoSuchKey → write new

        if not scanner_service.data_cache:
            return {"status": "failed", "error": "data_cache is empty"}

        # Build full ranking — every symbol with ≥60d history as of snapshot_date
        rankings = []
        for symbol, df in scanner_service.data_cache.items():
            if df is None or df.empty:
                continue
            hist = df[df.index <= snap_ts]
            if len(hist) < 60 or 'volume' not in hist.columns or 'close' not in hist.columns:
                continue
            avg_vol = float(hist['volume'].tail(60).mean())
            last_close = float(hist['close'].iloc[-1])
            last_date = hist.index[-1]
            rankings.append({
                "symbol": symbol,
                "avg_volume_60d": avg_vol,
                "last_close": last_close,
                "last_date": last_date.strftime("%Y-%m-%d") if hasattr(last_date, 'strftime') else str(last_date)[:10],
                "is_excluded": symbol in _EXCLUDED_SET,
            })

        # Sort by avg_volume descending; assign rank
        rankings.sort(key=lambda r: r["avg_volume_60d"], reverse=True)
        for i, r in enumerate(rankings, start=1):
            r["rank"] = i

        snapshot = {
            "snapshot_date": snapshot_date,
            "snapshot_time_utc": _dt.utcnow().isoformat() + "Z",
            "total_eligible_symbols": len(rankings),
            "excluded_count": sum(1 for r in rankings if r["is_excluded"]),
            "signal_universe_size_setting": int(os.environ.get("SIGNAL_UNIVERSE_SIZE", "0")) or None,
            "excluded_symbols_in_universe": sorted(r["symbol"] for r in rankings if r["is_excluded"]),
            "rankings": rankings,
        }

        # Persist
        body = json.dumps(snapshot).encode()
        if self._use_s3():
            s3 = self._get_s3_client()
            s3.put_object(
                Bucket=S3_BUCKET, Key=key,
                Body=body, ContentType='application/json',
            )
            location = f"s3://{S3_BUCKET}/{key}"
        else:
            (LOCAL_DATA_DIR / "universe-history").mkdir(parents=True, exist_ok=True)
            (LOCAL_DATA_DIR / "universe-history" / f"{snapshot_date}.json").write_bytes(body)
            location = str(LOCAL_DATA_DIR / "universe-history" / f"{snapshot_date}.json")

        return {
            "status": "written",
            "snapshot_date": snapshot_date,
            "total_eligible_symbols": len(rankings),
            "size_kb": round(len(body) / 1024, 1),
            "location": location,
        }

    def diagnose_corruption(self) -> Dict:
        """
        DuckDB-powered corruption scan across the universe. Runs SEPARATE
        count + examples queries per category so the reported totals are
        accurate (prior version reported the LIMIT, not the actual count).

        Categories:
        - abrupt_jumps: distinct symbols with any single-day |log return| > 0.5
        - dwap_ratio_extreme: symbols where latest close/dwap > 2.0 or < 0.5
        - date_gaps: symbols with any >10-day gap between rows (ticker reuse)
        - short_history: symbols with < 252 rows
        - low_recent_volume: latest volume < 1% of 200-day avg (halt/delist)
        """
        try:
            results = {}

            # --- Abrupt jumps (unique symbols affected) ---
            count = self.query_parquet("""
                WITH jumps AS (
                    SELECT symbol, close, LAG(close) OVER (PARTITION BY symbol ORDER BY date) AS prev_close
                    FROM prices
                )
                SELECT COUNT(DISTINCT symbol) AS n FROM jumps
                WHERE prev_close > 0 AND close > 0 AND ABS(LN(close/prev_close)) > 0.5
            """).iloc[0]['n']
            examples = self.query_parquet("""
                WITH jumps AS (
                    SELECT symbol, date, close,
                           LAG(close) OVER (PARTITION BY symbol ORDER BY date) AS prev_close
                    FROM prices
                )
                SELECT symbol, date, prev_close, close,
                       ROUND(((close/prev_close - 1) * 100)::DECIMAL(10,2), 2) AS pct_change
                FROM jumps
                WHERE prev_close > 0 AND close > 0 AND ABS(LN(close/prev_close)) > 0.5
                ORDER BY ABS(LN(close/prev_close)) DESC
                LIMIT 10
            """)
            results['abrupt_jumps'] = {
                'total_symbols': int(count),
                'examples': examples.to_dict(orient='records'),
            }

            # --- DWAP ratio extremes (latest bar only) ---
            count = self.query_parquet("""
                WITH latest AS (
                    SELECT symbol, close, dwap,
                           ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY date DESC) AS rn
                    FROM prices
                )
                SELECT COUNT(*) AS n FROM latest
                WHERE rn = 1 AND dwap > 0 AND (close/dwap > 2.0 OR close/dwap < 0.5)
            """).iloc[0]['n']
            examples = self.query_parquet("""
                WITH latest AS (
                    SELECT symbol, close, dwap,
                           ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY date DESC) AS rn
                    FROM prices
                )
                SELECT symbol, close, dwap, ROUND((close/dwap)::DECIMAL(10,2), 2) AS ratio
                FROM latest
                WHERE rn = 1 AND dwap > 0 AND (close/dwap > 2.0 OR close/dwap < 0.5)
                ORDER BY ABS(close/dwap - 1) DESC
                LIMIT 10
            """)
            results['dwap_ratio_extreme'] = {
                'total_symbols': int(count),
                'examples': examples.to_dict(orient='records'),
            }

            # --- Date gaps (ticker reuse signature) ---
            count = self.query_parquet("""
                WITH gaps AS (
                    SELECT symbol, date_diff('day', LAG(date) OVER (PARTITION BY symbol ORDER BY date), date) AS gap
                    FROM prices
                )
                SELECT COUNT(DISTINCT symbol) AS n FROM gaps WHERE gap > 10
            """).iloc[0]['n']
            examples = self.query_parquet("""
                WITH gaps AS (
                    SELECT symbol, date_diff('day', LAG(date) OVER (PARTITION BY symbol ORDER BY date), date) AS gap
                    FROM prices
                )
                SELECT symbol, MAX(gap) AS max_gap_days
                FROM gaps WHERE gap > 10
                GROUP BY symbol
                ORDER BY max_gap_days DESC
                LIMIT 10
            """)
            results['date_gaps'] = {
                'total_symbols': int(count),
                'examples': examples.to_dict(orient='records'),
            }

            # --- Short history ---
            count = self.query_parquet("""
                SELECT COUNT(*) AS n FROM (
                    SELECT symbol FROM prices GROUP BY symbol HAVING COUNT(*) < 252
                )
            """).iloc[0]['n']
            examples = self.query_parquet("""
                SELECT symbol, COUNT(*) AS rows FROM prices
                GROUP BY symbol HAVING COUNT(*) < 252
                ORDER BY rows ASC LIMIT 10
            """)
            results['short_history'] = {
                'total_symbols': int(count),
                'examples': examples.to_dict(orient='records'),
            }

            # --- Low recent volume (halt/delist signature) ---
            count = self.query_parquet("""
                WITH latest AS (
                    SELECT symbol, volume, vol_avg,
                           ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY date DESC) AS rn
                    FROM prices
                )
                SELECT COUNT(*) AS n FROM latest
                WHERE rn = 1 AND vol_avg > 0 AND volume > 0 AND volume/vol_avg < 0.01
            """).iloc[0]['n']
            examples = self.query_parquet("""
                WITH latest AS (
                    SELECT symbol, volume, vol_avg,
                           ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY date DESC) AS rn
                    FROM prices
                )
                SELECT symbol, volume::BIGINT AS vol, vol_avg::BIGINT AS vol_avg,
                       ROUND((volume/vol_avg)::DECIMAL(10,4), 4) AS ratio
                FROM latest
                WHERE rn = 1 AND vol_avg > 0 AND volume > 0 AND volume/vol_avg < 0.01
                ORDER BY volume/vol_avg ASC LIMIT 10
            """)
            results['low_recent_volume'] = {
                'total_symbols': int(count),
                'examples': examples.to_dict(orient='records'),
            }

            # Overall stats
            stats = self.query_parquet("""
                SELECT
                    COUNT(DISTINCT symbol) AS symbols,
                    MIN(date) AS first_date,
                    MAX(date) AS last_date,
                    COUNT(*) AS total_rows
                FROM prices
            """)
            results['universe_stats'] = stats.iloc[0].to_dict()

            # Union: all symbols flagged by ANY category — our "dirty" set
            dirty = self.query_parquet("""
                WITH jumps AS (
                    SELECT symbol FROM (
                        SELECT symbol, close, LAG(close) OVER (PARTITION BY symbol ORDER BY date) AS prev_close
                        FROM prices
                    ) WHERE prev_close > 0 AND close > 0 AND ABS(LN(close/prev_close)) > 0.5
                ),
                dwap_bad AS (
                    SELECT symbol FROM (
                        SELECT symbol, close, dwap,
                               ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY date DESC) AS rn
                        FROM prices
                    ) WHERE rn = 1 AND dwap > 0 AND (close/dwap > 2.0 OR close/dwap < 0.5)
                ),
                gaps_bad AS (
                    SELECT symbol FROM (
                        SELECT symbol, date_diff('day', LAG(date) OVER (PARTITION BY symbol ORDER BY date), date) AS gap
                        FROM prices
                    ) WHERE gap > 10
                ),
                short_bad AS (
                    SELECT symbol FROM prices GROUP BY symbol HAVING COUNT(*) < 252
                ),
                vol_bad AS (
                    SELECT symbol FROM (
                        SELECT symbol, volume, vol_avg,
                               ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY date DESC) AS rn
                        FROM prices
                    ) WHERE rn = 1 AND vol_avg > 0 AND volume > 0 AND volume/vol_avg < 0.01
                )
                SELECT COUNT(DISTINCT symbol) AS n FROM (
                    SELECT symbol FROM jumps
                    UNION SELECT symbol FROM dwap_bad
                    UNION SELECT symbol FROM gaps_bad
                    UNION SELECT symbol FROM short_bad
                    UNION SELECT symbol FROM vol_bad
                )
            """).iloc[0]['n']
            results['total_dirty_symbols'] = int(dirty)

            # JSON-serialize: convert pandas/numpy types to python primitives
            def _sanitize(obj):
                if isinstance(obj, dict):
                    return {k: _sanitize(v) for k, v in obj.items()}
                if isinstance(obj, list):
                    return [_sanitize(v) for v in obj]
                if hasattr(obj, 'isoformat'):
                    return obj.isoformat()
                if hasattr(obj, 'item'):
                    try:
                        return obj.item()
                    except Exception:
                        pass
                return obj

            return _sanitize(results)
        except Exception as e:
            import traceback
            return {"error": str(e), "trace": traceback.format_exc()[:500]}

    def export_consolidated(self, data_cache: Dict[str, pd.DataFrame]) -> Dict:
        """
        Export all cached data to a single consolidated gzipped CSV file.
        Much faster to load than individual files (single S3 GET vs 100+).
        """
        if not data_cache:
            return {"success": False, "message": "No data to export", "count": 0}

        try:
            # Combine all DataFrames into one with symbol column
            dfs = []
            for symbol, df in data_cache.items():
                if len(df) < 50:
                    continue
                df_copy = df.reset_index()
                df_copy['symbol'] = symbol
                dfs.append(df_copy)

            if not dfs:
                return {"success": False, "message": "No valid data to export", "count": 0}

            combined = pd.concat(dfs, ignore_index=True)

            # Ensure date column is proper datetime
            if 'date' in combined.columns:
                combined['date'] = pd.to_datetime(combined['date'])

            if self._use_s3():
                # Export to S3 as gzipped CSV
                buffer = io.StringIO()
                combined.to_csv(buffer, index=False)
                csv_bytes = buffer.getvalue().encode('utf-8')
                gzipped = gzip.compress(csv_bytes)

                s3 = self._get_s3_client()
                s3.put_object(
                    Bucket=S3_BUCKET,
                    Key='prices/all_prices.csv.gz',
                    Body=gzipped,
                    ContentType='application/gzip'
                )
                file_size = len(gzipped)
                storage_type = "S3"
            else:
                # Export to local file
                filepath = LOCAL_DATA_DIR / "all_prices.csv.gz"
                combined.to_csv(filepath, index=False, compression='gzip')
                file_size = filepath.stat().st_size
                storage_type = "local"

            # Save metadata
            self.last_export = datetime.now()
            self.exported_symbols = list(data_cache.keys())
            self._save_metadata()

            num_symbols = combined['symbol'].nunique()
            logger.info(f"Exported consolidated file with {num_symbols} symbols ({file_size / 1024 / 1024:.1f} MB)")

            return {
                "success": True,
                "count": num_symbols,
                "total_size_mb": round(file_size / 1024 / 1024, 2),
                "storage": storage_type,
                "bucket": S3_BUCKET if self._use_s3() else None,
                "timestamp": self.last_export.isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to export consolidated data: {e}")
            return {"success": False, "message": str(e), "count": 0}

    def _import_from_local(self) -> Dict[str, pd.DataFrame]:
        """Import parquet files from local filesystem"""
        data_cache = {}

        if not LOCAL_DATA_DIR.exists():
            logger.info("No local data directory found")
            return data_cache

        parquet_files = list(LOCAL_DATA_DIR.glob("*.parquet"))
        logger.info(f"Found {len(parquet_files)} parquet files locally")

        for filepath in parquet_files:
            try:
                symbol = filepath.stem  # filename without extension

                df = pd.read_parquet(filepath)

                # Set date as index
                if 'date' in df.columns:
                    df['date'] = pd.to_datetime(df['date'])
                    df = df.set_index('date').sort_index()

                # Compute indicators if not present
                if 'dwap' not in df.columns:
                    df = self._compute_indicators(df)

                data_cache[symbol] = df

            except Exception as e:
                logger.error(f"Failed to import {filepath.name}: {e}")

        logger.info(f"Imported {len(data_cache)} symbols from local files (with indicators)")
        return data_cache

    def get_last_date(self, symbol: str) -> Optional[datetime]:
        """
        Get the last date we have data for a symbol

        Used to determine what new data to fetch from yfinance.
        """
        try:
            if self._use_s3():
                s3 = self._get_s3_client()
                response = s3.get_object(Bucket=S3_BUCKET, Key=f"prices/{symbol}.csv")
                csv_content = response['Body'].read().decode('utf-8')
                df = pd.read_csv(io.StringIO(csv_content))
            else:
                filepath = LOCAL_DATA_DIR / f"{symbol}.parquet"
                if not filepath.exists():
                    return None
                df = pd.read_parquet(filepath)

            if 'date' in df.columns:
                return pd.to_datetime(df['date'].max())
            return None

        except Exception:
            return None

    def get_symbols_with_data(self) -> List[str]:
        """Get list of symbols that have saved data"""
        if self._use_s3():
            try:
                s3 = self._get_s3_client()
                paginator = s3.get_paginator('list_objects_v2')
                pages = paginator.paginate(Bucket=S3_BUCKET, Prefix='prices/')

                symbols = []
                for page in pages:
                    for obj in page.get('Contents', []):
                        if obj['Key'].endswith('.csv'):
                            symbol = obj['Key'].split('/')[-1].replace('.csv', '')
                            symbols.append(symbol)
                return symbols
            except Exception as e:
                logger.error(f"Failed to list S3 symbols: {e}")
                return []
        else:
            if not LOCAL_DATA_DIR.exists():
                return []
            return [f.stem for f in LOCAL_DATA_DIR.glob("*.parquet")]

    def get_status(self) -> Dict:
        """Get export status and statistics"""
        self._load_metadata()

        # Use stored count from metadata if available, otherwise count files
        symbols_count = len(self.exported_symbols) if self.exported_symbols else 0
        if symbols_count == 0:
            symbols_count = len(self.get_symbols_with_data())

        if self._use_s3():
            return {
                "storage": "s3",
                "bucket": S3_BUCKET,
                "files_count": symbols_count,
                "last_export": self.last_export.isoformat() if self.last_export else None,
                "symbols": self.exported_symbols[:50] if self.exported_symbols else []
            }
        else:
            parquet_files = list(LOCAL_DATA_DIR.glob("*.parquet")) if LOCAL_DATA_DIR.exists() else []
            total_size = sum(f.stat().st_size for f in parquet_files)

            return {
                "storage": "local",
                "data_dir": str(LOCAL_DATA_DIR),
                "files_count": len(parquet_files),
                "total_size_mb": round(total_size / 1024 / 1024, 2),
                "last_export": self.last_export.isoformat() if self.last_export else None,
                "symbols": symbols[:50]
            }

    def _save_metadata(self):
        """Save export metadata"""
        metadata = {
            "last_export": self.last_export.isoformat() if self.last_export else None,
            "symbols_count": len(self.exported_symbols),
            "exported_at": datetime.now().isoformat()
        }

        if self._use_s3():
            try:
                s3 = self._get_s3_client()
                s3.put_object(
                    Bucket=S3_BUCKET,
                    Key="prices/_metadata.json",
                    Body=json.dumps(metadata),
                    ContentType='application/json'
                )
            except Exception as e:
                logger.error(f"Failed to save metadata to S3: {e}")
        else:
            try:
                metadata_file = LOCAL_DATA_DIR / "_metadata.json"
                with open(metadata_file, 'w') as f:
                    json.dump(metadata, f)
            except Exception as e:
                logger.error(f"Failed to save metadata locally: {e}")

    def _load_metadata(self):
        """Load export metadata"""
        try:
            if self._use_s3():
                s3 = self._get_s3_client()
                response = s3.get_object(Bucket=S3_BUCKET, Key="prices/_metadata.json")
                metadata = json.loads(response['Body'].read().decode('utf-8'))
            else:
                metadata_file = LOCAL_DATA_DIR / "_metadata.json"
                if not metadata_file.exists():
                    return
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)

            if metadata.get("last_export"):
                self.last_export = datetime.fromisoformat(metadata["last_export"])
            # Load symbols count (create placeholder list for count)
            if metadata.get("symbols_count") and not self.exported_symbols:
                self.exported_symbols = ["symbol"] * metadata["symbols_count"]  # Placeholder for count
        except Exception:
            pass

    def delete_symbol(self, symbol: str) -> bool:
        """Delete saved data for a symbol"""
        try:
            if self._use_s3():
                s3 = self._get_s3_client()
                s3.delete_object(Bucket=S3_BUCKET, Key=f"prices/{symbol}.csv")
                return True
            else:
                filepath = LOCAL_DATA_DIR / f"{symbol}.parquet"
                if filepath.exists():
                    filepath.unlink()
                    return True
                return False
        except Exception as e:
            logger.error(f"Failed to delete {symbol}: {e}")
            return False

    def clear_all(self) -> int:
        """Delete all saved price data (use with caution!)"""
        count = 0

        if self._use_s3():
            try:
                s3 = self._get_s3_client()
                paginator = s3.get_paginator('list_objects_v2')
                pages = paginator.paginate(Bucket=S3_BUCKET, Prefix='prices/')

                for page in pages:
                    for obj in page.get('Contents', []):
                        s3.delete_object(Bucket=S3_BUCKET, Key=obj['Key'])
                        count += 1
            except Exception as e:
                logger.error(f"Failed to clear S3 data: {e}")
        else:
            for filepath in LOCAL_DATA_DIR.glob("*.parquet"):
                filepath.unlink()
                count += 1
            metadata_file = LOCAL_DATA_DIR / "_metadata.json"
            if metadata_file.exists():
                metadata_file.unlink()

        return count


    def export_signals_json(self, signals: list) -> Dict:
        """
        Export signals to a static JSON file on S3 for CDN delivery.

        This file is publicly accessible and cached by CloudFront,
        so the frontend can load signals instantly without API calls.

        Args:
            signals: List of SignalData objects from scanner

        Returns:
            Export result with URL
        """
        if not signals:
            return {"success": False, "message": "No signals to export", "count": 0}

        try:
            # Convert signals to JSON-serializable format
            signals_data = {
                "signals": [s.to_dict() if hasattr(s, 'to_dict') else s for s in signals],
                "generated_at": datetime.now().isoformat(),
                "count": len(signals)
            }

            json_content = json.dumps(signals_data, default=str)

            if self._use_s3():
                s3 = self._get_s3_client()

                # Upload to signals/ prefix (separate from price data)
                s3.put_object(
                    Bucket=S3_BUCKET,
                    Key='signals/latest.json',
                    Body=json_content.encode('utf-8'),
                    ContentType='application/json',
                    CacheControl='no-cache, no-store, must-revalidate'  # always fetch fresh — signal data goes stale fast
                )

                # Also save timestamped version for history
                timestamp = datetime.now().strftime('%Y-%m-%d')
                s3.put_object(
                    Bucket=S3_BUCKET,
                    Key=f'signals/{timestamp}.json',
                    Body=json_content.encode('utf-8'),
                    ContentType='application/json'
                )

                logger.info(f"Exported {len(signals)} signals to S3")

                return {
                    "success": True,
                    "count": len(signals),
                    "bucket": S3_BUCKET,
                    "key": "signals/latest.json",
                    "timestamp": datetime.now().isoformat()
                }
            else:
                # Local development - save to data directory
                signals_dir = LOCAL_DATA_DIR.parent / "signals"
                signals_dir.mkdir(parents=True, exist_ok=True)

                filepath = signals_dir / "latest.json"
                with open(filepath, 'w') as f:
                    f.write(json_content)

                logger.info(f"Exported {len(signals)} signals to {filepath}")

                return {
                    "success": True,
                    "count": len(signals),
                    "path": str(filepath),
                    "timestamp": datetime.now().isoformat()
                }

        except Exception as e:
            logger.error(f"Failed to export signals: {e}")
            return {"success": False, "message": str(e), "count": 0}

    def export_dashboard_json(self, dashboard_data: dict) -> Dict:
        """
        Export pre-computed dashboard data to S3/local for CDN delivery.

        Called by the scheduler after scans and nightly walk-forward.
        Frontend fetches this for instant dashboard loading.
        """
        try:
            json_content = json.dumps(dashboard_data, default=str)

            if self._use_s3():
                s3 = self._get_s3_client()
                s3.put_object(
                    Bucket=S3_BUCKET,
                    Key='signals/dashboard.json',
                    Body=json_content.encode('utf-8'),
                    ContentType='application/json',
                    CacheControl='no-cache, no-store, must-revalidate'  # always fetch fresh — signal data goes stale fast
                )
                logger.info(f"Exported dashboard JSON to S3 ({len(json_content)} bytes)")
                return {"success": True, "storage": "s3", "bucket": S3_BUCKET}
            else:
                signals_dir = LOCAL_DATA_DIR.parent / "signals"
                signals_dir.mkdir(parents=True, exist_ok=True)
                filepath = signals_dir / "dashboard.json"
                with open(filepath, 'w') as f:
                    f.write(json_content)
                logger.info(f"Exported dashboard JSON to {filepath}")
                return {"success": True, "storage": "local", "path": str(filepath)}

        except Exception as e:
            logger.error(f"Failed to export dashboard JSON: {e}")
            return {"success": False, "message": str(e)}

    def read_dashboard_json(self) -> Optional[dict]:
        """
        Read pre-computed dashboard data from S3/local.

        Returns the cached dashboard dict, or None if not available.
        """
        try:
            if self._use_s3():
                s3 = self._get_s3_client()
                response = s3.get_object(Bucket=S3_BUCKET, Key='signals/dashboard.json')
                content = response['Body'].read().decode('utf-8')
                return json.loads(content)
            else:
                filepath = LOCAL_DATA_DIR.parent / "signals" / "dashboard.json"
                if filepath.exists():
                    with open(filepath, 'r') as f:
                        return json.load(f)
                return None
        except Exception as e:
            logger.warning(f"Failed to read dashboard JSON: {e}")
            return None

    def export_snapshot(self, date_str: str, dashboard_data: dict) -> Dict:
        """
        Export a date-keyed dashboard snapshot for time-travel mode.

        S3 key: snapshots/{date_str}/dashboard.json
        Local: data/snapshots/{date_str}/dashboard.json
        """
        try:
            json_content = json.dumps(dashboard_data, default=str)

            if self._use_s3():
                s3 = self._get_s3_client()
                s3.put_object(
                    Bucket=S3_BUCKET,
                    Key=f'snapshots/{date_str}/dashboard.json',
                    Body=json_content.encode('utf-8'),
                    ContentType='application/json',
                )
                logger.info(f"Exported snapshot for {date_str} to S3 ({len(json_content)} bytes)")
                return {"success": True, "storage": "s3", "date": date_str}
            else:
                snapshot_dir = LOCAL_DATA_DIR.parent / "snapshots" / date_str
                snapshot_dir.mkdir(parents=True, exist_ok=True)
                filepath = snapshot_dir / "dashboard.json"
                with open(filepath, 'w') as f:
                    f.write(json_content)
                logger.info(f"Exported snapshot for {date_str} to {filepath}")
                return {"success": True, "storage": "local", "path": str(filepath)}

        except Exception as e:
            logger.error(f"Failed to export snapshot for {date_str}: {e}")
            return {"success": False, "message": str(e)}

    def compute_signal_continuity(
        self, today_symbols: List[str], lookback_days: int = 14
    ) -> Dict[str, Dict]:
        """For each symbol in today's buy_signals, compute consecutive-day
        continuity by reading recent daily snapshots from S3.

        Returns: {symbol: {
            consecutive_days: int,        # length of the current uninterrupted run
            is_new_today:    bool,        # True iff today is day 1 of a fresh run
            is_resignal:     bool,        # True iff the run started after a >=2 day gap
            gap_days_before: int|None,    # trading days the symbol was missing right before
                                          # the current run started (None unless is_resignal)
            run_started_date: str|None,   # ISO date when the current run began
        }}

        Rules:
        - 0-day gap (consecutive trading days): Day count grows.
        - 1-day gap: tolerated (data noise); count continues across it but the gap
                     day itself is not counted as a present day.
        - >=2 day gap: run breaks; current run starts after the gap.
        - We only consider days for which a snapshot exists (= trading days).
          Weekends and holidays don't have snapshots, so they don't count as
          "missing" — going from Friday to Monday is one consecutive trading day.

        Edge: if our lookback only contains a small number of days, we report what
        we can see; we don't fabricate a gap from "before our visibility window."
        """
        from datetime import date, timedelta
        today = date.today()

        # Build a map of {date_iso: set_of_symbols} for each day we have a snapshot.
        # Skip the no-snapshot dates (weekends, holidays, scan failures) entirely.
        snap_by_date: Dict[str, set] = {}
        for d_offset in range(0, lookback_days + 1):
            d = today - timedelta(days=d_offset)
            d_str = d.strftime("%Y-%m-%d")
            snap = self.read_snapshot(d_str)
            if snap and isinstance(snap.get('buy_signals'), list):
                snap_by_date[d_str] = {
                    s.get('symbol') for s in snap['buy_signals'] if s.get('symbol')
                }

        # Trading days we have data for, oldest first
        sorted_dates = sorted(snap_by_date.keys())
        if not sorted_dates:
            return {sym: {
                "consecutive_days": 1, "is_new_today": True, "is_resignal": False,
                "gap_days_before": None, "run_started_date": None,
            } for sym in today_symbols}

        out: Dict[str, Dict] = {}
        for sym in today_symbols:
            # Presence list in chronological order; last entry = today (or most recent snap)
            presence = [(d, sym in snap_by_date[d]) for d in sorted_dates]

            # Defensive: if today's snap doesn't yet contain the symbol (caller is
            # mid-build before the snapshot is written) treat as fresh-day-1.
            if not presence[-1][1]:
                out[sym] = {
                    "consecutive_days": 1, "is_new_today": True, "is_resignal": False,
                    "gap_days_before": None, "run_started_date": presence[-1][0],
                }
                continue

            # Walk backward through trading days; tolerate single-day gaps, break on 2+.
            run_length = 0
            run_start_date = None
            pending_misses = 0
            broke_on_gap = False
            i = len(presence) - 1
            while i >= 0:
                d_str, is_present = presence[i]
                if is_present:
                    run_length += 1
                    run_start_date = d_str
                    pending_misses = 0
                else:
                    pending_misses += 1
                    if pending_misses >= 2:
                        broke_on_gap = True
                        break
                i -= 1

            # If broken on gap, count the full gap length going further back
            gap_days_before = 0
            if broke_on_gap:
                gap_days_before = pending_misses
                j = i - 1
                while j >= 0 and not presence[j][1]:
                    gap_days_before += 1
                    j -= 1

            out[sym] = {
                "consecutive_days": run_length,
                "is_new_today": run_length == 1,
                "is_resignal": gap_days_before >= 2,
                "gap_days_before": gap_days_before if gap_days_before >= 2 else None,
                "run_started_date": run_start_date,
            }

        return out

    def read_snapshot(self, date_str: str) -> Optional[dict]:
        """
        Read a date-keyed dashboard snapshot for time-travel mode.

        Returns the snapshot dict, or None if not available.
        """
        try:
            if self._use_s3():
                s3 = self._get_s3_client()
                response = s3.get_object(
                    Bucket=S3_BUCKET,
                    Key=f'snapshots/{date_str}/dashboard.json',
                )
                content = response['Body'].read().decode('utf-8')
                return json.loads(content)
            else:
                filepath = LOCAL_DATA_DIR.parent / "snapshots" / date_str / "dashboard.json"
                if filepath.exists():
                    with open(filepath, 'r') as f:
                        return json.load(f)
                return None
        except Exception as e:
            if 'NoSuchKey' not in str(e):
                logger.warning(f"Failed to read snapshot for {date_str}: {e}")
            return None

    def get_dashboard_url(self) -> str:
        """Get the public URL for the dashboard JSON."""
        if self._use_s3():
            return f"https://{S3_BUCKET}.s3.amazonaws.com/signals/dashboard.json"
        else:
            return "/api/signals/dashboard.json"

    def get_signals_url(self) -> str:
        """
        Get the public URL for the latest signals JSON.

        In production, this should be the CloudFront URL.
        """
        if self._use_s3():
            # Return S3 URL - in production this should be the CloudFront URL
            return f"https://{S3_BUCKET}.s3.amazonaws.com/signals/latest.json"
        else:
            return "/api/signals/latest.json"

    # ─────────────────── Parquet migration Stage 3a — diff harness ───────────────────

    async def compare_pickle_to_parquet(
        self,
        pickle_data: Dict[str, "pd.DataFrame"],
        sample_value_diffs: int = 5,
        batch_size: int = 100,
    ) -> Dict:
        """
        Compare pickle-sourced data_cache against parquet symbol-by-symbol via
        batched filtered reads. Writes divergence rows to
        parquet_divergence_events. Returns a summary dict.

        Args:
            pickle_data: dict[symbol -> DataFrame] — typically scanner_service.data_cache
            sample_value_diffs: how many mismatched cells to record per (symbol,
                column) — keeps details_json bounded.
            batch_size: how many symbols to filter-read per parquet query. Trades
                memory (~50KB/symbol × batch) against query overhead.

        Memory profile: downloads parquet to /tmp once (disk, not RAM), then
        reads `batch_size` symbols at a time via pyarrow filter. Peak RAM
        beyond pickle_data is ~batch_size × 50KB = ~5 MB. Constant regardless
        of universe size — won't OOM the Worker like the prior load-the-whole-
        parquet approach did on Apr 28 2026.

        Used by Stage 3a parallel-read observation; see
        project_parquet_stage3_plan.md.
        """
        import json as _json
        import pandas as _pd
        import os
        import tempfile
        from app.core.database import async_session, ParquetDivergenceEvent

        # 1. Stage parquet to /tmp (disk, not RAM) — single S3 download
        tmp_path = None
        try:
            if self._use_s3():
                s3 = self._get_s3_client()
                tmp_path = os.path.join(tempfile.gettempdir(), "compare_data.parquet")
                with open(tmp_path, 'wb') as f:
                    obj = s3.get_object(Bucket=S3_BUCKET, Key='prices/all_data.parquet')
                    for chunk in obj['Body'].iter_chunks(chunk_size=8 * 1024 * 1024):
                        f.write(chunk)
                source = tmp_path
            else:
                source = str(LOCAL_DATA_DIR / "all_data.parquet")
        except Exception as e:
            print(f"⚠️ compare_pickle_to_parquet: failed to stage parquet: {e}")
            return {"compared": 0, "diverged": 0, "diverged_symbols": 0,
                    "by_type": {}, "error": str(e)[:300]}

        # 2. Discover parquet's symbol set (CHEAP — read just the symbol column)
        try:
            import pyarrow.parquet as pq
            sym_table = pq.read_table(source, columns=['symbol'])
            parquet_symbols = set(sym_table.column('symbol').unique().to_pylist())
            del sym_table
        except Exception as e:
            print(f"⚠️ compare_pickle_to_parquet: failed to list parquet symbols: {e}")
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)
            return {"compared": 0, "diverged": 0, "diverged_symbols": 0,
                    "by_type": {}, "error": str(e)[:300]}

        all_symbols = sorted(set(pickle_data.keys()) | parquet_symbols)
        events: List[Dict] = []  # accumulated, single-batch write at the end

        # Columns we actually care about value-comparing. Indicators (dwap,
        # ma_50, ma_200) get recomputed lazily, so a mismatch there isn't
        # necessarily corruption — close/volume/high/low/open are the load-bearing
        # raw columns.
        value_cols = ['open', 'high', 'low', 'close', 'volume']

        # 3. Process symbols in batches: filter-read each batch from the staged
        #    parquet (constant memory ~5 MB regardless of universe size),
        #    compare against pickle, free the batch, move on.
        def _read_parquet_batch(syms):
            try:
                df = _pd.read_parquet(source, filters=[('symbol', 'in', syms)])
                if df.empty:
                    return {}
                out = {}
                for s, group in df.groupby('symbol'):
                    out[s] = group.drop(columns=['symbol']).set_index('date').sort_index()
                return out
            except Exception as e:
                print(f"⚠️ compare: batch read failed: {e}")
                return {}

        for batch_start in range(0, len(all_symbols), batch_size):
            batch_syms = all_symbols[batch_start:batch_start + batch_size]
            # Only filter-read the batch_syms that exist in parquet at all
            batch_syms_in_parquet = [s for s in batch_syms if s in parquet_symbols]
            parquet_batch = _read_parquet_batch(batch_syms_in_parquet) if batch_syms_in_parquet else {}

            for sym in batch_syms:
                p_rows = 0
                q_rows = 0
                try:
                    p_df = pickle_data.get(sym)
                    q_df = parquet_batch.get(sym)

                    p_rows = len(p_df) if p_df is not None else 0
                    q_rows = len(q_df) if q_df is not None else 0

                    if p_df is None:
                        events.append({
                            "symbol": sym, "type": "missing_in_pickle",
                            "details": {"parquet_rows": q_rows},
                            "p_rows": 0, "q_rows": q_rows,
                        })
                        continue

                    if q_df is None:
                        events.append({
                            "symbol": sym, "type": "missing_in_parquet",
                            "details": {"pickle_rows": p_rows},
                            "p_rows": p_rows, "q_rows": 0,
                        })
                        continue

                    # Both present — structural compare
                    if p_rows != q_rows:
                        events.append({
                            "symbol": sym, "type": "row_count_diff",
                            "details": {"pickle_rows": p_rows, "parquet_rows": q_rows,
                                        "delta": p_rows - q_rows},
                            "p_rows": p_rows, "q_rows": q_rows,
                        })

                    # `date` representation differs by store: pyarrow's natural
                    # form puts it on the DataFrame index, while older pickle
                    # exports kept it as a regular column. The diff harness
                    # should treat "index named X" and "column named X" as the
                    # same logical fact on either side. Without the symmetric
                    # parquet normalization below, every symbol reported a
                    # spurious column_set_diff (~4750 events/day) blocking the
                    # Stage 3b cutover for what was a representation difference,
                    # not a data difference.
                    p_cols = set(p_df.columns)
                    if p_df.index.name:
                        p_cols.add(p_df.index.name)
                    q_cols = set(q_df.columns)
                    if q_df.index.name:
                        q_cols.add(q_df.index.name)
                    if p_cols != q_cols:
                        events.append({
                            "symbol": sym, "type": "column_set_diff",
                            "details": {"only_in_pickle": sorted(p_cols - q_cols),
                                        "only_in_parquet": sorted(q_cols - p_cols)},
                            "p_rows": p_rows, "q_rows": q_rows,
                        })

                    # Value compare on overlapping date range, common columns
                    shared_cols = [c for c in value_cols if c in p_cols and c in q_cols]
                    if not shared_cols:
                        continue

                    # Align on shared dates only — pickle/parquet may have different
                    # tail behavior (e.g. one has today's bar, other doesn't yet)
                    shared_idx = p_df.index.intersection(q_df.index)
                    if len(shared_idx) == 0:
                        events.append({
                            "symbol": sym, "type": "index_range_diff",
                            "details": {
                                "pickle_first": str(p_df.index.min()) if p_rows else None,
                                "pickle_last": str(p_df.index.max()) if p_rows else None,
                                "parquet_first": str(q_df.index.min()) if q_rows else None,
                                "parquet_last": str(q_df.index.max()) if q_rows else None,
                            },
                            "p_rows": p_rows, "q_rows": q_rows,
                        })
                        continue

                    p_sub = p_df.loc[shared_idx, shared_cols]
                    q_sub = q_df.loc[shared_idx, shared_cols]

                    # Use a small relative tolerance — float roundtrip via parquet can
                    # introduce 1e-7 noise on prices; that's not corruption.
                    # Only flag genuine value differences.
                    for col in shared_cols:
                        p_col = _pd.to_numeric(p_sub[col], errors='coerce')
                        q_col = _pd.to_numeric(q_sub[col], errors='coerce')
                        diff_mask = ~((p_col == q_col) | (p_col.isna() & q_col.isna()))
                        # Tolerate tiny float roundtrip noise (relative 1e-6)
                        if col != 'volume':  # volume is integer, no tolerance needed
                            rel_err = (p_col - q_col).abs() / p_col.abs().replace(0, 1)
                            diff_mask = diff_mask & (rel_err > 1e-6)
                        n_diffs = int(diff_mask.sum())
                        if n_diffs > 0:
                            sample = []
                            for idx in p_sub.index[diff_mask][:sample_value_diffs]:
                                sample.append({
                                    "date": str(idx),
                                    "pickle": _safe_json_value(p_col.loc[idx]),
                                    "parquet": _safe_json_value(q_col.loc[idx]),
                                })
                            events.append({
                                "symbol": sym, "type": "value_diff",
                                "details": {"column": col, "n_diffs": n_diffs,
                                            "compared_rows": len(shared_idx),
                                            "sample": sample},
                                "p_rows": p_rows, "q_rows": q_rows,
                            })

                except Exception as e:
                    events.append({
                        "symbol": sym, "type": "compare_error",
                        "details": {"error": str(e)[:300]},
                        "p_rows": p_rows,
                        "q_rows": q_rows,
                    })

        # Single batched DB write — keeps connection cost low even with many events
        if events:
            async with async_session() as db:
                for e in events:
                    db.add(ParquetDivergenceEvent(
                        symbol=e["symbol"],
                        divergence_type=e["type"],
                        details_json=_json.dumps(e["details"], default=str)[:8000],
                        pickle_row_count=e.get("p_rows"),
                        parquet_row_count=e.get("q_rows"),
                    ))
                await db.commit()

        # Cleanup: remove the staged parquet from /tmp (frees ~350 MB ephemeral)
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass

        # Build summary
        from collections import Counter
        by_type = Counter(e["type"] for e in events)
        return {
            "compared": len(all_symbols),
            "diverged": len(events),
            "diverged_symbols": len({e["symbol"] for e in events}),
            "by_type": dict(by_type),
        }


def _safe_json_value(v):
    """Coerce numpy/pandas scalars to JSON-serializable Python types."""
    try:
        import math
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except Exception:
        return None


# Singleton instance
data_export_service = DataExportService()
