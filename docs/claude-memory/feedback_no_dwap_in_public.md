---
name: NEVER name "DWAP" in any public-facing document
description: DWAP is the proprietary indicator name. Internal CODE field references are fine; user-visible prose, public docs, marketing materials, investor materials, and emails must NOT name it. Use generic phrasing instead.
type: feedback
originSessionId: 1081317d-f863-470f-ab07-65ddc614e856
---
**Rule:** Do not mention "DWAP" by name in any public-facing document, marketing material, investor doc, blog post, email body, or social post. The name is proprietary; revealing it gives away strategy details.

**Why:**
- Erik is a solopreneur with no plans to sell the company or take outside investors. The "investor doc" is more of a credibility document for prospects, lenders, or strategic partners than an actual investor pitch.
- DWAP (Daily Weighted Average Price) is the proprietary timing indicator at the heart of the Ensemble strategy. Naming it in public prose tells competitors what to copy.
- Keeping the indicator unnamed preserves the "proprietary timing reference" framing as a meaningful brand asset.
- The ONLY exception is material legal discussions (e.g., securities counsel, regulatory filings) where specific methodology disclosure may be required.

**How to apply:**
- In user-visible PROSE: use "long-term accumulation reference," "proprietary timing indicator," "long-term price benchmark," or similar generic terminology.
- In CODE: field names like `signal.dwap`, `pct_above_dwap` are fine — they're internal API contracts. Email user-visible labels already say "Wtd Avg" rather than "DWAP" — leave those alone.
- In ADMIN UI (Strategy Editor, FlexibleBacktest, WalkForwardSimulator, AdminDashboard, StrategyGenerator): "DWAP" is fine — admin-only, Erik's the only viewer.
- In any DOC SHARED OUTSIDE THE BUILD (investor report, technical architecture, signal intelligence, beta-tester guides, marketing/editorial pipeline docs, anything in `design/documents/*.html`): **DWAP must not appear at all** — including schema column rendering, strategy-type enums, and quoted code paths. The user calls the indicator "deprecated" for external purposes; these docs render with public-safe substitutes (`accum_ref` for column names, "multi-factor entry gauntlet" / "timing reference" for prose). The actual database columns retain their legacy names — this is a presentation alias only.
- In TRULY INTERNAL ARTIFACTS (memory notes here, registry files in `docs/claude-memory/`, my own working drafts): DWAP is acceptable for clarity — these never leave the dev environment.

**Forbidden phrases:**
- "DWAP timing"
- "DWAP threshold"
- "Price > DWAP × 1.05"
- "200-day DWAP"
- Any blog post, marketing doc, email, social post, or investor doc referring to DWAP by name

**Marketing-safe substitutes:**
- "Proprietary long-term accumulation reference"
- "Proprietary timing indicator, refined over years of indicator work"
- "Long-term price benchmark with a tested breakout threshold"
- "Our proprietary entry-timing signal"

**Status (May 7 2026):**
- `design/documents/rigacap-investor-report-v2.html` — clean
- `design/documents/rigacap-signal-intelligence.html` — clean
- `design/documents/rigacap-technical-architecture.html` — clean (schema columns now render as `accum_ref`)
- `frontend/src/MethodologyPage.jsx` — V1 archived at `/methodology-v1`; delete-or-update decision pending
- `docs/beta-tester-update-apr2026.md` — 1 mention, fix or remove if obsolete
- `docs/rigacap-editorial-pipeline.md` — 1 mention in a topic outline, soften
