---
name: AWS Lambda memory cap stuck at 3008 MB — support tier blocker
description: AWS support tier doesn't permit a service-quota increase above 3008 MB Lambda memory. Confirmed May 14 2026. Parquet migration is the real unblock; no point pursuing AWS ticket without a support-plan upgrade.
type: project
originSessionId: c3d0833d-cb3f-474f-8dd8-e530f3300c60
---
The Worker Lambda is capped at **3008 MB** memory and the AWS support tier on this account does not permit a service-quota increase above that ceiling. Confirmed May 14 2026.

This is a real architectural constraint, not a "waiting on AWS" situation. The Terraform comment (`main.tf` line 975) says "verified May 3 2026" — that holds.

## What this means

**Do NOT propose:**
- Bumping `memory_size` above 3008 in Terraform (will fail apply)
- Filing another AWS quota-increase ticket (the cap is tied to support plan, not request count)
- Suggesting `memory_size = 10240` or any value > 3008 as "the simple fix"

**Cost-realistic alternatives:**
- Business support ($100/mo + 10% usage) would unlock the quota — but that's a real recurring cost for what may be solved another way
- Enterprise support ($15K/mo min) — out of scope

**The actual solution:** parquet migration. Post-cutover, workers partial-read by symbol filter rather than holding the full 700 MB pickle in process. Frees up the bulk of the memory footprint without touching Lambda config.

## Active workarounds

1. **`periods_limit=1`** on nightly-WF chunked runner (shipped May 14 after OOM). Halves per-chunk memory at the cost of more chunks. Each chunk now finishes 3-5 min with plenty of headroom under 3008.
2. **Pickle stays on Worker only.** API Lambda runs at 1024 MB and would OOM if it ever loaded the pickle. Worker is the only Lambda allowed to hold it.
3. **10y pickle research jobs run locally via Docker** (per Terraform comment), not in Lambda. Local has no memory cap.

## When this could change

- Support plan upgrade (cost decision)
- Parquet migration completes (most likely)
- AWS raises the default cap for all Basic-tier accounts (unlikely; the 2020 raise to 10240 only went to some accounts)

## Connected

- `project_parquet_divergence_blocker.md` — parquet migration status; now blocker-priority for memory mitigation
- `project_storage_migration_roadmap.md` — overall parquet plan
- Terraform: `infrastructure/terraform/main.tf` line 975 has the inline comment
