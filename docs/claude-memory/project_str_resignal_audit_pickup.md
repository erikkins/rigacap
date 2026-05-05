---
name: STR re-signal audit pickup (May 4 → next session)
description: Mid-task state for tightening the audit_str_resignals worker action and backfilling missed re-signals
type: project
originSessionId: c3d0833d-cb3f-474f-8dd8-e530f3300c60
---
Pickup point for tightening the STR re-signal audit before backfill.

**Why:** a4f0c41 fixed the dedup bug (re-signals create new STR rows) but deployed at 8:19 PM ET on May 4 — too late for that day's 4:43 PM ET entry job. Older days (Apr 15→May 4) silently skipped re-signals under the old "any-open-symbol blocks" dedup. User wants those backfilled.

**Status as of pause (May 4 ~9:30 PM CT):**
- 0% P&L fix shipped (commit `69d0b51`) — S3 daily-close CSV fallback live.
- Audit action shipped (commit `cbedf67`) — `aws lambda invoke ... '{"model_portfolio":{"action":"audit_str_resignals"}}'`.
- First audit run found **22 raw missed rows / 15 unique (symbol, ensemble_entry_date) events** for window 2026-04-15 → 2026-05-05. Output saved at `/tmp/audit.json` on Erik's machine (may be gone).
- The 22 over-counts because a single signal stays `is_fresh` for several days; each fresh-day produces a row.

**How to apply:** Next session, do this:

1. **Tighten the audit** so it only returns the FIRST fresh day per `(symbol, ensemble_entry_date)`, AND filters out events already captured by existing STR rows (read `signal_data_json` from each STR row to extract its captured `ensemble_entry_date`). True missed re-signals only.
   - Edit: `backend/app/services/model_portfolio_service.py` → `audit_str_resignals`
   - Build `existing_eed_keys = set((p.symbol, json.loads(p.signal_data_json or "{}").get("ensemble_entry_date")) for p in existing if p.signal_data_json)`
   - Skip dates seen earlier in the loop for the same `(symbol, ensemble_entry_date)` (only first fresh day kept)
   - Skip events present in `existing_eed_keys`
2. **Re-run the audit.** Expected true misses (from initial analysis): GOOG 4/30, GOOGL 4/30, possibly CRWV 4/13 / CIFR 4/14 / RIVN 4/22 / AMZN 4/13 if they're not in closed STR rows.
3. **Add `backfill_str_resignals` worker action** that takes the audit output and inserts ModelPosition rows. `entry_date` = the first-fresh-day in the audit (the day STR *should* have entered). `entry_price` = signal's price on that day. `signal_data_json` = the snapshot signal dict.
4. **Run backfill, then verify** the STR endpoint now shows GOOG / GOOGL twice (Apr 15 + Apr 30 / May 1 entries).

**Constraint:** STR's logical PK is `(symbol, ensemble_entry_date)`, not `(symbol, calendar day)`. The current production code in `process_signal_track_entries` (post-a4f0c41) dedups by same-calendar-day, which means a signal that stays fresh for 5 days will create 5 STR rows going forward. That's a bug too — should also dedup by ensemble_entry_date when entering. Defer that fix; flag for next session.

**Audit window default:** `start_date=2026-04-15` (per Erik: "Apr 15 is our true start day with clean data and a reliable strategy"), `end_date=today`.
