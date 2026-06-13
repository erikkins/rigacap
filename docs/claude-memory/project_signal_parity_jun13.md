---
name: project-signal-parity-jun13
description: Jun 13 2026 — achieved 100% prod-vs-t30v-backtest parity. Found+fixed 6 divergences incl. universe SIZE drift (200 vs 100). Live record re-dated Jun 14; first real entries Mon Jun 15 scan. THE config + entry-path reference.
metadata: 
  node_type: memory
  type: project
  originSessionId: 701a2e93-33c0-4e85-a7bc-2cb9d9956d94
---

# Signal Pipeline Parity — 100% prod == t30v bench (Jun 13 2026)

**Trigger:** the daily digest showed "2 picks" (VZ/BAC) under a "zero signals" briefing. Investigation found the live entry path had NEVER matched the validated t30v backtester. The "Day 1/2 = disciplined cash" (Jun 11-12) was a BUG, not selectivity — the book should have held a small confirmed set.

## The 6 divergences (all fixed, verified 3 ways: logic 7/7 vs CustomBacktester, runtime, config audit 0 gaps)
1. **Cache-zero (Bug 1):** dashboard ran a SECOND `scanner_service.scan()` after the pickle-export step → 0 buy_signals (Jun 11-12). Fixed by removing the 2nd scan entirely (see #5). Plus a symptom guard in main.py (`_run_daily_scan`): re-run + admin-alert if 0 buys while raw scan healthy + friendly regime.
2. **Missing near-high quality filter:** live entries ignored Factor-3 (within-3%-of-50d-high). Added `passes_quality` gate in compute_shared_dashboard_data.
3. **Wrong ranking:** sorted by `ensemble_score` (compute_signal_strength, a 0-100 display heuristic, r=0.083) instead of momentum composite. Fixed in BOTH compute_shared_dashboard_data AND model_portfolio_service.process_entries (sort by `momentum_score`). `ensemble_score`/`is_fresh` are DISPLAY-ONLY now.
4. **Universe pollution:** `get_top_liquid_symbols` (strategy_analyzer.py) ranked by share-volume with NO ETF exclusion + NO min-price floor → 39% penny stocks (ADTX $0.01, NIO, SNAP…) displaced legit large-caps (META/CRM/UBER/KO/TSM). Fixed to mirror `_get_top_symbols_as_of`: exclude `_EXCLUDED_SET` + `^`-prefix + MIN_PRICE floor at selection.
5. **DWAP boundary (KVUE, Erik's "ONE SOURCE"):** dashboard intersected `scan()` ∩ momentum-ranking — two DWAP computations that disagreed at the 5% line (KVUE 5.29%: backtester in, scan out). Fixed by building buy_signals from the momentum ranking + DWAP read DIRECTLY from the cache indicator (`row.get('dwap')`), exactly as the backtester does. Removes scan() entirely → also kills Bug 1's second scan. rank_stocks_momentum keeps the same SPY<200MA market filter, so regime exit preserved.
6. **UNIVERSE SIZE drift (the dangler):** prod env `SIGNAL_UNIVERSE_SIZE=200` but the t30v canon used `uni_n=100`. 200 → 28 signals; 100 → the bench's 7. Fixed env on BOTH lambdas (worker+api) to 100 via SAFE full-merge (never `--environment` replace). Backups at /private/tmp/env_backup_*.json.

## ⭐ LESSON: code parity ≠ runtime parity (Erik asked "how did we miss pool size")
Every local parity test hardcoded `SIGNAL_UNIVERSE_SIZE=100` to match the bench — masking that PROD ran 200. I validated the LOGIC at the known-good config, not the DEPLOYED config. **Parity testing MUST diff prod's actual runtime config (env + DB params + settings) against the bench, not assume it.** Erik's instinct to re-run on REAL prod (not local replication) is what caught it — prod runs its true config; local runs your assumptions.

## Verified config (audit clean, 0 gaps) — prod effective == t30v bench
universe=100 · dwap_threshold=5.0 · near_50d_high=3.0 · min_price=15 · min_vol=500k · mom_days=5/60 · **mom_weights=0.3/0.2/0.15** (in settings — NOT the old 0.5/0.3/0.2 v2 defaults; this is why composite scores match) · market_filter=on · max_pos=20 · pos_size=4.5% · trail=30%. NOTE: settings DEFAULTS for max_pos(6)/pos_size(15)/trail(12)/near_high are STALE but OVERRIDDEN by the strategy_adaptive_params t30v_cutover row — that row is load-bearing.

## Live record
- **Re-dated to Jun 14** (Jun 11 "Day 1" was the bugged zero — don't count it). Book = clean $100k cash (reset after smoke).
- **Entry path SMOKED (passed):** `{"model_portfolio":{"action":"process_entries","portfolio_type":"live"}}` entered 7 positions, vol-weighted, ~$24k deployed/$76k cash — correct selective behavior. Then reset (`action:reset`).
- **First REAL entries = Monday Jun 15 4:30 scan** on live data (first full-pipeline run of the entry path — WATCH IT).
- Jun 12 parity entry set (reference): SNDK, WULF, BAC, KEY, KO, KVUE, VZ.

## Signal presentation (Erik decision Jun 13): lead with $ amount, not # shares
% weight = canonical instruction; **$ amount = primary actionable** (stable vs intraday ticks, most brokers take dollar orders, sidesteps "0.7 shares of $1980 SNDK"); # shares = small "≈ X at $Y" helper. Set portfolio size once → system does the math. Fractional shares in the MODEL are CORRECT (matches backtest; rounding would break parity). For the dashboard-actionability pass.

## SNDK: real, not a data artifact — $293B cap near $1980 (3 sources confirm). High-momentum, legit.
