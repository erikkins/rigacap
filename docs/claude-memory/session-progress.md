---
name: session-progress
description: "Live session snapshot (auto-checkpointed ~15min) — what's done, in flight, and next"
metadata: 
  node_type: memory
  type: project
  originSessionId: 2dce3134-d861-45c4-a371-80378750f8c0
---

# Session snapshot — Jul 2 2026 (Thu) — Phase 2 Step 2 done (shadow signal builder validated)

**Context:** 2-TIER product (Base=Preserver / Maximizer++=paid add-on) from regime-adaptive engine. Branch `research/shape-diversifiers-regime-allocator`. Phase 0 (SSOT) on MAIN b2b8624. Phase 1 tier vintages done (daily shippable: Preserver last-2yr 31/1.75/-13, 2021-26 19/1.33/-13; Maxpp 49/1.94/-17, 36/1.61/-20). Framing doc + landing copy drafted.

**⭐ PHASE 2 PROGRESS (productionize Preserver — ALL ADDITIVE, nothing live touched):**
- Step1 ✅ `backend/app/services/preserver_sleeves.py` — prod port of pullback_ma+oversold_bounce detectors (frozen params) + route(regime). PARITY vs research = EXACT (0 mismatches).
- Step2 ✅ `backend/app/services/preserver_signal_service.py` — build_daily_signals(data_cache, regime, t30v_buy_signals, date): route→ t30v passthrough (rotating_bull/range_bound ~70%) OR sleeve (calm_bull→pullback, capitulation{panic/recovery/weak_bear}→oversold), ranked by $-vol top-N. Validated: routing correct all regimes; pullback generates books (strong/weak_bull 8/8, 1/2); t30v passthrough works.

**⭐ ARCHITECTURE FINDINGS (Explore trace):** `ensemble_signals` table has NO strategy_id (single-strategy); dashboard/process_entries single-strategy → CANNOT reuse; need PARALLEL table+builder. Reusable safe: scanner_service.data_cache (dict[sym,DataFrame] w/ FULL OHLCV+dwap/ma50/ma200), rank_stocks_momentum, market_regime_service. Pipeline: main.py:1151 _run_daily_scan → signals.py:774 compute_shared_dashboard_data (builds t30v buy_signals + regime) → ensemble_signal_service.persist_signals (main.py:1653).

**⭐ KEY INSIGHT:** sleeves fire RARELY (oversold ~35 signals/4.5yr) → Preserver is a HELD PORTFOLIO (entries carried `hold` days), NOT a daily signal feed. 0-signal capitulation days = normal (holds existing). → shadow VALIDATION must check accumulated PORTFOLIO equity vs research curve, not daily signals.

**NEXT (asked Erik):** build Preserver PORTFOLIO REPLAY (accumulate routed entries into held book, per-sleeve hold + t30v in dominant regime) + shadow-validate equity reproduces research Preserver curve. THEN storage table (migration-first) + daily-scan wiring. Phases: 0✅1✅2(in prog)3. Memories: [[feedback_survivorship_free_not_marketing]], [[project_secret_dossier]], [[project_newsletter_exit_stops_topic]].
