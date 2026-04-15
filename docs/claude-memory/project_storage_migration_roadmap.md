---
name: Roadmap away from gzipped pickle storage
description: Options, trade-offs, and triggers for migrating market data off the 275MB gzipped pickle toward parquet / DuckDB / TimescaleDB
type: project
originSessionId: 39ce1e26-1ab7-4fbd-8e9a-6c892d933b00
---
## Why this matters

The current architecture stores ~4500 symbols × 7yr OHLCV + indicators in a single gzipped pickle (`s3://rigacap-prod-price-data-149218244179/prices/all_data.pkl.gz`, ~275MB compressed, loads into ~1.5GB RAM). This worked for bootstrapping but has structural problems that bit us repeatedly during Apr 2026 debugging:

- **Memory cost:** Worker Lambda needs 4GB just to hold the data. API Lambda can't load it at all — forced us to build a separate dashboard.json cache.
- **Atomic-rewrite bottleneck:** every daily scan rewrites the whole 275MB pickle to S3. Pickle-shrink guardrail (Apr 1) existed precisely because of this fragility. Triggered false-positive blocks and hid silent failures.
- **Indicator management:** fetch_incremental strips/appends raw OHLCV bars. Indicators re-compute lazily but the recompute logic has bitten us twice (NaN-tail bug + missing-column bug in Apr 2026 drought).
- **No schema enforcement:** pandas DataFrames with mixed tz-awareness, inconsistent date alignment (broke Apr 2026 after split-refetch had end=today while rest of pickle was end=yesterday), silent data-type drift.
- **No partial reads:** can't query one symbol without loading whole blob. Every diagnostic handler has to iterate the full cache.
- **Concurrency:** concurrent writes to the same pickle would corrupt it. Only saved by serial single-writer cron.

## Ranked migration options

### Option 1 — Parquet on S3, partitioned by symbol (LOW FRICTION — recommended first)

- `s3://.../prices/parquet/symbol=NVDA/year=2024/*.parquet` etc.
- `pandas.read_parquet(path)` reads one symbol in milliseconds without loading anything else
- Indicator columns can live in separate parquet files, or in the same file (column schema enforced)
- Atomic per-symbol writes — one bad fetch doesn't blow up everyone
- Gains: ~50% size reduction vs pickle (parquet's columnar compression beats gzip)
- Cost: ~8-16 hours to migrate + code changes to scanner/backtester
- Risk: low. Parquet is battle-tested. Pandas supports it natively. No runtime dependencies beyond pyarrow.

### Option 2 — DuckDB over S3 parquet (SQL LAYER)

- Builds on Option 1
- Adds `duckdb.sql("SELECT * FROM 's3://.../prices/parquet/symbol=NVDA/*.parquet' WHERE date > '2024-01-01'")`
- Enables admin queries, ad-hoc analytics, per-symbol dashboards without Python scripts
- Cost: +2-4 hours on top of Option 1
- Risk: low. DuckDB is the right tool for this exact pattern.

### Option 3 — TimescaleDB (Postgres time-series extension)

- One database for everything: trades, positions, prices, regimes, users
- Native time-series features (continuous aggregates, retention policies, compression)
- All our existing Postgres code stays compatible
- Cost: ~20-40 hours migration + RDS plan upgrade ($25-50/mo extra)
- Risk: medium. Can the WF backtester handle SQL-fetch latency? Current pandas bulk-load is fast because it's in-memory.

### Option 4 — QuestDB / ClickHouse (purpose-built time-series)

- Extreme performance but adds operational complexity
- Not worth the investment for our scale
- **Skip unless we hit a scaling wall Option 1-3 can't solve**

## Recommended sequencing (UPDATED Apr 15 2026)

**Decision: migrate to Parquet NOW, before marketing blitz.** Erik's reasoning: only 2 active users (6 invited, 4 inactive) means disruption tolerance is highest it will ever be. Every major architectural change destabilizes before it strengthens. Better to absorb that pain pre-paid-subscribers than post-launch.

## Four-stage plan (committed Apr 15 2026)

**Stage 1: Shadow write (DONE Apr 14-15 2026)** ✅
- `data_export_service.export_parquet()` writes `s3://<bucket>/prices/all_data.parquet` alongside pickle on every daily_scan + hygiene run
- `data_export_service.import_parquet(symbols=None)` reads back with filtered/partial support
- DuckDB SQL queries validated on Lambda (via /tmp download workaround due to AL2 glibc)
- Both stores stay in lockstep — every update writes both

**Stage 2: Lambda runtime upgrade to AL2023** (NEXT — queued)
- Rebase Dockerfile from `python:3.9` (AL2) to `python:3.11+` (AL2023)
- Enables native DuckDB httpfs extension (no /tmp workaround needed)
- 10-25% faster Python execution = lower Lambda bill
- ~2-4 hour focused session
- Test: full regression on local + canary deploy

**Stage 3: Consumer migration** — migrate scanner/backtester/WF from pickle-sourced `data_cache` to per-symbol parquet reads
- `scanner.py` — lazy dict, loads per-symbol from parquet on demand
- `backtester.py` — same pattern, per-symbol lazy loads
- `walk_forward_service.py` — per-period loads instead of whole-universe
- Huge memory win (most scans only touch top 100 symbols; Worker Lambda could drop from 3GB → 500MB)
- ~6-10 hours

**Stage 4: Decommission pickle**
- Remove `export_pickle()` / `import_pickle()` path
- Delete the gzipped pickle from S3 (keep backups)
- Guardrail and size-check code becomes dead
- Dashboard.json cache may become unnecessary for many queries (API Lambda can read parquet directly via DuckDB post-AL2023)
- ~2-4 hours

**Stage 5 (optional): DuckDB as primary query engine**
- Admin diagnostics page with SQL console
- Replace Python-loop diagnostics with SQL
- Adds operational leverage once comfortable with parquet

## Future options if we outgrow parquet

- **TimescaleDB** only if we consolidate infra (unlikely in the next 12 months)
- **QuestDB / ClickHouse** — not planned, revisit only if scaling wall hit

## Session-specific pickle issues that informed this

- Indicator-strip bug (Apr 2026): fetch_incremental stripped indicators, 3.5 weeks of silent signal drought. Fixed, but highlighted fragility.
- NaN-tail bug: `_ensure_indicators` didn't detect partial NaN column, just fully-missing. Fixed.
- Split misalignment bug (Apr 14 2026): local refetch ended at `datetime.now()` while rest of pickle was at prior close. Caused -85% fake returns in WF. Fixed by truncation.
- Size guardrail false positive (Mar 28): pickle shrunk legitimately from indicator-strip, guardrail blocked exports for 4 days.
- Lambda cold start: 9-10s INIT loading 275MB pickle. Lives in the memory budget before our code even runs.

Each of these would have been impossible or trivial to detect under parquet + SQL.
