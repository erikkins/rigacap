---
name: Newsletter operations and timing
description: Market Measured weekly ops — Saturday 10 AM ET generate, Sunday 7 PM ET publish. Filenames use Sunday's date. Lock guardrail prevents overwrite-of-locked-draft incidents.
type: project
originSessionId: 1081317d-f863-470f-ab07-65ddc614e856
---
**Live schedule (in production as of Apr 29 2026):**
- **Saturday 10:00 AM ET (14:00 UTC) — EARLY SATURDAY is intentional:** EventBridge cron `rigacap-prod-newsletter-draft-saturday` fires `{"generate_newsletter": true}` at the worker Lambda. Generates the upcoming Sunday's draft, saves to `s3://rigacap-prod-price-data-149218244179/newsletter/drafts/{next_sunday}.json`, emails admin "📝 Newsletter draft ready for {date}" with the full copy embedded so Erik can read on phone without opening the admin UI. Early generation is the design — Erik wants all of Saturday available to review/edit. Do NOT propose pushing this later "for fresher Friday data" or similar — the editorial window matters more than freshness here.
- **Saturday afternoon → Sunday 7 PM ET:** Erik edits + locks via admin UI Newsletter tab. Lock writes to BOTH `newsletter/drafts/{sunday}.json` (status: locked) AND `newsletter/issues/{sunday}.json` (public archive).
- **Sunday 7:00 PM ET (23:00 UTC):** EventBridge cron `rigacap-prod-market-measured-weekly` fires `{"market_measured": {"_": 1}}`. Handler looks for `drafts/{today}.json` (today=Sunday); if locked, sends; otherwise SKIPS and emails admin.

**CRITICAL load-bearing rules (from Apr 25/26 incident):**

1. **Filenames use the publish date (Sunday), not the generation day.** Implemented in `generate_draft()`: when called without an explicit `target_date`, computes upcoming Sunday and uses that for the filename. There is exactly ONE canonical file per week.

2. **Lock guardrail in `generate_draft()`** — refuses to overwrite a locked draft unless `force=True` is explicitly passed. This is the primary safety net against any code path (manual click, cron, batch script) accidentally trampling an editorial commit. Throws `ValueError`.

3. **Admin notification on lock-conflict** — if Saturday cron tries to regen a draft already locked from earlier, admin gets "ℹ️ Newsletter generate skipped — draft already locked" so they know nothing was lost.

**Weekend news gap:** Accepted by design. Newsletter is written from Friday's close. If something massive happens Sat/Sun, skip the send and write a manual note — more powerful than auto-updating. The system responds to data, not headlines.

**Apr 25/26 incident (the bug that motivated all this):**
- A Saturday-generated draft was dated Apr 25 (generation day).
- A Sunday-generated draft was dated Apr 26 (different generation day).
- The April 26 unlocked draft got locked and published, overwriting the editorial commit on April 25.
- Erik manually sent the correct April 25 version, then we cleaned up S3 (overwrote bad April 26 issue with correct April 25 content, redated to April 26 internally) and shipped the Sunday-date + lock-guardrail code fix.

**Files / commits:**
- Code fix: commit `c3b37c9` — `backend/app/services/newsletter_generator_service.py` + `backend/main.py`
- Terraform: `infrastructure/terraform/main.tf` Saturday cron resources (deployed via `terraform apply -target=...newsletter_draft_saturday`)
- S3 cleanup logged in this session 2026-04-29

**How to apply:**
- Don't propose timing changes without acknowledging the lock guardrail must remain.
- If anyone proposes "auto-lock on Sunday morning to save Erik the click" — reject. The lock is the editorial commit; auto-locking removes the editorial layer.
- If a future feature needs to regen a locked draft (e.g., emergency content correction), pass `force=True` explicitly. Don't soften the guardrail.
