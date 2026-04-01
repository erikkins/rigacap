# AI TPE Optimizer Walk-Forward Results

## AI TPE v1 (2026-03-16, Job 184)
- **5-year WF (2021-02-01 → 2026-02-01), enable_ai=true, n_trials=30, carry_positions=true, max_symbols=100**
- Result: **+79.2%** return, **1.31 Sharpe**, **-11.3% max DD** vs SPY +91.2%
- Fixed-param benchmarks: +206% (job 148, 6×15% carry), +289% (jobs 113-116 compound)
- **TPE v1 verdict: FAILED on returns, good on risk.** Sharpe 1.31 > 0.87 fixed, drawdown -11.3% < -24.7% fixed. But massively underperformed on total return.
- **Root cause:** Optimizer switched once (Nov 2021) to ultra-conservative params (3 pos @ 11%, 9% stop) and never switched again across 130 periods. `min_score_diff=10.0` too high. Single-objective (Sharpe) on 60-day lookback inherently favors capital preservation.

## AI TPE v2 (2026-03-17)
- **V2 round 1 (jobs 188-190): FAILED.** Same single-switch problem as V1. Degenerate Pareto frontier, only 41-69 trades in 5 years.
- **V2 round 2 (jobs 191-193): SUCCESS.** Three critical fixes:
  1. Always re-optimize every period for V2
  2. Tightened param space (trailing stop min 10%, RSI filter 60-100, etc.)
  3. More trials (50 per period)

| Job | risk_pref | Return | Sharpe | Max DD | vs SPY (+91.2%) |
|-----|-----------|--------|--------|--------|-----------------|
| 191 | 0.2 (conservative) | **+226.2%** | **1.28** | -25.6% | +135pp |
| 192 | 0.5 (balanced) | **+72.7%** | 0.74 | -29.0% | -18.5pp |
| 193 | 0.8 (aggressive) | **+176.6%** | 1.03 | -28.2% | +85.4pp |

- **NOTE:** These results were pre-bug-fix (pre-7e5518e, pre-2cc461f, pre-8df8a10). Need to re-run with honest baseline to validate.
- **Key files:** `optuna_optimizer_v2.py`, `strategy_params_v2.py`, `walk_forward_service.py`
- **Lambda timeout:** `periods_limit=1` required for V2 AI sims.

## DWAP Crossover Age Analysis (2026-02-18, 698 trades)
- **Stale DWAP crosses perform BETTER, not worse.**
- Fresh (0-10d): 115 trades, 49.6% win, +0.07% avg
- Mid (11-60d): 275 trades, 50.5% win, +1.36% avg
- Stale (90+d): **206 trades, 56.8% win, +1.50% avg, +0.92% median**
- **Conclusion:** Stale DWAP + fresh momentum = strong trend continuation, NOT reversal.
