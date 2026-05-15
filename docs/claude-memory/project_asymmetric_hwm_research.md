---
name: Asymmetric HWM mode WF research (Path B)
description: WF jobs 1248 (baseline) and 1249 (test) compare close-only HWM vs day-high HWM with close trigger. Tests whether b-full's -17pp ann result was the day-low trigger's fault or the day-high HWM's. Kicked off May 15 2026 19:00 PDT.
type: project
originSessionId: c3d0833d-cb3f-474f-8dd8-e530f3300c60
---
## The hypothesis

The May 3 2026 b-full WF validation showed `intraday_aware=True` (day-high HWM + day-low trigger bundle) cost **-17pp annualized** vs the EOD-default (close HWM + close trigger). Production was promptly disabled to EOD-only on May 3.

**But the test bundled two behaviors.** Hypothesis from May 15: the **day-low trigger** is the cost (false intraday-flush exits), and **day-high HWM tracking** might independently win or be neutral. The asymmetric variant — day-high HWM + close trigger — was never measured.

## What was built

`CustomBacktester.hwm_from_day_high` flag (default False). When True AND `intraday_aware=False` AND `day_high` is provided, HWM updates from the day's HIGH while the stop trigger fires only on close. Plumbed through `walk_forward_service.run_walk_forward_simulation` → WF job event payload.

## Jobs in flight (May 15 2026 evening)

Both 5y biweekly, strategy_id=5 (DWAP+Momentum Ensemble), max_symbols=500, carry_positions=true, periods_limit=1 (low-memory chunks).

| Job ID | hwm_from_day_high | Purpose |
|--------|---|---|
| **1248** | false | Baseline (current production behavior) |
| **1249** | true  | Asymmetric: day-high HWM + close trigger |

Both started at ~19:00 PDT. Chained-runner ETA ~3-5 hours wall-clock.

## How to compare when done

Look at `walk_forward_simulations` table for jobs 1248 vs 1249:
- `total_return_pct`
- `sharpe_ratio`
- `max_drawdown_pct`
- `num_trades` (from trades_json)

**Win condition:** Job 1249 needs to beat 1248 on total_return AND not materially worse on MaxDD before we'd consider shipping asymmetric to production. Marketing claims live or die on this comparison.

If 1249 wins: ship `hwm_from_day_high=true` to production for both ModelPortfolio + user-position dashboard alerts, and update marketing.

If 1249 loses or ties: keep production on close-only (current Path A state), retire the flag (or keep it dormant).

## Connected

- `project_intraday_tpe_research.md` — production intraday trailing stops DISABLED May 3 2026; this is a follow-up exploration to that decision
- `feedback_wf_prod_parity.md` — the parity rule that forces this kind of test before any production change
- `project_cluster_day_ab_test.md` — separate parallel A/B research on signal-day clustering

## Loose ends to revisit

- **User-position dashboard alerts** (scheduler.py line 617-620) still use day-high HWM as of May 15. Decision held pending this test result. If 1249 wins, asymmetric mode is the right answer everywhere. If it loses, drop day-high from the user-alert path too (Path A everywhere).
