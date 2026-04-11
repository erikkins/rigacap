---
name: MDD reduction ideas — next features to test
description: Advanced features to reduce max drawdown below 20%, for implementation after TPE run 1 completes.
type: project
originSessionId: 7dc69abd-ade1-4ef8-b901-42d3cee7df53
---
## MDD Reduction — Next Features (After TPE Run 1)

**Goal:** Max drawdown < 20% across all start dates, while keeping 5-year return > 200% and annualized ~25%.

### Features to Add to Backtester

1. **VIX-adjusted position sizing** — reduce position size when VIX > 25. Higher VIX = smaller positions = less exposure during volatile periods. Could use a scale: VIX 15-20 = 100% size, 20-25 = 75%, 25-30 = 50%, 30+ = 25%.

2. **Drawdown circuit breaker** — if portfolio is down 15% from its high water mark, halve all position sizes until it recovers to within 10% of the peak. Prevents compounding losses during drawdowns.

3. **Tighter trailing stop in bear regimes** — use 8% trailing stop when regime is Weak Bear or worse, 12% in normal conditions. Already have regime data in the backtester. Just need conditional stop logic.

### TPE Run 2 Search Space (after adding features)
All existing params PLUS:
- `vix_scale_threshold`: 20-30 (VIX level to start reducing size)
- `vix_scale_factor`: 0.25-0.75 (how much to reduce)
- `drawdown_circuit_pct`: 10-20 (drawdown % to trigger circuit breaker)
- `drawdown_scale_factor`: 0.25-0.75 (how much to reduce when triggered)
- `bear_trailing_stop_pct`: 6-10 (tighter stop in bear regimes)

### Current Status (Apr 11, 2026)
TPE Run 1 in progress — 50 trials, 4 start dates, searching 11 existing params. Expected completion ~2 AM. If no config achieves <20% MDD with >200% return, implement features above and run TPE Run 2.
