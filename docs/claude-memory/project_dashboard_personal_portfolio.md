---
name: Dashboard Portfolio Banner — make user-personal, not model-portfolio
description: Tuesday May 5 2026 work. Current Portfolio Value banner ($42K, 4/6 positions, 0% win rate) is the MODEL portfolio's data shown to subscribers as if it were theirs. Fix: same visual treatment, but each stat is user-personal (their starting capital × their signup-date replay).
type: project
originSessionId: 1081317d-f863-470f-ab07-65ddc614e856
---
**The bug surface (May 3 2026):** Dashboard's "Your Journey" + "Portfolio Value" banner mixes two unrelated things on one screen:
- "Your Journey" = personalized to user (signup date + hardcoded $10K notional)
- "Portfolio Value: $42,172" = the **model portfolio's** open-position market value (not the user's)

A subscriber reading this naturally thinks "Portfolio Value" is theirs. It isn't. It's our admin tracking, equivalent to showing them a stranger's portfolio that happens to follow our signals from a different start date and a $100K seed.

**Erik's framing:** *"It's no different than showing them another user's portfolio that started on the same date as the model one."*

**The fix Erik approved (Tuesday work):** Keep the banner's visual treatment — he likes the at-a-glance layout — but feed each stat user-personal data.

**Each banner stat must become user-personal:**

| Banner Field | Currently shows | Tuesday: should show |
|---|---|---|
| Portfolio Value | Model's deployed equity ($42K) | User's hypothetical portfolio value (their $X starting capital, replayed through every signal from THEIR signup date) |
| Open P&L | Model's unrealized | User's hypothetical unrealized |
| Cost basis | Model's | User's |
| Positions (4/6) | Model's open count | User's hypothetical open count from their signup forward |
| Buy Signals | Universal | Universal (no change — same for all users) |
| Win Rate | Model's since model started | User's win rate on closed trades since THEIR signup |

**Implementation (~half day):**

1. **DB migration first** (per memory rule — never deploy schema and code together):
   - `users` table: add `portfolio_size` (FLOAT, default 10000.0)
   - New `user_portfolio_state` table:
     - `user_id` (FK), `as_of_date`, `portfolio_value`, `cost_basis`, `open_pnl_dollars`, `open_pnl_pct`, `open_positions_count`, `closed_trades_count`, `winning_trades_count`, `updated_at`
     - Cached per-user nightly snapshot to avoid live re-simulation on every dashboard load.

2. **Per-user simulation** (`backend/app/services/user_portfolio_simulator.py`):
   - Input: user's starting capital + signup date.
   - Replays every published signal from signup forward.
   - Applies same allocation rules (6 positions × 15%, 12% trailing stop, etc.).
   - Tracks open/closed positions, capital, P&L, win rate.
   - Returns the user_portfolio_state row payload.

3. **Daily-scan hook**: after EOD exits/entries process, recompute user_portfolio_state for every active subscriber. Caches into DB. Performance: ~50-200 active subscribers × ~few seconds each = manageable in the daily-scan window.

4. **API**: new endpoint `GET /api/signals/my-portfolio-banner` returns the cached row for the authenticated user. Falls back to live computation if cache miss.

5. **Frontend**:
   - Add portfolio_size input on a small settings card or inline edit on the banner ("Customize for $___")
   - Banner reads from /my-portfolio-banner instead of mixed sources.
   - Persist user portfolio_size via PATCH /api/auth/me.

6. **Onboarding flow**: ask new subscribers their portfolio size during signup. Optional — default $10K is safe.

**Edge cases to handle:**
- User signed up TODAY: no replay needed; show `portfolio_value = portfolio_size`, no positions, 0% win rate.
- User has fewer simulated entries than the model (signed up after some had already opened): only replay from signup, ignore prior model history.
- User's hypothetical portfolio runs out of cash (signal density too high for $X capital): cap at 6 positions like normal — extra signals are skipped exactly like the model would skip them.

**Why Tuesday, not tonight (Sun May 3):**
- Today already shipped: intraday-stop disable, CloudFront cutover, Sonnet 4.6, voice filter, CB-in-production, advisory-lock fix.
- This change touches dashboard (most-viewed surface) + DB schema + daily-scan flow.
- Buffer day to confirm advisory-lock fix actually closes the cold-start deadlock before adding more complexity.

**Connected:**
- [Signal slippage tracking](project_signal_slippage_tracking.md) — when this lands, we can layer in slippage-adjusted user numbers (entry price = next-day-open instead of signal-publication-close).
- [Trial length decision](project_trial_length_decision.md) — onboarding flow that asks portfolio size also asks trial preference.
