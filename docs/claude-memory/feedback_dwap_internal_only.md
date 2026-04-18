---
name: DWAP is internal-only — never use in external content
description: DWAP (Daily Weighted Average Price) is our proprietary internal name for the breakout trigger. All user-facing content should say "breakout trigger" or "breakout detection" or similar marketing-friendly terms.
type: feedback
originSessionId: 39ce1e26-1ab7-4fbd-8e9a-6c892d933b00
---
DWAP must NEVER appear in external-facing content: blog posts, emails, landing page, track record, Market Measured newsletter, social posts, investor docs, or any subscriber-visible UI.

**Why:** DWAP is our internal technical name for the breakout timing indicator. Exposing it reveals strategy mechanics and sounds jargon-heavy to everyday investors. The marketing term should be approachable — "breakout trigger," "breakout detection," "timing signal," or similar.

**How to apply:**
- When writing blog posts, emails, or marketing copy: say "breakout trigger" or "breakout detection" instead of DWAP
- When describing the ensemble's 3 factors: "timing (breakout detection) + quality (momentum ranking) + confirmation (near 50-day high)"
- The dashboard UI already shows "Breakout%" which is fine — that's the output, not the method name
- Code, CLAUDE.md, internal docs, memory files: DWAP is fine
- Admin emails (Erik-only): DWAP is fine
- Subscriber-facing emails (daily digest, Market Measured): use "breakout" not DWAP

**Where DWAP currently leaks externally (needs cleanup):**
- Possibly in the new blog posts just drafted (check BlogMomentumTradingPage, BlogTrailingStopsPage, etc.)
- Possibly in design documents (investor report, technical architecture)
- signal-intelligence docs may reference it
