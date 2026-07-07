---
name: session-progress
description: "Live session snapshot (auto-checkpointed ~15min) — what's done, in flight, and next"
metadata:
  node_type: memory
  type: project
  originSessionId: 2dce3134-d861-45c4-a371-80378750f8c0
---

# Session snapshot — Jul 7 2026 (EOD) — big shipping day: Preserver shadow LIVE, parity bug fixed, Stripe add-on done

Full state: [[project_preserver_2tier_phase2]]. Brand: [[feedback_brand_claret_paper]] (claret+paper only). Names LOCKED: Preserver/Core/Maximizer (t30v + Maximizer++ = internal only).

## ✅ SHIPPED TODAY (all on main, deployed, verified)
1. **Preserver shadow LIVE** — migration applied+verified, run_shadow_day real-DB dry-run passed, merged→main→deployed, `PRESERVER_SHADOW=true` set on worker (safe RMW). **Starts recording at Jul 8 4pm scan.** VERIFY tomorrow: `🕯️ Preserver shadow:` log + 1 row each in preserver_signals / preserver_book_snapshots. Rollback=unset env.
2. **Dashboard sell-ribbon PARITY BUG fixed** (commit 1bf75b9) — was hardcoded 12% trail vs live 30%; now reads regime_adjusted value → dashboard==email==model. Was pushing ALL subscribers into premature exits. Detail: [[project_sell_alert_parity_bug_jul7]]. STILL DEFERRED: rollup sell-email (Erik wants it) + harden 12% fallbacks signals.py:839/848/1123.
3. **Stripe Maximizer add-on COMPLETE** (commit 4ba4297) — has_maxpp_addon col (migration-first), checkout appends tier-matched add-on line item, webhook detects on created+updated, base-price anchored. Env vars SET on API+worker, SMOKE TEST PASSED (3 prices LIVE/active: FOUNDING $79/mo, STANDARD $100/mo, ANNUAL $1000/yr, interval-compatible). Backend done + inert until frontend sends maximizer=true.

## ⏭️ NEXT — Erik-approved order
1. ✅ Stripe env vars + smoke test — DONE.
2. **⭐ MAXIMIZER PRODUCTIONIZATION (critical path, the real blocker on charging for the tier)** — mirror the Preserver port: prod detectors for breakout sleeve + momentum-crash vol-brake (signal-exact vs research scripts/regime_allocator_v2.py BREAKOUT={buffer:0.014,vol_mult:1.38,mom_min:-0.005,hold:29} + Barroso vol-scaling), penny-exact replay, shadow tables, env-gated hook, ~1wk shadow. Erik offered to start now OR fresh next session (I recommended fresh — it's EOD + big). **AWAITING his pick.**
3. Frontend 2-tier UI + add-on toggle + landing-copy 2-tier rewrite (landing-copy-3tier.md still 3-tier). Full paid E2E checkout test comes with this.
4. Marketing/social in claret-paper; Stripe Portal add-on config (dashboard).

GATE: no tier performance claims / no tier charges until that tier produces LIVE signals. Preserver shadow (~1wk) + Maximizer port both gate their tiers going live. Branch: research/shape-diversifiers-regime-allocator (merged to main 3×; currently checked out).
