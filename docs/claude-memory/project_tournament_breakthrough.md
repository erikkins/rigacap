---
name: Tournament breakthrough — 19.9% avg annualized (Apr 3 2026)
description: Parameter tournament found near_50d_high_pct=3% is the key lever. 7/7 positive, 3/7 hit 20%+, avg 19.9% ann.
type: project
---

## The Breakthrough (Apr 3 2026)

**One param change:** `near_50d_high_pct` from 5% → 3% (require stocks within 3% of 50-day high instead of 5%)

### Results — 7 Start Dates
| Start | Return | Ann% | Sharpe | MaxDD |
|-------|--------|------|--------|-------|
| Jan 18 | +266.9% | 29.7% | 0.95 | -20.4% |
| Jan 25 | +164.6% | 21.5% | 0.88 | -23.0% |
| Feb 1 | +162.1% | 21.3% | 0.91 | -22.4% |
| Feb 8 | +130.2% | 18.1% | 0.81 | -23.9% |
| Mar 1 | +129.2% | 18.0% | 0.90 | -16.6% |
| Jan 4 | +117.0% | 16.8% | 0.82 | -18.9% |
| Feb 15 | +92.6% | 14.0% | 0.71 | -19.1% |

**Avg: 19.9% ann | 7/7 positive | 3/7 ≥20% | All beat SPY**

### vs Previous Best (Warmup 13)
- Old: 11.4% avg ann, 7/7 positive, 2/7 ≥20%
- **New: 19.9% avg ann, 7/7 positive, 3/7 ≥20%** — nearly doubled

### How We Found It
1. Parameter tournament: 16 single-param sweeps in parallel (6.5 min on M4 Max)
2. Identified top 6 params by impact
3. Tested combined tournament winners → +146% flat backtest but only +37% in WF (8% stop killed it)
4. Kept trailing_stop at 12% (proven in WF), applied only near_50d_high_pct=3% → **+162% on Feb 1**
5. Validated across 7 start dates ��� consistent

### Why It Works
Tightening from 5% to 3% of 50-day high = only entering stocks at genuine breakout points. The extra 2% filter eliminates "almost breaking out" stocks that often fail. Stronger entry quality → better win rate → better returns.

### Key Lesson
The optimizer was searching 17 dimensions when only 1 mattered for WF mode. The tournament approach (test each param independently) found this in 6.5 minutes vs weeks of WF runs.

### Config for Production
```
near_50d_high_pct: 3.0  (changed from 5.0)
trailing_stop_pct: 12.0  (unchanged)
dwap_threshold_pct: 5.0  (unchanged)
max_positions: 6  (unchanged)
position_size_pct: 15.0  (unchanged)
All other params: baseline (Job 224)
```

### Additional Validations (Apr 3-4 2026)
- **2% vs 3% vs 4%:** 3% confirmed as sweet spot (21.2% ann vs 19.9% at 2%)
- **10-year WF:** +497% (19.6% ann), Sharpe 0.97 — validated, not projected
- **Regime adjustments DISABLED:** both original and flipped directions destroy returns (19.9% → 1.7% / 2.8%). Fixed params across all regimes is optimal. Regime EXIT filter (SPY < 200MA → cash) still active — that's the real risk management.
- **Signal frequency:** 3-4 signals per month with 3% filter (was claiming ~15)
- **All marketing pages updated** with validated numbers

### Production Config (deployed Apr 3 2026)
```
near_50d_high_pct: 3.0  (was 5.0)
trailing_stop_pct: 12.0  (unchanged, fixed across all regimes)
regime param adjustments: DISABLED
regime exit filter: ACTIVE (SPY < 200MA → cash)
All other params: baseline
```

### Things That DON'T Help (all tested, all hurt returns)
- AI optimizer (Optuna, any version) — adds noise, never consistently beats fixed
- More optimizer trials (100 vs 30) — marginal improvement, not the bottleneck
- ATR-based stops — wrong for momentum (widens stops on volatile stocks = bigger losses)
- Min hold days — blocks good exits
- Profit-lock stop tightening — optimizer wastes trials on it
- Regime param adjustments (either direction) — 19.9% → 1.7% or 2.8%
- Pyramiding / doubling down on winners — 19.9% → 14.1% (15/10/2) or 17.8% (8/10/1)

### The Final Strategy (simplest wins)
```
near_50d_high_pct: 3.0
trailing_stop_pct: 12.0
dwap_threshold_pct: 5.0
max_positions: 6
position_size_pct: 15.0
No optimizer. No regime adjustments. No pyramiding.
Regime EXIT filter (SPY < 200MA → cash) still active.
```

### What Goes Live Monday Apr 7
- First scan with 3% breakout filter at 4:30 PM EDT
- Fixed params, no regime adjustments, no optimizer, no pyramiding
- Monitor for signal quality and frequency
