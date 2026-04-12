---
name: Never duplicate Lambda WF jobs with identical params
description: Don't re-launch a WF job that's already running with the same params. Parallel jobs with DIFFERENT params are fine.
type: feedback
originSessionId: 7dc69abd-ade1-4ef8-b901-42d3cee7df53
---
Never launch a duplicate WF job with the same params as one already running.

**Why:** On Apr 9 2026, launched 3 jobs with identical params when only 1 was needed. Also launched a job with an unsupported `excluded_symbols` param instead of computing the answer from existing trade data.

**How to apply:**
1. Before launching ANY Lambda job, ask: is an identical job already running?
2. Parallel jobs with DIFFERENT params (e.g., 12 different start dates) are fine
3. Check if params are actually supported BEFORE invoking
4. If you can compute the answer from data you already have, do that instead of launching a job
5. When running multiple LOCAL backtests with different params, run them in PARALLEL (separate processes) — they're independent and the M4 Max has plenty of cores
