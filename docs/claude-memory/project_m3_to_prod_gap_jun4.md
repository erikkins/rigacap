---
name: m3-to-production-gap-is-only-the-volatility-basket-verified-jun-4-2026
description: "Erik decided M3 = new prod. Verified in code: prod model portfolio already runs M3's base (ensemble entry, 12% flat trail, 6x15%, regime, CB). The ONLY missing piece to make prod=M3 is the Volatility Basket overlay. t10/s8 is in NEITHER prod nor M3. Registry \"T3\" canonical numbers do NOT match production."
metadata: 
  node_type: memory
  type: project
  originSessionId: daad830f-fb74-43b7-b3d5-fc34eed698de
---

**Date:** Jun 4 2026. Erik's call: "we want M3 to be the new prod...it's what gave us 50% ann in the last 2 years."

**M3 = current production ensemble + Volatility Basket overlay.** Verified by reading the real subscriber-facing path (`model_portfolio_service.process_entries` + exits), NOT just `scanner.scan()`.

**What production model portfolio ALREADY does (matches M3 base):**
- Entry: reads fresh ensemble signals from dashboard cache, sorts by `ensemble_score`, fills up to MAX_POSITIONS slots (`process_entries`, model_portfolio_service.py:143). Full DWAP+momentum ensemble IS live (persisted fields momentum_rank/score/short/long confirm).
- Sizing: 15% of current cash (`POSITION_SIZE_PCT`). Max 6 positions.
- Exit: 12% flat trailing stop (EOD-gated; intraday fires disabled May 3) + regime exit + biweekly rebalance (WF) / no-force (live).
- Circuit Breaker live (`circuit_breaker_state.is_paused`, honored in process_entries).

**What's MISSING for M3 (the only port needed):**
- **Volatility Basket overlay** — VIX>30 cross-up → buy 7 mega-caps (NVDA TSLA AAPL MSFT AMZN GOOGL META) @ 10% cash each, 8% own trail, parallel (doesn't count vs max_positions), survives regime cash. Backtester reference impl exists as `cb_pause_basket_*` with `cb_pause_basket_vix_trigger` (backtester.py ~396-415, 1886-1958). Zero in prod.

**t10/s8 (DD-conditional trail tighten) is in NEITHER:** not in prod model_portfolio_service, and NOT part of M3's tested config (M3 base trail = 12% flat). So the registry's "T3 t10/s8 52-Monday" canonical (23.4%/1.00/26.4%) does NOT describe production OR M3 — registry is stale, needs rewrite to M3 vintage. See [[project_numbers_citations_registry]].

**Therefore "M3 = new prod" = "ship the Volatility Basket to prod"** — which was already the Jun 4 locked plan (VB ship this week, see [[project_surface_decisions_jun4]]). Not a strategy rebuild.

**Caveat — pre-existing displacement gap still applies:** `process_entries` only fills vacancies (slots = MAX_POSITIONS - open_count), so the [[project_wf_prod_displacement_gap]] still affects M3 realizability. Separate known issue, not introduced by M3.

**Parity-locked sequence (the rule is sacrosanct — see [[feedback_wf_prod_parity]]):**
1. Build + ship VB to prod (model_portfolio_service basket entry/exit + scheduler VIX-cross detection + ModelPosition basket flag + UI). Migration-first if schema change.
2. Parity-validate: prod basket behavior == backtester M3.
3. THEN flip marketing to M3 numbers (19.3%/33.6%/50.2%) in lockstep. Not before.

Marketing numbers + hero treatment: [[project_m3_distribution_breakthrough]]. Stale-surface list: [[project_stale_numbers_audit_jun4]].
