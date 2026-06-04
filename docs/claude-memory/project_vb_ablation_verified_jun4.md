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

**Net:** VB is genuinely the dominant alpha, not a marginal tail-hedge — which RAISES the stakes on productionizing it correctly. But its value is conditional on a big VIX>30 spike + mega-cap recovery landing in-window; validate held-out + recent before marketing. Supersedes the wrong "+5.7pp / worsens MDD" claim I made mid-session.
