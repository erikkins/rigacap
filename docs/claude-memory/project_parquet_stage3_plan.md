---
name: Parquet Stage 3 cutover plan
description: Detailed sequencing for migrating data reads from pickle to parquet, with parallel-read diff harness, staged cutover via feature flag, and 30-day rollback retention.
type: project
originSessionId: 1081317d-f863-470f-ab07-65ddc614e856
---
## Why this plan exists

Stage 1 (shadow write) has been running since Apr 14-15 — both pickle and parquet are written every daily scan. Stage 2 (AL2023/Python 3.12) deployed sometime before Apr 28. The remaining work (Stage 3 consumer migration, Stage 4 decommission) needs careful sequencing because there's no formal regression suite — we use the daily walk-forward as continuous integration, plus a dedicated divergence-events log during the parallel-read window.

## Sequencing (committed Apr 28 2026)

### Stage 3a — Parallel-read + diff harness (~6-8h)

**3a-1:** `data_export_service.read_both_and_compare(symbol)` reads both stores, returns the pickle copy (zero behavior change), logs any divergence to `parquet_divergence_events` table. Diff includes: column set, row count, index range/dtype, sampled value-level diffs on close/volume/key indicators.

**3a-2:** Wire one production read site (daily scan symbol-load loop) to use the harness behind `PARQUET_PARALLEL_READ=true` env var. DB migration adds `parquet_divergence_events` table.

**3a-3:** `GET /api/admin/parquet-divergence` endpoint — returns counts by column/symbol over a window. Lets us spot patterns ("VIX has tz divergence on every read"; "BRK-B never matches").

**3a-4:** Two-week observation window. Acceptance for moving to 3b: zero divergences on close/volume/indicator columns for 7 consecutive days, OR all observed divergences are explainable + filterable.

### Stage 3b — Read-from-parquet feature flag (~6-8h)

Add `READ_FROM_PARQUET=false` env var (default off). When true, scanner_service backs `data_cache` via per-symbol parquet lazy loads. **Set on Worker first** (smaller blast radius — only ~6 cron paths use it). Run for 1 week. Watch nightly WF + daily scan for regressions.

Rollback: flip env var, redeploy. ~5 min.

### Stage 3c — API + admin cutover (~2-3h)

After Worker stable for 1+ week, flip API + admin Lambdas. Side benefit: API Lambda can drop scanner_service module-level import (Stage 4 prep) since lazy parquet loads remove the "must be a worker to touch price data" constraint.

### Stage 4 — Decommission pickle (~3-4h)

Only after 30+ days of stable parquet reads with zero divergence events. Stop writing pickle, delete `s3://.../prices/all_data.pkl.gz` (keep one /backups copy forever), remove pickle import paths, remove guardrail/size-check code. Optional: remove dashboard.json cache if API can read parquet via DuckDB.

## Safety nets (three independent)

1. **3a-2 divergence log** — production traffic does the testing, mechanical
2. **Daily walk-forward result delta** — existing canary; subtle data corruption surfaces in equity-curve diff vs pickle baseline within one day
3. **Pickle retention** — kept writing through 3b/3c, kept readable for 30+ days post-cutover. Rollback is one env var.

## What's NOT in scope

- Removing the `dashboard.json` S3 cache — that's separate, only relevant if API Lambda gets fast enough at parquet reads to skip the cache layer
- Migrating WalkForwardSimulation/PeriodResult tables to parquet — those stay in Postgres
- TimescaleDB/QuestDB — explicitly skipped per the original storage-migration roadmap

## Decision points / off-ramps

- **After 3a-4:** if divergence rate is high or unexplainable, pause. Fix parquet writer first.
- **After 3b Worker:** if regression spike, revert (5 min) and don't proceed to 3c.
- **Before Stage 4:** require 30+ days zero-divergence + zero pipeline regressions. If anything's been flaky, extend retention.

## Estimated total

~25-30 hours of focused work, spread over ~6 weeks (most of it is observation windows, not active coding).
