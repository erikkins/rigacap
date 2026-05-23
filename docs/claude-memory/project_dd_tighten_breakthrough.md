---
name: DD-conditional trailing stop tighten (t15/s8) — validated 50-date breakthrough
description: When portfolio is ≥15% below running peak, tighten trailing stop 12% → 8%. Validated across 50 weekly start dates 2021-01 to 2021-12. Wins baseline on 92% (ret), 90% (Sharpe), 98% (MaxDD), 94% (Calmar). Local research script only — NOT in production yet.
type: project
originSessionId: c3d0833d-cb3f-474f-8dd8-e530f3300c60
---
## What the lever is

**DD-conditional trailing stop tightening.** Mechanism:
- Track WF synthetic equity across periods (chained from each period's `total_return_pct`)
- At start of each biweekly period, compute `dd_pct = (peak - equity) / peak * 100`
- If `dd_pct ≥ 15`: override `self.trailing_stop_pct = 0.08` for this period (all positions)
- Else: restore baseline `self.trailing_stop_pct = 0.12`
- Reset (new peak) and re-evaluate every period

**Critical**: trigger is **portfolio-DD-based**, not regime-based, not VIX-based, not position-level.

## Validated results (50-date sweep, May 22 2026)

52 weekly Mondays starting 2021-01-04, each → +5y. 50 succeeded, 2 missed on DB flakes that were later rerun (full 50 included).

| Metric | baseline median | t15/s8 median | Win rate |
|---|---|---|---|
| Total return | +159% | **+181%** | **92%** (46/50) |
| Annualized | 21% | **23%** | — |
| Sharpe | 0.83 | **0.91** | **90%** (45/50) |
| MaxDD | 33.5% | **27.6%** | **98%** (49/50) |
| Calmar | 0.65 | **0.89** | **94%** (47/50) |

MaxDD distribution caps at 24-28% (baseline was bimodal at 30/33.5). The patch genuinely puts a ceiling on drawdown.

## Failure mode (3 known-bad dates)

3 March 2021 starts (2021-03-08, -15, -22) where tightened-periods exceeded 50% (70-112 of 131). When trigger fires that often, the 8% trail starts churning the strategy. Sharpe collapses to 0.31-0.52 on those dates.

**Pattern**: portfolio enters 15% DD early, stays in DD persistently (shallow but never recovers). 8% trail keeps stopping out on noise. Cumulative churn losses.

## What's been ruled OUT as refinement

**Capped-consecutive variant** (tried May 22): if tightened ≥8 consecutive periods, release to baseline for 2 periods. **WORSE on every date tested.** On Date 2: ret +96 → +24, MaxDD 27.6 → 42.3 (-72pp return loss from just 4 cap-releases). Diagnosis: releasing the stop DURING DD lets losers compound. Wrong direction.

**Depth-graduated variant** (tried May 22): DD bands 15-20%=10% trail, 20-25%=8%, ≥25%=6%. Loses to BASELINE on 4 of 5 validation dates. Date 2 collapsed (+96 → +21, Sharpe 0.64 → 0.29). 6% trail in deep DD churns the strategy the same way t10/s6 did. The graduated approach modestly helps the already-broken March 2021 dates (+19pp on worst date) but converts a working Date 2 into a disaster. Net negative. Diagnosis: any aggressive tightening below 8% causes churn in deep DDs.

**Hard conclusion: t15/s8 is the FINAL form of this lever family.** To go higher (Sharpe/Calmar ≥ 1.0), must use orthogonal mechanism.

## What's still on the table

**Depth-graduated** (next to test): instead of binary tight/baseline, scale by DD depth:
- DD 15-20%: trail 10% (gentler, gives positions room)
- DD 20-25%: trail 8% (current)
- DD 25%+: trail 6% (aggressive — force out persistent bleeders)
This rewards survivors of shallow DDs and forces out persistent losers in deep DDs.

**Orthogonal levers** (stacking candidates):
- Bear-regime trailing stops (regime classifier trigger instead of portfolio-DD)
- VIX-conditional sizing (forward signal not reactive)
- Mega-cap basket during CG pause (universal rule, 12-event evidence pre-fix data)

## Scripts

- `scripts/wf_dd_tighten_stop.py` — the breakthrough script, runtime monkey-patch, local-only
- `scripts/wf_dd_tighten_capped.py` — the dead-end cap variant (kept for reference, do NOT ship)
- Sweep launcher: `/tmp/sweep_52mon_dd_tighten_runner.sh`
- Sweep results: `/tmp/sweep_52mon_dd_tighten_t15s8/summary.csv`

## To productionize

Wiring into the backtester needs a real change, not just monkey-patch. Two production touch points:

1. **Backtester read site** (`backend/app/services/backtester.py:738`):
   ```python
   effective_stop_pct = exit_strategy.trailing_stop_pct
   # ADD: check pos['tightened_stop'] (currently written by CB-tighten with no reader)
   ```

2. **DD-state tracker**: need a per-period equity/peak tracker in the WF service that sets `pos['tightened_stop']` when DD ≥ 15%. The CB-tighten infrastructure (`StrategyParams.circuit_breaker_tighten_pct`) is already half-wired — needs the read side AND the DD trigger replaces the CB-cascade trigger (or runs alongside).

**Parity rule (load-bearing)**: any production lever MUST match what WF tested. The t15/s8 lever is portfolio-DD-triggered, not CB-triggered. Wire it as a separate code path; don't try to overload CB-tighten with this.

## Marketing-numbers implications

If we ship t15/s8 to production, marketing claims should reflect the 50-date sweep:
- Median 5y return: +181% (vs canonical Apr 28 baseline +160%)
- Median Sharpe: 0.91 (vs canonical 0.92 — comparable)
- Median MaxDD: 27.6% (vs canonical 20.4% — WORSE on this metric, but baseline 33.5% is more comparable)

The 20.4% MaxDD canonical number was an Apr 28 sweet-spot, not a typical path. The honest range is 24-28% with the lever, 30-34% without.

## User goal not yet hit

User stated goal: median Sharpe ≥ 1.0 AND median Calmar ≥ 1.0. Current: 0.91 / 0.89. Need ~+0.10 on each. Likely path: stack t15/s8 with one orthogonal lever (bear-regime stops or VIX sizing or mega-cap basket).
