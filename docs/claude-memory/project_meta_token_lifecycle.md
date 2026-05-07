---
name: Meta (IG + Threads) access tokens — full lifecycle to solve
description: Full picture of the IG/Threads token mess discovered May 6 2026 — short-lived recovery, long-lived exchange path, automated refresh need, and the API-base gotcha
type: project
originSessionId: c3d0833d-cb3f-474f-8dd8-e530f3300c60
---
The launch sequence on May 6 2026 surfaced multiple compounding issues with Meta access tokens. The user explicitly deferred a real fix ("don't have any more energy tonight"). The full problem space, captured for the next sitting:

**Why:** Without a proper token lifecycle, every ~60 days IG and Threads silently stop publishing. The cron handler swallows the OAuth 190 errors; the user only finds out when they look at platform analytics or notice posts going Twitter-only. Bandaid token swaps work for one launch but the cycle repeats.

**How to apply:** When the user wants to revisit the social-publishing pipeline, walk through the punch list below. Don't conflate "I have a token now" with "the system is robust." Both must be solved.

---

## The four problems, in order

### 1. Short-lived token recovery (DONE — bandaid)
- Both `INSTAGRAM_ACCESS_TOKEN` and `THREADS_ACCESS_TOKEN` had been expired since late April. Cron swallowed the 190 errors, no alarm.
- Recovery path used May 6: Graph API Explorer → grant scopes → debug_token to confirm app — token is short-lived (1-6 days). Pasted via `refresh_meta_tokens` Lambda handler (`backend/main.py`, accepts `instagram_access_token` and/or `threads_access_token`). Handler reads full env, mutates target var, writes whole env back — preserves DATABASE_URL etc.
- Page token good for 6 days only. Will expire ~May 12.

### 2. Long-lived token exchange (BLOCKED on app secret issue)
- The proper exchange (`grant_type=fb_exchange_token` against graph.facebook.com) requires `client_id` + `client_secret` + the short-lived token. Returns a 60-day long-lived user token. Then `/me/accounts` returns Page tokens (don't expire while user token is valid).
- User attempted this May 6, got `"Error validating client secret"` even after fixing whitespace and confirming 32-char hex length. Unresolved — possibly the app secret was reset by Meta, or a copy from "Show" dialog mangled a character that's hard to spot. Resetting the secret in Meta Developer console is the clean answer; just confirm no other production integration depends on the current secret first.
- App ID confirmed via debug_token: **25180275888318086** (RigaCap app). Token type PAGE, profile_id 971214166079229, granular_scopes target IG account 17841480242857160.

### 3. Automated refresh (NOT BUILT)
- There's a `refresh_threads_token` method in `social_posting_service.py` but it only extends a still-valid token. No equivalent for IG. Nothing runs on a schedule.
- What's needed: an EventBridge cron (~weekly) that calls Meta's refresh endpoints, persists the new tokens to both Lambdas' env vars (using the safe full-env-readback pattern), and emails the admin if the refresh fails so we get warning before the 60-day cliff. Without this, every ~60 days both platforms silently fall off again.

### 4. The IG API-base gotcha (FIXED in commit `c442705` — May 6 2026)
- `INSTAGRAM_API_BASE` was `https://graph.instagram.com/v24.0` — the **Instagram Login API** which only accepts IG User Access Tokens from Instagram's own OAuth flow.
- A token from Facebook Graph API Explorer is a **Page token** that only works against `https://graph.facebook.com`. The two bases share zero auth even though the path shapes are identical (`/{ig_id}/media`, `/media_publish`, etc.).
- This bug masked symptom #2: even with a valid token, posts failed with `"Cannot parse access token"`. Switched the base; future IG posting will work as long as the token + business-account-id pair are mutually consistent.

## Account ID confusion (May 6 2026)

- Old `INSTAGRAM_BUSINESS_ACCOUNT_ID`: 35213611594904500 — the user thinks this was the *business* IG account.
- Token granted on May 6 had granular_scopes target_id: 17841480242857160 — the user thinks this might be the *personal* account.
- 35213611594904500 returned `does not exist or no permissions` against the new Page token — either the token wasn't granted for it, or the IG-FB Page link no longer covers it.
- Env var was changed to 17841480242857160 to match what the token grants. **If 35213611594904500 is actually the desired account**, the user needs to re-do Graph API Explorer with explicit selection of *that* account when granting permissions, then update the env var back.

## What "done right" looks like

1. App Secret confirmed working (reset if necessary) so long-lived exchange completes cleanly end-to-end.
2. Helper script (or admin endpoint) that takes one short-lived token and: exchanges → fetches Page tokens → fetches IG account ID → updates Lambda env. One human step, no manual JSON edits.
3. Weekly EventBridge cron that calls `/refresh_access_token` on both tokens (extends them while still valid, before they hit the 60-day wall). Email admin on any failure.
4. Decide which IG account is canonical (business vs personal) and document it. Bake the ID into the env var refresh helper so it's never wrong again.

## Don't lose

- `refresh_meta_tokens` handler pattern is good — keep it as the user-facing escape hatch even after #3 is built.
- The full-env-readback pattern (read all env vars → modify one → write whole dict back) is what makes `update_function_configuration` safe. Documented as the only way to write env vars per the master memory rule.
- Twitter posting is fully functional and uses a different token type (OAuth 1.0a consumer/access keys) that doesn't have this expiry problem. The lifecycle work is IG/Threads only.
