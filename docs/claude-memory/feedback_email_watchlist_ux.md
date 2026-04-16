---
name: Daily digest email — ticker deep links
type: feedback
description: Tickers in daily digest emails should be clickable deep links that open the chart popup on the dashboard
originSessionId: 39ce1e26-1ab7-4fbd-8e9a-6c892d933b00
---
## Ticker deep links in daily digest emails

**Status:** #1 (watchlist count mismatch) FIXED. #2 (deep links) still open.

### Tickers in emails should deep-link to platform chart

**Current behavior:** Ticker symbols (e.g., "NVDA", "BAC") in the email body are plain text.

**Fix:** wrap tickers as anchor tags that deep-link to the platform with that symbol selected. Example target:
```
https://rigacap.com/dashboard?chart=NVDA
```

Apply to tickers in:
- Watchlist section
- Monitoring section
- Missed Opportunities section
- Fresh buy signals section

**Platform-side work:** make sure the dashboard honors a `?chart=X` query param on load — auto-open the chart popup for that symbol. Same pattern as `?subscribe=market_measured#newsletter`.

### Implementation pointers

- Deep links: `backend/app/services/email_service.py` `send_daily_summary` / `send_bulk_daily_summary` — wrap ticker strings in `<a href="https://rigacap.com/dashboard?chart={sym}">{sym}</a>`
- Frontend URL handler: `frontend/src/App.jsx` useEffect on mount to read `?chart=` query param + trigger `setChartModal(...)` for that symbol
