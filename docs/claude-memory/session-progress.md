---
name: session-progress
description: "Live session snapshot (auto-checkpointed ~15min) — what's done, in flight, and next"
metadata: 
  node_type: memory
  type: project
  originSessionId: 2dce3134-d861-45c4-a371-80378750f8c0
---

# Session snapshot — Jul 1 2026 (Wed) — RESEARCH COMMITTED + 3-tier marketing + SSOT is STALE

**Context:** Shapes research → 3-tier product (Preserver/Core-t30v/Maximizer++) from one regime-adaptive engine. Erik intermittent/remote.

**✅ COMMITTED:** branch `research/shape-diversifiers-regime-allocator` commit **6e29f21** (177 files: shape_tpe/regime_allocator*/momentum_crash_proxy*/shape_lab/etc + framing doc + additive-inert backtester equity_curve + legacy/sql). NOT merged to main, NOT pushed. t30v sole live strategy.

**✅ RESEARCH RESULT (recap):** 7-regime allocator beats t30v (validated cross-half/EXT/daily-DD/walk-forward). Breakout@rotating_bull = +30% but -33% (momentum-crash, IRREDUCIBLE by market-regime flag — it's a FACTOR crash). TAMED via factor-vol scaling (Barroso), hardened w/ INDEPENDENT long-only momentum proxy (TOPD works; WML fails). Maximizer++ ≈ 25%/-25%/Sharpe1.28.

**PRODUCT MODEL decided (Erik):** RISK DIAL = 3 discrete detents (signals service → each tier = a clean signal feed; discrete beats continuous for execution/validation/behavior). CAN blend (tiers = points on breakout-weight continuum); expose 3 (maybe 5) validated detents; continuous blend = future ADVISER/managed feature. Switch allowed w/ friction (rotates holdings). Onboarding risk-quiz → recommend tier. **Preserver (~13% DD) is the ACTUAL fit for $250k+ (t30v's ~26%→really 19% was a mismatch).** Erik chose: FULL 3-tier copy "as if live" + PRODUCTIONIZE PRESERVER FIRST.

**✅ Landing copy drafted:** `design/documents/landing-copy-3tier.md` (risk-dial hero + 3 tiers + FAQ).

**⚠️⚠️ CRITICAL FINDING — SSOT IS STALE/WRONG (Erik caught it):** I cited t30v DD -26% from `docs/numbers-citations-registry.md` (May-27 vintage) but LIVE t30v = **~19%** (Erik confirmed; matches our research 17.6-18.5% + 21y canon). `docs/canonical_numbers.json` (Apr-28) says 20.4%, registry says 26.4% — they DISAGREE, and BOTH predate the Jun-10 t30v cutover. SSOT drifted out of sync w/ live product → live site may be citing stale numbers NOW.

**NEXT (proposed Phase 0, Erik to greenlight):** reconcile+refresh canonical_numbers.json + registry to LIVE t30v vintage, run `scripts/refresh_perf_citations.py --apply` to fix all surfaces. THEN Phase 1 (validate Preserver/Maximizer++ vintages), Phase 2 (productionize Preserver), Phase 3 (roll 3-tier across surfaces — full list in chat). Pending: [[project_secret_dossier]].

**UNCOMMITTED (safe):** landing-copy-3tier.md, framing doc edits (3-tier), momentum_crash_proxy_v2.py (committed? — v1 yes; v2 created after commit → verify). Memories: [[feedback_survivorship_free_not_marketing]], [[project_secret_dossier]], [[project_newsletter_exit_stops_topic]].
