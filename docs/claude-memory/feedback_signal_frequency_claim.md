---
name: Canonical signal frequency claim is "3-4 per month"
description: Use "3-4 high-conviction signals per month" everywhere — not "6-8 every 2 weeks" or "~15 per month". Both alternatives are stale drift.
type: feedback
originSessionId: 39ce1e26-1ab7-4fbd-8e9a-6c892d933b00
---
The canonical, Erik-authored signal frequency claim is **"3-4 high-conviction signals per month"** — sometimes followed by "and zero when conditions aren't right" to set the regime-aware expectation.

**Why:** The codebase has accumulated three competing claims through copy drift over time. Erik's own authored sources (landing FAQ, product tour, social post templates, design/documents/rigacap-messaging-frameworks.html) all say "3-4 per month". The "6-8 every 2 weeks" and "~15 per month" variants are outliers from older specs that never got cleaned up. CLAUDE.md does NOT specify signal count — it only says "Max 6 positions @ 15% each, Biweekly rebalancing", which is portfolio sizing, not signal frequency.

I (Claude) once wrongly told Erik that "6-8 every 2 weeks" was canonical per CLAUDE.md and propagated it into the D8 win-back email. He caught it immediately ("when did we change to 6-8 picks every 2 weeks?"). Don't repeat the mistake.

**How to apply:**
- When writing new copy that mentions signal frequency, default to "3-4 high-conviction signals per month".
- If you see "6-8 every 2 weeks" or "~15 per month" in the codebase, flag it as drift to fix — don't propagate it.
- Known stale outliers as of Apr 13 2026:
  - `design/brand/social-launch-cards.html:613` (launch-5 card body says "6-8 high-conviction signals every 2 weeks")
  - `backend/app/services/email_service.py:795, 871` (welcome email says "~15 per month")
- Never invent a frequency claim from "Max N positions / biweekly rebalancing" arithmetic — defer to Erik's authored copy.
