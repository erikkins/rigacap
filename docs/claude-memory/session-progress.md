---
name: session-progress
description: "Live session snapshot (auto-checkpointed ~15min) — what's done, in flight, and next"
metadata: 
  node_type: memory
  type: project
  originSessionId: 2dce3134-d861-45c4-a371-80378750f8c0
---

# Session snapshot — Jul 7 2026 (Tue) — rule B ✅, PHASE 2 DB PLUMBING CODE-COMPLETE (dark-launch gated); next = commit + off-hours migration + deploy

**Full state:** [[project_preserver_2tier_phase2]]. Brand: [[feedback_brand_claret_paper]] (claret+paper only). Names LOCKED: Preserver/Core/Maximizer (t30v + Maximizer++ = internal only).

**⭐ rule B ✅ (Erik)** — hold-to-exit + layer (no churn on regime flip; positions exit by own hold; new entries from active book). Unblocks the Preserver migration → Track A can start.

**⭐ PHASE 2 SHADOW COMPUTE CORE COMPLETE + PROVEN (all backend/app/services/, additive, undeployed):** preserver_sleeves.py (detectors signal-exact), preserver_signal_service.py (routing), preserver_portfolio.py replay_sleeve (PENNY-EXACT vs research), preserver_service.py PreserverBook LIVE-ROBUST (days_held counter; to_positions/from_state serialization; re-validated 2634d = $167,048, round-trip ✓).

**⭐⭐ DB PLUMBING CODE-COMPLETE (Jul 7, uncommitted on research branch, validated to LOAD, needs REAL-DB test):**
- `run_shadow_day(db, signal_date, regime, t30v_signals, data_cache, n=15)` IMPLEMENTED in preserver_service.py: reconstruct book from latest PreserverBookSnapshot → route → advance one day (rule B) → pg_insert-upsert today's routed PreserverSignals + fresh snapshot → commit. Async ✓.
- 2 SQLAlchemy models in database.py (PreserverSignal, PreserverBookSnapshot) — columns MATCH backend/migrations/preserver_shadow_tables.sql; load ✓.
- Isolated daily-scan hook ADDED in main.py after §6 ensemble-persist (~line 1665): try/except (never aborts scan) + **env-gated `PRESERVER_SHADOW` (dark launch — code deploy = NO-OP until env set)**. Regime chain type-verified: RegimeType(str,Enum).value → data['regime_forecast']['current_regime'] string → route() buckets match EXACTLY (no silent t30v fallthrough). main.py parses ✓.
- **DEPLOY SEQUENCE (all safe, dark until last step):** (1) commit ✅ (`ca5f5d3`); (2) apply migration off-hours via `{"run_migration": true}` worker (or add SQL to runner) → verify 2 tables exist; (3) deploy code (hook still dormant — env unset); (4) set `PRESERVER_SHADOW=true` via SAFE read-modify-write (NEVER --environment); (5) watch ~1wk of scans (🕯️ log line) → compare vs offline replay; (6) flip tiers. Rollback = unset env.
- **⚠️ run_shadow_day has NEVER hit a real DB** — parses + models load, but upsert paths + snapshot round-trip need one dry run before step 4 env-gate.

**Q&A this turn — Maximizer on a 1-day regime blip (99% rotating_bull, occasional 1-day strong_bull flip):** essentially a NON-EVENT. Breakout sleeve is ENTRY-gated on rotating_bull but HOLDS 29 days through ANY regime (breakout_tame.py) + rule B = no churn on flip. So: no forced exits, at most 1 day of paused breakout entries (near-full book ⇒ ~0 free slots ⇒ ~0 cost), self-heals next day. DELIBERATE: we did NOT build flatten-on-flip because the 2021 −33% momentum crash happened at 100% rotating_bull the whole time — regime flags can't catch momentum crashes; the brake is factor-vol scaling (Barroso), classifier left free to blip. Caveat: Maximizer routing/vol-brake still RESEARCH-only (only Preserver ported); exact strong_bull→sleeve mapping not frozen (v2 lumps into else→t30v) but barely matters on a 1-day blip under rule B.

## ✅✅ PRESERVER SHADOW FULLY LIVE (Jul 7 EOD) — migration + deploy + flag ALL DONE
- Merged research→main (410090e), CI/CD deploy SUCCESS, `PRESERVER_SHADOW=true` set on worker via SAFE boto3 RMW (49→50 keys, all critical intact). **Shadow starts recording at TOMORROW's (Jul 8) 4pm ET daily scan** → writes preserver_signals + preserver_book_snapshots (isolated try/except, live scan untouched). VERIFY tomorrow: `🕯️ Preserver shadow:` log line + 1 row appears in each table. Rollback = unset PRESERVER_SHADOW.
- ~1wk shadow validation → compare persisted book vs offline replay → then tier serving + Stripe gating.

## ⭐⭐ (superseded above) MIGRATION DONE + shadow deploy queued (Jul 7)
- **Preserver shadow migration APPLIED to prod** (worker `{run_migration, sql:[...6 stmts]}`): both tables exist + verified (cols match models, 0 rows). **run_shadow_day REAL-DB dry-run PASSED** (idempotent upsert, snapshot round-trip, cleaned up pristine). Caveat cleared.
- **Stripe config.py:** added 3 MAXPP env-var declarations (STANDARD/FOUNDING/ANNUAL) — inert until referenced. UNCOMMITTED.
- **DEPLOY DECISION (Erik):** **merge WHOLE research branch → main** (brings runtime + scripts + docs + launch pkg) → CI/CD deploys. Merge is CONFLICT-FREE (verified; main's SSOT commit b2b8624 touches files research didn't). NOT yet done — paused for the bug below. Shadow stays DARK post-deploy until PRESERVER_SHADOW env set (separate step).

## 🚨🚨 SELL-ALERT PARITY BUG found (Jul 7, priority) — dashboard 12% vs model/email 30% trailing stop
- Erik held 4 (GLW/UMC/MRVL/WULF), daily scan ran, got **1 email (WULF) but dashboard showed SELL ribbons+buttons on ALL 4** → he sold all 4.
- **ROOT CAUSE:** dashboard `generate_sell_signals` (signals.py:1818) uses hardcoded `settings.TRAILING_STOP_PCT=12.0`; email EOD pass (main.py:1938) + model exits use `_get_regime_trailing_stop(data)` = regime-adjusted **30%** today. At 12% all 4 breach (ribbons); at 30% only WULF (−30.2% off high) breaches (email). GLW/MRVL/UMC were −27.5/−25.7/−14.9% off high → NOT at model's 30% exit.
- **EMAIL WAS CORRECT** (WULF = only true model exit); **DASHBOARD IS STALE** = MISSED SPOT in the t30v 12%→30% display-parity sweep (see [[project_preserver_2tier_phase2]] TODO #2). Affects ALL subscribers → premature exits. Erik was pushed into 3 exits the model would HOLD.
- **2 bugs:** (1) PRIMARY money bug = dashboard trail 12%≠30% (fix signals.py:1818 → `_get_regime_trailing_stop(data)` / 30). (2) SECONDARY = EOD alert sends 1 email PER symbol, no ROLLUP (latent today, only 1 breached) — Erik's original ask; build consolidated "today's exits" email.
- **AWAITING Erik's nod** on direction (align dashboard to 30% model-truth = ribbons should've shown only WULF). Then fix both, ride the research→main deploy.

**NEXT:** (a) get Erik's OK on 30% direction → fix dashboard parity + rollup email; (b) merge research→main → deploy (shadow + parity fix together); (c) set PRESERVER_SHADOW; (d) Stripe add-on wiring (checkout line item + has_maxpp_addon migration-first + portal + gating).

**⭐ STRIPE add-on prices CREATED (Erik):** Standard $100/mo=price_1Tqf2nCOYW9ZRoIIkfELxlzb, Founder $79/mo=price_1Tqf2nCOYW9ZRoII6rbnXbhF, Annual $1000/yr=price_1Tqf2nCOYW9ZRoIISghdCu2W (in launch-plan doc). NEXT wire: config.py STRIPE_PRICE_ID_MAXPP_STANDARD/_FOUNDING/_ANNUAL getenv + set Lambda env (SAFE RMW) + checkout add-on line item + has_maxpp_addon entitlement col (migration-first) + portal + gating.

**⚠️ RECOMMENDED NEXT (asked Erik, my vote):** (1) COMMIT the large uncommitted pile (Phase 2 files + launch docs + naming + stripe IDs) on research branch — overdue hygiene before live-infra work; (2) implement DB plumbing (critical path); (3) Stripe wiring parallel. Launch = week of July 21, 2-wk sprint gated on shadow validation. Memories: [[project_secret_dossier]], [[feedback_survivorship_free_not_marketing]], [[project_newsletter_exit_stops_topic]].
