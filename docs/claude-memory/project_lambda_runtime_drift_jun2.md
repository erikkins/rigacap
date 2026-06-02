---
name: Local vs Lambda runtime drift — 5pp annualized swing (Jun 2 2026)
description: Same code + same pickle hash produces different backtest results between local Python 3.9 venv and Lambda Python 3.13 runtime. ~5pp annualized + 14 trades difference on validation window. Lambda is the authoritative bench going forward.
type: project
originSessionId: c3d0833d-cb3f-474f-8dd8-e530f3300c60
---
**Discovered Jun 2 2026.** Migrated v2 sweeps from local to Lambda for true prod-runtime parity. First Lambda-vs-local diff was much bigger than expected.

## The smoking gun

Same backtest config, same pickle, same code path:

**Validation window 2023-06-05 → 2026-05-29, top-100, baseline params:**

| Metric | Local (Python 3.9) | Lambda (Python 3.13) | Δ |
|---|---|---|---|
| Trades | 91 | 77 | -14 |
| 5y total | 37.06% | 58.61% | +21.55 |
| Annualized | 11.15% | **16.73%** | **+5.58pp** |
| Sharpe | 0.68 | **1.00** | +0.32 |
| MaxDD | 18.29% | 16.20% | -2.09pp |
| Calmar | 0.61 | **1.03** | +0.42 |

Same pickle hash both runs. Same git SHA. Same params. **Different decisions emerge from runtime differences.**

## Likely sources

1. **Float precision** — Python 3.9 vs 3.13, numpy 1.26 vs newer. Tiny composite-score differences push different symbols over the top-6 cutoff. Different positions → different trade history → cascading effect.
2. **Sort tie-breaking** — When two symbols have identical scores, sort order may differ between numpy/pandas versions.
3. **Dict iteration order** — Order-of-build could differ subtly.
4. **NaN propagation** — Slight differences in how missing data propagates through indicator stacks.

None of these is a "bug" per se. They're consequences of using different runtime stacks for the same code.

## Strategic implications

### The honest baseline picture changes dramatically

| Metric | Local (yesterday's read) | Lambda (today's actual) | Target | Verdict |
|---|---|---|---|---|
| Annualized | 11.24% | **16.73%** | ≥20% | Gap = 3.27pp (was 8.76pp) |
| Sharpe | 0.68 | **1.00** | ≥1.0 | **PASS** (was FAIL) |
| MaxDD | 18.29% | 16.20% | ≤20% | **PASS** (was PASS) |
| Calmar | 0.61 | **1.03** | ≥1.0 | **PASS** (was FAIL) |

**Yesterday I concluded the strategy template was exhausted at 12% with no path to 20%.** Lambda shows we're already at 16.73% with 3 of 4 targets met. Much smaller structural change can close the remaining gap.

### All prior local-runtime sweeps are invalidated

Yesterday's local sweeps (baseline, T3, E1-E4, A1) used Python 3.9 + macOS. They produced numbers consistently ~5pp annualized lower than reality. The "A1 catastrophe" (5.96% ann) might or might not look different in Lambda — A1 may still fail, but the magnitude is suspect.

### "Signal quality is the bottleneck" conclusion now suspect

Yesterday's hypothesis from A1's failure was that the signal at rank 4 ≈ rank 6 in expected return, so concentration amplifies undifferentiated noise. That conclusion was based on local-runtime numbers. **It may still be true, but it must be re-verified by running A1 in Lambda.**

## Rule for future work

- **Lambda runtime is the authoritative bench.** All Tier 1 + Tier 2 sweeps invoke `rigacap-prod-worker` via the `native_backtest` handler.
- **Local Python remains useful for**: smoke testing handler logic, debugging, exploring data. NOT for producing comparable performance numbers.
- **Backlog reset**: B1, B2 (profit-lock variants) and any further work must run in Lambda from the start.
- **Drift investigation**: worth a follow-up day to identify which runtime element causes the divergence (float precision? sort? both?). Lower priority than continuing strategy research.

## Related memory

- [Testing methodology v2](project_testing_methodology_v2.md) — needs amendment: "standalone backtester" implies Lambda not local. Update doc.
- [A1 failed → signal quality bottleneck](project_a1_failed_signal_quality_bottleneck.md) — conclusion may need revisit after re-running A1 in Lambda.
- [WF↔prod displacement gap](project_wf_prod_displacement_gap.md) — different parity gap, separate finding.
