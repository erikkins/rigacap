---
name: Admin run_sql Lambda handler (TODO)
description: Add a generic SQL/diagnostic event handler to the worker Lambda for ops/debug queries — avoids tripping the worker-errors alarm with ad-hoc invokes
type: project
originSessionId: c3d0833d-cb3f-474f-8dd8-e530f3300c60
---
Add a generic `run_sql` (and/or `diagnostic`) event handler to the worker Lambda so ops/debug queries don't trip the `rigacap-prod-worker-errors` alarm.

**Why:** On May 12 2026 a single `aws lambda invoke --payload '{"run_sql": "SELECT …"}'` probe threw a Mangum RuntimeError (no handler matched), counted as a Lambda error, and tripped the alarm for 5 min before auto-clearing. Same will happen for any future ad-hoc payload shape — manually querying production state via Lambda is currently impossible without either (a) hand-writing a typed event branch or (b) hitting the API behind auth.

**How to apply:** In `backend/main.py` `handler()`, add an early branch:

```python
if event.get("run_sql"):
    # Admin-only. Accepts {"run_sql": "SELECT ...", "params": [...]}.
    # Returns rows (capped at N). SELECT-only — reject any DDL/DML by
    # parsing for keywords or wrapping in a read-only transaction
    # (SET TRANSACTION READ ONLY).
    ...
```

Requirements / gotchas:
- **Read-only enforcement.** Either keyword-reject `INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|GRANT` or open the connection in a read-only transaction. Don't trust the caller — the Lambda is reachable from anyone who can `aws lambda invoke`.
- **Cap rows + result size.** Hardcode `LIMIT 1000` or return-truncate to avoid blowing past Lambda's 6 MB response limit.
- **No PII leak.** Audit the call site list before shipping — anyone with `aws lambda:InvokeFunction` perms can read user emails, hashed passwords, Stripe customer IDs, etc. Today that's only Erik's local profile, but if CI/CD or a co-founder gets a role with invoke perms, this becomes a side door.
- **Log every call.** Print the SQL, requesting principal (from `context.identity` if present), row count to CloudWatch for audit.
- **Pair with `diagnostic` event.** While in there, also add a `{"diagnostic": "pickle_status" | "wf_orphans" | "stale_data" | …}` branch for canned health checks — same admin pattern, no free-form SQL needed for routine probes.

Effort: ~30 min for the handler + ~30 min for tests + read-only guard.

When this lands, the in-line memory rule `feedback_lambda_payload_truthy.md` ("Lambda payloads must be TRUTHY") still applies — `run_sql` must be a non-empty string for the branch to fire.
