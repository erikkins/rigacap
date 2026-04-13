---
name: Twitter v1.1 media/upload.json field naming
description: Raw binary uses 'media' field, base64 uses 'media_data' — wrong field silently drops images from tweets
type: reference
originSessionId: 39ce1e26-1ab7-4fbd-8e9a-6c892d933b00
---
Twitter v1.1 `/1.1/media/upload.json` multipart form field naming:
- `media` — raw binary file (what httpx `files={}` tuples produce)
- `media_data` — base64-encoded string

Using `media_data` for raw bytes returns HTTP 400 `"media type unrecognized."` The existing publish flow in `backend/app/services/social_posting_service.py::_upload_media_to_twitter` catches this, logs, and returns None, so `post_to_twitter` publishes **text-only with no visible failure** — the tweet_id comes back normally, just without media.

**How to spot the silent failure:** check CloudWatch `/aws/lambda/rigacap-prod-worker` for `"Twitter media upload failed"` around publish time. The `social_admin approve_and_publish` response does NOT surface this error.

Fixed in commit 2b410ab (Apr 13 2026) after post 511 shipped without its launch-2.png attachment.
