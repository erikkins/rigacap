---
name: Trial 37 — discovered on dirty data, validated on clean. Stay with it.
description: Trial 37 params were originally found via TPE on indicator-corrupted pickle. After two rounds of data fixes, the same params validate at +160%/0.92/20.4% MDD on clean data across multiple start dates. Decision Apr 29 2026 to NOT re-run TPE — accept Trial 37 as canonical.
type: project
originSessionId: 1081317d-f863-470f-ab07-65ddc614e856
---
## Discovery (Apr 15 2026)

Trial 37 params (currently in production) were originally optimized against a pickle containing unadjusted splits for NVDA, CMG, WMT, AVGO (and ~75 other split events). The optimizer found entry timing that exploited the split-day price "jumps" — not real momentum.

## Two clean-data validations of Trial 37 params

| Date | Data state | Trial 37 result | Verdict |
|---|---|---|---|
| Apr 15, 2026 | Post-split-fix only | +96% / 0.58 / -36.6% MDD | Poor — flagged as broken |
| **Apr 28, 2026** | Post-split-fix + post-indicator-corruption-fix (`fetch_incremental` + `_ensure_indicators` two-layer bug fixed) | **+160% / 0.92 / -20.4% MDD across 8 start dates** | **Validated — current canonical** |

The same parameter values went from "poor" to "validated" because the underlying data quality jumped a step between Apr 15 and Apr 28. Trial 37 params encode something real about market structure, not just artifacts — they survive on cleaner data.

## Cascade Guard impact (Apr 28 validation)

Validated against a true no-CG counterfactual on clean data: **+37 percentage points of return / +3.7 pp annualized / +0.14 Sharpe**. Replaces the over-fit "+87 pp / same MDD" claim from the Apr 19 vintage.

## Decision Apr 29 2026: do NOT re-run TPE on cleaner data

Considered running fresh TPE on the Apr 28 cleanest pickle to see if a better param set exists. **Decided against.** Reasons captured in this session:

1. **Trial 37 is validated.** +160% / 21.1% ann / 0.92 / 20.4% MDD across 8 start dates is a real, defensible result. Every year positive. CG validated.
2. **Subscriber-facing strategy stability has value.** Once shipping, swapping params under subscribers' feet introduces version churn ("which Trial am I on?") without guaranteed marginal improvement.
3. **Live execution data is the higher-information next signal.** After 60-90 days post-launch, real subscriber-facing slippage, regime-call accuracy, and adoption patterns will tell you 100× more than another simulation pass.
4. **Re-optimization carries downside.** If a fresh TPE finds materially better params, full re-validation + canonical_numbers regen + marketing-content sweep + subscriber comm = days of work + potential trust hit. Marginal improvement may not warrant.

**Revisit only if:** live results materially diverge from walk-forward expectations, OR a new data-integrity layer is discovered, OR a structural strategy enhancement (not just re-tuning) becomes available.

## Production state — what's actually deployed

- **Strategy ID 5** (Ensemble): Trial 37 fixed params
- 6 positions × 15% allocation
- 12% trailing stop (with profit-tightening above +12%)
- DWAP 5% breakout threshold (NEVER reveal value publicly per `feedback_no_dwap_in_public.md`)
- near_50d_high_pct = 3%
- biweekly rebalancing
- Cascade Guard at 3+ same-day stops, 10-day pause
- carry_positions = True, cb_pause_carries_periods = True

## TPE Run3 archive

`tpe_run3_archive/` directory contains the Apr 16 TPE re-run output (on the partially-clean Apr 15 data). Not adopted. Preserved for reference if a future fresh run is desired.

## Pre-Trial-37 rollback

`project_ensemble_pre_trial37_params.md` has the params that preceded Trial 37. Rollback reference if Trial 37 ever needs to be retired.
