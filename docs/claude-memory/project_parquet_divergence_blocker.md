---
name: Parquet divergence blocker — RESOLVED (May 13 2026), clean-window clock running
description: Stage 3a diff harness flagged thousands of structural divergences early May; root-caused to pickle-side schema drift (not parquet bugs) and fixed across two passes. First clean 24h window observed May 12-13. 7-day clean clock starts now.
type: project
originSessionId: c3d0833d-cb3f-474f-8dd8-e530f3300c60
---

**RESOLVED May 13 2026.** Pipeline-health email showed `Parquet Divergence: 0 events / 24h` — pickle and parquet in lockstep. First clean day of the 7-day window needed before Stage 3b cutover.

## What the bug actually was

NOT a parquet bug. Three pickle-side schema inconsistencies that parquet's strict-schema concat-union exposed:

1. **88% — `_ensure_indicators` trigger too narrow.** Only checked `dwap` for missing/stale-tail, so symbols that already had dwap but never had `atr` stayed atr-less in pickle forever. Parquet's `pd.concat` union NaN-filled atr for them on write → `column_set_diff` on every comparison.

2. **8% — Recently-added thin-history symbols** had no indicators at all. Would have healed naturally from #1's fix on next ensure-indicators call, but the narrow trigger blocked it.

3. **4% — `^VIX` / `^GSPC` index inconsistency.** Created via a `yf.download` path that skipped `set_index('date')`, leaving `index.name=None`. Everywhere else in pickle and ALL of parquet uses `'date'`. Parquet's import-roundtrip always sets it, so the diff harness saw 'date' as `only_in_parquet`.

## What we shipped (May 12 2026)

- `scanner.py:_ensure_indicators` — trigger now checks every column in `EXPECTED_INDICATORS = ('dwap', 'ma_50', 'ma_200', 'vol_avg', 'high_52w', 'atr')` for missing or NaN-tail; recomputes on any.
- `data_export.py:_import_from_s3` + `:export_pickle` — both normalize `index.name='date'` across all symbol DataFrames. Belt and braces: heals existing in-memory cache on load AND keeps persisted state canonical on write.
- `main.py:pickle_rebuild_from_scan` (deferred write path) — same index.name normalization applied here too, since it bypasses `export_pickle`.
- `main.py:parquet_alignment_heal` event — one-time forced reload + per-symbol `_ensure_indicators` + re-export. Ran successfully May 12: 4814 symbols loaded, 57 gained indicator columns, exported cleanly.
- `main.py:pickle_validate` event — standalone pickle health-check (schema, freshness, value sanity, row distribution). Verdict came back `structural_clean: true, ready_for_parquet_cutover: true`.
- `main.py:parquet_divergence_inspect` event — diagnostic that groups raw events by shape so future investigations don't require ad-hoc SQL.

## Process win

The user's rule from this session, now memory-pinned (`feedback_parquet_fix_not_silence.md`): when the diff harness flags a divergence, ask "if parquet were already primary, which side is correct?" Align parquet with target behavior. Never broaden "explainable" just to make the warning go away. That principle held — we fixed pickle-side schema instead of widening the diff harness's allow-list, and the schema we landed on is the one parquet-primary will deliver post-cutover.

## What's next

- **7-day clean clock now running** (Day 1 = today). If divergence stays at 0 every day, the Stage 3b cutover gate is met by ~May 20.
- **Two consecutive weekly runs** with structural diff = 0 before flipping parquet to primary (the conservative gate from the original plan, kept).
- **Then Stage 3b** — shadow-read cutover (parquet read in parallel, pickle remains authoritative for writes).
- **Then ~mid-June** — parquet promoted to primary; pickle demoted to shadow.
- **Then ~end June / early July** — pickle decommissioned.

## Loose end

The validator also flagged **69 stale symbols** in the pickle (>4 days old without updates). Not a parquet blocker (same data on both sides → no divergence) but a hygiene-layer gap — these are likely delistings / SPAC mergers that Layer 2 should be quarantining. Track separately, don't conflate with the parquet work.

## Connected

- `project_storage_migration_roadmap.md` — overall four-stage plan.
- `project_parquet_stage3_plan.md` — Stage 3 work packages, 2-week observation gate.
- `feedback_parquet_fix_not_silence.md` — the principle.
- `project_pickle_fix_apr1.md` — the indicator-strip-on-incremental nuance that explains why dwap-only-trigger was insufficient.
- `project_dr_posture.md` — parquet migration eliminates pickle as DR concern; this unblock matters.
