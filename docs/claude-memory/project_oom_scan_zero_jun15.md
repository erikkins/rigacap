---
name: project-oom-scan-zero-jun15
description: Jun 15-17 2026 — the recurring 0-signal scan was TWO unrelated bugs. REAL root cause (found Jun 17) = MOMENTUM_SECTOR_CAP=0 dropping every sector'd stock. SEPARATE issue = the 3008 MB OOM (fixed by the parquet flip). Both shipped. THE resume doc.
metadata:
  node_type: memory
  type: project
  originSessionId: 701a2e93-33c0-4e85-a7bc-2cb9d9956d94
---

# ⭐ CORRECTION (Jun 17): the 0-signal bug was NEVER memory — it was the SECTOR CAP
**REAL root cause:** `MOMENTUM_SECTOR_CAP = 0` in config + rank_stocks_momentum's sector-cap logic `if count < CAP`. With CAP=0, `count < 0` is ALWAYS False → EVERY candidate that had a known sector was DROPPED, leaving only unknown-sector names → ranking collapsed to ~1 → 0 buy_signals. **It only bit when stock-universe SECTORS were LOADED** (the daily scan) — NOT the cold recovery/diag/export_dashboard_cache paths (sectors empty → nothing dropped → always produced the correct set). THAT is the "daily scan=0, every recovery=correct" pattern we chased for 3 days, and why it never reproduced locally (local universe load returns empty sectors). Fix (commit after 1ed2491): `cap <= 0` now means DISABLED (keep all); verified rank 1→100. Config comment even flagged it: `= 0  # NOT REVERTED`.
**Lesson:** I chased 4 WRONG theories first (memory, the fetch/merge, settlement/timing, "Lambda runtime drift") — each time a "X works, Y doesn't, diff is Z" where Z was wrong. The instrumentation that finally nailed it: print-level [DASH-DIAG] gate counts (ranked/pass_quality/ge200/px>=15/examples) IN THE LAMBDA. Stop theorizing; instrument the real runtime.

## The OOM was a SEPARATE, real problem (fixed by the parquet flip Jun 17)
The 3008 MB cap WAS real (hygiene OOM'd; the daily scan ran at the ceiling) but it was NOT the 0-signal cause. **Parquet flip SHIPPED Jun 17:** `PRICE_SOURCE=parquet` → import_all does a SCOPED partial read (top-600 liquid universe from the latest universe-history snapshot + SPY/^VIX/^GSPC, from all_data.parquet = byte-identical to the pickle) → ~603 symbols, **memory 2353→1486 MB, OOM gone.** fetch_incremental defaults to the loaded cache so the scan stays scoped. Daily scan SKIPS export_pickle/parquet in parquet mode (a scoped cache would shrink the stores). Flag-gated (default pickle = instant env rollback; backups /tmp/envbak_*). PRICE_SOURCE=parquet is LIVE on the worker.

## 🔥 PARQUET TEETHING CASUALTY #2 (Jun 21 2026) — pickle_rebuild infinite OOM loop (RESOLVED)
The Sunday 00:00 UTC `pickle-rebuild` cron spun into a **27-hour infinite OOM loop: 426 Runtime.OutOfMemory, ~15/hr**. Cause: in parquet mode each cold start loads only the scoped ~603 symbols, so the rebuild's chunked "fetch the missing 4421, self-chain" NEVER accumulates — every chained invocation reloads 603, sees ~4421 missing, fetches 200, OOMs at the 3008 cap, re-chains (remaining stuck at 3874 for 27h). The OOMs logged NOTHING before REPORT (looked like init-phase OOM) — found by reading the lines BEFORE the OOM REPORT in-stream → `keys=['pickle_rebuild']`. **The full-pickle rebuild is OBSOLETE in parquet mode.** FIXED (commit 32080a5): both `pickle_rebuild` + `pickle_rebuild_from_scan` skip when PRICE_SOURCE=parquet (no self-chain → killed the in-flight loop on next iteration) + EventBridge rule `rigacap-prod-pickle-rebuild` DISABLED. Loop dead, 0 OOMs. **Pickle freshness as a read-fallback is now stale-by-design; the proper fix is a parquet-native append job (still TODO).** LESSON: any full-universe/full-pickle job is an OOM landmine in parquet mode — audit them.

## 📅 HOLIDAY CALENDAR → pandas_market_calendars (Jun 21 2026)
Jun 19 2026 (Juneteenth) was MISSING from the hand list → the Fri scan treated it as a trading day → expected a Jun-19 SPY bar, 271s Alpaca-settlement stall, yfinance delisting-error wall, stale-data ABORT → no snapshot + 2 spurious "HELD" admin emails (double_signals 21:00 + daily_emails 22:00 both check _is_trading_day but it read the incomplete list). FIXED: (1) added Juneteenth to 2026/2027 hand lists; (2) **swapped is_us_trading_day to pandas_market_calendars (NYSE) as PRIMARY**, cached per-container ~3yr window, hand list = fallback if the lib import fails (commit ba0b83c, pmc==4.4.1, verified live on Lambda no-fallback); (3) daily_scan now has an explicit is_us_trading_day guard at the top (skip cleanly on weekends/holidays before any settlement stall); (4) fixed stale-data abort admin alert passing a User obj instead of email str (`'User' object has no attribute 'lower'` → it silently failed to notify). All shipped Jun 20-21.

## 🩹 HOTFIX (Mon Jun 22) — holiday guard crashed the scan (UnboundLocalError)
The Jun 20 holiday guard used `ZoneInfo` at main.py:1224, but ZoneInfo is re-imported LATER in the same function (the freshness gate, ~line 1292) → Python makes the bare name a function-local for the whole scope → `cannot access local variable 'ZoneInfo'` → the ENTIRE daily scan crashed on the FIRST trading day after the holiday fix (today). Dashboard stuck at Jun-18, double_signals + daily_emails correctly HELD (freshness gate working). FIXED (commit after ba0b83c): distinct local alias `_ZoneInfo` in the guard. Recovered: re-ran daily_scan → 15 signals fresh Jun-22, held digest sent to 3 subs. **LESSON (2nd time this week): py_compile does NOT catch UnboundLocalError — must run an IMPORT smoke (`python -c "import main"`-equivalent) before pushing hot-path changes. I skipped feedback_smoke_locally_before_deploy on both the holiday-fix push AND earlier. Smoke hot-path edits, every time.**

## ⚠️ PARQUET TEETHING (the "few days of growing pains" — active)
- **RECOVERY CHANGED:** in parquet mode, no-fetch rebuilds (`export_dashboard_cache`) give STALE signals (parquet base is ~1 day old, Jun-15). **Recovery = re-run `{"daily_scan": true}`** (it fetches today's bars), NOT export_dashboard_cache. The old runbook's one-shot is wrong now.
- Store freshness (parquet base advancing) not yet automated — the scan fetches on top each day; proper incremental-append is a follow-up. Universe-history snapshot now ranks ~603 (was 5020) — self-consistent but wire a periodic full-universe refresh.
- **CLEANUP PENDING (strip tomorrow):** temp instrumentation `[DASH-DIAG]`/`[LEN-DIAG]` in signals.py, `diag_scan_build` + `rebuild_snapshot` events in main.py (rebuild_snapshot has a `data_cache={}` cache-clear footgun — remove). 
- **AGE FIELDS BUG (open):** dashboard `days_since_entry=44` for NBIS (entered Jun 15 = ~2d) — find_ensemble_entry_date computes the BACKTESTER entry, not the live-book entry; "day N" labels not trustworthy. Dashboard-data fix, separate from the digest.

## Digest rework (Jun 17, shipped) — lead with active, never open with "0"
On a no-new-crossover day the email LED with "New Today (0) / No new signals" (read like the empty-bug despite 7 active). Fixed: (1) email_service body leads with the active set (slim "No new entries today — N active below" line; centered notice only on a truly-empty day; Open cap 6→10). (2) SUBJECT leads with active count ("N signals active · M approaching"), never "0 new". (3) scheduler.send_daily_emails reads buy_signals from the DASHBOARD cache (was ensemble_signals DB → 6 vs context's 7) so email == site == briefing. Sent to all 3 subscribers Jun 17 eve.

# (HISTORICAL / SUPERSEDED below — the Jun-15 "it's the memory cap" diagnosis was WRONG for the 0-signal; kept for the OOM facts which ARE real)

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
