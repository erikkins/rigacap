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

**NEXT (unblocked, Erik to pick):** (a) schedule off-hours migration → shadow, or (b) parallel Stripe add-on wiring (config.py MAXPP env vars + safe Lambda RMW + checkout line item + has_maxpp_addon migration-first + portal + gating).

**⭐ STRIPE add-on prices CREATED (Erik):** Standard $100/mo=price_1Tqf2nCOYW9ZRoIIkfELxlzb, Founder $79/mo=price_1Tqf2nCOYW9ZRoII6rbnXbhF, Annual $1000/yr=price_1Tqf2nCOYW9ZRoIISghdCu2W (in launch-plan doc). NEXT wire: config.py STRIPE_PRICE_ID_MAXPP_STANDARD/_FOUNDING/_ANNUAL getenv + set Lambda env (SAFE RMW) + checkout add-on line item + has_maxpp_addon entitlement col (migration-first) + portal + gating.

**⚠️ RECOMMENDED NEXT (asked Erik, my vote):** (1) COMMIT the large uncommitted pile (Phase 2 files + launch docs + naming + stripe IDs) on research branch — overdue hygiene before live-infra work; (2) implement DB plumbing (critical path); (3) Stripe wiring parallel. Launch = week of July 21, 2-wk sprint gated on shadow validation. Memories: [[project_secret_dossier]], [[feedback_survivorship_free_not_marketing]], [[project_newsletter_exit_stops_topic]].
