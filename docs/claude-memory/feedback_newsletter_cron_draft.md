---
name: Newsletter cron MUST use locked draft
description: Sunday market_measured cron must check for locked draft before sending — never regenerate independently
type: feedback
originSessionId: 39ce1e26-1ab7-4fbd-8e9a-6c892d933b00
---
The Sunday EventBridge cron for `market_measured` MUST check for a locked newsletter draft in S3 before sending. If a locked draft exists, it sends that version via `send_newsletter_from_draft`. Only falls back to legacy `send_market_measured` if NO locked draft is found.

**Why:** April 26 2026 — the cron sent a completely different auto-generated newsletter to ALL subscribers, ignoring the version Erik spent hours editing and approving in the admin editor. The cron handler and the editor were completely disconnected. This is the worst kind of bug: silent, user-facing, and destroys trust with subscribers.

**How to apply:** Any code path that sends the weekly newsletter (cron, admin button, test) must read from the locked draft first. Never add a new send path that bypasses the draft system. The editor IS the source of truth for what goes out.
