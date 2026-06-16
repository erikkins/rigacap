---
name: project-oom-scan-zero-jun15
description: Jun 15 2026 — ROOT CAUSE of the recurring 0-signal scan + the hygiene alarm emails = the 3008 MB Lambda memory cap. BOTH FIXES SHIPPED same night (commit 1ed2491). VERIFY on the Jun 16 4:30 scan. THE resume doc.
metadata:
  node_type: memory
  type: project
  originSessionId: 701a2e93-33c0-4e85-a7bc-2cb9d9956d94
---

# 0-signal scan + hygiene OOM — both are the 3008 MB memory ceiling (Jun 15 2026)

## ✅ STATUS: both fixes SHIPPED + CONFIRMED LIVE Jun 15 night (commit 1ed2491)
- CI/CD green (4m22s); both Lambdas updated **01:20 UTC Jun 16**, State=Active (worker still 3008 MB cap — unchanged, that's fine).
- Fix 1 = daily-scan dashboard build moved BEFORE the pickle/parquet exports (headroom) + BUG-1 guard retry removed (alert-only).
- Fix 2 = nightly_data_hygiene drops the inline export_parquet after split-refetch (keeps export_pickle + gc).
- **MUST VERIFY on the Tue Jun 16 4:30 PM ET scan:** (1) scan REPORT Max Memory comfortably < 3008 MB; (2) dashboard.json buys ≈ bench set (not 0) on a healthy regime; (3) book entries match; (4) no worker-errors alarm from hygiene that night. If the scan STILL writes 0 with mem under cap → it was NOT (only) memory; escalate to the decouple-into-fresh-invocation plan (Fix 1 alt below).

## 🧳 Jun 16 travel plan (Erik OFFLINE during scans — laptop in a bag)
- **DECIDED: NO auto-recover cron.** The Fix-1 alert-only guard is server-side and emails `erik@rigacap.com` on the failure signature. That email IS the tripwire: Erik spins up the laptop → returns to THIS chat → we run the recovery together (below). Plus the 8 CloudWatch alarms cover Lambda-error / hygiene-OOM paths.
- **Watch-for email subject:** `🚨 RigaCap: 0 buy_signals despite healthy raw scan`. No email = scan worked (expected).

## 🚑 RECOVERY RUNBOOK (if the scan writes 0 again — exactly what worked Jun 15)
The cold/fresh worker invocation rebuilds the dashboard with memory headroom → correct set. Two equivalent paths:

**One-shot (preferred):** fresh invocation does dashboard + snapshot + ensemble persist + ENTRIES + regime:
```
aws lambda invoke --function-name rigacap-prod-worker --profile rigacap --region us-east-1 \
  --payload '{"export_dashboard_cache": true, "include_snapshot": true, "include_ensemble": true}' \
  --cli-binary-format raw-in-base64-out --cli-read-timeout 300 /tmp/rec.json
```
**Two-step (what I literally ran Jun 15, if you want to eyeball the dashboard before entering):**
1. `{"export_dashboard_cache": {"_": 1}}` → rewrites dashboard.json (check buys != 0; Jun 15 gave 17).
2. `{"model_portfolio": {"action": "process_entries", "portfolio_type": "live"}}` → enters the set (Jun 15: 17 positions, $36k cash left).
**Then verify:** `aws s3 cp s3://rigacap-prod-price-data-149218244179/signals/dashboard.json - | python3 -c "import json,sys;d=json.load(sys.stdin);print(len(d['buy_signals']))"`
Always sanity-check the names against the t30v bench (SNDK/MRVL/INTC/AMD/UMC/MU… on Jun 15) before trusting. process_entries is idempotent-ish on a fresh day but DON'T double-run it (it would add to an already-entered book) — check current positions first: `{"model_portfolio":{"action":"status","portfolio_type":"live"}}`.

## What happened (Mon Jun 15, first live-entry day)
- 4:30 scan ran, found **43 raw DWAP signals**, regime `rotating_bull` — but the dashboard build wrote **buy_signals:0 AND watchlist:0**. BUG-1 guard fired, retried IN THE SAME PROCESS, still 0, alerted admin. Live book entered 0.
- A couple hours later (~22:34–22:42 UTC) `nightly_data_hygiene` hard-crashed `Runtime.OutOfMemory` and auto-retried 2–3× → **the alarm emails Erik saw.**

## ROOT CAUSE (verified): the worker hit the 3008 MB cap
- 4:30 scan invocation REPORT: **Max Memory Used: 3008 MB** (the hard cap), 487 s duration. Status "ok" — it did NOT hard-OOM, it ran AT the ceiling.
- One warm process does: fetch → `scan()` → `export_pickle` (695 MB decompressed) → `export_parquet` shadow → gc → **`compute_shared_dashboard_data`**. By the time the dashboard build recomputes the momentum ranking (allocates indicator columns across the full ~100 universe over 5020-symbol cache), there's no headroom — pandas/numpy ops quietly yield empty/degraded results instead of raising. Signature = **0 buys + 0 watchlist, NO exception, NO OOM exit.**
- `nightly_data_hygiene` (refetch splits + hold full cache + rebuild+rewrite pickle) went past the cap → hard OOM.

## Why it NEVER reproduced locally (the trap)
Local box has 16+ GB → zero memory pressure → the recompute ALWAYS gives the correct **17**. The bug exists ONLY under the 3008 MB ceiling. Pure "code parity ≠ runtime parity" — I wasn't reproducing the *memory* environment. Proof points:
- COLD `export_dashboard_cache` (fresh process, ~2325 MB, headroom) → **17** ✓
- IN-PIPELINE build (same process already at 3008 MB) → **0** ✗
- Every local ordering (scan-first, +canonicalize) → 17.

## Ruled out along the way (don't re-chase these)
- Market filter / `spy_above_200ma` — TRUE both windows (SPY 754 ≫ 200MA 684). Not firing.
- `_dynamic_excluded` — never set (comment-only ref).
- export_pickle/export_parquet mutating cache — they `.copy()`; canonicalize re-ensured 0 symbols.
- Swallowed exception in the buy/watchlist `try` (signals.py:1049) — no error logged.
- `get_top_liquid_symbols` empty universe — reads data_cache (full), not DB/S3.

## Today's manual recovery (live record intact)
- Cold `export_dashboard_cache` → dashboard.json corrected to **17** (SNDK, MRVL, INTC, AMD, UMC, MU, NBIS, CORZ, WULF, AAL…).
- `process_entries` (live) → entered **17 positions**, ~$64k deployed, $36k cash. Erik approved keeping them ("all good"). This is the correct parity set for Mon's close.
- NOTE: pickle was REWRITTEN by hygiene at 22:32 (5020 symbols) after I pulled /tmp/mon_pickle.pkl.gz — re-pull before any fresh diff.

---

# FIX 1 (primary) — Decouple the dashboard build from the scan process
**Goal:** the dashboard build + entries must run in a FRESH, low-memory invocation, never inline in the memory-saturated scan process. This is Erik's own directive: "if the scan ran, all processes should pull from the stored place." Scan's job ENDS at writing the pickle; a separate process reads it and builds.

**Key fact:** the fresh path ALREADY EXISTS and ALREADY WORKS — the deferred `export_dashboard_cache` handler (main.py ~2008–2117) with `include_snapshot:true, include_ensemble:true` is a COMPLETE SUPERSET of the inline path: dashboard export, snapshot, ensemble persist+invalidate, `process_entries` + BUY notify, regime snapshot, regime history, WF-cache chain. It gave us the correct 17 today.

**Change (main.py `_run_daily_scan`):**
1. After `export_pickle` succeeds (~line 1488–1542), ALWAYS self-invoke the deferred dashboard path and RETURN — delete the inline block (lines ~1548–1700: the inline `compute_shared_dashboard_data`, the BUG-1 GUARD, inline snapshot/entries/regime). The existing `<5 min remaining` defer branch (line 1427) becomes the ONLY path; drop the time condition.
   ```python
   _lambda.invoke(FunctionName=_worker, InvocationType='Event',
       Payload=json.dumps({"export_dashboard_cache": True,
                           "include_snapshot": True, "include_ensemble": True}))
   ```
2. **Reconcile what the inline path does that the deferred one doesn't** before deleting:
   - Market-context history persistence (inline ~1588) — add to deferred handler (e.g. `include_market_context` flag) or confirm it's covered elsewhere.
   - Anything between 1580–1700 not in the 2008–2117 handler — diff the two blocks line by line.
3. **Delete the BUG-1 GUARD** (1552–1579) — obsolete; with a fresh-process build there's nothing to "recover," and Erik vetoed in-process reruns. Keep a LIGHT alert only if the deferred build self-reports 0 buys while raw scan ≥10 (alert, do NOT retry).
4. Keep `export_pickle`'s guardrails. The scan still: fetch → scan → store_signals → canary → export_pickle → (parquet shadow) → **invoke deferred → return.**

**Why it works:** the deferred invocation cold-starts at ~2325 MB with headroom; it only loads the pickle + builds the dashboard (no fetch/scan/double-export in the same process). Proven today: same code, fresh process → 17.

**Memory headroom bonus:** consider dropping the inline `export_parquet` shadow + `compare_pickle_to_parquet` from the scan process too (or gating behind env) — they pile onto the 3008 MB peak for observation-only value. Parquet migration supersedes them anyway.

**Verify (Tue Jun 16, before relying):**
- Smoke locally (import-only) per `feedback_smoke_locally_before_deploy`.
- Deploy via CI/CD (push to main). Off-hours ideally; it's code not schema, but it's the hot path.
- Trigger a manual `daily_scan`-equivalent OR wait for the 4:30 scan; confirm: scan REPORT mem well under 3008, deferred invocation REPORT also under cap, dashboard.json buys ≈ bench set, book entries match.
- Watch CloudWatch worker mem + the worker-errors alarm.

**Rollback:** revert the commit; the inline path returns. Low risk — we're routing to an existing, exercised handler.

---

# FIX 2 (separate) — nightly_data_hygiene memory diet
**Symptom:** `Runtime.OutOfMemory`, Max Memory 3008 MB, 22:34–22:42 UTC Jun 15, retried 2–3× → the alarm emails. Job: verify asset IDs (5018) → poll corp-actions → **force-refetch 5 split symbols** → **rebuild+rewrite the 347 MB pickle** — all holding the full 5020-symbol cache in one process.

**Options (pick Tue):**
1. **Split into chained invocations:** (a) verify+corp-actions+refetch writes only the touched symbols; (b) chain a SEPARATE `pickle_rebuild_from_scan`-style invocation for the rewrite (don't refetch AND rebuild in one process).
2. **Don't rebuild the whole pickle in hygiene** — apply split fixes to the touched symbols and let the next daily scan's export_pickle carry them. Removes the heaviest step.
3. Stream/batch the pickle rebuild to avoid holding clean_cache + source cache simultaneously (export_pickle already streams to tmp; the peak is holding both dicts).

**Structural cure for the whole class:** parquet migration (Option A, in progress) — partial per-symbol reads replace the 695 MB monolith. Both Fix 1 and Fix 2 are stopgaps until the read path stops loading the full pickle. See `project_storage_migration_roadmap`.

## Verification owed before calling either fix done
Diff the deferred handler vs inline path line-by-line (don't ASSUME superset — verify). Confirm no email/digest or history-persist step is silently dropped by routing to the deferred path.
