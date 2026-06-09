# Path A — Front API Gateway with CloudFront for WAF Coverage

> **Status:** Proposed plan, not yet executed.
> **Goal:** Bring the same WAF protection to `api.rigacap.com` that we just shipped to the frontend, without migrating off API Gateway HTTP API v2.
> **Estimated effort:** 3-4 hours focused work + ~15 min DNS propagation + monitoring window.
> **Estimated cost:** +~$5/mo CloudFront (new distribution) + $0/mo WAF (reuse existing ACL — supports multiple distributions).

## Why this plan exists

AWS WAFv2 doesn't support API Gateway HTTP API v2 (`aws_apigatewayv2_api`) directly. The two viable paths to put WAF on `api.rigacap.com` are:

1. Migrate to API Gateway REST API v1 (1-2 days; ongoing 3.5× per-request cost).
2. **Front the existing API Gateway with CloudFront and put WAF on the new CloudFront** (this plan).

Path 2 is the right call: small effort, no API/auth/client changes, keeps the cheap HTTP API pricing.

## Current state

```
Frontend:   rigacap.com → CloudFront (WAF ✓) → S3
API:        api.rigacap.com → API Gateway HTTP API → Lambda
```

Source-of-truth resources in `infrastructure/terraform/main.tf`:

- `aws_apigatewayv2_api.main` — the HTTP API
- `aws_apigatewayv2_domain_name.api` — custom domain wrapper for `api.rigacap.com`
- `aws_apigatewayv2_stage.default` — the `$default` stage Lambda is wired to
- `aws_route53_record.api_record` — Route53 A-record alias for `api.rigacap.com` → API GW custom domain
- `aws_acm_certificate.main` + `_validation.main` — the wildcard cert covering `*.rigacap.com`
- `aws_wafv2_web_acl.cloudfront` — the CloudFront-scope WAF currently attached to the frontend distribution; reusable for the API distribution too

## Target state

```
Frontend:   rigacap.com → CloudFront (WAF) → S3
API:        api.rigacap.com → CloudFront (WAF, same ACL) → API Gateway HTTP API → Lambda
                                ↑ NEW LAYER
```

## Change set

### 1. New CloudFront distribution: `aws_cloudfront_distribution.api`

- **Origin:** the API Gateway regional execute-api endpoint (`<api-id>.execute-api.us-east-1.amazonaws.com`)
- **Aliases:** `api.rigacap.com`
- **Cache policy:** `CachingDisabled` on the default behavior — every request goes through to API GW (no caching by default; we can selectively cache idempotent GETs later if we want)
- **Origin request policy:** `AllViewer` — forward all headers (including `Authorization`), cookies, and query strings
- **Allowed methods:** `[GET, HEAD, OPTIONS, PUT, POST, PATCH, DELETE]` — full method set, since this is an API
- **Viewer protocol policy:** `redirect-to-https`
- **SSL cert:** existing ACM cert (`aws_acm_certificate_validation.main` covers `*.rigacap.com`)
- **WAF:** attach `aws_wafv2_web_acl.cloudfront` (same ACL, no extra cost)
- **`viewer-request` function:** none needed (no www→non-www complication for api subdomain)

### 2. Route53 update: `aws_route53_record.api_record`

Currently aliases to `aws_apigatewayv2_domain_name.api`. Update to alias to the new `aws_cloudfront_distribution.api` instead.

```hcl
# Before:
alias {
  name    = aws_apigatewayv2_domain_name.api.domain_name_configuration[0].target_domain_name
  zone_id = aws_apigatewayv2_domain_name.api.domain_name_configuration[0].hosted_zone_id
}

# After:
alias {
  name    = aws_cloudfront_distribution.api.domain_name
  zone_id = aws_cloudfront_distribution.api.hosted_zone_id
}
```

### 3. Keep `aws_apigatewayv2_domain_name.api` as-is

The custom domain wrapper stays. It's only used internally; CloudFront will hit the regional execute-api endpoint directly. No removal needed (and keeping it preserves a fallback if we ever want to bypass CloudFront for testing).

### 4. CloudFront WAF re-attach (optional, $0)

Either:
- **(a)** keep the existing single ACL attached to the frontend distribution, AND attach the same ACL to the new API distribution (multi-attach is supported up to 20 distributions). **Recommended.** Same rules; saves $9/mo vs creating a separate API ACL.
- **(b)** create a separate `aws_wafv2_web_acl.api_cloudfront` if we ever want to tune API-specific rate limits differently. Not necessary at launch scale.

Going with (a).

## Risks and mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| **CloudFront caches an authenticated response and serves it to another user** | Low (with `CachingDisabled`) | Default cache policy disabled on the default behavior; only opt-in caching on specific paths if added later. **Validate with: hit a paid endpoint as user A, then user B; confirm no cross-leak.** |
| **CORS regressions** | Low | API Gateway HTTP API already returns CORS headers; CloudFront with `AllViewer` origin request policy passes them through unchanged. **Validate with: browser console on rigacap.com → api.rigacap.com call; confirm 200 + CORS headers present.** |
| **Stripe webhook breaks** (POST to `api.rigacap.com/webhooks/stripe`) | Low | CloudFront supports POST and forwards body unchanged. Stripe signature verification reads raw body. **Validate with: test Stripe webhook event from Stripe dashboard.** |
| **Source IP logged as CloudFront IP, not user IP** | High | CloudFront sets `X-Forwarded-For`. **Audit Lambda code for any place reading client IP — must read from `X-Forwarded-For` header, not connection's source IP.** Most common spot: rate-limit Lambda code, abuse logging. |
| **DNS propagation lag — some users hit old endpoint, some hit new** | Low (<1 hour with TTL=60s) | Reduce TTL to 60s 24 hours before cutover (or accept short propagation window). Both endpoints serve same Lambda — no broken state, just inconsistent WAF coverage during the gap. |
| **Latency increase** | High (10-30ms certain) | Acceptable trade — none of our endpoints are hard-real-time. Live quote refresh tolerates 100ms+. |
| **CloudFront limits on POST size** | Low | CloudFront supports 20 GB POST; our largest API requests are admin payloads (a few KB at most). |

## Pre-flight checklist

1. [ ] Audit any Lambda code that reads client IP — must use `X-Forwarded-For` not connection IP. Search: `request.client.host`, `remote_addr`, `req.ip`.
2. [ ] Confirm the wildcard ACM cert covers `api.rigacap.com` (it should — `*.rigacap.com`).
3. [ ] Reduce `api.rigacap.com` Route53 TTL to 60s 24+ hours before cutover (so any rollback is fast).
4. [ ] Identify the API Gateway execute-api endpoint URL: `<api-id>.execute-api.us-east-1.amazonaws.com` (currently `0f8to4k21c.execute-api.us-east-1.amazonaws.com`).
5. [ ] Confirm Stripe webhook URL points to `api.rigacap.com/...` and not the API GW direct execute-api URL.

## Cutover sequence

### T-24h: Reduce DNS TTL

```bash
# Edit aws_route53_record.api_record TTL from 300 → 60
# (or keep alias-based — alias records use AWS internal TTL)
# Alias records use a 60s implicit TTL anyway, so this step may be a no-op.
```

### T-0: Apply CloudFront + DNS

```bash
cd infrastructure/terraform
AWS_PROFILE=rigacap terraform apply \
  -target=aws_cloudfront_distribution.api \
  -target=aws_route53_record.api_record
```

CloudFront distribution provisioning takes ~10-15 minutes. The Route53 alias update is near-instant once the CloudFront distribution is `Deployed`.

### T+15m: Validation

```bash
# 1. Resolve api.rigacap.com — should return CloudFront IP
dig api.rigacap.com

# 2. HTTPS request — should return 200 (or expected auth response)
curl -i https://api.rigacap.com/health

# 3. CORS — open browser console on rigacap.com, hit a real endpoint
# Confirm: 200 OK + Access-Control-Allow-Origin header

# 4. Auth — log in to dashboard, confirm protected endpoints still work

# 5. Stripe webhook — send test event from Stripe dashboard

# 6. WAF — confirm CloudFront metric `rigacap-prod-frontend-waf` shows
# api.rigacap.com requests being inspected
aws cloudwatch get-metric-statistics \
  --namespace AWS/WAFV2 \
  --metric-name AllowedRequests \
  --dimensions Name=WebACL,Value=rigacap-prod-frontend-waf Name=Region,Value=Global
```

### T+24h: Confirm + tighten

- Review WAF metrics: any false positives? Adjust managed rule overrides if needed.
- Review API Gateway / CloudWatch metrics: latency increase confirmed acceptable?
- Review Stripe webhook delivery success rate.

## Rollback plan

If anything breaks badly within the first hour: revert Route53 to point back at the API Gateway custom domain.

```hcl
# In aws_route53_record.api_record, change the alias back:
alias {
  name    = aws_apigatewayv2_domain_name.api.domain_name_configuration[0].target_domain_name
  zone_id = aws_apigatewayv2_domain_name.api.domain_name_configuration[0].hosted_zone_id
}
```

```bash
AWS_PROFILE=rigacap terraform apply -target=aws_route53_record.api_record
```

DNS propagation back to API GW takes <60s with 60s TTL. CloudFront distribution can be left in place; idle distributions cost $0/mo.

## Out of scope for this plan

- Selective response caching for idempotent GETs (regime data, market context). Easy win once CloudFront is live; defer.
- Migrating to REST API v1. Not needed — this plan provides equivalent WAF coverage at lower effort.
- Adding API keys for partner integrations. Future work; would still require migration.
- WAF tuning (overrides, allow-listing for admin paths). Defer until we see real traffic and false-positive metrics.

## After this lands

- Update technical architecture doc to reflect new layer
- Fold the redesign of all `design/documents/*.html` (currently old navy+gold brand) into a separate plan
- Continue monitoring WAF metrics for 1-2 weeks before considering next defenses (account 2FA, etc.)
