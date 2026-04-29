---
name: WF backtest ↔ production signal generation MUST be identical
description: Any strategy lever proven in walk-forward backtesting must be carried forward into the production signal code. Marketing numbers come from backtests; subscribers must be able to realize them.
type: feedback
originSessionId: 1081317d-f863-470f-ab07-65ddc614e856
---
**Rule:** Whatever winning strategy is selected from walk-forward backtesting and ends up driving our marketing numbers MUST be the exact same strategy deployed to production signal generation. Any time we add a new lever (parameter, mechanic, exit rule, position management feature) to the WF test and decide it's a keeper, we MUST port that lever forward into the production signal code in lockstep.

**Why:** Marketing claims are derived from WF backtest results (§15 of the marketing strategy doc). Subscribers see and act on prod signals. If WF assumes a behavior that prod doesn't implement, subscribers cannot realize the marketed performance — that's a misrepresentation, regardless of intent. The marketing strategy doc's "discipline-as-a-service" framing breaks if discipline is simulated in the backtest but not enforced in the live system.

**How to apply:**
- When introducing a new strategy parameter/mechanic in WF: open a parallel implementation task in scanner / signal generation. Don't ship one without the other.
- When deciding "this lever is a keeper" based on a backtest: check whether prod has the same lever. If not, either (a) port it before quoting numbers, or (b) re-run the backtest WITHOUT the lever and quote those numbers.
- When auditing prod vs backtest: grep the codebase for the relevant param/mechanism in BOTH `app/services/backtester.py` AND `app/services/scanner.py`. If counts differ, there's a parity gap.
- When updating marketing numbers: confirm the strategy that produced them is fully realized in prod signal generation as of the date you cite the numbers.

**When memorializing a winning lever** (after A/B ablation testing):
1. Update the default value in code (e.g., flag default in `walk_forward_service.run_walk_forward_simulation`)
2. Update **`docs/MarketingNewsletterStrategyCLAUDE.md` §15** (marketing-doc methodology)
3. Update **`design/documents/rigacap-signal-intelligence.html`** (the "secret sauce" / Signal Intelligence doc)
4. Regenerate the PDF via headless Chrome (CLAUDE.md has the exact command pattern):
   ```
   "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
     --headless --disable-gpu --no-pdf-header-footer --print-to-pdf-no-header \
     --print-to-pdf="design/documents/rigacap-signal-intelligence.pdf" \
     design/documents/rigacap-signal-intelligence.html
   ```
5. If the lever's prod parity hasn't been ported yet (bot it should be after the win is confirmed), open a follow-up to port it into `app/services/scanner.py` before citing the numbers anywhere external.

## Known violations as of Apr 28 2026

- **Circuit breaker pause logic** (`_request_pause`, `_pause_until`, `circuit_breaker_stops`, etc.) lives in `backtester.py` (25 references) but is entirely absent from `scanner.py` (0 references). Backtests can simulate "after 3 same-day stops, pause new entries for 10 days." Production signal generation does not implement this. Marketing numbers that depend on CB protection during stress periods cannot be honestly cited until prod implements an equivalent mechanism (e.g., centralized model-portfolio stops counter + a "no new signals fire until DATE" gate in the daily scan). Surfaced when Erik asked "are we doing the CB pause carryover in prod?" on Apr 28.

This violation is closeable but non-trivial: model-portfolio-level stop tracking, a pause-state in dashboard.json, daily scan respecting the pause when generating signals, and a way to clear the pause manually if needed.

## What "carry forward" looks like in practice

The 5y × 8-date validation we ran on Apr 28 used Trial 37 fixed params (max_positions=6, position_size=15%, trailing_stop=12%, near_50d_high=3%, dwap_threshold=5%) — all of those are mirrored in prod scanner / position management, so the test result is honestly realizable by subscribers. But CB pause is *not* mirrored; if a future test adds CB and quotes numbers that benefit from it, that test ISN'T realizable in prod until the gap is closed.
