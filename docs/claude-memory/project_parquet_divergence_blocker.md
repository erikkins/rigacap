---
name: Parquet divergence blocking Stage 3b cutover (May 8 2026)
description: Stage 3a parallel-read diff harness flagged 4632 structural divergences in 24h (1 value_diff, 4631 row_count_diff) plus 9381 total. Stage 3b cutover blocked until diff reaches zero. Investigate /api/admin/parquet-divergence for sample diffs.
type: project
originSessionId: c3d0833d-cb3f-474f-8dd8-e530f3300c60
---
The May 7-8 hygiene email surfaced a Storage Migration block:

```
❌ Parquet Divergence — 4632 structural / 9381 total
Structural divergences in last 24h: value_diff=1, row_count_diff=4631
→ Inspect /api/admin/parquet-divergence for sample diffs.
   Pause Stage 3b cutover until resolved.
```

**Why this matters:** Stage 3a is the parallel-read diff harness comparing pickle (authoritative) vs parquet (shadow). It exists precisely to catch divergences before the Stage 3b cutover that makes parquet the primary read source. **4632 structural divergences across ~4,750 symbols means almost every symbol differs in row count between pickle and parquet.** That's not a near-miss; that's a systemic write-path or read-path bug.

**How to apply:** Do not cut over Stage 3b until divergence reaches zero or is reduced to a small, explainable set (e.g., known partition-edge cases). User explicitly wants to move off pickle directionally, so this is the critical path — but cutting over with this much divergence would silently corrupt signal generation.

## Triage path

1. **`GET /api/admin/parquet-divergence`** — endpoint returns sample diffs. Look at the per-symbol breakdown:
   - Are the row-count diffs bounded (e.g., parquet always has N fewer rows per symbol)? Suggests a partition / write-cutoff bug.
   - Are they random (some symbols 5 fewer, some 50 more)? Suggests filter mismatch in the diff harness itself.
   - Is the 1 value_diff a known indicator-recompute case (e.g., recently re-fetched split-adjusted bars)?

2. **Compare Stage 2 write logic**. Stage 2 deployed before Apr 28 (commit `21f9e51`). The parquet writes happen in `data_export_service.export_parquet()` — verify the write filter matches the pickle's filter. Specifically:
   - Are excluded ETFs being skipped on the pickle write but included on the parquet write (or vice versa)?
   - Is the universe-of-symbols set the same?
   - Are date-range filters the same?

3. **Read-path symmetry**. The harness reads from both stores using `compare_pickle_to_parquet` (memory `project_parquet_stage3_plan.md` references batched pyarrow filter reads). If the parquet read filter has a date or symbol predicate that doesn't match the pickle read, every symbol would diverge.

4. **Most likely root cause** (ranked):
   - **Partition column mismatch**. Parquet writes are partitioned by date or symbol; if the harness reads without setting the partition predicate correctly, it reads a subset of rows that doesn't match the pickle's full slice.
   - **Indicator-column inclusion**. The `fetch_incremental` shrink fix (Apr 1, memory `project_pickle_fix_apr1.md`) drops indicator columns on incremental writes; if parquet retains them while pickle drops them, schema-level diff shows up. But that wouldn't cause row-count diffs, only column / value diffs.
   - **End-of-history cut**: parquet writer commits at a different timestamp boundary than the pickle exporter. Especially likely on the day a daily scan runs — parquet has today's bar, pickle hasn't been re-exported yet (or vice versa).

## Connected

- `project_storage_migration_roadmap.md` — overall four-stage plan, Stage 2 ✅, Stage 3 in progress.
- `project_parquet_stage3_plan.md` — six work packages with the parallel-read diff harness and 2-week observation window. The 9381 24h count is the cumulative tally during this observation window.
- `project_pickle_fix_apr1.md` — the indicator-column-drop nuance that affected pickle shape; verify parquet write path matches.
- `project_dr_posture.md` — parquet migration is the recommended fix that eliminates pickle as a DR concern; this divergence blocks that benefit.

## What "resolved" looks like

- Structural divergence in the daily 24h window drops to <50 (small, explainable, ideally zero).
- Stage 3a observation window resumes for at least 7 fresh days at the new low divergence level before Stage 3b cutover begins.
- Pickle remains authoritative throughout. Do not flip parquet to primary until two consecutive weekly runs pass with structural diff = 0 and value diff < 5.
