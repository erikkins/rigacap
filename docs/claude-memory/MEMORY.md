# Stocker App - Key Learnings

## CRITICAL DEPLOYMENT RULES
- **NEVER deploy DB schema changes without running the migration FIRST.** Migration-first pattern: deploy SQL → run → verify, THEN deploy model changes.
- **NEVER use `aws lambda update-function-configuration --environment`** — it REPLACES ALL env vars, causing full outage.
- **Always deploy via CI/CD (push to main).** Manual `deploy-container.sh` races with CI/CD.
- The `run_migration` Lambda event handler can run ALTER TABLE without auth.

## AWS
- **Always use `--profile rigacap`** (account 149218244179). Default profile = wrong account (774558858301).
- **Two Lambdas:** `rigacap-prod-api` (1024 MB, 30s) and `rigacap-prod-worker` (3008 MB, 900s). Same image, `LAMBDA_ROLE` env var.
- **Manual invoke always targets worker:** `aws lambda invoke --function-name rigacap-prod-worker --profile rigacap ...`
- API Gateway 29s timeout — direct Lambda invoke for long ops. Lambda 10s init — DB connections lazy.
- **Lambda concurrency**: 1000 total, API reserved=50, Worker reserved=200 (increased from 10 after Mar 30 outage).

## Pickle Safety
- **Current: 7y pickle** (2019-06-03 → 2026-03-27, 4360 symbols, 269 MB). Built Mar 27, 2026.
- **CAN build locally** with backend venv (`numpy==1.26.3`). System numpy 2.x won't work.
- **NEVER replace without backup.** Guardrail checks symbol count (was byte-size, broke Mar 28-Apr 1). Weekly auto-archive.
- Pickle ONLY loads on Worker Lambda (3008+ MB). API Lambda will OOM.
- **10y pickle OOMs at 3008 MB** (347 MB compressed, 728 MB raw). Needs 4096+ MB Lambda.
- **Pickle shrink bug (fixed Apr 1 2026):** `fetch_incremental` strips indicator columns (dwap, ma_50, etc.) for lazy recompute, legitimately shrinking pickle ~50%. Old byte-size guardrail blocked ALL daily exports since Mar 28. Fixed: guardrail now checks symbol count, not byte size.
- Backups: `s3://rigacap-prod-price-data-149218244179/prices/backups/`

## Strategy IDs
- ID 1: DWAP Classic | ID 2: Momentum v2 | ID 3: DWAP Hybrid | ID 4: Concentrated Momentum | ID 5: DWAP+Momentum Ensemble

## Walk-Forward Testing Campaign (ACTIVE as of Apr 1 2026)
- See [wf-ab-test-results.md](wf-ab-test-results.md) for full test log
- **Goal:** 20%+ annualized consistently across 7 start dates
- **Baseline (Job 224):** +112.8% (16.3% ann), Sharpe 0.83, MaxDD -17.9%
- **Best consistency: Warmup (13 periods)** — 7/7 positive, 2/7 hit 20%+, avg 11.4% ann
- **Smoothing (0.7) COMPLETED** — all positive but lower than warmup
- **300-symbol batch: 6 JOBS STILL RUNNING** (periods 110-125 of ~131, ETA few hours)
- **Fixed params (no AI) still holds best single result** at 16.3% ann — AI optimizer hasn't consistently beaten it

## Entry Timing & Sizing Tests
- See [ai-optimizer-results.md](ai-optimizer-results.md) for TPE results and DWAP age analysis
- **12% trailing stop = Goldilocks.** 10% and 18% both worse.
- **DWAP 5% + 5% breakout window = critical.** Removing/widening either is catastrophic.
- **carry_positions=true is mandatory.** Without it, returns drop 50-90%.
- **Date boundaries matter enormously.** 5-day shift changed returns from +289% to +127%.

## Signal Strength Score
- See [signal-strength-analysis.md](signal-strength-analysis.md) for details
- **Formula B:** base=60 + 5 bonus factors. r=+0.083, validated 4/5 LOO-CV.

## Data Pipeline
- See [data-pipeline-lessons.md](data-pipeline-lessons.md) for Mar 6 outage details
- Daily scan chains CSV export (step 10). Scan at **4:30 PM EDT** (Alpaca settlement).
- Signal universe: top 100 by volume (`SIGNAL_UNIVERSE_SIZE=100`). Pickle loads all ~6900.
- Alert dedup persisted to S3. Dashboard.json is source of truth for all emails/alerts.
- CSV format: lowercase `open,high,low,close,volume,dwap,ma_50,ma_200,vol_avg,high_52w`. yfinance returns uppercase — must map.
- `replace_days` scan param can OOM on worker with large universe.
- DB tables: `model_positions` (not model_portfolio_positions), `model_portfolio_state`, `regime_forecast_snapshots` (col: `probabilities_json`).

## Dual-Source Market Data
- **Primary: Alpaca Pro (SIP).** yfinance = fallback + always for index symbols (^VIX, ^GSPC).
- Symbol normalization: hyphens (yfinance) ↔ dots (Alpaca) handled automatically.

## Lambda Gotchas
- **`anthropic` SDK not installed** — use raw httpx POST
- **NEVER add `from datetime import datetime` in handler() body** — shadows module-level, breaks all nested functions. Use aliased imports. See CLAUDE.md for full explanation.
- **`select(User).join(Subscription)` fails** with multiple FKs — use explicit join condition.
- Chained jobs must read from S3 dashboard, not in-memory state.
- `logger.info()` may not appear in CloudWatch — use `logger.warning()` or `print()` for must-see logs.
- Nested f-strings with quotes cause syntax errors on Lambda's Python — pre-compute into variables.
- `stock_universe_service.symbol_info` empty on Worker unless `ensure_loaded()` called — read `universe/symbols_cache.json` from S3 instead.

## EventBridge Cron (UTC, EDT = UTC-4)
- Scanner: `cron(30 20 ? * MON-FRI *)` (4:30 PM EDT)
- Daily emails: `cron(0 22 ? * MON-FRI *)` (6 PM EDT)
- Double signals: `cron(0 21 ? * MON-FRI *)` (5 PM EDT)
- Weekly regime: `cron(0 13 ? * MON *)` (Mon 9 AM EDT)
- Intraday monitor: `cron(0/5 13-19 ? * MON-FRI *)` (every 5 min market hours)

## Market Regimes (7 total, from market_regime.py)
- strong_bull, weak_bull, rotating_bull, range_bound, weak_bear, panic_crash, recovery

## Email Service
- `EmailService` (subscriber-facing) + `AdminEmailService` (admin-only, ADMIN_EMAILS allowlist)
- Freshness gate checks S3 dashboard `generated_at` first, then in-memory fallback
- `target_emails` admin bypass skips subscription/preference checks
- Market context (AI briefing): generated once at 4 PM scan, cached in S3 dashboard JSON, reused by email/API

## Excluded Symbols (updated Mar 24 2026)
- ALL ETFs excluded (leveraged, sector, index, crypto, thematic). Mining stocks allowed.
- Defined in `EXCLUDED_PATTERNS` (stock_universe.py) + `EXCLUDED_SYMBOLS` (config.py).
- ETF exclusion dropped WF from +206% to +83.6% with 100 symbols. Fix: use `max_symbols=500` for wider pool.

## WF Simulation Notes
- **Old benchmarks (jobs 113-116, 148, etc.) SUPERSEDED** — had SPY indicator bug, data starvation, inconsistent exclusions.
- **WF payload overrides:** `max_positions`, `position_size_pct`, `dwap_threshold_pct`, `near_50d_high_pct`, `trailing_stop_pct`
- Exit reason for period-end: `rebalance_exit`. Ensemble DB params: 6×15%.
- **DWAP stale crosses perform BETTER** — stale (90+d) = 56.8% win vs fresh (0-10d) = 49.6%

## Active Tasks
- **[BREAKTHROUGH: 19.9% avg annualized](project_tournament_breakthrough.md)** — near_50d_high_pct 5%→3%, validated 7/7 start dates
- [WF job dedup](project_wf_dedup.md) — add dedup check before creating WF jobs
- [WF launch protocol](feedback_wf_launch.md) — ALWAYS use periods_limit=1, test ONE job first
- [Pickle fix](project_pickle_fix_apr1.md) — VERIFIED working

## User Profile
- [Erik — solopreneur founder](user_profile.md) — actor background, lean budget, wants full automation from content to video to leads

## Marketing Pipeline (Future)
- **Content → Video → Social → Leads:** Social Intelligence Engine → HeyGen API (chosen over Synthesia — API from $5 PAYG vs $1k+/mo) → Buffer → HubSpot
- **Two content tracks:** AI avatar videos (automated) + founder-led videos (Erik shoots/edits)
- **Admin centralized:** Manage everything from RigaCap admin tab
- **NOT investing until strategy is locked at 20%+ annualized and live track record established**

## Social Posts
- [Full text in approval emails](feedback_social_emails_full_text.md) — never truncate post previews in admin emails

## Other
- [SLOW DOWN before Lambda jobs](feedback_slow_down_lambda.md) — think first, compute locally if possible, ONE job at a time
- [Concurrency rules](feedback_concurrency_guardrail.md) — NEVER launch >3 WF jobs during market hours
- [Signal consistency](feedback_signal_consistency.md) — all emails/alerts read from dashboard.json only
- [Deployment rules](feedback_never_saturate_production.md) — deployment safety
- Mobile OTA: `preview` channel, manual push with `npx eas update --branch preview`
- Terraform needs `AWS_PROFILE=rigacap`. CI/CD fights over `image_uri` — pass current tag.
- RDS endpoint: `rigacap-prod-db-v2.csfsa4i06rux.us-east-1.rds.amazonaws.com`
