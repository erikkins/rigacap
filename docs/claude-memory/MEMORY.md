# Stocker App - Key Learnings

## 🏷️ MARKETING: "survivorship-free" is TABLE STAKES, not a tagline
- [Why + how to apply](feedback_survivorship_free_not_marketing.md) — internal rigor only; keep out of customer copy. Lead with result + thesis (modern-market momentum), not methodology hygiene.

## 📰 QUEUED NEWSLETTER TOPIC — time-stop vs trailing-stop ("Why cut-your-losses can be the losing move")
- [Draft + framing](project_newsletter_exit_stops_topic.md) — Erik wants it in a FUTURE issue (NOT Jun 28's, already written). Principle piece, no recipe leak; anchors on t30v's public wide trail. Draft is ready to drop in.

## ▶▶▶ RESUME (Jun 25) — ADMIN iPHONE APP build (native Expo, push-first). Context recovered after a lost session.
- [Admin mobile app — goal, decisions, backend endpoints, next steps](project_admin_mobile_app_jun25.md) — native Expo admin, push-first; admin-tab data + Ads API; never app-store. Existing `mobile/` user app is May-5 stale — OPEN fork: separate app (leaning) vs bolt-on. Backend auth + `/api/admin/*` already exist. Next: confirm fork → scaffold.
- [Checkpoint memory DURING the session, not at shutdown](feedback_checkpoint_memory_during_session.md) — no shutdown hook can save context; Erik lost a session Jun 25 via VS Code close. Recover via `claude --resume` (not `--continue`).

## ▶▶▶ RESUME (Jun 17 EOD) — 0-SIGNAL BUG SOLVED = MOMENTUM_SECTOR_CAP=0 (not memory). Parquet flip LIVE. Digest reworked + sent.
- **[Full root cause + parquet + teething (READ FIRST)](project_oom_scan_zero_jun15.md)** — The 3-day 0-signal bug was **`MOMENTUM_SECTOR_CAP=0`**: rank_stocks `if count < CAP` with CAP=0 dropped EVERY sector'd stock → ranked collapsed to ~1 → 0 signals. Only bit when sectors loaded (daily scan), not recovery/diag paths (sectors empty) — THE "scan=0/recovery=correct" pattern, and why it never repro'd locally. Fixed: cap<=0 = disabled (rank 1→100). I chased 4 wrong theories first (memory, fetch/merge, settlement, "Lambda runtime") — print-level [DASH-DIAG] in the Lambda finally nailed it.
- **Parquet flip SHIPPED + LIVE (`PRICE_SOURCE=parquet`):** scoped partial read (top-600 universe + indices from all_data.parquet) → mem 2353→1486MB, OOM gone. Flag = instant rollback. **TEETHING: recovery is now `{"daily_scan":true}` (fetches), NOT export_dashboard_cache (gives stale parquet-base signals).**
- **Digest reworked + SENT to all 3 subscribers Jun 17:** subject + body lead with the active count (never open with "0 new"); email reads dashboard cache so counts match the site (was 6 vs 7).
- **CLEANUP next session:** strip temp instrumentation ([DASH-DIAG]/[LEN-DIAG]/diag_scan_build/rebuild_snapshot incl its data_cache={} footgun); fix dashboard age fields (days_since_entry=44 wrong); automate parquet store-freshness; periodic full-universe refresh.

## (superseded) ▶ RESUME — 0-SIGNAL SCAN was WRONGLY blamed on the 3008 MB MEMORY CAP (Jun 15). See above: real cause = sector cap.
- **[OOM root cause + fixes (READ FIRST)](project_oom_scan_zero_jun15.md)** — Mon's first-live-entry scan wrote 0 buys+0 watchlist (silent); hygiene OOM'd → the alarm emails. BOTH = worker hitting 3008 MB cap (scan REPORT: Max Memory 3008 MB). In-pipeline dashboard build degrades under memory pressure; COLD `export_dashboard_cache` → correct 17 (never reproduced locally — 16GB box has no pressure). **Recovered Mon manually:** cold rebuild → 17, `process_entries` → 17 live positions (~$64k, Erik "all good"). Live record intact.
- **SHIPPED + LIVE (commit 1ed2491; both lambdas Active 01:20 UTC Jun 16):** Fix 1 = daily-scan dashboard build moved BEFORE pickle/parquet exports (build gets ~2.3GB headroom) + BUG-1 guard retry removed (alert-only, Erik: no reruns). Fix 2 = nightly_data_hygiene drops inline export_parquet after split-refetch (keeps export_pickle+gc). NOTE: did NOT use the decouple-into-fresh-invocation approach — the deferred handler is NOT a superset (missing process_live_exits + CB + silent-cash); reorder was lower-risk single-path.
- **🧳 Jun 16 TRAVEL PLAN (Erik offline during scans, laptop in bag):** NO auto-recover cron. The alert-only guard emails `erik@rigacap.com` on failure → subject **`🚨 RigaCap: 0 buy_signals despite healthy raw scan`** is Erik's cue to spin up + return to chat. **RECOVERY RUNBOOK is in the project file** (one-shot `export_dashboard_cache` w/ include flags, or 2-step + verify; check positions first, don't double-enter). VERIFY Tue scan: REPORT mem < 3008, buys≈bench (not 0), entries match, no hygiene alarm. If still 0 under cap → escalate to decouple plan.
- Parquet migration (Option A) remains the structural cure (partial reads kill the 695 MB monolith) — Fix 1/2 are stopgaps.

## ⭐ POSITIONING CANON (Jun 11 — the analyst dialogue, B-→A-, KEEP USING THIS LANGUAGE)
Erik's analyst friend graded the product through 3 rounds → **A- "Elite Behavior-Adjusted Alpha" / "behavioral capital insurance" / "the Anti-Capitulation Engine" / "structurally buying a put option on the market; the premium is paid in bull-run underperformance."** The decisive matrix: same product = **F for the "Market Maximizer," A for the "Capital Preserver"** → marketing's job is FILTRATION, not conversion. New disclosed canon numbers (now on /methodology + landing FAQ "Who is this NOT for"): beats SPY in 39%/34%/23% of rolling 1/3/5y windows; never reclaimed the Mar-2009 relative peak (17y, anchor=GFC bottom); own-account worst wait 2.7y vs SPY's 5.5y; fee drag 1.55%@$100k/0.62%@$250k/0.15%@$1M → ideal persona $250k+. Analyst's 3 open offers (= roadmap): (1) onboarding copy that pre-sets multi-year relative-underperformance expectations (churn prevention), (2) RIA client-presentation framework for the 19% guardrail, (3) founding-100 social-proof strategy. Benchmark answers (turnover ~58 trades/yr, ~4mo holds, ~260% one-way, ~0.5pp@20bps; universe top-100-by-volume US common stocks, no ETFs/leverage/shorts) — reusable for due-diligence replies.

## ▶▶▶ RESUME SAT JUN 13 — EVALUATOR DIFF + "BUY = INSTRUCTION" taxonomy (Erik's closing principle Jun 12)
- **Erik's design principle (Jun 12 night, anchors the threshold work): "BUY" = act NOW/at-open — an INSTRUCTION, not a description.** User-facing: BUY = what the model book enters (mirror it) / WATCHING = approaching / aged-qualifying & below-cutoff = internal machinery, never labeled "buy." Signal buckets stay as internals; email+dashboard lead with the instruction layer.
- **Evaluator diff (MUST run before Mon 4:30 scan):** trace ARM/MRVL/VZ through today's compute_shared_dashboard_data funnel gate-by-gate vs the backtester's entry conditions. Dashboard said 0 qualify Jun 12; old regime-adjusted email path said 2 (VZ/BAC). Whichever is bench-faithful defines "what makes the model enter" + gets WRITTEN DOWN (methodology + Erik sign-off). Suspects: momentum_top_n=30 pre-filter (bench has no such cutoff?), regime-adjusted params in one path only, near-high band post-slide.
- **Jun 12 parity fixes SHIPPED (befe702 etc.):** process_entries is_fresh filter DROPPED (Erik-approved; enters currently-qualifying ranked by score, like bench); email live-regen fallback REMOVED (single source = persisted scan rows / dashboard cache); invalidation ALWAYS runs (zero-day gate bug); digest template = dashboard parity (score+label, New/Open w/ age/Approaching, truthful subject, clickable, labeled %s, age-derived freshness + dedupe); **896 fossil active ensemble_signals invalidated** (accumulating since spring). Monday's scan rebuilds the active set from scratch under the fixed pipeline; if dashboard evaluator says names qualify, the book ENTERS (first live capital deployment).
- Also Jun 12: Google Ads LIVE (stability-search-test-a, $25/d, bid cap $7 after low-AdRank diag, verification COMPLETE as RigaCap LLC via D&B, GA4 purchase importable; begin_checkout wired to landing CTAs + key-event pending sync; remaining: import conversions, AG2, negatives, sitelinks — build doc has all). Drips finalized (D1 actionability rewrite — no broker stop orders!, D6 table, D8 3-beat quote, COMEBACK20 killed: no shared codes ever, serialized-only IF data justifies). istop REJECTED at Tier-2 (see inversion campaign file). Pivot newsletter lead story staged (drafts Sat eve — REVIEW). Launch post 3 Sun 10am PT. Paul never reported Friday — follow up.

## ✅ LOOP CLOSED (Jun 24) — PITFWU is now the live read path (PITFWU_READ=true)
- **DONE in one session, staged + validated.** Step 1: ported PITFWU write into backend/app/services/pitfwu_store.py + `{"pitfwu_append"}` worker handler, chained after the daily scan (parquet mode) → store stays fresh daily (verified: caught up Jun12→Jun23, 1478MB). Step 2: ported the READ veneer (split-adjust-at-read) + `{"pitfwu_shadow_diff"}` → **closes match 100%** (the ~20% "mismatches" were VOLUME-only, immaterial: different vendor consolidated volume; closes drive all gating). Step 3: flag-gated PITFWU read in `_scoped_parquet_load` (PITFWU_READ env) — reads fresh per-symbol store + `_ensure_indicators`, **falls back to all_data.parquet for missing (BRK-B) + short-history (<250 bars) + indices** so it can never drop/under-rank a name. **FLIPPED LIVE** — diag: ge200=593 (== all_data exactly), ranked=100, 7 signals, 1762MB. Tonight's scan reads PITFWU (fresh base, ~1-day fetch gap vs the growing Jun-15 gap). Rollback = unset PITFWU_READ (backup /tmp/envbak_pitfwu.json).
- **CLOSE-THE-LOOP FOLLOW-UPS:** (a) full-backfill the ~11 short-history + BRK-B symbols' PITFWU history (gap-only currently → they fall back to all_data meanwhile); fix BRK-B hyphen/dot Alpaca mapping in the append. (b) the "PITFWU scoped read: N fell back" log under-counts (only counts missing, not short-history) — cosmetic. (c) the daily-WF still reads import_all (now PITFWU via the flag) — verify it picks up fresh data (the clamp handles any residual lag). (d) eventually retire all_data.parquet entirely once PITFWU coverage is 100%.
- **STILL TODO (the OTHER 2 sweeps):**
2. **t30v DISPLAY PARITY SWEEP** — audit EVERY UI/email surface that states an exit/target/param for stale Ensemble values. Found Jun 23: signal card (12% trail→30%, +20% target→none, FIXED), dashboard 1yr-WF (was strategy 5 Ensemble→t30v, FIXED), "% away from stop" wrong denominator (FIXED 3 spots). STILL TODO: chart "+20%" reference line (vestigial Ensemble target — swap for a trailing-stop line); grep for any remaining 12%/+20%/profit_target/1.20 in App.jsx + emails. Rule (feedback_wf_prod_parity): anywhere the UI states an exit param it MUST be the live t30v value or subscribers can't realize the marketed results.
3. **/for-advisers REVAMP** (from Paul) — pivot to SLEEVE framing, add the RE-ENTRY trigger explanation, the 60/40 sleeve illustration, underperformance honesty, advisor client-ed one-pagers. See project_paul_adviser_feedback_jun23.

## 🤝 PAUL (PJ) ADVISER FEEDBACK (Jun 23) — drives the for-advisers revamp + RIA motion
- **[Full feedback + RIA blueprint](project_paul_adviser_feedback_jun23.md)** — Family CFP @ Raymond James reviewed /for-advisers + /track-record. Validated the thesis ("behavior > asset selection"; behavioral edge > stats, said 2×). ⭐ KEY INSIGHT: career-risk asymmetry (advisers fear bull underperformance > crash participation) → position as a **SLEEVE (10-20%), not standalone**. Wirehouses (RJ/ML/MS) won't approve → **independent RIAs are the channel**. Biggest hurdle = CREDIBILITY (no live record) → multi-year build. TO-DO for /for-advisers: re-entry trigger (flagged 2×), 60/40 sleeve illustration (2×), underperformance honesty, advisor client-ed one-pagers, more risk metrics + explainer video. Steal his **F1 analogy** (brake/corner/control > speed). Paul = first adviser-side sounding board (signed up for newsletter; sees Erik in G weeks of Jul 6 & 20). Reply drafted Jun 23.

## 📉 AD CONVERSION TRACKING — "0 conversions" likely a measurement gap, NOT a dead funnel (Jun 24)
- **[Ad conversion tracking diagnosis](project_ad_conversion_tracking_jun24.md)** — Ads `stability-search-test-a` (Jun12-23): $304, 47 clicks, 0 conv. GA4 shows **73 key events** → firing works. Ads=0 → EITHER GA4→Ads conversion-actions not imported (linking ≠ importing; import sign_up/purchase as PRIMARY, NOT begin_checkout) OR ad-clickers genuinely didn't convert (73 = all-traffic). **Disambiguate: GA4→Acquisition→Traffic acquisition→Google/cpc row→Key events col** (>0 = import problem; 0 = real land→signup leak). gtag is consent-gated (CookieConsent.jsx loadGA4 only on Accept → decliners invisible). begin_checkout still sends STALE $39/$349 (AuthContext.jsx:167). Negatives: phrase "volatile stocks"/"most volatile" (NOT bare "volatile" — kills on-thesis "is market volatile now"). No Ads API wired (screenshots). Clicks ARE on-thesis (capital-preserver queries).

## 💳 PRICING WAS MISCONFIGURED + FOUNDING SYSTEM BUILT (Jun 23) — read before any billing work
- **[Pricing fix + founding system (THE reference)](project_pricing_founding_jun23.md)** — Checkout was charging **$39/mo + $349/yr** (stale price IDs) vs the advertised **$59 founding / $129 standard / $1099 annual**. FIXED env vars (now $59/$1099/$129; backups /tmp/envbak_price_*). Built the real founding system: server-side founding($59)→standard($129) switch at 100 seats, public `/api/billing/founding-status`, gated landing counter (silent until <40 left, then "Only X left", then "Filled"), ★ Founder pill + Leads tab in admin, auto-checkout after signup, soft-conversion "follow the newsletter" in the signup modal. **OPEN: "locked 12mo" is marketing-only (Stripe keeps founders at $59 indefinitely, not coded); no founder-cohort email job yet.** Funnel diagnosis: 44 ad clicks → 0 accounts = leak is PRE-account (land→signup), not Stripe; GA4 (not CloudWatch — API doesn't log paths) is the tool to localize.

## 📱 PAID TRAFFIC IS 100% MOBILE (Jun 16) — a load-bearing marketing fact
- Google Ads `stability-search-test-a` started delivering Jun 15 (188 impr / 3 clicks / $19.52, ~$6.50 CPC); **Interactions by Device = 100% mobile.** Earlier "14 impr/$0" was a stale window. Campaign is DELIVERY-limited (low search volume + low Ad Rank), NOT budget-limited ($0 of $25/day spent before the spike) — lever is keywords/Ad-Rank, not budget. Auction set (Fisher Investments, SeekingAlpha, MoneyTalksNews) validates on-thesis targeting; you trail Fisher on position (fine, different product). Jun-17 ad check: pull keyword "Low search volume" statuses + search-terms negatives.
- **One ad group lands DIRECTLY on /track-record** → mobile UX there is conversion-critical, not secondary. Jun 16 SHIPPED (commit 09769a3): track-record perf tables reflow to mobile card-stacks (Max Drawdown column no longer hidden behind horizontal scroll), regime rows stack; **TopNav got a hamburger menu site-wide** (nav links were `hidden sm:inline` → vanished on phones with no fallback). PortfolioRace chart left as-is (scales + touch-capable; micro-labels at phone width = known cosmetic TODO for a visual pass). ALL public-page mobile surfaces: re-check at 360px since paid traffic is phones.

## ⏰ REMIND ERIK THIS WEEK (set Sat Jun 13) — surface these at next session start
- **Ad check (~Wed Jun 17):** panic-discipline Impressions accruing? If yes → lower campaign max-CPC cap $9→$6-7 (bumped to $9 Sat to unlock new competitive 'should I sell' queries past low-Ad-Rank). Pull Search-terms report → add negatives from junk. Compare crash-protection vs panic-discipline cost-efficiency. 2-wk kill/scale decision (vs $150/trial) ~Jun 27.
- **Parquet freshness pipeline:** start this week AFTER Mon Jun 15 confirms live entries (Option A decided — see roadmap).
- **Ad polish if not done:** negatives + sitelinks (campaign-level).

## ▶▶▶ RESUME HERE (Jun 13 EOD — 100% PARITY ACHIEVED. Live record = Jun 14. Mon scan = first real entries)
- **[Signal parity — prod now == t30v backtest 100% (THE config+entry reference)](project_signal_parity_jun13.md)** — Jun 13: found the live entry path NEVER matched the validated bench. Fixed 6 divergences (cache-zero, missing near-high filter, wrong ranking, penny-universe pollution, DWAP one-source, **universe SIZE 200→100 env drift**). Verified logic 7/7 vs CustomBacktester + runtime + config audit (0 gaps). The Jun 11-12 "Day 1=cash=discipline" was a BUG. **Live record re-dated Jun 14; entry path smoked OK; first REAL entries = Mon Jun 15 4:30 scan (WATCH the first full-pipeline entry run).** Lesson: code parity ≠ runtime parity — diff prod's ACTUAL config, don't assume. Signal presentation: lead with $ amount not # shares.
- **Parquet flip = DECIDED Option A (Jun 13, [roadmap](project_storage_migration_roadmap.md)):** RAW bars + adjust-at-read canonical (PITFWU style, split-only price-return); retire pickle + all_data.parquet. Diff proved pickle==PITFWU to the penny on common dates (gaps were pure staleness — NO data-quality divergence; migration is plumbing). Hard part = raw-fetch + corp-action freshness pipeline. Sequence: freshness pipeline → veneer read-path → shadow-diff ~1wk → cutover. Start this coming week AFTER Mon confirms live entries; not a hot flip.
- **Config now (Jun 13):** SIGNAL_UNIVERSE_SIZE=100 (was 200 drift) on BOTH lambdas. mom_weights 0.3/0.2/0.15 in settings (correct). strategy_adaptive_params t30v_cutover row overrides stale settings defaults (max_pos/pos_size/trail/near_high) — load-bearing.
- **Newsletter (Jun 13):** lock no longer auto-publishes — `lock_draft` only freezes; new `publish_issue()` runs at Sunday email-send (main.py). Bad 6/14 issue PULLED from public + §01/§03 rewritten (removed "zero-signals=discipline" bug framing); corrected draft locked+private, sends Sun. Web render fixed: plain-text \n\n → <p>. Queue: lock=publish split DONE.

## ▶ (Jun 11) LAUNCHED — capital-preservation campaign (still valid)
- **Jun 11 = full launch day, all green:** launch post 1 LIVE on X/IG/Threads (posts 2-5 auto-fire Fri/Sun/Mon/Tue; Buffett post Wed 16:00Z); Day-1 scan clean — rotating_bull, 60 info signals, **0 buys → $100k 100% cash by choice** (the on-brand Day-1 story; suggested Day-2 post: "first decision it made with real money was patience"); beta email SENT to all 6 actives; analyst A- canon shipped everywhere; launch cards/profiles/OG on paper brand + Fraunces opsz-144; engagement voice live w/ SKIP guard + Buffett canon.
- **Erik's closing strategic note (Jun 11): world turmoil = PERFECT window to sell capital preservation hard.** Engagement engine already hunts drawdown-anxiety threads; if market breaks, the live book going to cash in public = "we called it" for risk management. Lean into this.
- **Social infra incident book (Jun 11, all resolved):** X = API credits depleted (billing, Erik topped up — watch burn rate vs engagement reads); Meta security sweep killed the Instagram-Login session (IGAA tokens dead) → switched publisher to graph.facebook.com + FB Page token via meta_token_setup handler (page tokens ≈ non-expiring; token dance OVER). meta_token_setup/meta_token_refresh Lambda handlers exist — USE THEM, don't hand-roll. Old failure-email mystery unresolved (check spam for '[RigaCap] Post #636 failed'); Erik wants first-failure email on billing/credential errors.
- **▶ TOMORROW'S HEADLINE (Erik, Jun 11 night): PLAN THE MARKETING BLITZ** (task #12) — who/how to target is open; inputs ready: F/A matrix (Capital Preserver, $250k+, filtration-not-conversion), dual channel, turmoil window, pricing-analysis market research, all launch assets live. Paul's Friday feedback feeds the RIA motion.
- **Next session queue:** (1) verify Day-2 scan + first real entries when buys appear (model-portfolio entry path not yet exercised live — logger.info invisible in CW), (2) egate/factor health check early next week (task #11), (3) HeyGen = decided NO for social (memo saved; phone videos instead), (4) Paul (family CFP @ Raymond James) emailed Jun 10 — traveling, will review /for-advisers + /track-record FRIDAY Jun 12; his feedback gates the firm-licensing one-pager, (5) firm-licensing one-pager after Paul's feedback.
## (same day, context) Jun 10 EVENING — t30v IS LIVE, site on 21-year canon
- **[Campaign + cutover + 21y canon (THE file — read first)](project_inversion_campaign_jun9.md)** — t30v WENT LIVE Jun 10 22:00 UTC (cutover: books wiped to $100k, strategy 6 = 20×4.5/trail30/volw1.0, adaptive-params row superseded — the live trail reads THAT table, not the strategy row!). Day 1 = Jun 11 scan. Site fully on 21y continuous canon (8.3%/0.73/19% vs naive-net 13.2%/57% vs SPY 9.8%/55%; last-24mo +32%/2.20; 2022 = **−7.5%** NOT positive — old claim was window-framing). Race animation live (human-first, nerve-range finale). QUEUE: egate fast-follow ("factor health check": tracker seeded from bench curve, gate SIGNALS, shadow first) → beta email → social voice. Erik's family RIA to review /for-advisers.

## ▶ (superseded) Jun 9 reckoning — resolved by the above
- **[Inversion campaign + frame forensic (Jun 9-10)](project_inversion_campaign_jun9.md)** — naive 28.8% CAN'T be defended w/ overlays (17 variants, none <40% daily MDD; naive TRUE daily MDD −52%, race JSON's −30% = sampling artifact). Full t30v ablation: gates≈0 net, ranking horizon ≈1pp, max_hold=NO-OP, min_price-on-end-adjusted EXCLUDED NVDA pre-2020 (fix: min_price=0 research). Frame gap SOLVED by trade forensic: vacancy-only=stagnation (~10%), displacement=5-day-hold noise churn (−50pp/3y); frame regime filter CRUSHED 2020 (+128/13MDD vs sim +83). Missing mode = wholesale periodic rotation → carry=False configs (incl. candidate product `t30v_m250_nocarry`) running → ablation_results.json. Erik: keep 14% copy live meanwhile.
- **[Jun 9 launch + STRATEGY RECKONING](project_jun9_strategy_reckoning.md)** — Marketing LAUNCHED live + verified (honest site, headline B, all blogs/PITFWU flagship, /for-advisers; t30v port deployed DORMANT). BUT the portfolio-race continuous analysis found the comfortable story is wrong: **held-from-2017, t30v = 9.8% CAGR (not the marketed 14% window-mean), LAGS SPY (13.6%) AND raw 12-mo momentum (28.8%) on return — only edge is drawdown (17.9% vs 30%+). t30v is DEFENSIVE (beats in down years, lags in bull years; lost a bull-heavy decade on return). LIVE COPY OVERSTATES IT.** Big open decision: which lens (continuous vs window-mean), is the give-up justified, fix live copy now? t30v go-live + clean live-portfolio reset + chart/animation + social ALL pending/gated on this. Beta email written but DON'T SEND yet. Switching to Fable 5 likely — this file is the handoff. **READ THIS FIRST.**
- **[t30 strategy detail + cutover checklist](project_t30_validated_strategy.md)** — full t30v config, the vol_weight prod port (dormant), CB-keep-on, the data-source finding (prod=7y pickle 2019-26, research=parquet 2016+), chart endpoint mechanics. Numbers here are WINDOW-MEAN — see the reckoning above for the continuous truth.

## ▶ (superseded) RESUME (Jun 5 2026) — STRATEGY VALIDATED, longer history next
- **[t30 — first honestly-validated strategy (LOCKED Jun 5)](project_t30_validated_strategy.md)** — PITFWU built+verified (7/7, yfinance cross-checks). Full reckoning: ALL prior numbers (50%/33.6%/19.3%/Trial-37/heuristic-26%) were mirages (splits+survivorship+single-window+overfit). Rebuilt from fundamentals on clean per-period WF: entry has real-but-thin edge; CONCENTRATION (6×15) was the disease; diversifying to 20×4.5 + wide trail → **t30: Tier-2 held-out 13.3% ann / 0.80 Sharpe / 14% MDD / no losing 2yr window / recent-2y +22.4%**. Costs negligible. Next: build longer history (2018/2020 windows ~free from existing 2016+ bars; pre-2016 needs yfinance) THEN regimes (regime-switch on N=1 bear = overfit). Read this first.
- **[Resume pointer — PITFWU build (Jun 4 night)](project_resume_here_jun4_night.md)** — superseded by the t30 lock above; kept for the build history.

## CRITICAL — BACKTEST PICKLE NOT SPLIT-ADJUSTED (Jun 4 2026)
- **[Backtest pickle has RAW unadjusted splits](project_pickle_split_bug_jun4.md)** — the prod backtest pickle (`prices/all_data.pkl.gz`, Jun-3 pull) has raw stock-split discontinuities (AMZN/GOOGL 20:1, NVDA 10:1, TSLA 3:1, etc.). Any backtest HOLDING a position across a split books a phantom −67% to −95% loss + corrupted indicators. Caused a bogus "M3 bear MDD 38%"; split-adjusting → MDD back to **20.6%** (the cited 21.5% was RIGHT). **PROD live data IS adjusted — pickle only, pull-time dependent.** ALL bear-inclusive/split-window research numbers suspect until re-run on adjusted data (the recurring "M3+addon → 38-40% MDD" pattern may also be this artifact, not the addon). Fix: rebuild pickle `adjustment='all'` + build PITFWU (point-in-time forward-walking universe). Marketing FROZEN until clean re-run.

## CRITICAL — NEVER WASTE PAID/LONG-RUNNING WORK
- **[Always checkpoint paid/long-running scripts](feedback_never_keep_paid_work_in_memory.md)** — any script that costs money OR runs >5 min MUST write incremental disk checkpoints. Jun 3 2026: Haiku scorer ran 50 min / $2.43, killed mid-run, ALL work lost because results accumulated in memory. Cheap durable saves beat elegant end-of-run writes EVERY TIME.
- **[Smoke backtester.py edits locally before pushing](feedback_smoke_locally_before_deploy.md)** — Lambda deploy is auto-CI/CD; a buggy hot-path commit triggers prod-worker error alarms on next invocation. 30 sec local smoke catches 90% of trivial bugs. Jun 3 2026: sentiment-exit `pos['symbol']` KeyError.

## CRITICAL — BRAND
- [NEVER publish the recipe](feedback_never_publish_recipe.md) — public surfaces get signal STRUCTURE, never coefficients (DWAP 5%, 5d/60d weights, 3% near-high). Jun 11: launch cards leaked the thresholds, Erik caught it. Classify surface public/private before propagating canon.
- [Paper brand EVERYWHERE](feedback_paper_brand_everywhere.md) — paper #F5F1E8 / ink #141210 / claret #7A2430, serif display. Navy/gold (#172554/#f59e0b) is the DEAD old brand; never generate/'preserve' assets in it (Jun 11: launch cards rebuilt in old brand, Erik caught it). 'Preserve the visual system' ≠ preserve a dead brand.

## CRITICAL — NEVER COMMIT SECRETS
- **[Never check in credentials](feedback_never_check_in_secrets.md)** — grep every file for password/postgres://*creds*/api.key/AKIA/sk-/whsec_ BEFORE `git add`. Never `git add .`. RDS master pw was leaked Apr 16 2026 via this exact failure mode; rotated same day. Scripts must read DATABASE_URL from env, never hardcode.

## CRITICAL DEPLOYMENT RULES
- **NEVER deploy DB schema changes without running the migration FIRST.** Migration-first pattern: deploy SQL → run → verify, THEN deploy model changes.
- **NEVER use `aws lambda update-function-configuration --environment`** — it REPLACES ALL env vars, causing full outage.
- **Always deploy via CI/CD (push to main).** Manual `deploy-container.sh` races with CI/CD.
- The `run_migration` Lambda event handler can run ALTER TABLE without auth.

## CRITICAL STRATEGY RULE
- **[WF backtest ↔ production signal generation MUST be identical](feedback_wf_prod_parity.md)** — any lever proven in walk-forward backtesting MUST be ported into production signal code in lockstep. Marketing claims come from backtests; subscribers must be able to realize them. **Known gap (Apr 28 2026): CB pause logic exists in backtester only, not in production scanner.**
- **[WF↔prod incumbent-displacement gap (May 29 2026)](project_wf_prod_displacement_gap.md)** — production `process_entries` only enters on vacancies (max-positions gate); WF service test methodology produces ~36 extra trades + 2× returns. Likely affects ALL prior strategy validations (Apr 28, Run5, Trial 37, T3). T3 productionization paused — option 1 (add prod displacement) leaning, deferred over weekend.
- **[North Star + phased plan (Jun 1 2026)](project_north_star_phased_plan.md)** — locked goal: 20% ann / ≤20% MDD / Sharpe ≥1 / Calmar ≥1. Four-phase unpeel: Phase 0 honest baseline (running) → Phase 1 lever/target decision → Phase 2 buy-signal definition (6-question tree) → Phase 3 surface alignment. Parity contract is sacrosanct.
- **[North Star target is LOCKED — do not propose lowering it](feedback_north_star_is_locked.md)** — 20/20/1.0/1.0 stands. When a variant falls short, propose stacking more levers, not redefining success.
- **[Testing methodology v2 — three tiers + cutoff lock (Jun 1 2026)](project_testing_methodology_v2.md)** — Tier 1 hypothesis (tuning 2019-2023) → Tier 2 validation (held-out 2023-2026, mandatory) → Tier 3 live shadow (recommended). Pickle/cutoff fixed per research cycle. 11y testing gated on parquet migration. All pre-Jun-1 results are hypothesis-only under v2.
- **[A1 failed → signal quality is the bottleneck (Jun 1 2026)](project_a1_failed_signal_quality_bottleneck.md)** — First v2-compliant variant (4×22% + T3) FAILED dramatically (5.96% ann, 29.7% MDD) ON LOCAL. Conclusion now SUSPECT — needs Lambda re-run per Jun 2 runtime-drift finding.
- **[Local vs Lambda runtime drift (Jun 2 2026)](project_lambda_runtime_drift_jun2.md)** — Same code, same pickle hash, ~5pp annualized swing between local Python 3.9 and Lambda 3.13. Lambda is THE authoritative bench; all local results invalidated. Cutoff revised to 2022-01-01 (bear-inclusive validation). Lambda baseline: 13.58% ann / 0.91 / 16.59 / 0.82.
- **[M3 is the local max — best after 22 variants (Jun 2 2026)](project_m3_local_max_jun2.md)** — VIX>30 mega-cap basket: Tier 2 ann 19.31% / Sharpe 1.09 / MDD 21.53 / Calmar 0.90. Closest balanced result; fails on MDD by 1.5pp + ann by 0.7pp. Disproofs confirmed mega-cap selection IS the alpha. Parameter mining exhausted; next leg needs orthogonal alpha (sector RS, news, earnings). Erik's call: "M3 is a very good product."
- **[News-volume signal DEAD — Path A exhausted (Jun 3 2026)](project_nv_dead_path_a_exhausted.md)** — NV1/NV2/NV3/NV1_solo all failed Tier 2 bear-inclusive (0/4 targets). NV1_solo is the canonical v2 overfit example: Tier 1 30.20/1.30/14.93/2.15 → Tier 2 10.65/0.70/22.07/0.48. Adding NV to M3 WORSENED M3 (MDD 21.53→38-40). Counts without polarity NLP not viable. Scaffolding preserved; counts.parquet stays in S3 for future Path B (sentiment NLP).
- **[News-sentiment Path B FAILED v2 (Jun 3 2026)](project_nv_path_b_failed.md)** — Haiku-scored sentiment ($3.73, 210k articles) beat Path A on every variant but still 0/4 on Tier 2. NV-P1_solo notable: FIRST variant ever to pass MDD ≤ 20% on bear-inclusive (17.82%), but ann 12.14 vs 20 target. Adding news to M3 doubles MDD (multiplicative concentration). News entry signal fully exhausted. Sentiment+headlines cached in S3 for future EXIT-signal / SIZING-modifier hypotheses (no re-pull needed).
- **[Sentiment-EXIT failed v2 BUT defensive validated (Jun 3 2026)](project_nv_exit_failed_but_mdd_validated.md)** — NV-X1/X2/X3 all 0/4 on Tier 2. NV-X1_solo set NEW MDD RECORD: 15.76% (best ever, 4.24pp under 20% target). Pattern across all 12 news variants: news+M3 → ~38% MDD always; news-solo → 15-22% MDD always. News fights M3 concentration. Asymmetric trail (loosen on positive sentiment, tighten on negative) is next legitimate test.
- **[NV-T asymmetric trail BREAKTHROUGH 2/4 (Jun 3 2026)](project_nv_t_asymmetric_trail_breakthrough.md)** — Erik's "loosen on good news + tighten on bad" intuition. NV-T1+M3 FIRST variant ever to pass ann≥20%+sharpe≥1.0 on bear-inclusive Tier 2 (21.41/1.02/39.77/0.54). NV-T1_solo first to pass sharpe+mdd (16.48/1.08/19.05/0.87). NV-T2 (scale=16) is canonical Tier1→Tier2 overfit: best T1 ever (15/26 4-pass) → worst T2 (0/4). Best v2 results to date: two 2/4. M3+news always ~38% MDD across 16 variant types.
- **[News research book COMPLETE (Jun 3 2026)](project_news_research_complete.md)** — 19 variants across 5 mechanisms (counts/entry/exit/trail/sizing) all tested under v2. Best: NV-T1+M3 (2/4, ann+sharpe) and NV-T1_solo (2/4, sharpe+mdd). Sentiment-as-sizing dead (redundant with trail). Compositional law proven: news+M3 always ~38-40% MDD; news+solo always 11-17% ann. Mechanisms don't compound. Next legitimate research: orthogonal data sources (earnings, options flow) — different from news, not tweaks of it.
- **[M3 distribution breakthrough (Jun 4 2026)](project_m3_distribution_breakthrough.md)** — pure-M3 baseline measurement: 33.6% mean ann across 26 bull-mostly 2y windows, 85% hit ≥20% ann, recent 2y is 4/4 v2 PASS (50.2/2.22/17.7/2.84). Bear-inclusive 19.31% was misleadingly conservative. Marketing pitch hierarchy locked: lead with 19.3%, add 33.6% mean + 85% pass rate context, footnote recent 2y. Strategy renamed external = "RigaCap Momentum Strategy".
- **[Surface work decisions LOCKED Jun 4 2026](project_surface_decisions_jun4.md)** — 3-bucket signal taxonomy `Approaching/New/Open`, ship Volatility Basket to prod this week, strongly recommend Personal Portfolio tracking. Plus stale-number audit (`project_stale_numbers_audit_jun4.md`) found Trial 37 + Apr 28 superseded numbers live on LandingPage and TrackRecord. Resume pointer: `project_resume_here_jun4_thursday.md`.
- **[M3 = new prod; gap is ONLY the Volatility Basket (Jun 4 2026)](project_m3_to_prod_gap_jun4.md)** — Erik: M3 becomes production. Verified in code: prod model portfolio ALREADY runs M3 base (ensemble entry sorted by ensemble_score, 12% flat trail, 6×15%, regime, CB). Only missing piece = VB overlay (VIX>30 mega-cap basket). t10/s8 in NEITHER prod nor M3 → registry "T3" canonical numbers are stale/wrong for both. Parity rule: ship VB → validate → THEN flip marketing to M3 numbers. Displacement gap still applies.
- **[~30% MaxDD is structural, not 2022-bear-driven](project_maxdd_structural_concentration.md)** — skip-2022 3y sweep (May 22) showed mean MaxDD ~31% across 3 windows with NO 2022 exposure. Ruled out: gradual deployment, CB-tighten, reactive portfolio-DD sizing. Lever is concentration (6×15%), not regime detection. Frame MaxDD work as concentration-attack, not bear-fix.
- **[DD-tighten breakthrough validated 50/52 dates (May 22)](project_dd_tighten_breakthrough.md)** — `scripts/wf_dd_tighten_stop.py` t15/s8 (DD ≥ 15% → trail 12→8%) wins baseline on 92/90/98/94% of dates (ret/Sharpe/MaxDD/Calmar). Median Sharpe 0.83→0.91, MaxDD 33.5→27.6, Calmar 0.65→0.89. LOCAL research only — not in prod. Capped-consecutive variant ruled out (releases stop DURING DD = compounds losses). Depth-graduated next.

## CRITICAL LEGAL FRAMEWORK
- **[Publisher's exemption + canonical disclaimer language](project_disclaimer_canonical.md)** — RigaCap operates under the Investment Advisers Act §202(a)(11)(d) publisher's exemption (confirmed by counsel Apr 30 2026). Three Lowe factors must be preserved: impersonal advice, bona fide commentary, regular circulation. Canonical disclaimer language (long/short/micro forms) lives in the linked file — use it consistently, don't paraphrase.

## AWS
- **Always use `--profile rigacap`** (account 149218244179). Default profile = wrong account (774558858301).
- **Two Lambdas:** `rigacap-prod-api` (1024 MB, 30s) and `rigacap-prod-worker` (3008 MB, 900s). Same image, `LAMBDA_ROLE` env var.
- **Manual invoke always targets worker:** `aws lambda invoke --function-name rigacap-prod-worker --profile rigacap ...`
- **SIGNAL_UNIVERSE_SIZE=100** on both lambdas (Jun 13; was a 200 drift that broke bench parity). Env changes: SAFE full-merge only (get all vars → change one → put all), NEVER `--environment` replace.
- API Gateway 29s timeout — direct Lambda invoke for long ops. Lambda 10s init — DB connections lazy.
- **Lambda concurrency**: 1000 total, API reserved=50, Worker reserved=200 (increased from 10 after Mar 30 outage).
- **[Lambda memory capped at 3008 MB](project_aws_lambda_memory_cap.md)** — AWS support tier blocks quota increase above 3008. DO NOT propose `memory_size > 3008` in Terraform; parquet migration is the real unblock (partial-read by symbol vs holding the full 700 MB pickle).
- **[Universe history snapshots (May 17 2026)](project_universe_history_snapshots.md)** — daily full ranked liquidity universe persisted to `s3://.../signals/universe-history/{date}.json`. Chained from daily scan. Future rank audits read directly instead of reconstructing.

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
- ID 1: DWAP Classic | ID 2: Momentum v2 | ID 3: DWAP Hybrid | ID 4: Concentrated Momentum | ID 5: DWAP+Momentum Ensemble | ID 6: **DWAP+Momentum Ensemble — T3** (active May 28 2026)
- **[Strategy 6 provenance — Apr 28 Canonical → T3 rename](project_strategy6_provenance.md)** — row 6 repurposed May 28 2026; pre-rename it documented Apr 28 baseline +160% / 0.92 / 20.4% on 11y pickle 8-date sweep

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

## Strategy Mechanism Caveats
- **[circuit_breaker_tighten_pct is a no-op](project_cb_tighten_incomplete.md)** — the write at backtester.py:1332 has no read site in the exit logic. Param defaults to 0 so prod is unaffected, but TPE results that searched over it were optimizing noise. Don't add the read-side fix without a regime-based CB trigger that fires during slow bears.

## Dual-Source Market Data
- **Primary: Alpaca Pro (SIP).** yfinance = fallback + always for index symbols (^VIX, ^GSPC).
- **SPY also routed to yfinance** (May 19 2026) — see [project_spy_routing_yfinance.md](project_spy_routing_yfinance.md). NOT because Alpaca is corrupted (confirmed via Alpaca support May 21: SPY 2026-02-02 $69.005 low was a real outlier trade) — but because we want outlier-filtered SPY for the 200MA regime detection, not SIP-faithful raw.
- Settlement-check probe is **AAPL** (not SPY) — Alpaca-native, never re-routed.
- Symbol normalization: hyphens (yfinance) ↔ dots (Alpaca) handled automatically.

## Lambda Gotchas
- **[Lambda payloads must be TRUTHY](feedback_lambda_payload_truthy.md)** — `if event.get("foo"):` skips on `{}` (falsy) → Mangum errors. Use `{"_": 1}` for config-less handlers. Burned 3× — manual invokes AND **EventBridge rule Target Input** (Jun 1 2026: monthly_recap). New EventBridge rules require truthy Input + smoke-fire before relying on cron.
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
- [Pickle → Parquet migration — REVISED Jun 10: promote PITFWU to canonical](project_storage_migration_roadmap.md) — migration target = the PITFWU layer itself (research↔prod 1:1 parity; kills the two-stores bug class). Needs: daily-append write path, adjustment-convention decision (split-only price-return proposed), shadow-diff validation. Pre-2016 EXT layer stays research-only.
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
- **[Run5 parity drift (Apr 19-May 18 2026)](project_run5_parity_drift_lesson.md)** — production ran Run5 over-fit params for 4 weeks while marketing claimed Apr 28 baseline. Rollback shipped May 18 (commit 0055177). LESSON: every commit touching strategy params requires a parity audit. Track Record sim_ids 922-930 still stale (separate fix).

## Planned Features
- **[Admin run_sql Lambda handler (TODO)](project_admin_run_sql_handler.md)** — add a generic read-only SQL/diagnostic event branch to the worker so ad-hoc invokes don't trip the worker-errors alarm. ~1 hr build with read-only guard + row cap + audit log.
- **[main.py housekeeping — extract event handlers](project_main_py_housekeeping.md)** — main.py is 9,228 lines, 90+ event-handler branches. Refactor target: `app/lambda_events/<domain>.py` modules dispatched from a list in main.py. Not urgent (no active pain); trigger when merge conflicts in main.py block shipping, OR during a quiet parquet-migration window. Start with the diagnostics cluster (highest growth rate, easiest to test).
- [Signal slippage tracking](project_signal_slippage_tracking.md) — post-publication price monitoring to measure real achievable execution vs published entry price
- [Balanced content rule](project_balanced_content_rule.md) — every 4th social post must be a loss/quiet week/limitation; trust-building differentiator
- [Trial length decision (post-launch+60d)](project_trial_length_decision.md) — default $0/14d auto-extend, A/B-test $19/30d paid; SaaS data favors paid trials for conversion. Don't act before 60 days of launch data.

## References
- [HeyGen avatar ID](reference_heygen.md) — Erik's current avatar for AI video generation
- **[HeyGen API key not wired (May 18 2026)](project_heygen_api_key_gap.md)** — Avatar V engine fix shipped but production Lambda has empty HEYGEN_API_KEY. Test fires fail. Resolve via `-var="heygen_api_key=..."` on next terraform apply.
- [Twitter media upload field naming](reference_twitter_media_api.md) — use 'media' for raw bytes, 'media_data' for base64; wrong field silently drops images
- [Cascade Guard = Circuit Breaker](reference_naming_cascade_guard.md) — external/marketing name vs internal/code name; same mechanism

## Other
- **[STR PK = (symbol, ensemble_entry_date)](project_str_resignal_audit_pickup.md)** — STR rows are one-per-signal-event, not one-per-fresh-day. Audit + backfill workflow + production dedup fix shipped May 4-5, 2026.
- [No dated callouts in design docs](feedback_no_dated_callouts_in_docs.md) — don't sprinkle "(Apr 2026)" or "newly added" markers; keep docs evergreen, let git history carry the session-dated context
- [Signal frequency = "3-4 per month"](feedback_signal_frequency_claim.md) — never "6-8 every 2 weeks" or "~15/month"; both are stale drift
- **[Re-validate "3-4 per month" after N=500 bump (May 18-31 2026)](project_signal_frequency_post_n500.md)** — universe bump to 500 may modestly raise fresh-entry count. Measure live model_portfolio entries over 2 weeks. Anchor count is FRESH ENTRIES, not dashboard buy_signals list (which will balloon).
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
- **[Engagement reply voice — calm specific, never contrarian](feedback_engagement_voice_calm_specific.md)** — Twitter engagement drafts must read as calm/specific antidote to noise, NOT as refutation. Use "would" tense for what discipline does, never "you're wrong". Phrase bans for "actually,", "not quite", "the problem with", etc. enforce mechanically. Don't reintroduce "disagreement is more engaging" framing — that was the bug we just fixed.
- **[US English only](feedback_us_english.md)** — favor/optimize/modeled/realize. Never favour/optimise/modelled/realise. Easy to slip into British forms unconsciously.
- **[NEVER name DWAP in public prose](feedback_no_dwap_in_public.md)** — proprietary indicator. Use "proprietary timing reference" / "long-term accumulation reference" instead. Code field names + admin UI + email labels are fine; prose is not.
- [Newsletter topic rotation](project_newsletter_topics.md) — §02 educational topics, review quarterly, add from new features + subscriber feedback
- **[Newsletter §04 variance preservation](feedback_newsletter_s4_variance.md)** — §04 (A Note From Erik) prompt has explicit theme rotation + anti-repeat + headlines hook. Do NOT simplify back to vague "current moment" guidance — caused every week to drift to "discipline / doing less, not more". Erik-flagged May 16 2026.
- [Newsletter ops and timing](project_newsletter_ops.md) — Sat 8PM generate, Sun 10AM auto-send, no weekend refresh by design
- [Newsletter has no signals](feedback_newsletter_no_signals.md) — purely editorial, same for free and paid, no tickers ever
- [Never blast emails without target_emails check](feedback_never_blast_without_target.md) — verify handler supports filtering BEFORE invoking
- [Newsletter cron MUST use locked draft](feedback_newsletter_cron_draft.md) — Apr 26 outage: cron sent wrong version to all subscribers
- **[Meta token lifecycle (IG + Threads) — full punch list](project_meta_token_lifecycle.md)** — short-lived recovery works (May 6); long-lived exchange blocked on app secret; auto-refresh cron not built; IG API base bug fixed (`graph.facebook.com` not `graph.instagram.com`)

## 📏 SOCIAL PLATFORM CHAR LIMITS (Jun 17 2026) — enforce per-platform
Threads = **500 chars** (hard; a >500 post 400s "Param text must be at most 500 characters"). X/Twitter = 280. IG caption = long (~2200). Jun 17: AI "We Called It" post exceeded 500 on Threads → now enforced at the PUBLISH layer (`social_posting_service.post_to_threads` truncates on a word boundary + logs). When generating/editing social content, fit Threads copy to ≤500 at the SOURCE too (don't rely only on the truncation safety net — it can clip a trailing URL/CTA).
