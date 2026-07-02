---
name: session-progress
description: "Live session snapshot (auto-checkpointed ~15min) — what's done, in flight, and next"
metadata: 
  node_type: memory
  type: project
  originSessionId: 2dce3134-d861-45c4-a371-80378750f8c0
---

# Session snapshot — Jul 2 2026 (Thu) — PARKED at Phase 2 review gate (Erik "sitting for a bit")

**Full state + open questions:** [[project_preserver_2tier_phase2]] (the resume note — read first).

**PRODUCT:** 2-tier risk dial. Base=**Preserver** ($129/mo; last-2yr 31%/1.75/-13%, 2021-26 19%/1.33/-13%). Add-on=**Maximizer++** (+$100-120/mo→$229-249; last-2yr 49%/1.94/-17%, 2021-26 36%/1.61/-20%). Core t30v (live, 20yr 8.3%/0.73/19%) = engine under both.

**⭐ DELIVERED this session:** product overview `design/documents/rigacap-2tier-product-overview.{html,png,pdf}` — sent to Erik (incl high-res single-page vector PDF). Rebuilt in CORRECT brand after Erik flagged navy/gold was OLD.

**⭐ BRAND RULE (new memory [[feedback_brand_claret_paper]]):** brand = CLARET + PAPER editorial (paper #F5F1E8 / ink #141210 / claret #7A2430; Fraunces + IBM Plex Sans; source frontend/tailwind.config.js). **NEVER navy/gold again** (retired). HTML→PDF: --virtual-time-budget for fonts + @page size (1080x1360) for single full-bleed page.

**PHASE 2 STATUS:** prod Preserver port PROVEN FAITHFUL (penny-exact) — all offline files built (backend/app/services/preserver_{sleeves,signal_service,portfolio,service}.py + backend/migrations/preserver_shadow_tables.sql + design doc). ALL on research branch, undeployed, nothing live touched.

**⚠️ REVIEW GATE (next = LIVE INFRA, needs Erik ✅):** (1) book-transition rule — rec **Option B (hold-to-exit+layer)**; (2) schedule migration off-hours. Then: migration→verify→shadow hook (isolated)→2-4wk shadow validation→tier field→serving→launch.

**PARKED THREADS:** Phase 3 (roll 2-tier across landing/emails/social + fix ~5 stale social-launch-cards-v2 citations; landing-copy-3tier.md still 3-tier). Uncommitted on research branch: all Phase-2 backend files + product HTML + docs (Phase-0 SSOT fix already on MAIN b2b8624). [[project_secret_dossier]] TODO. Memories: [[feedback_survivorship_free_not_marketing]], [[project_newsletter_exit_stops_topic]].
