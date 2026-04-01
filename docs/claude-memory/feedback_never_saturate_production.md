---
name: NEVER saturate Lambda concurrency in production
description: ABSOLUTE RULE - launching mass WF jobs took down the entire production API for 20+ minutes on Mar 30 2026. User was unable to log in from any device.
type: feedback
---

NEVER launch mass Lambda invocations that could saturate the account's concurrent execution limit. This is a HARD RULE, not a guideline.

**What happened:** On Mar 30 2026, 21 WF simulation jobs were launched simultaneously. The AWS account has only 10 concurrent Lambda executions. The worker consumed all 10 slots. The API Lambda was throttled — returning 503 on ALL requests including CORS preflight. No users could log in for 20+ minutes. The daily scan was also blocked. Setting reserved concurrency failed because the account limit was too low.

**The rule:**
- BEFORE launching ANY WF jobs, check current worker concurrency
- NEVER launch more than 3 WF jobs during market hours (9:30 AM - 6:30 PM ET)
- NEVER launch more than 5 WF jobs at any time until concurrency limit is raised
- NEVER run WF tests in the 4:00-5:30 PM ET window (daily scan + emails)
- ALWAYS ask the user before launching more than 3 concurrent jobs
- Add a server-side guardrail that caps max concurrent WF jobs

**Why this matters:** The user said "I NEVER WANT THIS TO HAPPEN IN PRODUCTION AGAIN. EVER." This directly impacts paying subscribers who cannot access the product.

**Fix applied (Mar 30 2026):** Concurrency increased to 1000. API reserved at 50, Worker reserved at 200.

**CRITICAL: After ANY emergency worker cap (setting to 0), ALWAYS restore to 200 before ending the session.** On Mar 30-31, the worker was left at 0 overnight — zero cron jobs, zero emails, zero scans ran for 15 hours.
