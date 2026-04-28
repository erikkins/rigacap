---
name: AL2023 Lambda runtime — DEPLOYED
description: Python 3.12 / AL2023 (glibc 2.34) is live in production for both API and Worker Lambdas. Migration completed via commit 21f9e51 sometime after Apr 15.
type: project
originSessionId: 1081317d-f863-470f-ab07-65ddc614e856
---
## Status: DEPLOYED

- **Dockerfile:** `backend/Dockerfile.lambda` is on `public.ecr.aws/lambda/python:3.12`
- **Migration commit:** `21f9e51 AL2023 migration: Python 3.11 → 3.12 (glibc 2.26 → 2.34)`
- **Both Lambdas (API + Worker) run Python 3.12 / AL2023.** Confirmed from worker traceback (`/var/lang/lib/python3.12/`).

## Side effects observed (Apr 28 2026)

- **Stricter pandas surfaced a tz-naive vs tz-aware comparison bug** in `market_regime.calculate_conditions` and `detect_regime` (`InvalidComparison: 2026-04-27 00:00:00-04:00`). Fixed across 4 sites by adding `elif as_of_ts.tz is not None: as_of_ts = as_of_ts.tz_localize(None)`. There are similar patterns in `scanner.py` (lines 636, 763) and `walk_forward_service.py` (lines 363, 1277, 1291, 1874) that may surface as the bug stack drains — defensive cleanup TODO.
- **DuckDB httpfs now usable** without /tmp workaround. The migration was a prereq for parquet/DuckDB Stage 3.

## What this unblocks

- Storage migration **Stage 3 (consumer migration to parquet)** can proceed — ~6-10 hours, biggest memory win.
