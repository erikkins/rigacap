---
name: vb-ablation-verified-research-artifact-location-jun-4-2026
description: "Clean base-vs-M3 ablation proves Volatility Basket is the dominant alpha (+14.6pp ann, improves MDD) on 2019-21 COVID windows. Backtester entry is vacancy-only (no displacement) = matches prod. Recent-2y 50.2% run is NOT preserved. Research artifacts live in ~/rigacap-research/sweeps."
metadata: 
  node_type: memory
  type: project
  originSessionId: daad830f-fb74-43b7-b3d5-fc34eed698de
---

**Date:** Jun 4 2026. Triggered by Erik pressure-testing the M3 numbers before committing to productionize + remarket.

**Research artifacts live in `~/rigacap-research/`** (NOT /tmp — /tmp clears on reboot). `sweeps/<tier>_<variant>_<datestamp>/` each holds `MANIFEST.json` (full config) + `summary.csv` (per-window) + per-date `result.json`. Runner scripts in `~/rigacap-research/scripts/*.sh` invoke the prod worker `native_backtest` handler via Lambda (true runtime parity). Dates in `~/rigacap-research/dates/`. See [[feedback_never_keep_paid_work_in_memory]].

**VB clean ablation (Tier 1, 26 windows, 2019-06→2021, all span COVID VIX spike):**
M3 = BASELINE_v3 + ONLY `cb_pause_basket_enabled` flipped true. Byte-identical otherwise. Both `dd_tighten=0` (no t10/s8).

| | ann | sharpe | mdd | calmar | trades |
|---|---|---|---|---|---|
| BASE (no VB) | 19.0% | 0.76 | 25.1% | 0.79 | 62 |
| M3 (base+VB) | 33.6% | 1.23 | 22.2% | 1.53 | 85 |
| **VB effect** | **+14.6pp** | **+0.47** | **−2.9pp (better)** | **+0.74** | +23 |

**VB STRICTLY DOMINATES here** — more return AND lower drawdown. BUT these are TUNING windows that ALL contain the March-2020 COVID VIX>80 spike + historic mega-cap recovery — the single most favorable scenario for "VIX>30 → buy mega-caps." This is the UPPER bound of VB value, not typical. Held-out Tier 2 (2022-2026) lift is smaller (memory ~base 13.6 vs M3 19.3, ≈+5.7pp).

**Backtester entry = vacancy-only, no displacement (backtester.py:2178 `if len(positions) < max_positions`, :2215 break when full).** Carries incumbents, exits on trail/regime only. This MATCHES prod `process_entries`. So the [[project_wf_prod_displacement_gap]] (a multi-period WF-service force-close artifact) does NOT apply to these single-window M3 backtests — M3's entry behavior is prod-realizable. Corrects my earlier over-worry.

**GAP: the recent-2y 50.2% headline run (2024-06→2026-05) is NOT preserved** — no saved sweep has a 2024+ window start. Cannot read VB fire count / basket P&L from disk. MUST re-run M3-vs-base on 2024-06→2026-05 to (a) count VIX>30 fires, (b) get basket trade P&L, (c) isolate whether 50.2% is VB- or base-driven. Domain-knowledge candidate fire: Aug 2024 yen-carry VIX spike (UNVERIFIED).

**Recent-2y ablation (2024-06-03→2026-05-29, Lambda, reproduced 50.21% exactly):**
| | ann | sharpe | mdd | calmar |
|---|---|---|---|---|
| BASE alone | 36.26 | 1.84 | **12.16** | 2.98 |
| M3 (base+VB) | 50.21 | 2.22 | 17.69 | 2.84 |
VB recent effect: **+13.95pp ann, +0.38 sharpe, but +5.53pp WORSE MDD.** BOTH pass 4/4 v2 — but **base-alone is the CLEANER pass** (lower MDD, higher Calmar). VB breaks the MDD budget in non-COVID windows.

**Per-fire breakdown (local trade-logged run, force_close_at_end):** VB fired **5×** in recent 2y (08-05-2024 yen carry; 04-03-2025 + 04-21-2025 tariff crash; 11-13-2025; 03-27-2026). Total basket P&L +$29.3k on $100k. **88% ($25.8k) came from ONE event — the April 2025 tariff-crash recovery** (4/21 fire was 6/6 winners: NVDA+72 META+48 TSLA+46 MSFT+38 AMZN+28). Other 3 fires ~+$3.5k combined. VB = a single "buy-the-best-when-VIX>30" bet that grand-slams on sharp V-bottoms, costs −8% stops otherwise. Lumpy, rare, regime-dependent.

**PRODUCT DECISION DIRECTION (Erik, Jun 4):** Reframe VB from "bake into core" → **separate opt-in premium "Volatility Basket" ADD-ON.** Rationale: (1) base-alone is the cleaner/honest 4/4 core (keep marketed core numbers at 36/1.84/12 MDD, conservative); (2) VB's lumpiness is BAD for a core track record but GREAT for an upsell (sell the April-2025 hero story); (3) "VIX>30 → buy 7 best mega-caps, ride the bounce" is a one-sentence pitch. Two-tier product: conservative core + aggressive VB turbocharger w/ own risk disclosure. SUPERSEDES the [[project_surface_decisions_jun4]] "ship VB into prod strategy" framing.

**CORRECTED product read (later Jun 4):** base-alone is NOT a clean core. Base-alone bear-inclusive validation (2022-01→2026-05) = **12.53% / 0.85 / 16.59 / 0.76 — FAILS 3/4** (only MDD). Base is clean 4/4 ONLY in the recent bull 2y (36.26/1.84/12.16/2.98). Through the honest bear-inclusive stress test base is mediocre. VB helps BROADLY: lifts ann + Sharpe in every window, and on bear-inclusive drags Sharpe 0.85→1.09. So M3 (base+VB) is the genuinely better flagship; its only blemish is bear-inclusive MDD 21.5 (1.5pp over 20% target — Erik: "21-22 isn't that bad").

**VB-ALONE is a FAIR-WEATHER TRAP (verified Jun 4):** standalone basket (max_positions=0, basket on):
| window | ann | sharpe | mdd | calmar |
|---|---|---|---|---|
| recent 2y | 28.3 | 2.38 | **6.4** | 4.46 (4/4 ✅) |
| bear-incl | **4.4** | 0.41 | **30.0** | 0.15 (0/4 ❌) |
Recent looks amazing but is April-2025 recovery luck. Through 2022 grinding bear VIX>30 fired repeatedly, basket bought mega-caps that kept falling → −8% stop whipsaw cluster → **30% MDD**. Standalone is the RISKIEST version (no base book to dilute bad fires) — worse than base (17) or M3 (22). Marketing VB-alone on the 28% would be a textbook cherry-pick.

**PRODUCT DECISION (Erik, Jun 4 — supersedes the add-on framing):** Don't nickel-and-dime full users — basket INCLUDED in full Momentum Strategy (M3). Erik floated a cheaper "lite" tier = VB-alone, but data says NO (fair-weather 30% bear MDD; would hand least-risk-tolerant users the riskiest product). Recommendation on the table: ONE clean product = full Momentum Strategy (basket included, ~21% MDD acceptable). If a cheap tier is still wanted, make it a LIMITED version of the full strategy (delayed signals / top-3 positions), NOT the standalone basket. Awaiting Erik's call.

**Net:** VB is excellent AS AN OVERLAY (base book tames it), dangerous STANDALONE. M3 = the flagship. Supersedes both the wrong "+5.7pp / worsens MDD everywhere" claim AND the "base is the clean core / VB is premium add-on" framing.
