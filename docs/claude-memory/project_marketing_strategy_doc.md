---
name: Marketing & brand strategy — authoritative source of truth
description: RigaCap brand/voice/pricing/compliance/marketing strategy. Points to the canonical doc at docs/MarketingNewsletterStrategyCLAUDE.md plus the non-obvious rules future sessions might violate by default.
type: project
originSessionId: 1081317d-f863-470f-ab07-65ddc614e856
---
## Authoritative source

**`docs/MarketingNewsletterStrategyCLAUDE.md`** is the source of truth for everything brand, voice, pricing, design, content, compliance, marketing, lifecycle, growth, and legal. ~1,090 lines, 25 sections. Read it directly when working on anything strategic.

The doc itself states: *"This file is the source of truth. If a decision documented here is overruled, update the file in the same commit as the implementation."* So changes to brand decisions belong in the doc, not in memory.

## Load-bearing rules future sessions might break by default

These contradict typical Claude defaults and need to be respected:

**Naming and copy:**
- **"discipline-as-a-service" is the named category, NOT a slogan.** Never in landing hero, taglines under logo, or nav. Use sparingly in essays / About / podcast bios. (§2)
- **Hero subhead pattern:** *"Built for the investor who's tired of fighting their own worst instincts."* Customer-framed, not product-framed. (§2)
- **"Record Entry" not "BUY"**, never all-caps action words. (§10)
- **"Walk-forward validated"** not "backtested". (§11)
- **Forbidden phrases:** "hedge fund returns", "AI-powered", "autonomous", "exclusive", "guaranteed", "game-changing", "join thousands of profitable traders", "unlock", "crush the market", any urgency language EXCEPT verifiable founding-member scarcity. (§11)

**Pricing (firm):**
- **$129/mo, $1,099/yr, $59/mo founding (first 100, locked 12mo).** Both monthly AND annual offered. Founding closes at 100 subscribers. Future raises: $149 at ~300 subs, $179 at ~700. (§4)

**Compliance (non-negotiable):**
- **Cannot charge any subscriber until RIA exemption analysis is complete with attorney.** (§17)
- **NEVER use testimonials** — Marketing Rule restriction. Includes family endorsements. (§17)
- **NEVER imply specific future returns** anywhere. (§11, §17)
- **Bear Ripper performance numbers** must NOT be published until out-of-sample validation completes. (§15)
- **Marketing Rule applies to every social post, every account** — every auto-generated post by the Social Intelligence Engine must comply. (§17)
- **Balanced-content requirement on Social Intelligence Engine:** for every "we called it" post, require one "system was quiet" or "signal didn't work out" post in the same 7-day window. (§17 — already captured separately in `project_balanced_content_rule.md`)

**Visual / design (load-bearing aesthetic):**
- **Editorial publication aesthetic, not fintech-SaaS.** Mixing the two = "confused product." Don't import gradients, drop shadows, rounded pills, decorative icons, system-default sans-serifs, component libraries (Material, Chakra), Tailwind without asking. (§5, §21)
- **Typography:** Fraunces (display) + IBM Plex Sans (body) + IBM Plex Mono (data). Never Inter/SF Pro/Roboto for headings. (§6)
- **Color:** paper `#F5F1E8`, ink `#141210`, claret `#7A2430` (NOT oxblood — that's the prior version). Color is for OUTCOMES only — realized P&L gets green/red, targets/stops/ranks do NOT. No saturated colors. No gradients. No pure white backgrounds. (§7)
- **Charts need clear differentiation** — editorial restraint hurts functional charts. Chart palette has its own tokens (§9) with hue+lightness+warm-cool separation.
- **Logo: drop the circle container.** Two-tone (ink + claret) on paper. Period in Claret is part of the wordmark: `RigaCap.` (§8)
- **Minimal border-radius (≤2px), thin 1px rules instead of drop shadows.** (§10)

**Content channels:**
- **Sunday newsletter** "The Market, Measured" 800-1500 words editorial. **Tuesday** Regime Report 300-600 words tactical. (§13)
- **Drip emails are signed by Erik personally** (founder voice). Newsletters use publication voice. Different registers. (§14)
- **Drip must include "reply directly to Erik" affordance** that reaches a real human. (§14)
- **Re-engagement worked examples** must run 24-48h after the signal fired (Marketing Rule), so prospects see signals as historical not tradable. (§14)
- **Quarterly attorney review** for marketing compliance. (§17)

## Older memory entries this doc supersedes / extends

The doc is more comprehensive than these but doesn't directly contradict them:
- `project_redesign_spec.md` — extended by §5-§10
- `project_rebrand_premium_publication.md` — extended by §4
- `user_target_audience.md` — extended by §3
- `feedback_signal_frequency_claim.md` — extended by §13
- `project_balanced_content_rule.md` — captured in §17
- `project_newsletter_topics.md`, `project_newsletter_ops.md`, `feedback_newsletter_no_signals.md` — extended by §13, §14
- `feedback_no_tape.md`, `feedback_no_dated_callouts_in_docs.md` — captured in §11

Don't delete the older files — they have specific historical context. The doc is the canonical reference; older files document specific incidents/decisions that informed it.

## Tensions noted on Apr 28 2026 first read

These need reconciliation by Erik:

1. **Performance numbers stale.** Doc §15 cites 5-year +204% / 23% ann / 0.95 Sharpe / 32% MDD (simulation), friction-adjusted ~21.5% ann as headline. Fresh 11y fixed-params run on Apr 27-28 produced +500.9% / 18.5% ann / 0.93 / 25.7% MDD. Different windows + different Sharpe/MDD. Need to pick one narrative.
2. **§22 "Pending Pre-Launch" assumes redesign not shipped** — but redesign IS shipped (per `project_rebrand_premium_publication.md`). Some specific items may still be open (drop circle container, BUY-button softening).
3. **§14 specs 10-step drip; memory says 5-step drip is shipped.** Either doc is aspirational or memory is stale.
4. **§12 specs editorial CMS in DynamoDB with admin UI** — no matching code in repo. Pure aspirational unless work was done outside this codebase.
5. **§22 says VWAP drift monitoring is built/deployed**; memory's `project_signal_slippage_tracking.md` lists it as planned. Reconcile.
6. **References to non-existent sister docs** — `rigacap-editorial-pipeline.md`, `rigacap-session-notes.md`. Either bring them into the repo or remove the references.

## Founder's Paragraph (the meta-test)

> *"I'm building a solo operation that generates $1-2M per year in recurring revenue, run from my desk in Los Angeles, with minimal administrative overhead, serving a sustainable number of subscribers at a premium price point. The product is an honest, methodology-led signal service built from 15 years of quantitative research. I price for the value delivered rather than competing on cost. I scale through discipline and tiering rather than headcount. I say no to opportunities — investment, partnerships, feature requests, growth tactics — that require compromising any of the above. The best version of this business is smaller than most people would advise and more profitable than they'd expect."*

When evaluating any decision and the answer isn't obvious: does this serve the paragraph or undermine it? If it undermines, the answer is no — regardless of how attractive the change looks individually.
