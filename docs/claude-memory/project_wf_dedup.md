---
name: WF job dedup needed
description: Walk-forward jobs lack dedup — duplicate launches waste Lambda cycles. Add check before creating new jobs.
type: project
---

WF sim launches have no dedup check. On Apr 1 2026, launching 28 jobs created ~49 instead (nearly doubled).

**Why:** `Event` invocation type is fire-and-forget with no idempotency. Multiple triggers (CI/CD deploy mid-launch, retry, etc.) can create duplicate jobs with identical configs.

**How to apply:** Before creating a new WF job in `walk_forward_service.init_simulation()` or `run_walk_forward_simulation()`, query DB for any `running` job with the same `start_date + end_date + strategy_id + config hash`. If one exists, return the existing job ID instead of creating a new one. Same config + same seed = identical results, so dupes are pure waste (~$1-2 per batch but adds up).
