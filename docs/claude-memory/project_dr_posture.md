---
name: DR posture and gaps — single-region stack, no active failover
description: Current production is single-region us-east-1. Realistic cold-rebuild ETA 4-12 hours dominated by RDS restore + ACM cert dependency. Logged after the May 7 2026 WAF-bypass work surfaced TF state on laptop.
type: project
originSessionId: c3d0833d-cb3f-474f-8dd8-e530f3300c60
---
The stack runs in `us-east-1` only. If the region goes hard down, the system is down. There is no active DR or warm standby. This note captures the current posture and the cheapest improvements.

**Why this matters:** subscriber-facing service (signal generation, dashboard, emails, social publishing) is single-region. CloudFront and Route 53 are global so the ingress survives, but every backend is in us-east-1. A multi-day regional outage means the product is offline.

**How to apply:** if user wants to invest in DR, the priority order in the Improvements section gets you most of the value cheaply. Start with remote Terraform backend (~30 min, no AWS cost). Cross-region RDS snapshots are the next-cheapest insurance. Active multi-region is a significantly bigger lift and usually not warranted at current revenue scale.

## What's where

| Component | Region | Recoverable how? |
|---|---|---|
| Lambda (API + Worker) | us-east-1 | Image in us-east-1 ECR; ~1 hr to push to second region's ECR + recreate |
| RDS `rigacap-prod-db-v2` | us-east-1 | Automated backups regional only; **cross-region snapshot copy not configured** |
| S3 price-data bucket | us-east-1 | Single region; pickle is 269 MB and regenerable in 1-2 hr from market data sources |
| S3 frontend bucket | us-east-1 | Single region; build artifact, fully regenerable from CI/CD |
| ECR | us-east-1 | Single region; image rebuildable from git but slow |
| API Gateway HTTP API | us-east-1 | Recreatable in ~10 min via `terraform apply` |
| ACM cert (CloudFront) | us-east-1 (required) | If us-east-1 is fully gone, can't issue or use — hard blocker for `api.rigacap.com` HTTPS |
| CloudFront, Route 53 | Global | Survive regional outage |
| Terraform state | Local laptop | **Single point of failure for IaC management** |

## Realistic ETAs

- **Laptop failure, AWS healthy:** Stack keeps running (CloudFront + Lambda + RDS + S3 are unaffected by losing TF state). Re-establishing TF management requires `terraform init` against a remote backend (if we set one up) or `terraform import` for each resource (hours of mechanical work). The shared CloudFront origin secret has three copies (TF state, CF config, Lambda env) so its loss only matters for managed rotation.
- **Full us-east-1 outage, hours to days:** product is down. Cold rebuild in another region: **4-12 hours** dominated by RDS restore (or accept data loss back to last cross-region snapshot) and ACM cert reissue (depends on whether DNS validation works during the outage).

## Improvements ranked by cost vs value

1. **Remote Terraform backend (S3 + DynamoDB lock)** — no AWS cost (S3 backend bucket + DynamoDB on-demand both free at this scale). Removes laptop SPOF for IaC. ~30 min setup. **Doing this May 7 2026.**
2. **Cross-region RDS automated-snapshot copy** — pennies/month, copies daily backups to us-west-2. Collapses DB recovery to "restore the latest copy in target region" instead of "wait for us-east-1 to come back." 1-2 hr setup including IAM.
3. **Parquet migration finishing** — removes the pickle entirely; price data lives in S3 partitioned parquet which is trivially S3-CRR-replicable. Targeted next 1-2 weeks per parquet stage 3 plan. **This collapses S3-side recovery to a near-zero concern.**
4. **S3 CRR on critical buckets** — pennies/month for the small frontend bucket; bigger for price-data (until parquet collapses it). Worth doing on frontend now; defer price-data CRR until post-parquet.
5. **Documented region-failover runbook** — collect the variables that need flipping (`aws_region`, `domain_name` aliases, ACM cert region) into a tested runbook. Would let any operator (not just Erik) execute a rebuild. Multi-hour effort, dominated by *testing* it actually works in a sandbox.
6. **Active multi-region** (warm standby in us-west-2) — significantly more cost (duplicated Lambda, RDS read replica, etc.) and ops complexity. Not warranted at current scale.

## What changes after parquet ships

- Pickle disappears as a DR artifact. Price data lives as partitioned parquet files in S3, trivially replicable cross-region with one `aws s3 sync` or via S3 CRR.
- The "regenerate pickle from market data" step (1-2 hr in current cold-rebuild ETA) drops to "point reads at the replicated bucket" (seconds).
- Net: cold-rebuild ETA drops from 4-12 hours to ~2-4 hours, dominated by RDS restore.
