---
name: Roadmap away from gzipped pickle storage
description: "Pickle → parquet migration. REVISED Jun 10 2026: the migration target is now the PITFWU per-symbol layer itself (promote research store to canonical) — absolute research↔prod data parity, not just an infra win. See the Jun 10 section first."
type: project
originSessionId: 39ce1e26-1ab7-4fbd-8e9a-6c892d933b00
---

## ✅ FALLBACK / PROVENANCE POLICY (Jun 14 2026, Erik-approved): self-heal price store + immutable provenance log
The daily-veneer-vs-pickle diff (Jun 14) found the per-day spikes are ONE day: **2026-03-27, entire universe, source-difference-shaped (mixed signs ±0.1-1.4%) = an Alpaca-outage/yfinance-fallback day** baked into the pickle. Not dividends, not a convention gap. Veneer matches pickle on 89/90 days. **Stock cutover gate is essentially MET** — the only divergence is the one fallback day, where the clean Alpaca veneer is MORE canonical than the pickle's yfinance stopgap.

THREE-LAYER data architecture (Erik's framing):
1. **PITFWU price store** = canonical Alpaca RAW, **SELF-HEALS** fallback days. yfinance is a reliability STOPGAP, not a data choice. When Alpaca recovers, re-fetch & overwrite the provisional bar. Backtests run on clean, consistent, reproducible single-source data. (Option A short-term fallback.)
2. **Decision ledger** (model_positions / signals tables) = immutable record of what was actually traded (entry prices, P&L). Already exists. The live book's recorded entry price is real regardless of source.
3. **Provenance log (NEW, immutable)** = EVERY fallback event logged, trade or no trade: {date, symbol, source=yfinance, reason, value_at_time, decision (entry/exit/none + ref), healed, healed_value, healed_at}. Row written the instant a fallback happens; the heal step UPDATES it (healed=true + Alpaca value) but NEVER deletes. So even after the price store heals to Alpaca, there's a permanent record that yfinance was used on date X and what we did on it. Erik: "I still want a record that we used yfinance at some point, whether there was an entry or not."

Rationale: price store wants consistent true prices (substrate); the fact that we deviated is an AUDIT concern (provenance); what we traded is a LEDGER concern. Three jobs, three stores. The ±0.1-1.4% one-day diff is NOT decision-material (no signal flips), so self-healing costs nothing in fidelity.

IMPLEMENTATION (freshness pipeline): each run writes Alpaca RAW; on Alpaca-down, write provisional (yfinance) + provenance row; next successful run re-fetches last ~5 days from Alpaca, overwrites provisionals, updates provenance healed=true. Rare (1/90 days), cheap, self-correcting.

## ✅ CONVENTION DECIDED (Jun 13 2026, Erik-approved): OPTION A — RAW bars + adjust-at-read is canonical
Erik confirmed Option A after the pickle-vs-PITFWU diff. **Canonical store = raw as-traded bars + corp-actions calendar, adjustments applied AT READ (PITFWU/veneer style), split-only price-return.** Prod aligns to this; the adjusted-baked pickle/`all_data.parquet` convention is RETIRED.
- **Diff result that drove the call:** on a common date (2026-06-04) pickle == PITFWU split-adjusted to the PENNY (0.00% on SNDK/WULF/BAC/KEY/KO/KVUE/VZ/SPY). The apparent gaps in the naive diff were PURE STALENESS (PITFWU ends ~Jun 4, no freshness pipeline yet) + the latest-price quirk (dividend adj only back-adjusts HISTORICAL prices). **No data-quality divergence — the migration is plumbing, not a data rescue.**
- **Why A (design reasons, not infra):** raw bars are immutable facts, adjustments are derived views (CRSP/Bloomberg standard); kills the re-adjustment bug class that caused EVERY prior data bug (Jun-4 pickle split discontinuity, min-price-on-end-adjusted exclusion, 7y-pickle-can't-reproduce-9y) — a new split becomes a one-line calendar entry, past bars never change; same bytes as research; verifiable vs any vendor; consistent with the canon (8.3%/19% came from split-only price-return, so prod REALIZES it not approximates).
- **The hard part = construction risk, not design risk:** the FRESHNESS PIPELINE must fetch+store RAW bars (vendors default to adjusted — Alpaca `adjustment='raw'`, yfinance `auto_adjust=False`+actions) AND detect daily corp actions to keep the calendar current. Guardrail discipline as pickle (symbol-count checks, backups, atomic per-symbol writes) + shadow validation before cutover.
- **Concrete sequence:** (1) raw-fetch + corp-action freshness pipeline → pitfwu/bars/; (2) prod read-path through the veneer (adjust-at-read; worker has headroom, partial-read solves the 3008MB cap); (3) shadow-diff both stores daily ~1 wk (harness exists); (4) cut over + retire pickle + retire `all_data.parquet`. End state: ONE store (PITFWU canonical), read by prod AND research.
- **Timing (Jun 13):** start the freshness pipeline this coming week (AFTER Mon Jun 15 confirms the live entry path on the current substrate); cut over once shadow proves clean (~1 wk out). NOT a hot flip onto the live book.

## ⭐ REVISED TARGET (Jun 10 2026, Erik-approved): promote PITFWU to canonical — research↔prod 1:1
Erik's framing: "wouldn't we want production to use the SAME EXACT parquet we're using for research? ABSOLUTE 1:1 parity." Decision: **the migration target is no longer a parquet mirror of the pickle (`prices/all_data.parquet`) — it is the PITFWU layer (`pitfwu/bars/{sym}.parquet` + corp_actions calendar + universe panels + veneer composition).** Marketing numbers then come from literally the same bytes prod trades on, and the entire two-stores bug class dies (min-price-on-end-adjusted bug, 7y-pickle-can't-reproduce-9y-validation, Jun-4 pickle split bug — all were two-store artifacts).

What's needed before cutover (≈1-2 wks careful work, NOT now — strategy decision still gates customer-facing):
1. **Freshness pipeline** — 4:30 PM scan appends daily bars per symbol to pitfwu/bars/, updates corp-actions calendar + rolls panels. Same guardrail discipline as pickle (symbol-count checks, backups, atomic per-symbol writes). The dual-source scan already produces the data; this is a write-path change.
2. **One adjustment convention, decided explicitly** (per [[parquet-fix-not-silence]]): prod pickle = fully adjusted; PITFWU = RAW + split-adjustment at read, price-return (no dividends). Proposal: PITFWU split-only price-return becomes canonical, prod aligns; existing diff harness validates a shadow period before cutover.
3. **Prod never reads the pre-2016 EXT layer** (yfinance-sourced, survivorship-biased, research-only behind v.EXT opt-in flag — built Jun 10: bars_ext/ 2096 symbols 2005+, calendar_pre2016, *_ext panels).
4. Indicators computed at load (Worker has headroom); per-symbol partial reads finally solve the 3008 MB Lambda cap — the original motivation, now a side benefit.

Stages 1-2 below (shadow write, AL2023) remain valid groundwork; Stage 3+ retargets to PITFWU instead of the monolith parquet.
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
