---
name: Engagement reply voice — calm-specific, never contrarian
description: Twitter engagement-opportunity drafts must read as the calm specific voice in a noisy thread, never as a refutation of the original author. "Discipline is the product" framed as antidote to uncertainty, not as correction.
type: feedback
originSessionId: c3d0833d-cb3f-474f-8dd8-e530f3300c60
---
The daily engagement-opportunities email generates 5 draft Twitter replies. Voice rule for those drafts:

**The reply is the calm, specific voice in a noisy thread — never the smartest person in the replies.**

**Why:** Erik flagged on May 17 2026 that prior drafts read as "smarty-pants refuting what's in someone's post" — so much so that he stopped posting them. The original prompt (in `engagement_service.py`) had option (b): *"a counterintuitive observation that pushes back against the original tweet OR against conventional fintwit wisdom. Disagreement is more engaging than agreement."* That single line + Claude's tendency to pick the most engagement-coded option produced steady refutations instead of curiosity.

**How to apply:**

1. **Frame discipline as antidote, not correction.** Use the "would" tense — what a disciplined system *would* do in conditions like these. Never "you're wrong" or "the problem with that view…"
2. **Address the topic, never the author.** No second-person "you" pointed at the OP. The reply talks about the market / regime / pattern, not the original tweet's stance.
3. **Specificity is the curiosity hook.** Numbers, walk-forward stats, regime-conditional behavior — these stop scrolls without picking a fight.
4. **Vulnerability is the trust signal.** "We missed this one" / "the system was wrong about X" — better than agreement OR disagreement.
5. **NEVER**: refute, debunk, "actually" the author, position as correction or teaching moment, lead with disagreement language, use passive-aggressive softeners.

**Mechanical enforcement** (in `voice_filters.PHRASE_BANS`):
- `"actually,"`, `"not quite"`, `"not really"`, `"i'd push back"`, `"the problem with"`, `"to be fair"`, `"to be honest"` — all banned, trigger Claude retry

**A reader should think "huh, that's a different angle" — not "ouch, Erik just called that guy out."**

**Anti-patterns in future prompt edits:**
- Don't reintroduce "disagreement is more engaging" or similar — it's exactly what we just removed
- Don't replace "would" tense with "should" / "must" / "the right answer is" — that's correction language
- Don't add "have a real opinion" without anchoring to discipline-as-frame — Claude reads that as "be contrarian"

Sister rules:
- `feedback_no_britisms_trader_jargon.md` — voice register
- `feedback_publication_is_aesthetic_only.md` — RigaCap is a signal product, FT register is voice
- `feedback_newsletter_s4_variance.md` — analogous tone discipline for §04 founder note
