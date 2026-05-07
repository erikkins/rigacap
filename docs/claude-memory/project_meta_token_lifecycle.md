---
name: Meta (IG + Threads) access tokens — lifecycle infrastructure
description: How long-lived Meta tokens are exchanged, refreshed, and persisted. Handlers + weekly cron exist; only blocker for new setup is a fresh short-lived token + valid app credentials.
type: project
originSessionId: c3d0833d-cb3f-474f-8dd8-e530f3300c60
---
After the May 6/7 2026 launch incident, the Meta token lifecycle is now fully wired. The only manual step is the initial **one-time setup** when an operator has fresh credentials in hand. Everything else runs on its own.

**Why:** Without this, every ~60 days IG and Threads silently fall off, the cron handler swallows OAuth 190 errors, and we discover during the next scheduled launch. Bandaid token swaps work for one launch but the cycle repeats.

**How to apply:** When the user wants to (re-)establish long-lived Meta tokens, walk them through the setup section below. Once it runs successfully, no further manual work — the weekly cron keeps tokens alive indefinitely.

---

## Initial setup (one-time, when credentials are in hand)

User needs:
- **FB app:** App ID + App Secret from `developers.facebook.com → My Apps → [RigaCap app] → Settings → Basic`. App Secret is exactly 32 hex chars; click "Show" + auth challenge to reveal. Confirm same app whose ID issues your test token.
- **FB short-lived token:** Graph API Explorer → select the same app → Generate User Access Token with scopes `instagram_basic`, `instagram_content_publish`, `pages_show_list`, `pages_read_engagement`, `business_management`. Copy the resulting token immediately — the page-token derivation has to happen while it's still alive.
- **Threads app:** App ID + App Secret from the separate Threads app on `developers.facebook.com`.
- **Threads short-lived token:** Either the Threads app's "Generate Token" tool, or the manual OAuth flow (`https://threads.net/oauth/authorize?client_id=...&redirect_uri=...&scope=threads_basic,threads_content_publish&response_type=code` then exchange the code).

Run `meta_token_setup` (handler in `backend/main.py`) with payload:
```json
{"meta_token_setup": {
  "fb_app_id": "...", "fb_app_secret": "...",
  "fb_short_lived_token": "EAA...",
  "fb_page_id": "971214166079229",
  "threads_app_id": "...", "threads_app_secret": "...",
  "threads_short_lived_token": "THA..."
}}
```

The handler:
1. `fb_exchange_token` short→long-lived user token (60 days)
2. `/me/accounts` → page access token + IG Business Account ID
3. `th_exchange_token` short→long-lived Threads token (60 days)
4. Persists `INSTAGRAM_ACCESS_TOKEN`, `META_LONG_LIVED_USER_TOKEN`, `META_FB_APP_ID`, `META_FB_APP_SECRET`, `META_FB_PAGE_ID`, `INSTAGRAM_BUSINESS_ACCOUNT_ID`, `THREADS_ACCESS_TOKEN`, `META_THREADS_APP_ID`, `META_THREADS_APP_SECRET` to BOTH Lambdas (api + worker), preserving every other env var via the safe full-readback pattern.

Returns expiry days for both tokens + the FB Page details for confirmation.

## Weekly refresh (automatic, no human input)

`aws_cloudwatch_event_rule.meta_token_refresh` (`infrastructure/terraform/main.tf`) fires `{"meta_token_refresh": true}` every Sunday 2 AM UTC. The handler:
- Re-runs `fb_exchange_token` on the stored long-lived user token to reset the 60-day clock (FB has no separate "refresh" endpoint for user tokens, but exchanging a still-valid long-lived token for another long-lived one is supported and equivalent).
- Re-fetches the page token using the refreshed user token.
- Calls `/refresh_access_token` on the Threads token (Threads has a real refresh endpoint).
- On any error, sends an admin email via `admin_email_service.send` so we get warning weeks before the 60-day cliff.

Manual refresh: `{"meta_token_refresh": true}` from the AWS CLI.

## Manual escape hatch

`refresh_meta_tokens` handler still exists for the case where an operator already has a long-lived token in hand and just wants to push it to the env without going through exchange logic. Prefer `meta_token_setup` for fresh setups.

## API base gotcha (fixed in commit `c442705`)

`INSTAGRAM_API_BASE` was `graph.instagram.com/v24.0` (Instagram Login API, requires IG-only OAuth). Switched to `graph.facebook.com/v19.0` which accepts FB Page tokens. Two different APIs that share zero auth — don't switch back without a new OAuth flow.

## Account ID note

Production currently uses IG Business Account `17841480242857160` (set May 7 to match the token's granular_scopes). Old value `35213611594904500` was stale or wrong. If a future setup grants for a different IG account, the meta_token_setup handler resolves the ID from `/me/accounts` instagram_business_account → automatically picks the right one.

## What still might need attention

- **App Secret validation issue.** May 6 attempt to exchange via curl URL failed with `"Error validating client secret"` even after fixing whitespace and confirming 32-char hex. May resolve itself when user retries via the new handler (handler does same exchange but with cleaner JSON-payload handling than browser URL-bar). If it still fails, reset the App Secret in Meta Developer console — but confirm no other service is using the current secret first.
- **The `meta_token_setup` and `meta_token_refresh` handlers have not been live-tested end-to-end.** Code reviewed and syntactically clean, but real run depends on user providing credentials. If anything fails on first real run, fix-forward and update this note.
