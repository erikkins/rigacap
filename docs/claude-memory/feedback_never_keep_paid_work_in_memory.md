---
name: NEVER accumulate paid/long-running work in memory
description: Any script that consumes money OR takes >5 min MUST checkpoint to disk every N units. No exceptions.
type: feedback
originSessionId: c3d0833d-cb3f-474f-8dd8-e530f3300c60
---
**Rule:** Any script that consumes money (Claude API, paid data feeds) OR runs longer than 5 minutes MUST write incremental checkpoints to disk. Never accumulate results in memory only to flush at end.

**Why:** Jun 3 2026 — Haiku scorer ran 50 minutes burning $2.43 on 210k news articles, ZERO durable saves. When user had to kill it (API credit balance), all 2,800 completed batches were lost. Re-running cost the same $2.43 again from scratch. Avoidable waste.

**How to apply:**
- Every N units of work (where N = 1-2 min of progress OR $0.10-ish of cost), call `checkpoint()` → write partial parquet/csv/json to disk
- Use `--resume` flag pattern: re-read checkpoint on startup, skip already-done units
- Same rule for any local long-running compute (FinBERT batch, parquet generation, multi-hour ML training)
- Checkpoint cadence beats end-of-run cleverness EVERY TIME. Don't optimize "elegance" by waiting until the end to write — that's a single point of failure
- This rule overrides "premature optimization" gut instinct. Cheap, immediate checkpointing is the correct default for ANY paid or long-running pipeline
