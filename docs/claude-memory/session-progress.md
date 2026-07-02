---
name: session-progress
description: "Live session snapshot (auto-checkpointed ~15min) — what's done, in flight, and next"
metadata: 
  node_type: memory
  type: project
  originSessionId: 2dce3134-d861-45c4-a371-80378750f8c0
---

# Session snapshot — Jul 2 2026 (Thu) — Phase 2 prod Preserver PORT PROVEN FAITHFUL (penny-exact)

**Context:** 2-TIER product (Base=Preserver / Maximizer++=paid add-on). Branch `research/shape-diversifiers-regime-allocator`. Phase 0 (SSOT) on MAIN b2b8624. Phase 1 daily tier vintages done (Preserver last-2yr 31/1.75/-13, 2021-26 19/1.33/-13). Framing doc = 2-tier + pricing.

**⭐⭐ PHASE 2 PORT PROVEN FAITHFUL — 3 new ADDITIVE files under backend/app/services/ (NOTHING live touched):**
- `preserver_sleeves.py` — detectors (pullback_ma/oversold_bounce, frozen params) + route(regime) + SLEEVE_FNS/SLEEVE_HOLD. Signal parity vs research = EXACT (0 mismatches).
- `preserver_signal_service.py` — build_daily_signals(): route→ t30v passthrough (rotating/range ~70%) OR sleeve (calm_bull→pullback, capitulation{panic/recovery/weak_bear}→oversold), $-vol top-N. Routing validated.
- `preserver_portfolio.py` — replay_sleeve() position-level sim. Reproduces research shapes_portfolio.simulate **TO THE PENNY (maxAbsDiff=0.0000)** for both sleeves over 2016-20.
- **CONCLUSION: wired to prod, Preserver WILL reproduce validated research numbers exactly. No drift.**

**KEY ARCH (from Explore trace):** ensemble_signals table has NO strategy_id (single-strategy) → need PARALLEL table+builder. Reusable-safe: scanner_service.data_cache (dict[sym,DataFrame] FULL OHLCV+dwap/ma50/ma200), rank_stocks_momentum, market_regime_service. Daily scan: main.py:1151 _run_daily_scan → signals.py:774 compute_shared_dashboard_data (t30v buy_signals + regime) → ensemble_signal_service.persist_signals (main.py:1653).

**⚠️ NEXT = FIRST LIVE-INFRA TOUCH (needs Erik sign-off before applying, per CLAUDE.md migration-first/off-hours):** (a) new storage table (migration-first) + (b) daily-scan SHADOW wiring (regime→route→run book→store, NOT served) + (c) DESIGN DECISION: regime book-transition rule (on regime flip, liquidate+rotate OR hold-t30v-till-exit+layer-sleeve?) — shapes the schema. Then tier field + tier-aware serving. Asked Erik: write up shadow-wiring+migration design for review, OR settle book-transition rule first.

**PHASES:** 0✅1✅ 2(port done, plumbing next) 3(roll copy). Memories: [[feedback_survivorship_free_not_marketing]], [[project_secret_dossier]], [[project_newsletter_exit_stops_topic]].
