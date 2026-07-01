---
name: session-progress
description: "Live session snapshot (auto-checkpointed ~15min) — what's done, in flight, and next"
metadata: 
  node_type: memory
  type: project
  originSessionId: 2dce3134-d861-45c4-a371-80378750f8c0
---

# Session snapshot — Jul 1 2026 (Wed) — Phase 0 SSOT audit: live site OK, SSOT files STALE

**Context:** 3-tier product (Preserver/Core-t30v/Maximizer++) from regime-adaptive engine. Research committed (branch `research/shape-diversifiers-regime-allocator`, 6e29f21, not merged/pushed). Landing copy drafted `design/documents/landing-copy-3tier.md`. Product = RISK DIAL, 3 discrete detents (signals feeds), Preserver=$250k+ fit. Erik chose: full 3-tier copy as-if-live + productionize Preserver first.

**⭐ PHASE 0 AUDIT DONE — precise diagnosis of the stale-SSOT problem:**
- **LIVE site `/track-record` (frontend/src/TrackRecordPageV2.jsx) is HONEST + coherent** = 21-YEAR CONTINUOUS CANON: **8.3% ann / 0.73 Sharpe / 19% MaxDD** (2007-26) + last-24mo +32%/2.20/8.5%DD + comparisons (raw-mom-net 13.2%/0.69/57%, SPY 9.8%/55%). Set Jun-10. Site is NOT broken.
- **`docs/canonical_numbers.json` (the SSOT file) is STALE** = Apr-28 5-yr-window lens (21.1% ann/0.92/20.4% MDD, +160% avg). Never updated when site moved to 21y canon Jun-10.
- **`docs/numbers-citations-registry.md` STALE** = May-27 T3 t10/s8 (23.4%/1.00/**26.4%**) — THIS is where my wrong -26% came from.
- So the FILE lies, the SITE is right (lens divergence: 5y-window vs 21y-continuous).
- **🔴 DANGER: do NOT run `scripts/refresh_perf_citations.py --apply`** — its canonical input is the stale file → would OVERWRITE the live honest 8.3%/19% with stale 21.1%/20.4% = regression. Surface-map find-patterns ALSO stale (target retired +204%/+86%/32%, not on page anymore). `scripts/perf_citations_surface_map.json` maps surfaces (TrackRecordPageV2.jsx = RECENT_ROWS/FOUNDATION_ROWS).

**NEXT — waiting on Erik's confirm:** he needs to confirm the 21-yr-continuous lens (8.3%/0.73/19%) is THE canonical (site already reflects it). THEN: (1) rewrite canonical_numbers.json to match live site + retire 5y-window & T3 vintages to log; (2) update registry to same; (3) re-point surface-map find-patterns to current TrackRecordPageV2 structure; (4) THEN propagator safe. AFTER Phase 0: Phase 1 validate tier vintages → Phase 2 productionize Preserver → Phase 3 roll 3-tier across surfaces.

**Memories:** [[feedback_survivorship_free_not_marketing]], [[project_secret_dossier]], [[project_newsletter_exit_stops_topic]].
