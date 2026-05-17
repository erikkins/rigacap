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
| ~~1249~~ | ~~true~~ | INVALID — wiring missed the fixed-strategy code path, ran baseline by mistake. Bit-for-bit identical to 1248. |
| **1251** | true | Asymmetric (Path B), re-fired May 16 20:32 UTC after wiring fix |

Baseline 1248 reference numbers: total_return_pct = 134.665, sharpe = 0.7183, MaxDD = 37.79%, total_trades = 216, benchmark (SPY) = 84.82%.

## RESULT (May 17 2026)

**Asymmetric mode LOSES on return and Sharpe; WINS marginally on MaxDD.**

| Metric | 1248 baseline | 1251 asymmetric | Delta |
|--------|---|---|---|
| Total Return | 134.665% | 110.650% | **−24 pp** |
| Sharpe | 0.7183 | 0.6723 | −0.05 |
| MaxDD | −37.79% | −31.70% | +6.1 pp better |
| Trades | 216 | 245 | +29 |

**Interpretation:** Day-high HWM tracking tightens the trailing stop earlier, firing 29 more exits over 5 years. That reduces drawdown by 6 pp but costs 24 pp of return. The MaxDD improvement is real but doesn't pay for the return loss. Close-only baseline (Path A as shipped May 15) is the validated optimum.

## Decisions (final, May 17 2026)

1. ✅ **ModelPortfolio on close-only** (Path A shipped May 15) — `process_live_exits`, `process_wf_exits`, `process_signal_track_exits` all use close-only HWM, commit unconditionally.
2. ✅ **User-position alert path on close-only** (Option B shipped May 17, commit f52f900) — HWM tracks `data_cache` latest close (yesterday's during market hours, today's after the 4:30 PM scan). Trigger still fires on `live_price` for intraday alerting. Closes last parity gap.
3. **`hwm_from_day_high` flag kept dormant** — harmless (default false), useful for any future asymmetric variant research.
4. **One-time HWM heal completed** (May 17) — 17 of 38 open positions had stale stored HWMs; corrected via `{"hwm_heal": {"_": 1}}` handler. AMD was the dramatic case ($100.56 gap), IREN was minor ($0.22).

Parity audit: all production HWM tracking paths now match WF default `intraday_aware=False` (close HWM + close trigger), except the user-alert path's trigger fires on live_price for intraday UX — which alerts EARLIER than WF but on the same stop LEVEL.

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
