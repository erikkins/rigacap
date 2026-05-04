---
name: Lambda event payloads must be truthy
description: Worker handler dispatch is `if event.get("foo"):` — empty dict `{}` is FALSY in Python, so the handler skips and falls through to Mangum's API-Gateway adapter, which then errors with "unable to infer a handler". Use `{"_": 1}` or `True` as the value, never `{}`.
type: feedback
originSessionId: 1081317d-f863-470f-ab07-65ddc614e856
---
The worker Lambda's handler in `main.py` dispatches via `if event.get("foo"):` — i.e. truthy check, not key-presence check. So:

- `{"pipeline_health_report": {"_": 1}}` ✅ truthy → dispatches
- `{"pipeline_health_report": true}`     ✅ truthy → dispatches
- `{"pipeline_health_report": {}}`       ❌ FALSY → falls through → Mangum errors

When the dispatch falls through, Mangum's API-Gateway adapter raises `RuntimeError: The adapter was unable to infer a handler to use for the event` and the invocation fails. Looks scary in CloudWatch but is just a malformed payload, not a real bug.

**Why:** I want to remember this because I've burned the same way twice in 3 days. May 2 (test_intraday_fetch routing) and May 4 (re-firing morning emails after the os bug fix). Each time the symptom looks like a deploy issue or routing issue, but it's just the empty-dict payload.

**How to apply:**

When invoking any worker handler via `aws lambda invoke --invocation-type Event`, the value MUST be truthy. Default pattern when there are no real config args:

```bash
echo '{"my_handler_name": {"_": 1}}' > /tmp/payload.json
aws lambda invoke ... --payload fileb:///tmp/payload.json
```

For handlers that genuinely accept no config, this is just busywork. But `{"_": 1}` is the convention already used in some existing comments (e.g. `{"engagement_opportunities": {"_": 1}}`) so stick with it.

**Pattern to also avoid:**
- `event.get("foo") is not None` — strict key-presence check (rare, would be safer for config-less handlers but isn't what the codebase uses)

**Connected fixes:**
- May 2: test_intraday_fetch handler routing — same falsy-fallthrough symptom
- May 4: morning emails (pipeline_health_report, admin_health_check) — needed `{"_": 1}` to dispatch
