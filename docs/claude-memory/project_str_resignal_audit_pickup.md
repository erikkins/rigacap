---
name: STR re-signal audit + backfill (May 4-5, 2026 — completed)
description: Audit + backfill of missed STR re-signal events; production entries dedup also fixed
type: project
originSessionId: c3d0833d-cb3f-474f-8dd8-e530f3300c60
---
Cleanup session that ran across May 4 evening → May 5 morning. Fully resolved.

**Root cause:** pre-`a4f0c41` `process_signal_track_entries` blocked any-already-open-symbol, silently dropping every re-signal of a held position. After Erik's "true start day" of 2026-04-15, several real signal events were dropped.

**Why STR's logical PK is (symbol, ensemble_entry_date):** a single signal stays `is_fresh=True` across multiple scan days. We want one STR row per unique signal *event*, not one per fresh-day. Erik's framing: "it should be on FIRST entry date".

**What shipped:**
- `9a967a9` — STR endpoint 500 fix (`dual_source_provider` → `market_data_provider`, hoisted to module level for deploy-time typo catch)
- `cef0c8b` — reverted scanner_service hoist back to local import (preserved file's prevailing pattern)
- `69d0b51` — STR 0% P&L fallback to `s3://...prices/{symbol}.csv` tail-read (close at column 5)
- `cbedf67` — `audit_str_resignals` worker action (dry-run, raw fresh-day count)
- `f362818` — audit tightened: dedup to (symbol, ensemble_entry_date), filter against existing STR rows' signal_data_json
- `e430fad` — `backfill_str_resignals` worker action with daily walk-forward exit simulation (12% trailing stop + Panic-Crash regime exit, mirrors `process_signal_track_exits` exactly minus state.current_cash + social-content)
- `6a9663c` — production `process_signal_track_entries` dedup matched to audit's PK; signals with null ensemble_entry_date are now skipped defensively

**Backfill outcome (May 5 11:32 AM CT):**
- 6 missed events inserted: RIOT, AMZN, AVGO (eed 4/13), NVDA (eed 4/16), GOOG, GOOGL (eed 4/30)
- RIOT closed historically on 4/29 via trailing_stop at -8.27%
- Other 5 still open as of 5/4 EOD; HWMs verified by hand-walking AMZN's full 11-day window
- Re-audit after insert: existing_str_rows 13 → 19, captured_event_count 13 → 19, missed 0

**How to apply:** This work is done. Future-relevant patterns:
- Worker actions for STR maintenance: `audit_str_resignals`, `backfill_str_resignals` (dry_run defaults true)
- Snapshot archive lives at `s3://...snapshots/<YYYY-MM-DD>/dashboard.json` and is permanent
- Per-symbol close history at `s3://...prices/<SYMBOL>.csv`, header `date,open,high,low,close,volume,atr,dwap,ma_50,ma_200,vol_avg,high_52w` (close at index 4)
- API Lambda's scanner_service.data_cache is unreliable; the S3 close fallback added in `69d0b51` is the canonical "what was today's close" for any admin endpoint
