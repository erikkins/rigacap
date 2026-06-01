---
name: Lambda event payloads must be truthy (manual invokes AND EventBridge rules)
description: Worker handler dispatch is `if event.get("foo"):` — empty dict `{}` is FALSY in Python, so the handler skips and falls through to Mangum's API-Gateway adapter, which then errors with "unable to infer a handler". Use `{"_": 1}` or `True` as the value, never `{}`. Applies equally to `aws lambda invoke --payload` AND EventBridge rule Target Input.
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
- **June 1 2026: monthly_recap EventBridge rule** — `rigacap-prod-monthly-recap` was created with Target Input `{"monthly_recap":{}}`. First fire of the rule (top-of-month cron) erred 3× before EventBridge gave up. May 2026 social recap posts were lost; backfilled manually. Fix: `aws events put-targets ... --targets file://<json>` with `"Input": "{\"monthly_recap\":{\"_\":1}}"`. **Third burn of this pattern — extending the rule from invokes to EventBridge.**

**When creating a new EventBridge rule that targets the worker Lambda, ALWAYS:**

1. Set Target Input to a truthy JSON object. Examples:
   - No config needed: `{"my_handler_key": {"_": 1}}` (or `{"my_handler_key": true}` — both work)
   - Config args: `{"my_handler_key": {"max_trades": 5, ...}}` (non-empty dict — truthy)
2. **Never `{"my_handler_key": {}}`.** Empty dict is FALSY and falls through to Mangum.
3. **Verify before merge:** `aws events list-targets-by-rule --rule <name> --query 'Targets[0].Input'`
4. **Verify handler gate:** grep `main.py` for the handler. If it uses `event.get(...)` (the common pattern), Input MUST be truthy. If it uses `"key" in event` (defensive, e.g. `nightly_wf_job` at main.py:4087), `{}` is tolerated — but still prefer truthy for consistency.
5. **Smoke-fire** the new rule manually before relying on the cron: `aws lambda invoke --function-name rigacap-prod-worker --payload fileb://<same-input.json> /tmp/result.json` and confirm `status: ok` (not Mangum error).
6. Audit script lives in session memory — re-run the cross-reference (EventBridge inputs × `if event.get(...)` gates in main.py) periodically and after any rule additions. June 1 2026 audit found 0 risks across 25 rules and 102 handler gates.
