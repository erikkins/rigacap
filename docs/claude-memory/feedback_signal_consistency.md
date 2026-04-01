---
name: Signal source consistency rule
description: ALL signal-facing code (emails, alerts, dashboard, API) must read from the SAME source — never independently compute signals
type: feedback
---

EVERY component that shows or sends signals to users MUST read from dashboard.json (the single source of truth). NEVER independently compute signals via rank_stocks_momentum() or scanner_service.scan() in email/alert jobs.

**Why:** On Mar 27 2026, the double signal alert emailed beta testers about "breakout signals" that didn't exist on the dashboard. The alert job was doing its own momentum ranking with looser criteria than the dashboard's ensemble filters. User had to send an embarrassing "never mind" email to beta testers. Also, `latest.json` went 9 days stale (since Mar 18) because the daily scan stopped updating it.

**How to apply:** Before adding ANY new signal-facing feature (email, push notification, social post, API endpoint), verify it reads from dashboard.json or the persisted ensemble_signals DB table — never from a fresh scan/ranking call. If a signal isn't on the dashboard, it doesn't exist. Period.
