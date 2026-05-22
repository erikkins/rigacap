---
name: ~30% MaxDD is structural to 6×15% concentration, NOT a 2022-bear artifact
description: Skip-2022 3y sweep (May 22 2026) showed mean MaxDD ~31% across 3 windows that contain NO 2022 exposure. Confirms MaxDD is a concentration-risk feature of the strategy, not a one-time bear event.
type: project
originSessionId: c3d0833d-cb3f-474f-8dd8-e530f3300c60
---
## Finding (May 22 2026)

Three 3-year canonical WF runs starting AFTER the 2022 bear (windows fully inside 2023-01 → 2026-05):

| start_date | total_return | annualized | Sharpe | MaxDD | Calmar |
|---|---|---|---|---|---|
| 2023-01-02 | +72.06% | 19.8% | 0.81 | 29.88% | 0.66 |
| 2023-01-23 | +117.83% | 29.6% | 0.94 | 33.43% | 0.89 |
| 2023-02-13 | +88.07% | 23.4% | 0.93 | 29.87% | 0.78 |
| **mean** | **+92.7%** | **24.3%** | **0.89** | **~31.1%** | **0.78** |

The 2023-01-23 window had its MaxDD peak 2023-07-24 → trough 2024-08-05 (Yen carry-trade unwind / VIX spike). That's a 12-month slow grind ending on a single vol event — NOT bear-market driven.

## Why this matters

1. **MaxDD reduction work cannot be framed as "fixing the 2022 problem."** 2022 is one example of a structural risk that recurs in any 12-18 month window where momentum names roll over.

2. **The lever is concentration, not regime.** 6 × 15% = 90% capital concentrated in momentum names. Whenever 2-3 of those names cluster-decline, the portfolio takes a 25-35% hit. This pattern is independent of broad market regime.

3. **The "no 2022" upper bound is still ~30% MaxDD.** That sets the structural floor — to break below ~25% MaxDD we have to attack concentration directly (more positions, smaller size, asymmetric stops, etc.), not just regime detection.

## What we ruled OUT as MaxDD levers

| Lever | Result | Why it failed |
|---|---|---|
| **Gradual capital deployment** | 20-date sweep — MaxDD identical (29.9% median) | Ramp finishes in 8 weeks, MaxDD comes from year-long cluster decline |
| **CB-tighten on cascade** | Date 3 — no change | CB doesn't fire in slow grinds (only 3 same-day stops sees it) |
| **Reactive portfolio-DD sizing** | 4-combo sweep — every variant hurt Calmar | Fires AFTER damage done; shrinking new entries can't reverse existing positions' decline |
| **Re-enable historical regime overlay** | Structural — never reached WF backtester anyway | (Different issue — see `project_cb_tighten_incomplete.md` for related parity gap) |

## What's still on the table

- **DD-conditional trailing stop TIGHTENING** (attacks the slow-bleed mechanism directly, not concentration)
- **Reduce position count in DD, keep size** (concentration via narrower-not-smaller)
- **VIX-conditional forward sizing** (predicts vol instead of reacting to DD)
- **SPY-200MA-based DD trigger** (broad market signal instead of portfolio noise)
- **Hard cap on per-position weight** (sector or correlation-bucketed)

## Use this when

- Asked "would lower MaxDD if we avoided 2022 bear" — answer: no, ~30% MaxDD is structural
- Designing MaxDD experiments — don't repeat skip-2022 framing
- Marketing claims about drawdown — the honest framing is "30% DD ~every 2-3 years is the price of 25%+ annualized in a 6-position momentum book"
