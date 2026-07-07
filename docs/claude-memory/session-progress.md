---
name: session-progress
description: "Live session snapshot (auto-checkpointed ~15min) — what's done, in flight, and next"
metadata:
  node_type: memory
  type: project
  originSessionId: 2dce3134-d861-45c4-a371-80378750f8c0
---

# Session snapshot — Jul 7 2026 (EOD) — Preserver shadow LIVE, parity bug fixed, Stripe add-on done, Maximizer port IN PROGRESS

Full state: [[project_preserver_2tier_phase2]]. Brand: claret+paper only ([[feedback_brand_claret_paper]]). Names LOCKED: Preserver/Core/Maximizer (t30v + Maximizer++ = internal).

## ✅ SHIPPED TODAY (main, deployed, verified)
1. **Preserver shadow LIVE** — migration+deploy+`PRESERVER_SHADOW=true`. Records at Jul 8 4pm scan (verify: `🕯️ Preserver shadow:` log + 1 row each preserver_signals/preserver_book_snapshots).
2. **Dashboard sell-ribbon PARITY BUG fixed** (1bf75b9) — was 12% trail vs live 30%; now dashboard==email==model. [[project_sell_alert_parity_bug_jul7]]. DEFERRED: rollup sell-email + 12% fallbacks signals.py:839/848/1123.
3. **Stripe Maximizer add-on COMPLETE** (4ba4297) — has_maxpp_addon col, checkout add-on line item, webhook detect, env vars SET + smoke-tested (FOUNDING $79/STANDARD $100/ANNUAL $1000, LIVE, interval-compatible).

## ⏳ MAXIMIZER SHADOW ROLLOUT — code deployed, ENV FLAG PENDING (Jul 7 late EOD)
- Full shadow port BUILT + committed (bfb32a4) + merged→main (5cadc41), **CI/CD deploying (run 28901519178, watch bnqkbzsjd)**. Migration APPLIED to prod + verified (maximizer_signals + maximizer_book_snapshots, 17 cols). run_shadow_day REAL-DB dry-run PASSED (rotating_bull→breakout confirmed, idempotent, cleaned up).
- **⏭️ NEXT (once deploy Active):** SAFE boto3 RMW to set `MAXIMIZER_SHADOW=true` on worker. Then BOTH shadows record at Jul 8 4pm scan → verify `🚀 Maximizer shadow:` + `🕯️ Preserver shadow:` logs + 1 row each in maximizer_*/preserver_* tables. Rollback = unset env.
- vol-brake = ENTRY-TIME exposure scale (held-book approx of research return-stream brake; faithful-in-range). eq_hist serialized for brake continuity. Sleeves N=15, Core=20.
- OPTIONAL confirmatory: full routed maxpp numbers ~49%/1.94/-17% (component-proofs already establish fidelity: detector signal-exact + replay penny-exact + vol_scale/route verbatim).

## (superseded above) MAXIMIZER PORT — earlier notes
- Maximizer = Preserver routing EXCEPT **rotating_bull→breakout (vol-scaled)** instead of t30v. calm→pullback, capitulation→oversold, range_bound→Core t30v (all shared w/ Preserver).
- **EXIT RULES (Erik asked):** sleeves = TIME-STOP (hold-day): breakout 29d, pullback 40d, oversold 11d. ONLY Core/t30v leg uses 30% trailing stop. Sleeve display/alerts must show "exits in X days" NOT a trail (future parity care).
- BUILT + VALIDATED: `maximizer_sleeves.py` (breakout detector **signal-parity EXACT** 4232=4232, 0 mismatch; +vol_scale Barroso target=0.20; +route), `maximizer_signal_service.py`, `maximizer_portfolio.py` (replay **mechanics PENNY-EXACT** vs research simulate, 0.000000). NOT committed yet.
- **POS COUNTS (Erik confirmed):** Core t30v=20×4.5% (prod). Research SLEEVES=N_POS=15 (shape_tpe:55). Book runs sleeves@15 (validated), Core leg@20 (live model). Keep sleeves@15 unless deliberate re-validation.
- **NEXT Maximizer:** confirm full routed numbers land ~49%/1.94/-17% (needs slow pitfwu_wf.run t30v_daily; timed out at 2min — run w/ 300s+); then MaximizerBook + maximizer shadow tables + hook + migrate + deploy + flag (mirror Preserver Phase 2). Then commit offline batch.

## 📣 QUEUED (Erik, after Maximizer deploy) — MARKETING/DOCS
1. **Journey doc** for his father — DWAP+12%-stops → now; timeline of decision points refuting previously-accepted ideas.
2. **Sales doc** — how to sell to different personas (for onboarding a salesperson).
3. Update Signal Intelligence doc + investor doc (+maybe others) — NON-critical.
4. **Entire marketing story overhaul + website HERO** — "woefully off for the superpowers we've unleashed." Real business urgency.
- Erik OPEN to pivoting to marketing NOW vs finishing Maximizer shadow first — AWAITING his call.
