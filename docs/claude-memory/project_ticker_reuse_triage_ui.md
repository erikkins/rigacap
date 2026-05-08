---
name: Ticker-reuse triage UI (follow-up to symbol-triage v1)
description: Hygiene email flags ticker-reuse cases (CCL, TRI as of May 7 2026) but there's no admin path to resolve them — they stay quarantined indefinitely and re-flag every night. Build a diff-view UI similar to the symbol-triage page so an admin can compare the conflicting asset IDs and confirm or override the auto-quarantine.
type: project
originSessionId: c3d0833d-cb3f-474f-8dd8-e530f3300c60
---
**Why:** When Layer 2 detects that a ticker symbol's Alpaca asset ID has changed, the symbol gets auto-quarantined to prevent stitching old-issuer prices with new-issuer prices in the pickle. That's the right safety default. But the admin currently has no way to:

1. See what changed (old asset ID → new asset ID, old company → new company).
2. Confirm the auto-quarantine was correct (yes, this really is a different issuer reusing the symbol — keep quarantined).
3. Override when wrong (the asset ID changed for a benign reason like exchange listing change — restore to active).
4. Decide where to redirect held positions (if any subscribers held the old issuer, they need exit guidance).

So `CCL` and `TRI` (May 7 2026) just sit on the email each night with no actionable path.

**How to apply:** Build alongside or after the v1 symbol-triage page (May 7 2026, commit `9be3299`). Same editorial design system. Probably reuses the same `_summarize_symbol_news` Claude helper.

## What the page should show

URL: `/admin/ticker-reuse/{symbol}/triage`

For each ticker-reuse case, two columns side-by-side:

| Old (quarantined) | New (current Alpaca) |
|---|---|
| Asset ID | Asset ID |
| Company name | Company name |
| Exchange | Exchange |
| Listing date | Listing date |
| Last bar in pickle | First bar from new asset |
| AI summary: what was the old issuer? Did they delist, merge, or rebrand? | AI summary: who's the new issuer? Is this a new IPO, a rename, or a different company entirely? |

Below the diff, a single row showing whether ANY subscriber held the old issuer (and how many positions × total notional).

## Three resolve actions

1. **Confirm reuse — keep quarantined.** Default. Adds a `quarantine_confirmed_at` timestamp so it stops re-flagging in the email.
2. **Restore to active.** When the asset ID change was benign. Restores the symbol to the active universe; clears the streak.
3. **Migrate to new symbol.** If the old issuer was renamed/restructured into a new ticker. Records the redirect; held positions get exit guidance.

## Backend endpoints to add

- `GET /api/admin/ticker-reuse/{symbol}/triage`
- `POST /api/admin/ticker-reuse/{symbol}/confirm-quarantine`
- `POST /api/admin/ticker-reuse/{symbol}/restore-active`
- `POST /api/admin/ticker-reuse/{symbol}/migrate` (with `new_symbol` body)

## Email integration

Update `nightly_data_hygiene` so the "ticker-reuse detected" critical-flag becomes a clickable list:

```
🚨 2 ticker-reuse detected:
   • CCL — triage  (held by 0 users)
   • TRI — triage  (held by 1 user — urgent)
```

Each link points at the new triage page.

## Estimate

~2 hr backend (4 endpoints, AI helper reuse, query reused-symbol metadata) + ~1 hr frontend diff-view page. Plus the email update is ~15 min. Total: half a day.

## Connected

- `/admin/symbol/{symbol}/triage` (symbol-triage v1, May 7 2026, commit `9be3299`) — same design language, same Claude helper.
- Layer 2 corp-actions / ticker-reuse detection (Apr 15 2026) — the upstream detector that triggers these quarantines.
- `feedback_alpaca_asset_api_inconsistency.md` — Alpaca's `/v2/assets/{sym}` sometimes 404s on real symbols; the ticker-reuse detector relies on `get_all_assets` which the same memory note flags as the right pattern. Make sure the triage backend uses get_all_assets for the new-asset lookup, not the per-symbol endpoint.
