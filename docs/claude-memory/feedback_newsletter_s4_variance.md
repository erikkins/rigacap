---
name: Newsletter §04 (A Note From Erik) — preserve theme variance
description: §04 prompt has explicit theme rotation + anti-repeat + headlines. Erik flagged May 16 2026 that prior drafts always drifted to the same "system doing less, not more" angle. Do not simplify the prompt back to vague guidance.
type: feedback
originSessionId: c3d0833d-cb3f-474f-8dd8-e530f3300c60
---
§04 "A Note From Erik" must show **theme variance** week over week. Erik flagged on May 16 2026 that prior drafts drifted to the same "system doing less, not more" / "discipline is the product" angle every single week.

**Why:** §04 is the relationship-builder. It's where the brand voice is most "Erik" and least "system." Same theme every week makes the newsletter feel auto-generated even when the §01-§03 content varies. Variance signals craft.

**How to apply:**

The prompt in `newsletter_generator_service.py` `generate_draft()` has three variance levers — keep them all:

1. **Theme rotation buckets** (6): `the_craft`, `founder_life`, `market_moment`, `week_in_world`, `community`, `philosophy`. Picked by `target_date.isocalendar()[1] % 6`. Predictable, recoverable.
2. **Anti-repeat**: prior week's §04 text passed in with explicit "DO NOT echo its theme or phrasing" instruction.
3. **Headlines hook**: Google News RSS top 5 included; the `week_in_world` theme can tie to a relevant headline.

**Anti-patterns to avoid in future prompt edits:**
- Vague "something tied to the current moment" guidance → drift back to discipline platitudes.
- Listing "the regime, the season, building in public" as ALL the options → narrow Claude into one default.
- Removing the prev-week anti-pattern → loses week-over-week distinctiveness.
- Allowing "doing less, not more" phrasing → that exact phrasing is over-used and explicitly banned in the `philosophy` bucket.

Sister rules:
- `feedback_no_britisms_trader_jargon.md` — voice register
- `feedback_publication_is_aesthetic_only.md` — RigaCap is signal product, FT register is aesthetic
- `project_newsletter_topics.md` — §02 educational topic rotation (separate but analogous discipline)
