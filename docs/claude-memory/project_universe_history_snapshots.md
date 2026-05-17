---
name: Universe history snapshots — durable record of daily ranking pool
description: Daily JSON snapshots of the full liquidity-ranked universe at S3 signals/universe-history/{date}.json. Shipped May 17 2026 after the SIGNAL_UNIVERSE_SIZE audit. Future rank-attribution queries read directly instead of reconstructing from pickle.
type: project
originSessionId: c3d0833d-cb3f-474f-8dd8-e530f3300c60
---
Daily snapshot of the full liquidity-ranked universe at scan time. Persistent S3 record so any future audit can answer "where did rank N go" without reconstructing from the current pickle (which has survivorship-bias edge cases — delisted symbols, exclusion-set drift, etc.).

## Location

`s3://rigacap-prod-price-data-149218244179/signals/universe-history/{YYYY-MM-DD}.json`

~500 KB per day raw JSON. Append-only — `snapshot_universe_history()` refuses to overwrite an existing snapshot. User directive: "any data is great...never delete data!"

## What's captured

```json
{
  "snapshot_date": "2026-05-17",
  "snapshot_time_utc": "2026-05-17T...",
  "total_eligible_symbols": 4815,
  "excluded_count": 423,
  "signal_universe_size_setting": 500,
  "excluded_symbols_in_universe": ["TQQQ", "SQQQ", ...],
  "rankings": [
    {"symbol": "AAPL", "rank": 1, "avg_volume_60d": ...,
     "last_close": ..., "last_date": "...", "is_excluded": false},
    ...
  ]
}
```

Every symbol with ≥60 days of history as of snapshot_date is in `rankings`, sorted by 60-day avg volume descending. Survivorship-bias-free.

## Three entry points

| Use | Payload |
|---|---|
| Today's snapshot (chained from daily scan) | `{"universe_snapshot": {"_": 1}}` |
| Specific historical date | `{"universe_snapshot": {"date": "YYYY-MM-DD"}}` |
| Chunked backfill across range | `{"universe_snapshot_backfill": {"start_date": "...", "end_date": "...", "max_per_run": 200}}` |

The daily-scan handler auto-chains today's snapshot at the end (alongside csv export + user portfolio recompute). No manual action needed for going-forward capture.

## Backfill expectations

5 years × ~252 trading days = ~1,260 days. At ~500 KB each ≈ **~630 MB total** in S3. Done in chunks of 200 dates per Lambda invocation to stay under timeout.

## Why this matters

The May 17 2026 SIGNAL_UNIVERSE_SIZE 100→500 investigation found that 70% of WF trades came from rank 101-500 — but the audit had to RECONSTRUCT each historical ranking from the current pickle, which has caveats: delisted symbols missing, exclusion list (`_EXCLUDED_SET`) is today's not history's, universe membership drift. The reconstruction was good enough for that audit but not authoritative.

Going forward, any rank-attribution query reads the snapshot directly. Bit-for-bit deterministic.

## Connected

- `feedback_wf_prod_parity.md` — the parity rule that drove the original audit
- `project_signal_slippage_tracking.md` — analogous "capture data we'll wish we had" project
- `feedback_data_provider_cache.md` — "never re-fetch from data providers" sister rule
