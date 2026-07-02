---
name: session-progress
description: "Live session snapshot (auto-checkpointed ~15min) — what's done, in flight, and next"
metadata: 
  node_type: memory
  type: project
  originSessionId: 2dce3134-d861-45c4-a371-80378750f8c0
---

# Session snapshot — Jul 2 2026 (Thu) — 2-tier locked in framing doc + Phase 2 STARTED (sleeve port validated)

**Context:** Regime-adaptive engine → 2-TIER product. Branch `research/shape-diversifiers-regime-allocator`. Phase 0 (SSOT) on MAIN b2b8624. Phase 1 tier vintages done.

**✅ FRAMING DOC updated to 2-TIER + pricing** (`design/documents/maximizer-vs-preserver-framing.md`): BASE=Preserver ($129/mo, contains t30v Core engine, on-brand preservation); Maximizer++=paid ADD-ON ~+$100-120/mo → $229-249/mo aggressive tier (sub-brand for firewall; separate-product only if different audience); Core t30v = engine+proof underneath (not a separate product). Daily numbers in table. Caution: price on DURABLE +7pp not the 49% peak.

**⭐ PHASE 2 STARTED — productionize Preserver (additive, migration-safe):**
- **STEP 1 ✅ DONE + PARITY-VALIDATED:** created `backend/app/services/preserver_sleeves.py` — prod port of pullback_ma + oversold_bounce detectors (frozen validated params) + `route(regime)` (calm_bull→pullback, capitulation{panic/recovery/weak_bear}→oversold, else→t30v). Parity vs research = EXACT (0 mismatches, apples-to-apples w/ base filter). Pure functions, NOTHING live touched.
- **PHASE 2 SEQUENCE:** 1✅ sleeves→prod. 2 SHADOW signal generator (daily scan computes regime via market_regime.py→route→gen Preserver signals under NEW strategy_id, store, DON'T serve). 3 shadow validation ~weeks. 4 tier field (MIGRATION-FIRST, off-hours). 5 tier-aware serving (flagged). 6 Preserver model portfolio.
- SAFETY: new strategy_id (t30v path untouched); shadow before serve; migration-first; reuse daily-scan data.

**NEXT (asked Erik):** Step 2 — trace daily-scan signal-gen path (how t30v signals generated+stored) then stand up shadow Preserver generator. Still additive/safe.

**PHASES:** 0✅ 1✅ 2(in progress) 3(roll copy). Landing copy `design/documents/landing-copy-3tier.md` (needs 2-tier update in Phase 3). Memories: [[feedback_survivorship_free_not_marketing]], [[project_secret_dossier]], [[project_newsletter_exit_stops_topic]].
