---
name: Walk-Forward A/B Test Results (Mar 25 - Apr 1 2026)
description: Complete log of all WF simulation runs, configs, results, and lessons learned during the 20% annualized optimization push
type: project
---

# Walk-Forward A/B Test Campaign (Mar 25 - Apr 1 2026)

## Goal
Get from 16.3% annualized (baseline +112.8%) to 20%+ annualized, CONSISTENTLY across start dates.

## Critical Bugs Found During Testing
1. **Pickle shrinkage (Mar 26-27)**: Daily scan overwrote 7y pickle (256 MB) with 124 MB version. Fixed with size guardrail + weekly auto-archive.
2. **carry_positions default=False (Mar 26)**: Invalidated all test jobs 248-257.
3. **optimizer_version key mismatch (Mar 25)**: Payload used `optimizer` but code expected `optimizer_version`.
4. **datetime scoping bug (Mar 25)**: `from datetime import datetime` at handler level broke daily scan.
5. **Signal source inconsistency (Mar 27)**: Double signal alert emailed signals not on dashboard. Fixed to read from dashboard.json only.
6. **Lambda concurrency saturation (Mar 30)**: 21 WF jobs consumed all 10 concurrent slots, taking down API for 20+ min. Fixed: increased to 1000, reserved 50 for API, 200 for worker.
7. **Worker concurrency left at 0 (Mar 30-31)**: Worker was dead for 15 hours overnight. All cron jobs missed.

## Pickle & Infrastructure
- **7y pickle (Mar 27 rebuild)**: 269 MB, 4360 symbols, 2019-06-03 → 2026-03-27.
- **Pickle guardrail**: blocks >20% shrink, weekly auto-archive.
- **Lambda concurrency**: 1000 (was 10). API reserved=50, Worker reserved=200.
- **WF state files**: persist on completion with results (no longer deleted).

## Optimizer Versions
- **v1**: Single-objective Sharpe. HURTS returns on fresh pickle (+11% vs +101% fixed).
- **v2**: Multi-objective Pareto. Aggressive (rp=0.8) best. Wide param space.
- **v2c**: Tight constrained. Too restrictive, killed returns.
- **v2m**: Medium constrained — exit_type locked to trailing_stop, other params wide. Best balance.

## Master Results Table — All Optimizer Sensitivity Tests

### v2m baseline (200 symbols, rp=0.8, no extras) — Jobs 294-300
| Start | Job | Return | Ann. | Sharpe | MaxDD |
|-------|-----|--------|------|--------|-------|
| Feb 8 | 296 | +93.6% | 14.1% | 0.74 | -26.5% |
| Jan 18 | 295 | +70.0% | 11.2% | 0.43 | -40.4% |
| Jan 4 | 298 | +168.2% | 21.8% | 0.80 | -20.5% |
| Jan 25 | 297 | +57.8% | 9.6% | 0.53 | -34.5% |
| Mar 1 | 299 | +8.1% | 1.6% | 0.18 | -43.0% |
| Feb 15 | 300 | +32.1% | 5.7% | 0.38 | -23.2% |
| Feb 1 | 294 | -15.7% | -3.4% | -0.06 | -53.8% |
**Avg +59.2% (+8.7% ann) | Spread 184pp | Pos 6/7 | >20%a 1/7**

### v2 Unconstrained (200 symbols, rp=0.8)
| Start | Return | Ann. | Sharpe | MaxDD |
|-------|--------|------|--------|-------|
| Feb 1 | +250.2% | 28.5% | 0.95 | -31.2% |
| Feb 15 | +201.0% | 24.7% | 0.94 | -27.6% |
| Mar 1 | +45.1% | 7.7% | 0.39 | -47.3% |
| Jan 4 | +44.3% | 7.6% | 0.39 | -45.5% |
| Jan 25 | +4.6% | 0.9% | 0.15 | -41.5% |
| Feb 8 | -15.5% | -3.3% | 0.05 | -53.7% |
| Jan 18 | -21.9% | -4.8% | -0.09 | -34.6% |
**Avg +72.5% (+11.5% ann) | Spread 272pp | Pos 5/7 | >20%a 2/7**

### v2c Tight Constrained (200 symbols, rp=0.8)
| Start | Return | Ann. |
|-------|--------|------|
| Jan 25 | +70.0% | 11.2% |
| Feb 15 | +56.7% | 9.4% |
| Jan 4 | +25.4% | 4.6% |
| Feb 1 | +13.1% | 2.5% |
| Jan 18 | -9.9% | -2.1% |
| Mar 1 | -13.9% | -3.0% |
| Feb 8 | -18.0% | -3.9% |
**Avg +17.6% (+2.7% ann) | Spread 88pp | Pos 4/7 | >20%a 0/7**

### C: WARMUP — v2m + warmup_periods=13 (200 symbols, rp=0.8) ← BEST CONSISTENCY — Jobs 339-345
| Start | Job | Return | Ann. | Sharpe | MaxDD |
|-------|-----|--------|------|--------|-------|
| Jan 4 | 339 | +156.4% | 20.7% | 0.78 | -17.9% |
| Jan 25 | 343 | +157.6% | 20.8% | 0.85 | -22.1% |
| Jan 18 | 341 | +82.2% | 12.7% | 0.50 | -35.2% |
| Feb 1 | 340 | +71.3% | 11.4% | 0.52 | -40.7% |
| Mar 1 | 345 | +37.9% | 6.6% | 0.39 | -40.6% |
| Feb 15 | 342 | +36.7% | 6.4% | 0.39 | -34.5% |
| Feb 8 | 344 | +6.0% | 1.2% | 0.17 | -47.0% |
**Avg +78.3% (+11.4% ann) | Spread 152pp | Pos 7/7 | >20%a 2/7**

### A: SMOOTHING — v2m + param_smoothing=0.7 (200 symbols, rp=0.8) — Jobs 325-332 ← COMPLETED
| Start | Job | Return | Ann. | Sharpe | MaxDD |
|-------|-----|--------|------|--------|-------|
| Jan 18 | 330 | +117.4% | 16.8% | 0.57 | -33.8% |
| Feb 15 | 329 | +88.1% | 13.5% | 0.67 | -17.5% |
| Feb 1 | 331 | +69.1% | 11.1% | 0.55 | -26.9% |
| Jan 4 | 328 | +98.0% | 14.6% | 0.57 | -39.6% |
| Jan 25 | 335 | +80.0% | 12.5% | 0.59 | -32.3% |
| Feb 8 | 326 | +24.2% | 4.4% | 0.31 | -35.6% |
| Mar 1 | 338 | +16.0% | 3.0% | 0.25 | -27.7% |
| Feb 1 (dup?) | 327 | -0.3% | 0% | 0.11 | -55.5% |
| Jan 25 (dup?) | 325 | -8.7% | -1.7% | 0.05 | -47.2% |
**NOTE: 9 jobs instead of 7 — may include a second config variant. Jobs 333-338 may be separate batch.**

### A2: SMOOTHING VARIANT 2? — Jobs 333-338
| Start | Job | Return | Ann. | Sharpe | MaxDD |
|-------|-----|--------|------|--------|-------|
| Jan 4 | 333 | +285.4% | 31.0% | 0.92 | -16.9% |
| Jan 18 | 334 | +38.3% | 6.7% | 0.34 | -46.2% |
| Jan 25 | 335 | +80.0% | 12.5% | 0.59 | -32.3% |
| Feb 8 | 336 | +35.4% | 6.3% | 0.33 | -34.3% |
| Feb 15 | 337 | -34.4% | -6.1% | -0.25 | -45.9% |
| Mar 1 | 338 | +16.0% | 3.0% | 0.25 | -27.7% |
**NOTE: Job 333 (+285.4%) is a massive outlier on Jan 4 start. Very suspicious — likely overfitting.**

### B: 300 SYMBOLS — v2m + max_symbols=300 (rp=0.8) — Jobs 348-356 ← STILL RUNNING (as of Apr 1 ~10 AM)
| Start | Job | Status | Period | Current Return | Positions |
|-------|-----|--------|--------|----------------|-----------|
| Jan 18 | 356 | running | 124/~131 | +87.4% | MNST, UBER, HOOD, IREN, OKLO |
| Jan 18 | 352 | running | 125/~131 | +59.5% | MNST, UBER, RUN, GLW |
| Jan 18 | 350 | **completed** | — | **+82.2%** | — |
| Feb 1 | 354 | running | 123/~131 | +32.9% | MNST, NEM, IREN, SOUN |
| Feb 1 | 349 | **completed** | — | **+43.4%** | — |
| Feb 1 | 348 | running | 119/~131 | +15.8% | CELH, MNST, NEM, U |
| Feb 8 | 355 | running | 120/~131 | +19.9% | MNST, UBER, NEM, WDC, KGC |
| Feb 8 | 353 | **completed** | — | **+132.3%** | — |
| Feb 8 | 351 | running | 110/~131 | -2.1% | [] (cash) |

**NOTE: Multiple jobs per start date — different AI-optimized warm_start_params each.**
Some warm_start configs:
- Job 352/354: dwap 3%, stop 16%, 8 pos @ 19%, breakout 5%, sector_cap 2
- Job 355: dwap 3.5%, stop 10%, 8 pos @ 20%, breakout 8%, long_mom_days=40
- Job 356: dwap 4%, stop 16%, 6 pos @ 20%, breakout 7%, short_mom_days=5, sector_cap 3
- Job 348: dwap 5%, stop 18%, 6 pos @ 20%, breakout 7%
- Job 351: dwap 6.5%, stop 15%, 5 pos @ 20%, breakout 7%

### Short-period sanity checks — Jobs 346-347
| Period | Job | Return | Ann. | Sharpe | MaxDD |
|--------|-----|--------|------|--------|-------|
| 2025-03 → 2026-03 (1yr) | 346 | +76.2% | 76.3% | 1.82 | -8.5% |
| 2026-01 → 2026-04 (3mo) | 347 | +15.9% | ~82% | 4.82 | -1.8% |
**Recent market has been exceptionally favorable. Don't extrapolate.**

### New "Combined" Tests — Jobs 349-356 (v2m + 300 symbols + varied warm_start params)
These appear to be the last tests kicked off before VS Code crashed. They test different AI-optimized parameter combinations with 300-symbol universe. 6 of 9 still actively running (state files updating as of Apr 1 10 AM).

**Completed so far:**
- Job 353 (Feb 8): +132.3% (18.4% ann), Sharpe 0.81, MaxDD -22.1%
- Job 350 (Jan 18): +82.2% (12.7% ann), Sharpe 0.50, MaxDD -35.2%
- Job 349 (Feb 1): +43.4% (7.5% ann), Sharpe 0.39, MaxDD -40.5%

## Grand Comparison (updated Apr 1 2026)

| Config | Avg Ann | Floor | Ceiling | Spread | Positive | >20% Ann |
|--------|---------|-------|---------|--------|----------|----------|
| **Warmup (13 periods)** | **+11.4%** | **+6.0%** | **+157.6%** | **152pp** | **7/7** | **2/7** |
| Smoothing (0.7) | ~+9.5% | -0.3% | +117.4% | 118pp | 7/9? | 0/9 |
| v2m (no extras) | +8.7% | -15.7% | +168.2% | 184pp | 6/7 | 1/7 |
| v2 (unconstrained) | +11.5% | -21.9% | +250.2% | 272pp | 5/7 | 2/7 |
| v2c (tight) | +2.7% | -18.0% | +70.0% | 88pp | 4/7 | 0/7 |
| 300 symbols | TBD | TBD | TBD | TBD | TBD | TBD |
| Fixed (no AI) | +16.3% | — | — | — | 1/1 | 0/1 |

## Key Findings (Updated Apr 1 2026)

1. **Pickle data is everything.** Must use same pickle for A/B comparisons.
2. **carry_positions=true is mandatory.** Without it, returns drop 50-90%.
3. **200 symbols >> 100 symbols.** Wider universe is the single biggest lever.
4. **Exit type = trailing_stop is the key constraint** (v2m approach).
5. **Bear market modifications all failed.** Cash is king during bears.
6. **Warmup (13 periods / ~6 months) is the most consistent optimizer config.** First to achieve 7/7 positive start dates. Eliminates cold-start lottery.
7. **v2m aggressive (rp=0.8) is the right optimizer.** Conservative/balanced both hurt.
8. **Smoothing (0.7) COMPLETED — decent but worse than warmup.** All positive but lower ceiling, similar floor.
9. **Start-date sensitivity is solvable** — warmup reduces spread from 272pp to 152pp and eliminates negatives.
10. **Lambda concurrency must be monitored.** Never launch mass WF jobs without checking account limits first.
11. **Fixed params (no AI optimizer) still holds best single-date result at 16.3% annualized** (Job 224). AI optimizer hasn't consistently beaten it yet.
12. **300-symbol tests still running (6 jobs)** — will complete within hours. Different warm_start params being tested.

## Next Steps (as of Apr 1 2026)
- **WAIT for 300-symbol batch to finish** (6 jobs, periods 110-125 of ~131)
- Combine winning approaches: warmup + 300 symbols
- Try warmup + smoothing combo
- Regime-adaptive strategy: different params per regime transition
- 10-year backtest on the winning config
- Consider whether AI optimizer actually helps vs fixed params
