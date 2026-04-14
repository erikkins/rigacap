---
name: Ensemble strategy params before Trial 37 deployment (Apr 13 2026)
description: Historical record of the live Ensemble (id=5) params before they were updated to Trial 37 values
type: project
originSessionId: 39ce1e26-1ab7-4fbd-8e9a-6c892d933b00
---
## What this records

The live Ensemble strategy (`strategy_definitions` id=5) ran with these params from initial deployment until **Apr 13, 2026**, when it was updated to match Trial 37 (the validated +240% configuration captured in commit 54d1c16).

These pre-Trial-37 values powered all live signals in the run-up to the marketing reset. If anyone ever asks "what was the strategy doing before Apr 13 2026?" — this is the answer.

## Pre-Trial-37 params (deprecated)

```json
{
  "dwap_threshold_pct": 5.0,
  "volume_spike_mult": 1.3,
  "short_momentum_days": 10,
  "long_momentum_days": 60,
  "near_50d_high_pct": 5.0,
  "max_positions": 6,
  "position_size_pct": 15.0,
  "trailing_stop_pct": 12.0,
  "market_filter_enabled": true,
  "min_volume": 500000,
  "min_price": 15.0
}
```

## What changed in the Trial 37 update

| Param | Pre-Trial-37 | Trial 37 |
|---|---|---|
| `dwap_threshold_pct` | 5.0 | **6.5** |
| `max_positions` | 6 | **8** |
| `position_size_pct` | 15.0 | **17.0** |
| `trailing_stop_pct` | 12.0 | **13.0** |

Direction: tighter entry (higher DWAP threshold), more diversification (8 vs 6 positions), larger per-position bet, slightly looser trailing stop. All other params unchanged.

## What was tested but NOT included in Trial 37

Pyramid sizing, profit-lock stop tightening, and bear_keep (gradual regime exit) were built into the codebase as optional levers but **were not part of the final Trial 37 configuration**. The +240% number was produced without them.

If those features ever get re-evaluated, they're in `strategy_params_v2.py` and `strategy_analyzer.py`.
