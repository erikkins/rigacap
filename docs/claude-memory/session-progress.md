---
name: session-progress
description: "Live session snapshot (auto-checkpointed ~15min) — what's done, in flight, and next"
metadata: 
  node_type: memory
  type: project
  originSessionId: 2dce3134-d861-45c4-a371-80378750f8c0
---

# Session snapshot — Jul 7 2026 (Tue) — 2-TIER LAUNCH PROGRAM kicked off (waitlist-first)

**Full product/Phase-2 state:** [[project_preserver_2tier_phase2]]. Brand rule: [[feedback_brand_claret_paper]] (claret+paper ONLY, never navy/gold).

**⭐ LAUNCH DECISIONS LOCKED (Erik):** (1) WAITLIST-FIRST — market live t30v recent numbers now + waitlist, build in parallel, flip tiers live when Phase 2 shadow-validates. (2) Pricing: Base Preserver unchanged $129/$59-founding/$1099; Maximizer++ = paid ADD-ON **+$100/mo → $229** (founding +$79, annual +$1000→~$2099). (3) SEGMENT BOTH audiences.

**⭐ WAITLIST DURATION (just discussed):** gate launch on shadow validation NOT calendar. ~4 WEEKS realistic. KEY nuance: short live shadow only exercises t30v-passthrough (~70% rotating_bull); rare sleeve regimes (calm_bull ~5%, capitulation ~10-15%) may not occur — BUT sleeve paths already penny-exact validated OFFLINE (10+yr history), so live shadow just confirms PIPELINE runs clean (~1-2wk), not wait-for-rare-regime. Plan: wk0 migration+deploy shadow, wk1-2 confirm pipeline+build demand+read tier-split, wk3 soft-launch to founders, wk4 fire. Keep ≤4wk so demand doesn't stale. Asked Erik: bake 4wk/validation-gated timeline into plan + build waitlist mechanics next.

**DOCS DELIVERED:** `design/documents/2tier-launch-plan.md` (spec+checklist), `2tier-social-marketing-strategy.md` (segment-both: Preserver=$250k+/advisers/LinkedIn; Maximizer++=aggressive-growth/X/YouTube; honest-gate what-to-say-now-vs-later). Product overview `rigacap-2tier-product-overview.{html,png,pdf}` (claret/paper) delivered earlier.

**⚠️ ERIK'S ACTION:** create Stripe "Maximizer++ Add-on" product w/ 3 Prices ($100/mo, $79/mo founding, $1000/yr) → give IDs. THEN I wire: config env vars STRIPE_PRICE_ID_MAXPP_*, checkout add-on line item, has_maxpp_addon entitlement col (MIGRATION-FIRST), portal toggle, gating. Billing trace: config.py:44-47 price IDs, billing.py:80 create_checkout_session, database.py:725 Subscription.stripe_price_id.

**PARALLEL BUILDABLE-NOW (no billing risk):** waitlist mechanics (landing CTAs + tier-tag endpoint), 2-tier landing update (claret/paper), social cards rebuild. Track A (product) still gated on rule-B ✅ + migration. Memories: [[project_secret_dossier]], [[feedback_survivorship_free_not_marketing]], [[project_newsletter_exit_stops_topic]].
