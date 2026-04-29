---
name: Cascade Guard = Circuit Breaker (CB) — naming convention
description: External/marketing name "Cascade Guard" and internal/code name "Circuit Breaker" refer to the same mechanism. Don't treat them as different features.
type: reference
originSessionId: 1081317d-f863-470f-ab07-65ddc614e856
---
**Cascade Guard** (external, marketing-friendly) = **Circuit Breaker** (internal, in code).

Same mechanism: when N positions hit trailing stop on the same day, pause new entries for M days. Defaults: 3 stops triggers a 10-day pause.

**Where each name appears:**

External / public-facing:
- `design/documents/rigacap-signal-intelligence.html` ("Cascade Guard" in §8)
- Marketing copy generally

Internal / code:
- `app/services/backtester.py` (`circuit_breaker_stops`, `circuit_breaker_pause_days`, `_request_pause`)
- `app/services/strategy_analyzer.py` (`StrategyParams.circuit_breaker_*`)
- `app/services/strategy_params_v2.py` (V2_PARAM_SPACES)
- Memory references: `feedback_wf_prod_parity.md` (the parity gap)

When updating one set of references, search for both names to avoid drift.
