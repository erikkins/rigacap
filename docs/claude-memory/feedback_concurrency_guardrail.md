---
name: Lambda concurrency guardrail — NEVER saturate during business hours
description: Account has only 10 concurrent Lambda executions. Running >7 WF jobs simultaneously took down the API and blocked all user logins. NEVER launch mass WF jobs during market hours.
type: feedback
---

NEVER launch more than 3-4 WF simulation jobs simultaneously. The AWS account (149218244179) has only 10 concurrent Lambda executions total — shared across API Lambda, Worker Lambda, and all EventBridge jobs.

**Why:** On Mar 30 2026, launching 21 WF jobs consumed all 10 concurrency slots. The API Lambda was throttled for 15+ minutes. No users could log in. The daily scan was also blocked. Setting reserved concurrency failed because the account limit is too low.

**How to apply:**
- During market hours (9:30 AM - 6:30 PM ET): max 3 concurrent WF jobs
- Off-hours: max 7 concurrent WF jobs (leave 3 for warmer/cron jobs)
- NEVER run WF tests between 4:00-5:30 PM ET (scan + email window)
- Concurrency increase to 1000 has been requested (pending as of Mar 30 2026)
- Once approved, safe to run ~20 concurrent WF jobs during off-hours
