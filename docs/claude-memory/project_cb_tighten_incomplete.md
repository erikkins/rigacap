---
name: circuit_breaker_tighten_pct is a no-op feature (half-implemented)
description: The CB-tighten param exists, is in TPE search space, and propagates through StrategyParams + configure() — but the write at backtester.py:1332 has no read site in the exit logic. Defaults to 0, so prod behavior is unaffected today.
type: project
originSessionId: c3d0833d-cb3f-474f-8dd8-e530f3300c60
---
## What we found (May 22 2026)

`circuit_breaker_tighten_pct` is wired through:
- `StrategyParams.circuit_breaker_tighten_pct: float = 0`
- `CustomBacktester.configure()` propagates it to backtester (yesterday's patch)
- `BacktesterService.run_backtest` sets `pos['tightened_stop'] = circuit_breaker_tighten_pct / 100` when CB fires (line 1332)
- V2 / V2M / V2C search spaces all include it in TPE-tunable params

But the **exit logic never READS `pos['tightened_stop']`**. The trailing-stop check at backtester.py:738 computes `effective_stop_pct = exit_strategy.trailing_stop_pct`, then applies `profit_lock` overrides, but never checks for the tightened_stop dict key.

**Net effect: the feature is a no-op.** Setting it to any non-zero value has zero effect on trade math. TPE search results that involved this param were optimizing over noise.

## Why we didn't ship the fix

The fix is two lines (insert after profit_lock check):
```python
if 'tightened_stop' in pos:
    tightened_pct = pos['tightened_stop'] * 100
    if tightened_pct < effective_stop_pct:
        effective_stop_pct = tightened_pct
```

We tested this on Date 3 (2021-01-25). Result: bit-near-identical to baseline (+185% vs +186%, MaxDD 33.5% → 33.5%, 9 extra exits but no MaxDD improvement). **Reason: CB doesn't fire during the 2022 slow-grind bear that creates the MaxDD.** Five CB fires on Date 3 are all in early 2021 + Feb 2023 (SVB precursor) + Aug 2024 (carry-trade unwind) — sharp single-day cascades. The 2022 bear is a months-long drift, never produces 3 same-day stops, never triggers CB.

So fixing the read-side wire-up wouldn't help our actual MaxDD problem. Shipping the fix would only:
- Give TPE another real lever (could find new bad local optima)
- Add code surface for a feature with no current use case

Revert kept production exactly as-is.

## When to revisit

If/when we add a different CB trigger that DOES fire during slow bears (e.g., regime-based CB: trigger when SPY < 200MA for N days), the tighten-pct read-side wire-up would become valuable. At that point, ship the 2-line fix alongside the new trigger.

## Connected

- Strategy uses regime detection (`market_regime.py`) but currently only for the binary "SPY < 200MA → close all" panic exit, not for graduated CB triggers
- MaxDD reduction research arc: actual lever needed is regime-based exposure management (position sizing or trailing-stop tightening), NOT cascade-based
