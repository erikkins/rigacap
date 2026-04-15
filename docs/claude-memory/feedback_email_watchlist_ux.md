---
name: Daily digest email — watchlist count mismatch + ticker deep links
type: feedback
description: Fix subject-vs-body count inconsistency and add clickable ticker links into the platform
originSessionId: 39ce1e26-1ab7-4fbd-8e9a-6c892d933b00
---
## Two UX issues on the daily digest email

### 1. Watchlist count mismatch between subject and body

**Current behavior:** Subject shows "Market Update — 4 on Watchlist", then body renders Monitoring section (1 row) + Watchlist table with only 3 rows. User sees 4 in subject but 3 in body — confusing.

**Likely cause:** the watchlist list passed to the template has 4 items, but some get promoted to Monitoring (the non-fresh section) and the template slices down. The subject uses `len(watchlist)` but the body uses a truncated slice.

**Fix:** show the full watchlist list in the email body, capped at 10-20 rows (not the current 6). Subject count must match body row count. Either:
- Subject counts only the rows we actually render, OR
- Body renders all rows reported in the subject

### 2. Tickers in emails should deep-link to platform chart

**Current behavior:** Ticker symbols (e.g., "NVDA", "BAC") in the email body are plain text.

**Fix:** wrap tickers as anchor tags that deep-link to the platform with that symbol selected. Example target:
```
https://rigacap.com/app?symbol=NVDA&view=chart
```
or whatever route pattern maps to "dashboard open to chart popup for NVDA".

Apply to tickers in:
- Watchlist section
- Monitoring section
- Missed Opportunities section
- Fresh buy signals section

**Platform-side work:** make sure the dashboard honors a `?symbol=X` query param on load — auto-scroll/open the chart popup for that symbol.

### Why this matters

Both are polish items but compound with the "Market, Measured." free-list ambitions. A subscriber reading a daily digest SHOULD be one click from "what does this stock actually look like?" — right now they have to manually navigate into the dashboard and hunt for the row.

### Rough implementation pointers

- Subject/body consistency: `backend/app/services/email_service.py` `send_daily_summary` — check the slicing in the HTML template vs the count used in subject line
- Deep links: same file, wrap ticker strings in `<a href="https://rigacap.com/app?symbol={sym}">{sym}</a>`
- Frontend URL handler: `frontend/src/App.jsx` useEffect on mount to read query param + trigger chart modal
