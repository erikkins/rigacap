# Stocker App - Key Learnings

## CRITICAL — NEVER COMMIT SECRETS
- **[Never check in credentials](feedback_never_check_in_secrets.md)** — grep every file for password/postgres://*creds*/api.key/AKIA/sk-/whsec_ BEFORE `git add`. Never `git add .`. RDS master pw was leaked Apr 16 2026 via this exact failure mode; rotated same day. Scripts must read DATABASE_URL from env, never hardcode.

## CRITICAL DEPLOYMENT RULES
- **NEVER deploy DB schema changes without running the migration FIRST.** Migration-first pattern: deploy SQL → run → verify, THEN deploy model changes.
- **NEVER use `aws lambda update-function-configuration --environment`** — it REPLACES ALL env vars, causing full outage.
- **Always deploy via CI/CD (push to main).** Manual `deploy-container.sh` races with CI/CD.
- The `run_migration` Lambda event handler can run ALTER TABLE without auth.

## CRITICAL STRATEGY RULE
- **[WF backtest ↔ production signal generation MUST be identical](feedback_wf_prod_parity.md)** — any lever proven in walk-forward backtesting MUST be ported into production signal code in lockstep. Marketing claims come from backtests; subscribers must be able to realize them. **Known gap (Apr 28 2026): CB pause logic exists in backtester only, not in production scanner.**

## CRITICAL LEGAL FRAMEWORK
- **[Publisher's exemption + canonical disclaimer language](project_disclaimer_canonical.md)** — RigaCap operates under the Investment Advisers Act §202(a)(11)(d) publisher's exemption (confirmed by counsel Apr 30 2026). Three Lowe factors must be preserved: impersonal advice, bona fide commentary, regular circulation. Canonical disclaimer language (long/short/micro forms) lives in the linked file — use it consistently, don't paraphrase.

## AWS
- **Always use `--profile rigacap`** (account 149218244179). Default profile = wrong account (774558858301).
- **Two Lambdas:** `rigacap-prod-api` (1024 MB, 30s) and `rigacap-prod-worker` (3008 MB, 900s). Same image, `LAMBDA_ROLE` env var.
- **Manual invoke always targets worker:** `aws lambda invoke --function-name rigacap-prod-worker --profile rigacap ...`
- API Gateway 29s timeout — direct Lambda invoke for long ops. Lambda 10s init — DB connections lazy.
- **Lambda concurrency**: 1000 total, API reserved=50, Worker reserved=200 (increased from 10 after Mar 30 outage).
- **[Lambda memory capped at 3008 MB](project_aws_lambda_memory_cap.md)** — AWS support tier blocks quota increase above 3008. DO NOT propose `memory_size > 3008` in Terraform; parquet migration is the real unblock (partial-read by symbol vs holding the full 700 MB pickle).

## Pickle Safety
- **Current: 7y pickle** (2019-06-03 → 2026-03-27, 4360 symbols, 269 MB). Built Mar 27, 2026.
- **CAN build locally** with backend venv (`numpy==1.26.3`). System numpy 2.x won't work.
- **NEVER replace without backup.** Guardrail checks symbol count (was byte-size, broke Mar 28-Apr 1). Weekly auto-archive.
- Pickle ONLY loads on Worker Lambda (3008+ MB). API Lambda will OOM.
- **10y pickle OOMs at 3008 MB** (347 MB compressed, 728 MB raw). Needs 4096+ MB Lambda.
- **Pickle shrink bug (fixed Apr 1 2026):** `fetch_incremental` strips indicator columns (dwap, ma_50, etc.) for lazy recompute, legitimately shrinking pickle ~50%. Old byte-size guardrail blocked ALL daily exports since Mar 28. Fixed: guardrail now checks symbol count, not byte size.
- Backups: `s3://rigacap-prod-price-data-149218244179/prices/backups/`
- **[Pickle build playbook](project_pickle_playbook.md)** — full build/validate/deploy process, ETF exclusions, guardrails, emergency restore

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
- **[Never re-fetch from data providers](feedback_data_provider_cache.md)** — anything pulled from Alpaca/yfinance/etc. must be cached durably (S3 parquet) and re-read forever. New research jobs check cache before calling any provider.
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
- **[Lambda payloads must be TRUTHY](feedback_lambda_payload_truthy.md)** — `if event.get("foo"):` skips on `{}` (falsy) → Mangum errors. Use `{"_": 1}` for config-less handlers. Burned twice in 3 days.
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

## Storage Roadmap
- [Pickle → Parquet/DuckDB/TimescaleDB migration](project_storage_migration_roadmap.md) — triggers, options, sequencing. Stay on pickle through ~500 paid subs, then start with Parquet on S3.
- **[Parquet: fix the difference, never silence the alarm](feedback_parquet_fix_not_silence.md)** — when the diff harness flags a divergence, ask "if parquet were already primary, which side is correct?" Align parquet with target behavior. Never broaden "explainable" just to make the warning go away. Once we cut over, every silenced quirk is permanent.

## Active Tasks
- **[Intraday WF validation pickup (Apr 30 night → May 1)](project_intraday_validation_apr30.md)** — production-matched 5-min cadence simulator suggests WF overstates production by ~5 pp annualized (linear approx). Tomorrow: verify prod code → b-full re-run → cadence sweep. Material parity-gap signal.
- **[CB live in production May 3 2026](project_cb_production_wiring.md)** — `CIRCUIT_BREAKER_ENABLED=true` on Worker Lambda; closes WF↔prod parity gap. State persists at `s3://rigacap-prod-price-data-149218244179/cb-state/<portfolio_type>.json`. Threshold default 3 same-day stops → 10-day pause. Smoke test passing (`scripts/test_circuit_breaker_smoke.py`, 35/35). Re-engagement tightening deferred to v2.
- **[Production ticker-rename plumbing](project_ticker_rename_plumbing.md)** — same week. SQ/XYZ duplicate surfaced in 11y WF result. Switch to asset_id as primary key, verify Layer 2 catches ticker changes, backfill-cleanup utility for the pickle.
- **[Intraday data-anomaly execution model](project_intraday_data_anomalies.md)** — real fix for FCEL/AMRN flash-spike artifacts in minute bars. Multi-minute confirmation + slippage model. ~1-2 day research project.
- **[TPE on intraday execution parameters](project_intraday_tpe_optimization.md)** — after b-full baseline + univariate sweeps. Cadence × lockout × stop-width × confirmation. Mid-May target.
- **[Production: intraday trailing stops DISABLED May 3 2026](project_intraday_tpe_research.md)** — b-full showed -17 pp ann cost. Production now EOD-only via `INTRADAY_TRAILING_STOP_ENABLED=false` (default). HWM tracking + regime exits still run intraday. TPE research goal: find sub-strategies where intraday DOES help (lockout window, multi-min confirm, VIX-conditional).
- **[Asymmetric HWM research (jobs 1248/1249, May 15 2026)](project_asymmetric_hwm_research.md)** — A/B test isolating whether b-full's -17pp result came from day-low trigger or day-high HWM. Tests `hwm_from_day_high=true` (HWM from day_high, trigger from close) vs baseline. If 1249 wins, ship asymmetric to production + user-alert path; if it loses, drop day-high from user-alert path too. Also paired with May 15 Path A change that already aligned ModelPortfolio to close-only HWM.
- ✅ **[WAF bypass closed (DONE May 7 2026)](project_execute_api_waf_bypass.md)** — CloudFront `X-Origin-Verify` header + `OriginVerifyMiddleware`; direct-execute-api hits now 403. Secret lives in TF state (local) + CF origin + Lambda env. DR notes in linked file.
- **[DR posture / single-region stack](project_dr_posture.md)** — us-east-1 only, no active failover. 4-12 hr cold rebuild ETA dominated by RDS restore + ACM cert. Improvements ranked: remote TF backend (doing now) → cross-region RDS snapshots → parquet migration eliminates pickle. Active multi-region not warranted at current scale.
- **[Cluster-day vs isolated-day entry A/B (follow-up wk May 11-18 2026)](project_cluster_day_ab_test.md)** — May 6 fired 5 simultaneous entries; test whether 3+ same-day entries lag isolated fresh signals on 14d/30d/60d horizons. Don't act without data; live May 2026 cohort provides real-money observation in parallel.
- **[Ticker-reuse triage UI (follow-up to symbol-triage v1)](project_ticker_reuse_triage_ui.md)** — hygiene email flags reuse cases (CCL, TRI as of May 7) but there's no admin resolve path; build a diff-view page with confirm-quarantine / restore-active / migrate-to-new-symbol actions. ~half day.
- **[Hygiene-email threshold follow-ups](project_hygiene_threshold_followups.md)** — bulk "Needs Attention" items still dead-end: missing-in-Alpaca >20 threshold, universe dirty count >1500. Quickest wins (30 min each): tighten auto-quarantine 30d→14d; convert dirty-count alarm from absolute to rate-of-change. Recommended order in linked file.
- ✅ **[Parquet divergence RESOLVED (May 13 2026)](project_parquet_divergence_blocker.md)** — 0 events / 24h. Root cause was pickle-side schema drift (atr-trigger gap + ^VIX/^GSPC index.name asymmetry), NOT parquet bugs. 7-day clean clock now running; if it holds, Stage 3b shadow cutover ~May 20. Diagnostic + heal handlers (`pickle_validate`, `parquet_alignment_heal`, `parquet_divergence_inspect`) preserved.
- ✅ **[Dashboard Portfolio Banner — user-personal (DONE; verified May 8 2026)](project_dashboard_personal_portfolio.md)** — banner reads from `/api/portfolio/positions` which returns the user's manually-entered positions filtered by `user_id`. Verified live with erik@rigacap.com showing 5 open positions / $49.5K cost / +7.3%. No auto-population, matches the directive against tracking every user's trades.
- **[Parquet migration 4-stage plan](project_storage_migration_roadmap.md)** — Stage 1 shadow write ✅ (Apr 14-15). **Stage 2 AL2023 ✅ (deployed before Apr 28 via commit `21f9e51`).** Stage 3 consumer migration → Stage 4 decommission pickle. Goal: parquet becomes primary, pickle retired.
- **[Stage 3 detailed plan](project_parquet_stage3_plan.md)** — 6 work packages (3a-1, 3a-2, 3a-3, 3a-4, 3b, 3c, 4) with parallel-read diff harness + 2-week observation window before any cutover. Three independent safety nets. ~25-30h total spread over ~6 weeks.

## Deferred UX Improvements
- **[Daily digest email watchlist UX](feedback_email_watchlist_ux.md)** — subject/body count mismatch (subject says "4 on Watchlist" but body renders 3); tickers in email should deep-link to platform chart popup

## Deferred Infra Improvements
- **[WF cache table size check — Oct 2026](project_wf_cache_size_check.md)** — daily/nightly WF cache rows are now append-only (no DELETE). Revisit Oct 2026 to confirm growth isn't problematic.

## Data Hygiene Roadmap
- **[Layer 2 — corp-actions + ticker-reuse detection](project_data_hygiene_layer2_apr2026.md)** — nightly Alpaca corp-actions poll + asset-ID integrity check. Catches ticker reuse, silent splits, delistings before next-day scan. ~4-5 hour build. DEPLOYED Apr 15 2026.
- **[Alpaca Trading API symbol inconsistency](feedback_alpaca_asset_api_inconsistency.md)** — MMC and similar real tradeable symbols return 404 on `/v2/assets/{sym}` while Data API has full bars. Bulk-fetch via `get_all_assets()` + data-API fallback fixes (~30-60 min).

## Trial 37 & Clean-Data Reoptimization
- **[Trial 37 was over-fit to corrupted pickle](project_trial37_overfit_clean_data.md)** — advertised +240%/0.89/24% MDD collapses to +96%/0.58/36.6% on clean data. TPE run3 re-optimizing in background, ~12h. Don't quote old numbers externally.
- **[AL2023 canary staged, not deployed](project_al2023_canary_staged.md)** — image in ECR, Dockerfile change local-only, rollback SHA captured. Follow runbook when ready.
- **[Silent signal drought root cause](feedback_silent_signal_drought_rootcause.md)** — fetch_incremental + _ensure_indicators two-layer bug. Fixed + 3 safeguards added.

## Trial 37 Validation Tasks
- **MDD forensics** — once 8-date clean run completes, pull equity curve for a representative start date, identify peak→trough window, cross-ref with trade exits during that window. Determine specific event (2022 bear, summer 2024, or regime-shift lag).
- **Secondary strategy (after TPE re-optimization)** — if optimized clean-data numbers still leave a gap vs advertised, test: (1) megacap defensive overlay during regime exits, (2) RS Leaders redux on clean data, (3) low-vol sleeve for bear regimes, (4) inverse-vol ETF during regime transitions.


- **[Strategy optimization FINAL](project_position_sizing_tests_apr2026.md)** — TPE Trial 37 deployed: +240% avg, 24% MaxDD, ~28% ann. 2023 weakness accepted.
- **[MDD reduction ideas](project_mdd_reduction_ideas.md)** — VIX-adjusted sizing, drawdown circuit breaker, bear regime stops — for TPE Run 2
- **[Bear Ripper strategy](project_bear_ripper_strategy.md)** — targeted bear-regime sub-strategy: find 1-2 high-conviction trades during bear markets to reduce MDD from 30% to ~20%. Start after clean-data strategy is locked.
- **[Per-regime sub-strategy decision (DEFERRED)](project_regime_substrategy_decision.md)** — Apr 28 considered BR/range-bound/per-regime sub-strategies; shelved due to 4-5 bear sample being too small for optimization. Two-track framework (disclosure + universal-rule-only) captured if we revisit.
- **[BREAKTHROUGH: 19.9% avg annualized](project_tournament_breakthrough.md)** — near_50d_high_pct 5%→3%, validated 7/7 start dates
- [WF job dedup](project_wf_dedup.md) — add dedup check before creating WF jobs
- [WF launch protocol](feedback_wf_launch.md) — ALWAYS use periods_limit=1, test ONE job first
- [Pickle fix](project_pickle_fix_apr1.md) — VERIFIED working

## User Profile
- [Erik — solopreneur founder](user_profile.md) — actor background, lean budget, wants full automation from content to video to leads
- [Target audience — sophisticated retail](user_target_audience.md) — know trailing stops, use brokerage apps, follow fintwit, no time to build own system

## Marketing Pipeline (Future)
- **Content → Video → Social → Leads:** Social Intelligence Engine → HeyGen API (chosen over Synthesia — API from $5 PAYG vs $1k+/mo) → Buffer → HubSpot
- **Two content tracks:** AI avatar videos (automated) + founder-led videos (Erik shoots/edits)
- **Admin centralized:** Manage everything from RigaCap admin tab
- **NOT investing until strategy is locked at 20%+ annualized and live track record established**

## Social Posts
- [Full text in approval emails](feedback_social_emails_full_text.md) — never truncate post previews in admin emails
- **[CRITICAL: NEVER cite specific WF start-date count](feedback_no_7_dates.md)** — use "multiple" or "many", never "7"/"8"/etc. Applies to PUBLIC and INTERNAL docs. Violated repeatedly; treat as load-bearing.

## Marketing & Brand Strategy (NEW Apr 28, 2026 — authoritative)
- **[Marketing strategy doc — source of truth](project_marketing_strategy_doc.md)** — points to `docs/MarketingNewsletterStrategyCLAUDE.md` (1,090 lines, 25 sections). Brand, voice, pricing, design, content, compliance, lifecycle, growth. Read the doc directly when working on anything strategic. Memory entry covers load-bearing rules + tensions to reconcile.
- **["Publication" is aesthetic-only, not product positioning](feedback_publication_is_aesthetic_only.md)** — RigaCap is a signal service. FT/Economist/Stratechery references are voice/aesthetic register only. Bios and lead copy must foreground the signal product.

## Redesign — Premium Editorial Publication (SHIPPED Apr 27, 2026)
- **[Rebrand SHIPPED](project_rebrand_premium_publication.md)** — $129/mo premium publication is live. Treat editorial framing as the live brand.
- **[Design system spec](project_redesign_spec.md)** — Fraunces+IBM Plex, Claret accent, paper background — source of truth for ongoing decisions. (Now extended by the marketing strategy doc above.)

## Numbers Discipline
- **[Numbers citations registry](project_numbers_citations_registry.md)** — `docs/numbers-citations-registry.md` enumerates every surface citing perf numbers. Walk it before any number refresh. No partial updates.

## Planned Features
- **[Admin run_sql Lambda handler (TODO)](project_admin_run_sql_handler.md)** — add a generic read-only SQL/diagnostic event branch to the worker so ad-hoc invokes don't trip the worker-errors alarm. ~1 hr build with read-only guard + row cap + audit log.
- **[main.py housekeeping — extract event handlers](project_main_py_housekeeping.md)** — main.py is 9,228 lines, 90+ event-handler branches. Refactor target: `app/lambda_events/<domain>.py` modules dispatched from a list in main.py. Not urgent (no active pain); trigger when merge conflicts in main.py block shipping, OR during a quiet parquet-migration window. Start with the diagnostics cluster (highest growth rate, easiest to test).
- [Signal slippage tracking](project_signal_slippage_tracking.md) — post-publication price monitoring to measure real achievable execution vs published entry price
- [Balanced content rule](project_balanced_content_rule.md) — every 4th social post must be a loss/quiet week/limitation; trust-building differentiator
- [Trial length decision (post-launch+60d)](project_trial_length_decision.md) — default $0/14d auto-extend, A/B-test $19/30d paid; SaaS data favors paid trials for conversion. Don't act before 60 days of launch data.

## References
- [HeyGen avatar ID](reference_heygen.md) — Erik's current avatar for AI video generation
- [Twitter media upload field naming](reference_twitter_media_api.md) — use 'media' for raw bytes, 'media_data' for base64; wrong field silently drops images
- [Cascade Guard = Circuit Breaker](reference_naming_cascade_guard.md) — external/marketing name vs internal/code name; same mechanism

## Other
- **[STR PK = (symbol, ensemble_entry_date)](project_str_resignal_audit_pickup.md)** — STR rows are one-per-signal-event, not one-per-fresh-day. Audit + backfill workflow + production dedup fix shipped May 4-5, 2026.
- [No dated callouts in design docs](feedback_no_dated_callouts_in_docs.md) — don't sprinkle "(Apr 2026)" or "newly added" markers; keep docs evergreen, let git history carry the session-dated context
- [Signal frequency = "3-4 per month"](feedback_signal_frequency_claim.md) — never "6-8 every 2 weeks" or "~15/month"; both are stale drift
- [SVG attachments cause 400 loops](feedback_svg_attachments.md) — always pre-convert SVG→PNG before downstream use
- **[S3 list+sort always filter subdirs](feedback_s3_list_filter_subdirs.md)** — `list_objects_v2(Prefix=)` returns nested paths too. `backups/` and other subdirs sort above dated files because `b` > digits. Surfaced May 16 when newsletter editor stubbornly showed May 3 draft for 12 days because backup file outranked live drafts in descending sort.
- **[Social card render — strip gallery-view body styling](feedback_social_card_render_gray_strip.md)** — the launch-cards source HTML has `body { background: #999; padding: 40px }` for gallery preview. Single-card screenshots leak gray strips top/bottom unless you inject `html, body { background: transparent !important; padding: 0 !important; margin: 0 !important; }` override before rendering.
- [SLOW DOWN before Lambda jobs](feedback_slow_down_lambda.md) — think first, compute locally if possible, ONE job at a time
- [Concurrency rules](feedback_concurrency_guardrail.md) — NEVER launch >3 WF jobs during market hours
- [Signal consistency](feedback_signal_consistency.md) — all emails/alerts read from dashboard.json only
- [Deployment rules](feedback_never_saturate_production.md) — deployment safety
- Mobile OTA: `preview` channel, manual push with `npx eas update --branch preview`
- Terraform needs `AWS_PROFILE=rigacap`. CI/CD fights over `image_uri` — pass current tag.
- RDS endpoint: `rigacap-prod-db-v2.csfsa4i06rux.us-east-1.rds.amazonaws.com`
- [No "tape" in brand voice](feedback_no_tape.md) — trader jargon, banned everywhere including section names
- **[No Brit-isms or trader-desk shorthand](feedback_no_britisms_trader_jargon.md)** — "what it says on the tin", "catches a bid", "no joy" etc. all banned. Voice is editorial-sharp US-English. Sister rule to no-tape and us-english.
- **[US English only](feedback_us_english.md)** — favor/optimize/modeled/realize. Never favour/optimise/modelled/realise. Easy to slip into British forms unconsciously.
- **[NEVER name DWAP in public prose](feedback_no_dwap_in_public.md)** — proprietary indicator. Use "proprietary timing reference" / "long-term accumulation reference" instead. Code field names + admin UI + email labels are fine; prose is not.
- [Newsletter topic rotation](project_newsletter_topics.md) — §02 educational topics, review quarterly, add from new features + subscriber feedback
- **[Newsletter §04 variance preservation](feedback_newsletter_s4_variance.md)** — §04 (A Note From Erik) prompt has explicit theme rotation + anti-repeat + headlines hook. Do NOT simplify back to vague "current moment" guidance — caused every week to drift to "discipline / doing less, not more". Erik-flagged May 16 2026.
- [Newsletter ops and timing](project_newsletter_ops.md) — Sat 8PM generate, Sun 10AM auto-send, no weekend refresh by design
- [Newsletter has no signals](feedback_newsletter_no_signals.md) — purely editorial, same for free and paid, no tickers ever
- [Never blast emails without target_emails check](feedback_never_blast_without_target.md) — verify handler supports filtering BEFORE invoking
- [Newsletter cron MUST use locked draft](feedback_newsletter_cron_draft.md) — Apr 26 outage: cron sent wrong version to all subscribers
- **[Meta token lifecycle (IG + Threads) — full punch list](project_meta_token_lifecycle.md)** — short-lived recovery works (May 6); long-lived exchange blocked on app secret; auto-refresh cron not built; IG API base bug fixed (`graph.facebook.com` not `graph.instagram.com`)
