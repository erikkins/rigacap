---
name: WAF bypass closed via CloudFront origin shared-secret header (DONE May 7 2026)
description: Direct-execute-api WAF bypass closed. CloudFront injects X-Origin-Verify, FastAPI middleware rejects requests without it. Secret lives in Terraform state + CloudFront origin config + Lambda env var.
type: project
originSessionId: 1081317d-f863-470f-ab07-65ddc614e856
---
**STATUS: SHIPPED May 7 2026** in commit `8bd0305` + Terraform apply. Validated end-to-end:

- `https://api.rigacap.com/api/market-data-status` → 200
- `https://0f8to4k21c.execute-api.us-east-1.amazonaws.com/api/market-data-status` → **403 Forbidden**

## Implementation summary

1. **`random_password.cloudfront_origin_secret`** in Terraform — 48-char alphanumeric, generated once. Lives in TF state (`infrastructure/terraform/terraform.tfstate`).
2. **CloudFront API distribution origin** has a `custom_header` block named `X-Origin-Verify` with the secret as value.
3. **API Lambda env var** `CLOUDFRONT_ORIGIN_SECRET` set to the same value via Terraform.
4. **`backend/app/core/origin_guard.py`** — FastAPI middleware compares `X-Origin-Verify` header to env var via `hmac.compare_digest`. Exempts OPTIONS preflight + `/health`. No-ops if env var is empty (so local dev / partial deploys don't break).

## Where the secret lives (3 copies)

| Location | Authoritative? |
|---|---|
| `terraform.tfstate` (local file at `infrastructure/terraform/`, gitignored) | Yes — TF source of truth |
| CloudFront distribution origin custom_header | Set by TF, drift-detectable |
| API Lambda env var `CLOUDFRONT_ORIGIN_SECRET` | Set by TF, drift-detectable |

If TF state is intact, all three stay in sync via `terraform apply`. If any drift, TF will overwrite the stale copy.

## DR / continuity caveats

- **TF state is local-only on the operator's laptop**, no remote backend. If the laptop dies, state is gone. The CloudFront config and Lambda env var will still hold the working secret — production keeps running — but managing those resources via Terraform requires either re-importing them OR letting `terraform apply` generate a new secret and atomically update both surfaces (both the CloudFront origin and Lambda env var change in the same apply, so the service stays consistent).
- **The secret itself is non-sensitive in a recovery sense** — losing it just means generating a new one. There's no data tied to it; rotation is one TF apply.
- **Full us-east-1 outage:** everything is down (Lambda, RDS, S3, ECR, API GW are all single-region). The shared secret is the smallest of many DR concerns in that scenario.

## Rotation

`cd infrastructure/terraform && AWS_PROFILE=rigacap terraform taint random_password.cloudfront_origin_secret && terraform apply`. Atomic — both CloudFront origin and Lambda env var update in the same apply, no downtime window.
