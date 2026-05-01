---
name: TPE optimization over intraday-execution parameter space
description: After tonight's production-matched baseline lands, run univariate sweeps then TPE over intraday execution params (cadence, lockout, multi-min confirmation). Sweet spot likely exists between EOD-only and aggressive 1-min checking.
type: project
originSessionId: 1081317d-f863-470f-ab07-65ddc614e856
---
**Why:** Apr 30 2026 intraday WF validation revealed 10+ trades where intraday triggers cut winners short by 50-120 pp (IREN, ASTS, RIOT, NVAX, TNDM, MRNA, ASAN, CELH, SNDK, LITE — all real momentum trades hit by single-day intraday volatility). Per-trade median gain was modest; tail losses dominated. Suggests a non-obvious sweet spot exists in the parameter space.

**Why TPE specifically:** Multivariate. Cadence × lockout × stop-width × confirmation interact in non-linear ways. Single-param sweeps would miss combinations that work together but not individually.

**Pre-conditions before running TPE:**
1. **Production-matched baseline locked** — re-run intraday validation at 5-min cadence with live-price-exit (matches `process_live_exits` in `model_portfolio_service.py`). Done Apr 30 2026.
2. **Univariate sweeps first** — characterize each parameter individually. Discover which actually matter. Example sweeps:
   - lockout_days: 0, 3, 5, 7, 10
   - cadence_minutes: 1, 5, 15, 60
   - stop_pct_intraday: 10, 12, 15, 18 (separate from EOD)
   - multi_min_confirmation: 1, 2, 3, 5 minutes
3. **Strict OOS protection** — TPE sees only 2015-2022 data. Held-out 2023-2026 used ONLY for final scoring, never for fitting.

**TPE search space (tentative, after univariate validation):**
- 3-5 parameters max in the search space
- Drop any that showed no signal in univariate
- Bounded ranges informed by univariate findings

**Why be cautious:**
- Trial 37 over-fit to corrupted pickle (see [project_trial37_overfit_clean_data.md](project_trial37_overfit_clean_data.md))
- Over-fitting risk grows with parameter count and search-space breadth
- Marketing numbers can't move down a second time without serious credibility cost

**Connected work:**
- [Intraday WF validation](#) — Apr 30 2026, baseline being established
- [Intraday data anomalies](project_intraday_data_anomalies.md) — must fix flash-spike model BEFORE TPE so it doesn't optimize against bad data
- [CB-in-production wiring](project_cb_production_wiring.md) — blocker before any production-changing optimization
- [Bear Ripper](project_bear_ripper_strategy.md) — separate strategy refinement on bear regime

**Schedule:** After Apr 30 baseline is clean and CB-in-production wiring is done. Probably ~mid-May 2026.
