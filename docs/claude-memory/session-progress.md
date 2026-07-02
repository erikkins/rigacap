---
name: session-progress
description: "Live session snapshot (auto-checkpointed ~15min) — what's done, in flight, and next"
metadata: 
  node_type: memory
  type: project
  originSessionId: 2dce3134-d861-45c4-a371-80378750f8c0
---

# Session snapshot — Jul 2 2026 (Thu) — Phase 1 tier vintages: validated first cut

**Context:** 3-tier product (Preserver/Core-t30v/Maximizer++) from regime-adaptive engine. On branch `research/shape-diversifiers-regime-allocator`. SSOT fix + surface-map fix on MAIN (b2b8624, Phase 0 done). 12-miss audit: 11/12 already-fixed (live surfaces honest); only stale = social-launch-cards-v2.html (superseded brand asset). Surface-map polish DEFERRED to Phase 3 (rebuilt then anyway).

**⭐ PHASE 1 FIRST CUT DONE (scripts/tier_vintages.py, 2009-2026 continuous EXT, biweekly):**
| tier | Ann | Sharpe | MaxDD(biwk) |
| Core t30v [SANITY] | 9.2% | 0.74 | -19.5% |
| Preserver (v1) | 11.2% | 0.93 | -16.2% |
| Maximizer++ (v2 vol-sc) | 15.7% | 1.04 | -17.0% |
- **SANITY PASSED:** Core 9.2/0.74/-19.5 ≈ canonical 8.3/0.73/19 (Sharpe+DD near-exact; +1pp ann = 2009-vs-2007 start + EXT surv-bias) → methodology validated, tiers trustworthy.
- **KEY FINDING: Preserver DOMINATES plain t30v over 17y** (higher return, higher Sharpe, LOWER DD) → productionizing it = UPGRADING Core, not just adding a tier.
- Maximizer++ tops return (15.7/1.04), vol-scaling brake holds it.

**CAVEATS before publishable:** (1) MaxDD is BIWEEKLY = understates; Maximizer++ true DAILY DD ~-25% (2021 momentum crash is a daily event); Preserver/Core less affected. (2) pre-2016 EXT surv-biased (~1pp lift). (3) 2009 start not 2007.

**NEXT (asked Erik):** (a) run daily-DD + recent-window (last-2yr per tier) pass for SHIPPABLE numbers, OR (b) proceed to Phase 2 productionize Preserver (the validated cut may be enough). Phases: 0✅ → 1 (this) → 2 productionize Preserver → 3 roll 3-tier. Landing copy draft `design/documents/landing-copy-3tier.md`. Product=RISK DIAL 3 detents, Preserver=$250k+ fit. Memories: [[feedback_survivorship_free_not_marketing]], [[project_secret_dossier]], [[project_newsletter_exit_stops_topic]].
