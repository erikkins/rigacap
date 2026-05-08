---
name: Hygiene-email threshold follow-ups (May 8 2026)
description: Three "Needs Attention" items in the daily data-hygiene email that still surface as dead-end warnings rather than auto-resolving or being one-click actionable. Symbol-triage v1 (May 7) handled the per-symbol case; these are the bulk / threshold cases.
type: project
originSessionId: c3d0833d-cb3f-474f-8dd8-e530f3300c60
---
After the symbol-triage v1 ship on May 7 2026 (commit `9be3299` + spacing/auth follow-ups), three classes of "Needs Attention" items still land in the daily hygiene digest with no actionable path:

1. **Ticker-reuse cases** (e.g. CCL, TRI on May 7). Logged separately at `project_ticker_reuse_triage_ui.md` — needs a diff-view triage page with confirm-quarantine / restore-active / migrate-to-new-symbol actions. ~half day.

2. **Missing-in-Alpaca count above the 20 threshold** ("⚠️ 63 symbols missing in Alpaca"). Currently a single critical-flag line; the per-symbol triage page handles individual cases but the threshold itself is a quantity warning with no resolve path. Two options:
   - **Auto-prune at a safe default**: anything missing >14 days that's not in an open position gets auto-quarantined (already happens for >30d at `symbol_metadata_service.py:225`). Tightening from 30d to 14d would cut the chronic count down faster and the threshold warning would mostly self-heal.
   - **One-click "investigate batch" action** in the email: link to a list view of all `investigate` rows with multi-select + bulk-resolve buttons. Reuses the per-symbol triage AI summary cached per symbol.
   
   Option A is ~30 min. Option B is ~half day.

3. **Universe dirty count above the 1500 threshold** ("⚠️ Universe dirty count 1503 above 1500 threshold"). The dirty count is symbols with corrupted indicators (failed quality filters in `_is_data_quality_ok`). 1503/4753 = 31.6% — that's a lot, and growing slowly. Two options:
   - **Auto-rebuild dirty indicators** in the nightly hygiene job: any symbol with corrupt `dwap`/`ma_50`/`ma_200` triggers a re-fetch of split-adjusted history + indicator recompute. Already partially happens for split-detected symbols; expanding to all dirty rows would shrink the count.
   - **Raise the threshold** to a value that's signal rather than noise (e.g., alert when growth rate exceeds X%/week, not absolute count). The absolute number isn't actionable; the trend is.
   
   ~30 min for the threshold-as-rate change. ~1-2 hr for the bulk re-fetch.

## Recommended order (when next session has time)

1. **Tighten auto-quarantine to 14d** (option 2A) — instantly reduces email noise. ~30 min.
2. **Threshold-as-rate for universe dirty count** (option 3 second variant) — converts a chronic warning into a signal that means something. ~30 min.
3. **Ticker-reuse triage page** (`project_ticker_reuse_triage_ui.md`) — most of a day.
4. **Bulk dirty-symbol re-fetch** — only if the auto-quarantine + rate-threshold changes don't bring the email back to a clean slate.

## Why these were deferred

User got the cleaner-spacing email on May 7, confirmed it was readable, asked specifically about what `mark-delisted` does on the backend, fixed the universe-exclusion gap, then explicitly said "but that's for tomorrow" for the threshold items. End of session for May 7 2026.
