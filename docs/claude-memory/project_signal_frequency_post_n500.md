---
name: Signal-frequency claim re-validation after N=500 universe bump
description: Marketing claim "3-4 high conviction picks per month" was set under SIGNAL_UNIVERSE_SIZE=100. After May 17 2026 bump to 500, measure actual fresh-entry count to model_portfolio (live) over 2 weeks; revise claim if it routinely exceeds 7-10/month.
type: project
originSessionId: c3d0833d-cb3f-474f-8dd8-e530f3300c60
---
## What's being measured

**Fresh entries to the live model_portfolio** — i.e., new positions opened, NOT:
- Dashboard buy_signals list count (always larger; will balloon at N=500)
- Per-symbol new ensemble_entry_date events (includes re-signals on names that have fired before)

This count is the right anchor for the marketing claim because it's what subscribers can ACT ON in their own brokerage — every fresh entry is a name the system actually committed slot capacity to.

## The mechanical context

- `MAX_POSITIONS = 6` — hard cap
- Trailing stop ~12-14% (regime-adjusted) — typical hold weeks to months
- Fresh entries are throttled by slot availability, not universe breadth
- AMD has been in 33 days, GOOG/GOOGL 33 days — winners are sticky

So even at N=500, fresh-entry count should not 5x. Expected modest uptick (3-4/month → 4-7/month) because:
- Higher-quality candidates compete for the same 6 slots
- Slot turnover (exits) is the rate-limiter, not candidate scarcity

## Window to measure

**From May 18 2026 daily scan (first N=500 scan) through May 31 2026** — 2 trading weeks. Count distinct symbols entering model_positions with portfolio_type='live' in that window.

Query (or extend signal_month_analysis to a date range):
```sql
SELECT DISTINCT symbol, entry_date
FROM model_positions
WHERE portfolio_type = 'live'
AND entry_date >= '2026-05-18'
AND entry_date <= '2026-05-31'
ORDER BY entry_date;
```

## Decision tree

- **Fresh entries 3-6/month** → claim is fine as-is ("3-4 high conviction picks per month")
- **Fresh entries 7-10/month** → soften phrasing: "a handful, typically 4-7 per month"
- **Fresh entries 10+/month** → claim needs full rewrite; check whether the strategy is now churning differently than WF validated

## Existing related rules

- `feedback_signal_frequency_claim.md` — never "6-8 every 2 weeks" or "~15/month"; current "3-4 per month" is the load-bearing phrasing
- `feedback_no_7_dates.md` — don't cite specific WF start-date counts
- `project_universe_history_snapshots.md` — daily universe snapshots starting May 17 will be the historical ground truth for any future audit

## Connected

- `project_universe_history_snapshots.md` — snapshot data supports the measurement
- `feedback_wf_prod_parity.md` — universe bump was a parity fix, not a strategy change
