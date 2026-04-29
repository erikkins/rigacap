---
name: Use US English everywhere — never British
description: All RigaCap content (subscriber-facing, investor docs, internal docs, social, emails) uses US English spelling. British forms slip in unconsciously and Erik flags them.
type: feedback
originSessionId: 1081317d-f863-470f-ab07-65ddc614e856
---
**Rule:** Always use US English spelling in any RigaCap content — subscriber-facing, investor docs, internal documents, social posts, emails.

**Watch for these common slips:**
- favour → favor, favorable
- behaviour → behavior
- centre → center
- colour → color
- realise → realize
- emphasise → emphasize
- analyse → analyze
- optimise / optimisation → optimize / optimization
- defence → defense
- programme → program
- modelled / modelling → modeled / modeling
- labour → labor
- honour → honor
- theatre → theater
- metre → meter

**Why:** Erik is US-based, RigaCap is a US company serving US retail investors, all financial regulators referenced (SEC) are US. British spelling reads as inconsistent / pretentious in this context, and Erik flags it as a copyediting issue.

**How to apply:**
- Before showing prose to Erik, scan for common British forms.
- The substring `optimis` catches both `optimise` and `optimisation`; `modell` catches `modelled` and `modelling`.
- Don't trust word-boundary regex in BSD sed (`\b` doesn't work the same as GNU); use the explicit suffix instead.

**Violations to remember:**
- 2026-04-29 session: introduced "favourable", "optimisation" (×3), "modelled" (×4), "realise" in the investor doc V2. Erik flagged.
