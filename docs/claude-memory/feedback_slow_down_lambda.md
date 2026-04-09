---
name: SLOW DOWN — think before launching Lambda jobs
description: Do not launch Lambda WF jobs impulsively. Think first, compute locally if possible, never launch duplicates.
type: feedback
originSessionId: 7dc69abd-ade1-4ef8-b901-42d3cee7df53
---
SLOW DOWN before launching any Lambda walk-forward job.

**Why:** On Apr 9 2026, launched 3 WF jobs when only 1 was needed. One timed out (harmless), one was the real job, and one was completely useless (tried to use an unsupported `excluded_symbols` param). Could have computed the no-GME answer from existing trade data in 2 seconds instead of launching a whole job.

**How to apply:**
1. Before launching ANY Lambda job, ask: can I compute this from data I already have?
2. Never launch a second job without confirming the first one failed or finished
3. Check if params are actually supported BEFORE invoking
4. One job at a time. Period.
