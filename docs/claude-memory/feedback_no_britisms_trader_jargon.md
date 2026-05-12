---
name: No Brit-isms or trader-desk shorthand in copy
description: RigaCap's voice is editorial-sharp US-English. Ban folksy idioms ("what it says on the tin") and trader-desk shorthand ("catches a bid") wherever subscriber-facing copy is generated.
type: feedback
originSessionId: c3d0833d-cb3f-474f-8dd8-e530f3300c60
---
Subscriber-facing copy — daily briefings, social posts, email subject lines, newsletter, dashboard chrome — must avoid two families of phrasing:

**Folksy idioms / Brit-isms.** Examples: "what it says on the tin", "doing the heavy lifting", "no joy", "punching above its weight", "spot of bother", "Bob's your uncle". They land as cute when the brand register is FT / Stratechery.

**Trader-desk shorthand.** Examples: "catches a bid", "gets bid up", "finds offers", "tape action", "ripping", "bid for". Same family as the existing 'tape' ban — clubby language that excludes the everyday-investor audience.

**Why:** The brand voice is editorial-sharp US-English. The audience is sophisticated retail (knows trailing stops, uses brokerage apps) but not pit traders. Folksy idioms feel breezy in a sector where everyone else is breezy, but they undermine the discipline framing. Trader jargon signals "this is for insiders" — the opposite of the publisher's-exemption positioning.

**How to apply:**

1. **AI-generated briefings (signals.py prompt)** — the rule is already in the system prompt. If new violations slip through, tighten the prompt with the specific phrase as a negative example.
2. **Hand-written copy** — landing page, methodology, newsletter, social drafts. Run a self-edit pass before shipping. The tells: idioms older than the audience, phrases that wouldn't appear in the FT.
3. **Substitutions:** "catches a bid" → "rallies" / "is being bought" / "leads". "what it says on the tin" → "as advertised" / "exactly that" / drop it. "doing the heavy lifting" → "driving the move" / "doing the work". "no joy" → "didn't pan out".

Sister rules in memory: `feedback_no_tape.md` (no 'tape'), `feedback_us_english.md` (US spellings), `feedback_publication_is_aesthetic_only.md` (FT/Stratechery register is for voice, not product claims).
