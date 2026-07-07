---
name: session-progress
description: "Live session snapshot (auto-checkpointed ~15min) — what's done, in flight, and next"
metadata:
  node_type: memory
  type: project
  originSessionId: 2dce3134-d861-45c4-a371-80378750f8c0
---

# Session snapshot — Jul 7 2026 (late) — BOTH shadows LIVE, parity fixed, Stripe done; now on MARKETING DOCS

Full state: [[project_preserver_2tier_phase2]]. Brand: claret/paper ([[feedback_brand_claret_paper]]) — BUT for PRINTABLES use WHITE bg (paper wastes ink), claret OK as light accent. Names LOCKED: Preserver/Core/Maximizer.

## ✅ SHIPPED TODAY (all deployed + verified)
1. **Preserver shadow LIVE** (PRESERVER_SHADOW=true) + **Maximizer shadow LIVE** (MAXIMIZER_SHADOW=true). BOTH record at Jul 8 4pm scan → verify `🕯️ Preserver shadow:` + `🚀 Maximizer shadow:` logs + 1 row each preserver_*/maximizer_* tables. ~1wk validate → tier serving. Rollback=unset env.
2. Maximizer port (main 5cadc41): breakout detector signal-parity EXACT, replay mechanics PENNY-EXACT, MaximizerBook (rule B + entry-time vol-brake, eq_hist serialized). Migration applied+verified, real-DB dry-run passed. Sleeves=time-stops (breakout29/pullback40/oversold11), Core=30%trail@20pos; sleeves@15.
3. **Dashboard sell-ribbon PARITY BUG fixed** (1bf75b9) — 12%→live 30% trail. [[project_sell_alert_parity_bug_jul7]]. DEFERRED: rollup sell-email + 12% fallbacks signals.py:839/848/1123.
4. **Stripe Maximizer add-on COMPLETE** — has_maxpp_addon col, checkout+webhook, env vars set + smoke-tested (LIVE prices $79/$100/$1000).

## 🖊️ NOW — MARKETING/DOCS queue (Erik pivoted here)
1. ✅ **Journey doc DELIVERED** — `design/documents/rigacap-journey.{html,pdf}` (5pg, white bg, light claret, Fraunces/Plex). Myth-busting timeline: DWAP→today via "accepted idea→what data showed→what we did" (8 milestones: tight-stops/concentration/reckoning/honest-lag/regimes/vol-brake). Numbers = honest canon, no recipe leak. AWAITING Erik feedback: dedication line? tighten 5pg→3? bolder timeline dots?
2. **Sales doc** — sell to personas (salesperson onboarding). NEXT.
3. Update Signal Intelligence doc + investor doc (non-critical).
4. **Marketing story overhaul + website HERO** ("woefully off for the superpowers"). Big business urgency.

Branch: research/shape-diversifiers-regime-allocator (merged to main 5×; checked out). PDF gen: headless Chrome --print-to-pdf.
