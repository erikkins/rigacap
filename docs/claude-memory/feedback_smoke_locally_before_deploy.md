---
name: Smoke-test hot-path edits locally BEFORE deploy to Lambda
description: Lambda deploys auto-fire to shared prod worker. A first-pass bug in entry/exit code triggers prod-worker error alarms.
type: feedback
originSessionId: c3d0833d-cb3f-474f-8dd8-e530f3300c60
---
**Rule:** Any backtester.py edit that touches a hot path (entry filter, exit check, daily loop) MUST be smoke-tested locally with a minimal in-process backtest BEFORE pushing to main. Lambda deploys to BOTH worker and api, so a buggy first commit immediately fires CloudWatch error alarms when the next test invocation runs.

**Why:** Jun 3 2026 — pushed sentiment-exit wiring with `pos['symbol']` lookup that the positions dict didn't have. First smoke-test invocation crashed Lambda with KeyError → triggered prod-worker-errors alarm. No actual production damage (no scheduled job hit the bug), but a needless alarm + extra deploy cycle to push the fix.

**How to apply:**
- For any change inside backtester.py methods that run per-bar (entry candidate eval, exit checks, daily loop), do a 5-line local script: load pickle, run a tiny 30-day backtest, verify no crash
- Doesn't need to be exhaustive — just enough to catch trivial KeyError/AttributeError/None-deref
- Once it runs clean locally, push. CI/CD will run the same paths but at scale, so a local smoke that loads ONE day of data catches 90% of the silly stuff
- Cheap insurance: ~30 seconds of local work vs deploy cycle + alarm cleanup
- Especially critical when the new code touches data structures that vary across strategy_type branches (entry pos shape, basket pos shape, etc.)
