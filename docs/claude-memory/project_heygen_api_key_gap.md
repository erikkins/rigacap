---
name: HeyGen API key not wired into production Lambda
description: HEYGEN_API_KEY env var is declared in Terraform but empty default. The avatar_v engine code change (May 18 2026) cannot be verified until the key is populated via -var on terraform apply.
type: project
originSessionId: c3d0833d-cb3f-474f-8dd8-e530f3300c60
---
The HeyGen integration is fully built in code, the `engine: {"type": "avatar_v"}` fix shipped May 18 2026, BUT the `HEYGEN_API_KEY` env var on the worker Lambda is empty. Test fires return `HeyGen service disabled - HEYGEN_API_KEY not configured`.

## What's there

- Variable declared in `infrastructure/terraform/main.tf` as `var.heygen_api_key` (likely no default or empty default)
- Lambda env wired: `HEYGEN_API_KEY = var.heygen_api_key`
- Code paths complete: `heygen_service.py`, `heygen_video` event handler in main.py:4343

## What's missing

The actual API key value, passed via `-var="heygen_api_key=..."` at terraform apply time. Same pattern as the May 17 META_IG drift fix — value must come from outside the repo.

## To unblock

```bash
cd infrastructure/terraform
AWS_PROFILE=rigacap terraform apply \
  -var="lambda_image_tag=<current-sha>" \
  -var="meta_ig_app_id=1797236520885383" \
  -var="meta_ig_app_secret=<value>" \
  -var="heygen_api_key=<value>" \
  -target=aws_lambda_function.worker
```

After apply, re-fire the test:
```
{"heygen_video": {
  "action": "create",
  "script": "Quick test of the Avatar V engine.",
  "aspect_ratio": "9:16",
  "resolution": "1080p"
}}
```

Should return `video_id` instead of `null`. Then poll status to confirm queued OK.

## Connected

- `reference_heygen.md` — avatar/voice IDs and the Avatar V engine resolution note
- `project_aws_lambda_memory_cap.md` — same `-var` pattern caveat applies
