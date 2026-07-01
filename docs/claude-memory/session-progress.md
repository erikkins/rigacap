---
name: session-progress
description: "Live session snapshot (auto-checkpointed ~15min) — what's done, in flight, and next"
metadata: 
  node_type: memory
  type: project
  originSessionId: 2dce3134-d861-45c4-a371-80378750f8c0
---

# Session snapshot — Jul 1 2026 (Wed) — Phase 0 SSOT reconciliation DONE + committed to main

**Context:** 3-tier product (Preserver/Core-t30v/Maximizer++) from regime-adaptive engine. Research on branch `research/shape-diversifiers-regime-allocator` (6e29f21). Currently ON that branch.

**✅ PHASE 0 COMPLETE — SSOT reconciled to live 21yr canon, committed to MAIN `b2b8624`:**
- Root cause found: live `/track-record` (TrackRecordPageV2.jsx) moved to honest **21-YEAR CONTINUOUS canon (8.3% ann / 0.73 Sharpe / 19% MaxDD, 2007-26 + last-24mo +32%/2.20/8.5%)** on Jun-10, but SSOT FILES never followed → `canonical_numbers.json` (Apr-28, 21.1%/20.4%) + `numbers-citations-registry.md` (May-27, 26.4%) were STALE. My earlier -26% cite came from the stale registry.
- FIX (on main): canonical_numbers.json got authoritative `live_canon` block + flat `canon_*` keys (propagator uses `template.format(**canonical)` = flat keys only) + retired old lenses; registry got SUPERSEDED banner.
- ⭐ Re-pointed 4 track-record hero surface entries → clean no-ops. **DRY-RUN CAUGHT A LANDMINE:** 2 `block` entries (trackrecordv2-perf-table, landingv2-perf-table) held STALE 5y-window markup → would REVERT live tables on --apply. DISABLED them (→manual). Propagator now SAFE (0 block auto-changes).
- NOTE: SSOT fix is on MAIN only; research branch still shows pre-fix docs (expected — don't re-apply there).

**PHASE 3 AUDIT LIST (12 surface-map "no match" — review stale-vs-already-fixed):** LandingPageV2.jsx (FAQ/pricing), social-launch-cards-v2.html (5 cards), email_service.py (welcome×2/onboarding/pricing), Blog2022StoryPage.jsx, BlogIndexPage.jsx + rebuild the 2 disabled perf-table block templates.

**PRODUCT (decided):** RISK DIAL = 3 discrete detents (Preserver=$250k+ fit, Core=t30v live, Maximizer++=breakout+vol-scaling). Landing copy draft `design/documents/landing-copy-3tier.md` (untracked). Full 3-tier "as if live" + productionize Preserver first.

**PHASES:** 0 ✅ → 1 validate Preserver/Maximizer++ vintages → 2 productionize Preserver → 3 roll 3-tier + clear 12 misses. Memories: [[feedback_survivorship_free_not_marketing]], [[project_secret_dossier]], [[project_newsletter_exit_stops_topic]].
