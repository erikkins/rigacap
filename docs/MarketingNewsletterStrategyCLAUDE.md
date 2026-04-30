# CLAUDE.md — RigaCap

> Context file for Claude Code (and other AI coding assistants) working on the RigaCap codebase. This document captures the strategic, brand, design, technical, and operational decisions that should inform every change to this codebase. Read this before making non-trivial decisions.

---

## How to use this file

This file is **authoritative context**, not exhaustive documentation. When working on RigaCap:

1. **Read the relevant section before starting work.** Strategy decisions (pricing, positioning) shouldn't be re-litigated by code changes. Design decisions (palette, typography) shouldn't drift through one-off styling. Compliance constraints (Marketing Rule, RIA exemption) shouldn't be violated by helpful-feeling features.

2. **When in doubt, ask.** The principles here override default assumptions, but edge cases will arise. Ask the operator (Erik) rather than guessing.

3. **Update this file when decisions change.** This file is the source of truth. If a decision documented here is overruled, update the file in the same commit as the implementation.

4. **The Founder's Paragraph at the end is the meta-test.** When evaluating any decision and the answer isn't obvious, ask: "does this serve the paragraph or undermine it?" If it undermines, the answer is no, regardless of how attractive the change looks individually.

---

## Table of Contents

1. [Product Identity](#1-product-identity)
2. [The Real Value Proposition](#2-the-real-value-proposition)
3. [Customer Segments](#3-customer-segments)
4. [Pricing Strategy](#4-pricing-strategy)
5. [Brand & Visual System](#5-brand--visual-system)
6. [Typography](#6-typography)
7. [Color System](#7-color-system)
8. [Logo System](#8-logo-system)
9. [Chart & Data Visualization](#9-chart--data-visualization)
10. [UI/UX Principles](#10-uiux-principles)
11. [Content & Editorial Voice](#11-content--editorial-voice)
12. [Editorial Pipeline](#12-editorial-pipeline)
13. [Email Architecture](#13-email-architecture)
14. [Drip & Re-Engagement](#14-drip--re-engagement)
15. [Performance & Methodology](#15-performance--methodology)
16. [Strategy Capacity & Monitoring](#16-strategy-capacity--monitoring)
17. [Regulatory & Compliance](#17-regulatory--compliance)
18. [Marketing & Acquisition](#18-marketing--acquisition)
19. [Subscriber Lifecycle](#19-subscriber-lifecycle)
20. [Growth Targets & Phasing](#20-growth-targets--phasing)
21. [Technical Stack Notes](#21-technical-stack-notes)
22. [Operational Decisions](#22-operational-decisions)
23. [Legal Counsel](#23-legal-counsel)
24. [Open Items](#24-open-items)
25. [The Founder's Paragraph](#25-the-founders-paragraph)

---

## 1. Product Identity

**Company:** RigaCap, LLC (California, single-member LLC, owned by Erik Kins)
**Domain:** rigacap.com
**Founded:** 2026
**Operator:** Erik Kins, Los Angeles, CA — solo founder, no employees, no outside capital
**Founder background:** Former Chief Innovation Officer at a $1.5B publicly traded healthcare software company. 15 years parallel quantitative research. Self-taught engineer with a degree in International Business / International Relations from Lehigh. Patent-filed inventor ("Ubiquity"). Had the #1 song in Latvia in 2006 — origin of the company name.

**Two-line description:**
> RigaCap is a disciplined momentum signal service for self-directed investors who've decided indexing is too passive and solo trading is too emotional. Built by one former public-company CIO, it's an external discipline layer — a system that enforces the boring rules you already know you should follow, and stays in cash when it shouldn't be trading at all.

**What RigaCap is NOT:**
- Not a hedge fund
- Not a registered investment advisor (relies on publishers' exemption pending attorney confirmation)
- Not a Discord-room signal service
- Not a tech-startup-aesthetic SaaS
- Not "AI-powered" branding (regardless of underlying tech)
- Not promising "hedge fund returns" or any specific return numbers in marketing

---

## 2. The Real Value Proposition

**The single most important conceptual frame in the entire product:**

You are not selling signals. You are selling **external discipline**. Or, named more precisely: **discipline-as-a-service**.

Most retail traders are reasonably good at finding ideas and reliably bad at three specific things:
- Sitting in cash when nothing is working
- Honoring stops without second-guessing
- Not doubling down on losers

These are emotional discipline problems, not analytical ones. They are the reason most self-directed trading underperforms the index.

RigaCap is an external discipline layer. The system tells subscribers when to enter, when to exit, and — just as importantly — when to do nothing. When a trailing stop hits, the position closes without internal argument. When the seven-regime detector moves to cash, the subscriber doesn't have to summon willpower to stay out of the market.

**The value prop sentence to use repeatedly:**
> The hardest work of investing isn't the analysis. It's executing boring rules consistently. *That's what you're paying for.*

**The phrase "discipline-as-a-service":**
This is the named category for the product. **DO NOT put it in landing page hero copy, taglines under the logo, or nav bars.** It loses its power when used as a slogan. It works when readers discover it through earned context — in essays, in newsletter issues, in podcast bios, in the About page. Use sparingly. Let it function as the *naming of an idea*, not the headline of a sales pitch.

**Hero subhead pattern:**
> Built for the investor who's tired of fighting their own worst instincts.

This phrase shifts framing from describing the product to describing the customer. It's the line that makes sophisticated readers recognize themselves.

---

## 3. Customer Segments

**Primary (Phase 1):** Self-directed traders who currently trade their own portfolios with mixed results. They're not buying signals — they can find those anywhere. They're buying the ability to stop doing the parts of trading they're bad at.

**Secondary (Phase 1):** Slightly dissatisfied indexers. People with $100K+ portfolios who hold only VTSAX and feel they should be "doing something" but found active trading unrewarding. RigaCap offers them systematic active management they don't have to think about.

**Tertiary (Phase 2 target):** Advisor-paying investors. Someone with $500K paying a 1% advisor is spending $5,000/year. RigaCap at $1,548/year is one-third the cost with significantly more transparency. Hardest to acquire — existing relationship to leave, more conservative, slower to trust digital products. Phase 2 only.

**The real competitor is the prospect doing nothing.** Status quo is the default competitor for any new product. Most acquisition work is convincing prospects that their current behavior is costing them more than $129/month already.

---

## 4. Pricing Strategy

### Standard Pricing
- **Monthly:** $129/month
- **Annual:** $1,099/year (recommended) — represents ~29% discount, good annual-pull ratio
  - Alternative: $1,149/year at ~26% discount (acceptable but less aggressive pull)

### Founding Member Tier (First 100 Subscribers)
- **Rate:** $59/month
- **Lock-in:** 12 months at the founding rate, then transitions to $129/month standard
- **Closes:** Once 100 subscribers fill the cohort
- **Why 100 (not 50):** More research-cohort data, larger early track record, better word-of-mouth seed

### Pricing Discipline Timeline
- **Launch:** $129 / $59 founding
- **At ~300 subscribers:** Consider $149 for new subscribers
- **At ~700 subscribers:** Consider $179 for new subscribers
- **Maturity:** Core at $149-179, Premium tier (if added) at $299-399

### Both Monthly AND Annual Must Be Offered
Annual gets prominent placement but isn't pushed aggressively. Reasons:
- Annual subscribers are *owners*, monthly are *renters* — different psychology, different retention
- Cash flow: $1,099 upfront vs. drip of $129/month, valuable for bootstrapped operation
- Retention: annual sidesteps month-to-month "is this worth it" reconsideration triggers (especially during flat months)
- Annual subscribers' renewal rates run 60-80%; monthly cohorts shed faster
- Existence of annual makes monthly *feel* premium-convenience, supporting price perception

**Do NOT offer annual-only.** Removing monthly is a significant acquisition barrier for a new product.

### Why $129 (not $99)
- $99 anchors subscribers to a price requiring a 50% increase to reach $149 later
- $129 leaves room for future moves to $149-179 as smaller psychological lifts
- Captures 30%+ more revenue in the interim
- Aligns with premium positioning across the rest of the brand

### Pricing Math Justification (For FAQ / Methodology Page)
On a $100K portfolio:
- Strategy targets ~21.5% annualized (friction-adjusted)
- vs. SPY's historical ~13% annualized
- Potential uplift: ~$8,500/year
- $1,548/year subscription captures less than 20% of value created
- For comparison: hedge funds take 20% of *returns* (not excess returns) + 2% AUM; advisors take 1% AUM
- $129 holds up financially up to ~$179/month before the math stops being obviously favorable

---

## 5. Brand & Visual System

### Aesthetic Category
RigaCap's visual and editorial register draws from financial publications, not from fintech apps. References:
- *Grant's Interest Rate Observer*
- *The Economist*
- *Financial Times*
- Bloomberg research notes
- Stratechery

**This is an aesthetic and voice choice, not a product-category claim.** The product is a signal service (see §1). The publications above are reference points for *how it presents* — restrained typography, editorial prose, no hype, treats the reader as intelligent. Calling RigaCap "a publication" in customer-facing copy creates a different kind of confusion: prospects expect to be paying for the writing, when they're actually paying for the decisions. Bios, taglines, and lead copy should foreground the signal product; the editorial register is carried by the *voice*, not by labeling the product as a publication.

RigaCap is **NOT**:
- A modern fintech app aesthetic (Robinhood, Stripe-derivative SaaS)
- A trading-platform aesthetic (TradingView, ThinkOrSwim)
- A crypto / Discord-room aesthetic
- A consumer-finance app aesthetic (Mint, Personal Capital)

### Why This Matters
Design language is a pricing signal. Prospects unconsciously sort products into categories by appearance, and the category sets the price ceiling. Tech-startup aesthetics signal "Discord-room category," which has a $79 ceiling. Editorial-publication aesthetics signal "research-publication category," with a ceiling around $500-800. RigaCap at $129 lands comfortably below the editorial ceiling and is hard-sell at the tech-startup ceiling.

**You can't mix the two.** Importing tech-startup elements (gradients, drop shadows, rounded pills, decorative icons) into the editorial system creates a "confused product that doesn't know what it is." Maintain the editorial aesthetic across every surface: landing page, About, methodology, newsletter, dashboard, signal detail, social, even internal admin tools.

---

## 6. Typography

### Font Stack
```css
--font-display: 'Fraunces', Georgia, 'Times New Roman', serif;
--font-body: 'IBM Plex Sans', -apple-system, BlinkMacSystemFont, sans-serif;
--font-mono: 'IBM Plex Mono', 'Courier New', monospace;
```

### Usage Rules

**Fraunces (display serif):**
- All headings (h1 through h4)
- Pull quotes
- Newsletter ledes
- Editorial voice italics
- Numbers in stat cards (renders as "considered figure" rather than "alert")
- Use the variable `opsz` axis: `144` for hero, `96` for h2, `72` for h3, `48` for stat cards, `24` for inline italic

**IBM Plex Sans:**
- Body copy
- UI labels, buttons, navigation
- Form fields

**IBM Plex Mono:**
- Tabular numbers (prices, percentages, dates)
- Code-like elements
- Section labels in small-caps style
- Timestamps, IDs, technical data

### Italic Use
Fraunces italic is the editorial voice marker. Use for:
- Pull quotes
- Section ledes
- "What we're seeing" commentary
- Phrases the writer wants to inflect with editorial emphasis

Use sparingly. Overuse degrades the effect.

### Anti-Patterns
- No system-default sans-serifs (Inter, SF Pro, Roboto) — those signal "default SaaS"
- No display sans-serifs for headings (e.g., no Inter Display, no GT America)
- No condensed/compressed display fonts
- No script fonts
- No decorative fonts under any circumstances

---

## 7. Color System

### Core Tokens

```css
:root {
  /* Backgrounds */
  --paper: #F5F1E8;        /* warm cream, primary background */
  --paper-deep: #EDE7D8;   /* secondary background, footers */
  --paper-card: #FAF7F0;   /* card / section background */

  /* Text */
  --ink: #141210;          /* primary text, default element color */
  --ink-mute: #5A544E;     /* secondary text, captions */
  --ink-light: #8A8279;    /* tertiary text */

  /* Structure */
  --rule: #DDD5C7;         /* subtle separator lines */
  --rule-dark: #C9BFAC;    /* emphasized separators */

  /* Accent */
  --accent: #7A2430;       /* Claret — grounded in Latvian flag red */
  --accent-hover: #8F3D4D; /* hover state for accent */

  /* Financial semantic colors (use sparingly) */
  --positive: #2D5F3F;     /* muted forest green — gains */
  --negative: #8F2D3D;     /* muted oxblood — losses */
  --neutral: #6B6458;      /* neutral data */
}
```

### The Latvian Red Connection
The accent color is rooted in Latvian flag red (Pantone 1807 C, ~#9D2235), pulled toward paper-editorial usability as Claret (#7A2430). This is not coincidental decoration — the brand has three connected elements:
- Name (Riga = capital of Latvia)
- Color (drawn from the Latvian flag red palette)
- Founder origin (Erik had the #1 song in Latvia in 2006)

Subtle reference in About page or footer:
> The mark is rendered in Claret, a restrained variant of the Latvian flag red — a reference to the country where the company takes its name.

### Color Usage Rules

**Color is for outcomes, not decoration.**
- Positive/negative coloring applies ONLY to actual realized gains/losses (P&L on closed positions)
- Targets, stops, ranks, percentages without semantic value: ink, not green/red
- Do not color-code things that aren't outcomes. A trailing stop value isn't "bad" — it's just a number.

**Restraint in tone, not in information.**
- Marketing-page palette is rigorously minimal: paper, ink, claret, plus financial semantic colors when needed
- Functional surfaces (charts, data tables) can have more hue differentiation — see Chart section below
- The principle: ornamental restraint hurts functional elements but helps editorial elements

**No saturated colors anywhere.**
- No bright greens, no saturated reds, no neon, no electric blues
- All accent colors should feel desaturated, warm, and at home on cream paper

### Color Anti-Patterns
- No rainbow color coding (e.g., the original regime bar)
- No gradients (especially purple-to-blue startup gradients)
- No drop shadows in saturated colors
- No "wallet pink" or other consumer-fintech color signatures
- No pure white backgrounds (always warm paper)

### Background Texture
A faint noise texture is applied as a `body::before` overlay at ~3-4% opacity to add subtle paper grain. SVG implementation:
```css
body::before {
  content: '';
  position: fixed;
  inset: 0;
  background-image: url("data:image/svg+xml,...turbulence filter...");
  opacity: 0.03-0.04;
  pointer-events: none;
  z-index: 1;
}
```

---

## 8. Logo System

### The Mark
The current logo SVG depicts an upward-rising chart line breaking through architectural columns, with a dart element at top-right. The geometry is meaningful — the rising line is *literally* a breakout through resistance, semantically aligned with the momentum strategy.

**Keep the mark.** Only the color treatment changed during the rebrand.

### Color Treatments

**Primary (recommended, two-tone):**
- Architectural columns: ink (#141210)
- Rising-chart elements + dart: claret (#7A2430)
- Paper background, no container

**Utility (monochrome ink):**
- All elements: ink (#141210)
- For favicons, small sizes, print, black-and-white contexts

**Reverse (dark mode):**
- All elements: paper (#F5F1E8) on ink (#141210) background
- For dark hero sections or dark-mode UIs

### Container
**No circle container.** The mark sits directly on the paper background. The white circle in the original dashboard nav must be removed — it interrupts the paper flow and introduces a third background color into a system that should only have paper and paper-card.

### Wordmark
"RigaCap" rendered in Fraunces at weight 600, with letter-spacing -0.01em. Followed by a Claret period: `RigaCap.`

The period in Claret is part of the logotype. It's small, but it's intentional — a tiny accent that ties the wordmark to the color system.

---

## 9. Chart & Data Visualization

### Critical Principle
**Editorial restraint hurts functional charts.** Charts are analytical work — colors aren't decoration, they're encoding information. Restraint is for landing pages and editorial content; charts need clear differentiation.

The first version of the chart palette (ink + claret + ochre + muted teal) was too visually similar — values too close, hue differentiation insufficient. The revised palette below maintains the editorial aesthetic but provides clear at-a-glance differentiation.

### Chart Palette (Revised)

```css
--chart-price: #141210;      /* ink black — primary price line, 2px solid */
--chart-ma-fast: #7A2430;    /* muted claret — fast MA, dashed (semantic tie to signal accent) */
--chart-ma-slow: #B8923D;    /* muted mustard-gold — slow MA, dashed (warm, lighter than claret) */
--chart-trend: #2B6B8C;      /* muted teal-blue — trend/momentum, solid (cool contrast) */
--chart-volume: #A99E87;     /* warm gray — volume bars, ~50% opacity */
--chart-signal: #7A2430;     /* claret — signal/entry markers (matches MA-fast intentionally) */
--chart-grid: #DDD5C7;       /* rule line — gridlines, dashed, low opacity */
--chart-fill: rgba(20, 18, 16, 0.05); /* subtle ink fill under price line */
```

### Differentiation Strategy
Each color sits in a different region of color space:
- Hue separation: warm-neutral, warm-saturated, warm-light, cool
- Lightness separation: dark, medium-dark, medium-light, light
- Warm-cool axis: ink and claret and gold are warm; teal is the only cool element

This redundancy makes the chart readable at a glance. Don't rely on any single dimension of differentiation.

### Price Line Fill
The fill area beneath the price line should use `rgba(20, 18, 16, 0.05)` — a faint ink darkening rather than claret tint. Reasoning:
- Claret tint can imply directional sentiment (associates with negative/loss color)
- Ink darkening reads purely as "visual weight" without semantic implication
- Better practice for editorial-classical chart treatment

For more sophistication, use a linear gradient that darkens near the line and fades to transparent at the bottom of the chart area:
```css
fill: url(#priceFill);
/* defs: linearGradient from rgba(20,18,16,0.08) at top to rgba(20,18,16,0) at bottom */
```

### Calibration Note for Warm Paper
**Opacity values calibrated against pure-white mental model run too light on warm paper.** When something I specify as "5% opacity" looks invisible in practice, try 10%. The warm paper has less contrast with subtle fills than white, so the same opacity reads lighter. Always test on actual paper background.

### Markers

**Active signal entry marker (live signal chart):**
- Vertical dashed claret line at signal date
- "ENTRY" label in IBM Plex Mono, 9px, claret, letter-spacing 1.5
- Current price marker: filled claret circle (5px radius), 2px paper-colored stroke for halo

**Historical entry/exit markers (missed-opportunity chart):**
- Entry: filled claret triangle pointing up, 2px paper stroke, sitting on price line at entry date
- Exit: filled ink triangle pointing down, 2px paper stroke, sitting on price line at exit date
- Drop interior glyphs (no "A" or "V" inside triangles — adds clutter without information)
- Color logic: entry is in signal-family (claret), exit is closure (ink, neutral)

### Horizontal Reference Lines
Match colors to the markers they relate to:
- Entry price line: claret dashed, with claret label
- Exit price line: ink dashed, with ink label, italic parenthetical for context (e.g., "(market regime)")

This gives the chart two parallel visual stories (everything claret = entry event, everything ink = exit event), readable independently.

---

## 10. UI/UX Principles

### Behavioral Design Principle (Most Important)
**Trading apps are designed to feel exciting. RigaCap is designed to feel considered.**

Gradients, bright greens, pill buttons, BUY in all caps — these are retail trading visual languages that train users to trade more actively than the strategy recommends. Editorial restraint trains users to read carefully, absorb context, act thoughtfully.

For a strategy whose edge comes from *knowing when not to trade*, the UI must reinforce that posture rather than fight it. Every UI decision should be tested against: "does this make subscribers trade more, or does it support the discipline the system is designed to enforce?"

### Specific Patterns

**Buttons:**
- Sharp rectangles, minimal border-radius (2px)
- Primary CTA: ink-filled (#141210), paper text, hover to claret
- Secondary CTA: transparent, ink text, ink border on hover
- No rounded pill shapes
- "Record Entry" instead of "BUY" (softer, less excitement-driving)

**Cards / containers:**
- Thin 1px rules instead of drop shadows
- Paper-card (#FAF7F0) as background, not white
- No rounded corners (or minimal: 2px max)

**Section labels:**
- Small-caps IBM Plex Sans, letter-spacing 0.18-0.22em
- Preceded by a short horizontal claret rule (24px wide, 1px tall)
- 0.65-0.78rem size

**Numbers:**
- Render in Fraunces, not bold sans-serif
- Use OpenType `tnum` feature for tabular alignment
- Ink color by default; semantic color only for realized P&L

**Stat cards / data strips:**
- Newspaper-almanac style: label in small-caps above, large Fraunces value, mono sub-label below
- Bordered top and bottom with ink rule
- No floating elevation

**Editorial ledes:**
- Larger Fraunces italic (Fraunces opsz 48-72)
- Left-side accent rule (3px claret)
- Generous padding
- Treat as the visual hero of the section

### Anti-Patterns to Reject
When subscribers/colleagues give feedback like:
- "This feels cold"
- "Where's the color?"
- "Why no icons?"
- "Could we make the CTA pop more?"
- "Add a gradient to make it more modern"

**These come from people whose mental models are calibrated to tech-startup conventions.** Politely thank them for the feedback and ignore it. The restraint is load-bearing — anything that waters it down moves the product back toward the category we just escaped.

---

## 11. Content & Editorial Voice

### Voice Principles

**Tone:** Considered, restrained, methodical. Editorial-financial-publication register. Not hype-driven. Not folksy.

**Vocabulary:** Plain English where possible. Technical terms when they earn their place. Avoid Wall Street jargon when a clearer term works. **Avoid SaaS-startup vocabulary entirely** ("game-changing," "disrupt," "leverage" as a verb, "solution," "synergy").

**Structure:** Lead with the most important point. Use specific numbers and examples. Acknowledge counterarguments before dismissing them. End with a clear takeaway, not a sales pitch.

### Style
- Em-dashes welcome — they're editorial
- Short paragraphs in newsletters; longer in essays
- Avoid bullet points in editorial content unless genuinely structural
- No exclamation points
- Italics (Fraunces) for emphasis and editorial voice — use sparingly

### Forbidden Phrases
- "Hedge fund returns"
- "AI-powered"
- "Autonomous"
- "Exclusive"
- "Guaranteed"
- "Game-changing"
- "Join thousands of profitable traders"
- "Unlock"
- "Crush the market"
- Any urgency-manufacturing language EXCEPT the founding-member tier (where scarcity is real and verifiable)

### Required Framings
- "Discipline" / "external discipline layer" / "discipline-as-a-service" (last one used sparingly)
- "Walk-forward validated" (not just "backtested")
- "Friction-adjusted" (when discussing performance)
- "When the system stays quiet" (positive framing of inactivity)
- "Honestly" / "transparently" (when describing methodology)

### Performance Language Rules
- All performance figures must be presented as historical / hypothetical, with appropriate Marketing Rule disclosures
- Always present friction-adjusted numbers alongside or in place of zero-friction simulation
- Never imply specific future returns
- Never use testimonials (Marketing Rule restrictions)
- Family-member endorsements (e.g., uncle Juris) cannot be used in marketing without disclosure of the relationship

### Recurring Phrases (Approved)
- "The investor who's tired of fighting their own worst instincts"
- "The boring rules you already know you should follow"
- "When the system stays quiet, that's the discipline working"
- "Built solo by choice, from a desk in Los Angeles"
- "Walk-forward validated over 5 years"

---

## 12. Editorial Pipeline

### Backing Store
DynamoDB-backed editorial CMS with admin UI. Schema and seed content in `rigacap-editorial-pipeline.md` (separate file). Key model:

```typescript
interface EditorialItem {
  id: string;
  title: string;
  description: string;
  stage: 'IDEA' | 'DEVELOPING' | 'OUTLINED' | 'DRAFTED' | 'EDITED' | 'SCHEDULED' | 'PUBLISHED' | 'ARCHIVED';
  channel: 'NEWSLETTER' | 'REGIME_REPORT' | 'BLOG' | 'METHODOLOGY' | 'SOCIAL_X' | 'SOCIAL_FB' | 'SOCIAL_IG' | 'SOCIAL_LINKEDIN' | 'DRIP_EMAIL' | 'REENGAGEMENT' | 'PODCAST_PITCH' | 'INTERNAL_DOC';
  theme: Theme[];
  priority: 'P0' | 'P1' | 'P2' | 'P3';
  body: string;
  outline: string;
  references: string[];
  createdAt: string;
  updatedAt: string;
  scheduledFor: string | null;
  publishedAt: string | null;
  publishedUrl: string | null;
  triggerEvent: string | null;
  audienceFilter: string | null;
  estimatedWordCount: number;
  actualWordCount: number;
  attorneyReviewed: boolean;
  attorneyReviewedAt: string | null;
  marketingRuleNotes: string;
  archivedReason: string | null;
}
```

GSIs:
- GSI1: `stage` PK, `updatedAt` SK
- GSI2: `channel` PK, `scheduledFor` SK
- GSI3: `priority` PK, `updatedAt` SK

### Recurring Workflow
- **Sunday 30-min review:** Triage IDEA stage, advance items, confirm week's commitments
- **First Sunday of month, 60-min:** Calendar planning, theme audit, archive review, voice check
- **Quarterly, 2-hour:** Strategy alignment, compliance audit, performance review, roadmap update

---

## 13. Email Architecture

### Cadence Discipline
Email volume is a budget, not a count. Adding new content types means displacing something else, not stacking.

### Channel Schedule

**Sunday (morning delivery):**
- The Market, Measured (weekly newsletter, flagship editorial)
- 800-1,500 words, editorial voice
- Marketing Rule applies; balanced content requirement

**Tuesday (morning delivery):**
- Regime Report (weekly briefing)
- 300-600 words, tactical/analytical voice
- Deliberately offset from newsletter to give Sunday content time to breathe

**Wednesday-Friday (variable):**
- Drip emails (lifecycle-triggered, see below)
- Re-engagement emails (event-triggered)
- Schedule to avoid Sunday-Tuesday window when broadcast emails land

**Any day:**
- Signal alerts (trade-event-driven, not on editorial schedule)

### Email Volume Target
Active subscriber receives:
- 2-3 scheduled emails per week (newsletter + regime report + maybe one drip)
- Plus signal alerts as fired
- Plus occasional contextual triggers

If a subscriber consistently receives more than 4-5 emails per week from RigaCap, the cadence is over-saturated — investigate and trim.

### Subscriber Email Preferences
**Build subscription preference management from day one.** Subscribers should be able to choose which email types they want:
- Newsletter only
- Regime reports only
- Signal alerts only
- All of it
- Custom combinations

This is good for compliance, retention, and trust.

---

## 14. Drip & Re-Engagement

### Drip Email Sequence (Lifecycle-Triggered)

| ID | Trigger | Stage | Theme |
|---|---|---|---|
| DR-001 | signup (Day 0) | Welcome from Erik personally | Personal, set expectations |
| DR-002 | Day 3 | "What you're paying for" | External-discipline framing |
| DR-003 | Day 5, no signal yet | "You haven't seen a signal yet" | Quiet-period reframe |
| DR-004 | First signal received | Signal context walkthrough | Methodology explanation |
| DR-005 | First trailing-stop hit | Stop-out reframe | Discipline-not-failure |
| DR-006 | First profitable exit | Win reframe | Systematic-not-luck |
| DR-007 | Day 30 | Personal check-in | Pre-empt churn moment |
| DR-008 | 7 days no signals after first | Quiet-week reframe | Regime awareness |
| DR-009 | Day 60 | Methodology spotlight | Deeper rigor demonstration |
| DR-010 | Day 90 | "What we've learned together" | Gratitude, retention |

**Drip emails are signed by Erik personally** (as opposed to the publication voice of newsletters). This distinction matters — the drip is the founder relationship channel, the newsletter is the publication channel. Different registers, different purposes.

**Every drip email must include a "reply directly to Erik" affordance**, and those replies must reach a real human inbox, not an autoresponder.

### Re-Engagement Sequence (Event-Triggered for Lapsed Trials)

When a trial ends without conversion:
- Tag the trial exit with context: "exited during quiet period," "exited after N signals fired," etc.
- This tagging is the foundation for downstream re-engagement.

| ID | Trigger | Purpose |
|---|---|---|
| RE-001 | Trial exited quiet period + signal subsequently fires | Show worked example of fired signal, offer trial extension |
| RE-002 | Trial exit + 30 days | Generic "still here" check-in, light touch |
| RE-003 | Trial exit + 90 days | Quarterly summary of what RigaCap has been doing |

### The Worked-Example Mechanism (RE-001)

When a trial exited during a quiet period and a signal then fires, the re-engagement email shows the signal as a *worked historical example* — entry, stop, target, methodology, regime context — but delivered 24-48 hours after the signal fired. This timing matters:
- Prospects see the signal as a verifiable historical event, not a tradable opportunity
- Current subscribers retain first-mover access (preserves subscription value)
- Stays inside the spirit of the Marketing Rule
- Run by Juris (legal counsel) before shipping

### Trial Length Policy
Currently: 7-day free trial. Issue: subscribers can experience entire trial during a quiet week with no signals fired, leaving them no information to evaluate the product on.

Options to consider after launch data:
1. 14-day trial with auto-extension if no signal fires (recommended first move)
2. 30-day paid trial at reduced price ($19/$29)
3. Money-back guarantee instead of free trial
4. Use founding cohort as the trial mechanism during launch period

Don't change immediately. Watch trial-conversion data for 60+ days first, then revisit.

---

## 15. Performance & Methodology

### Canonical Numbers (current vintage)

**Source:** Clean-data walk-forward across multiple start dates from early 2021, each measured over a full 5-year window. Numbers regenerated on a known-clean indicator pickle (the prior dataset had silent indicator corruption that inflated the earlier published figures; see vintage log in `docs/canonical_numbers.json`).

**5-Year Walk-Forward (avg of multiple start dates):**
- Total Return: **+160%**
- Annualized: **~21.1%** (publish as **~21.5%** — within rounding, kept stable for marketing continuity)
- Sharpe: **0.92**
- Max Drawdown: **20.4%** (real-world result was meaningfully better than the 32% the prior simulation modeled)
- Worst-case start date: **+109%** (still nearly doubled capital over the window)
- Best-case start date: **+252%**

**S&P 500 (SPY, price only) Benchmark:**
- Total Return (5y avg of same windows): **+93%**
- Annualized: **~13%**
- Alpha: **+67 percentage points** total / **~7 pp annualized**

**11-Year Walk-Forward (single start, Oct 2015 → Apr 2026, fixed Trial 37 params on clean data):**
- Total Return: **+675%**
- Annualized: **~21.6%** ← *within rounding of the 5y's 21.1%*
- Sharpe: **0.95**
- Max Drawdown: **28.1%** (longer window includes more bear cycles)
- SPY benchmark over same window: +318%
- Alpha: +357 pp total / ~7.6 pp annualized

**The internal-consistency story:** 5-year multi-start average annualized of 21.1% and 11-year single-start annualized of 21.6% land within rounding of each other. Same strategy, two different windows of different lengths and start dates, same compound growth rate. This is the strongest internal validation signal available without live execution data.

**Use both publicly:** 5y for distribution disclosure (worst/best/average across multiple starts), 11y for long-window consistency confirmation. Frame: *"21% annualized over both 5 years and 11 years."*

**2022 Capital Protection (clean-data finding):**
- Every start date ended 2022 in **positive territory** (avg ~+8%, range +2% to +12%) while the S&P fell ~20%
- This is a stronger story than the previously published "flat in 2022" — real performance during the bear year was meaningfully positive

### Per-Start-Date Distribution (publish on Track Record page)

| Start | 5y total | Sharpe | MaxDD | SPY same window |
|---|---|---|---|---|
| 2021-01-04 | +145% | 0.92 | 20% | +98% |
| 2021-01-18 | **+252%** ← best | 0.88 | 26% | +96% |
| 2021-01-25 | +160% | 0.83 | 20% | +92% |
| 2021-02-01 | +156% | 0.96 | 20% | +97% |
| 2021-02-08 | +156% | 0.96 | 20% | +97% |
| 2021-02-15 | +156% | 0.96 | 20% | +97% |
| 2021-03-01 | +146% | 0.95 | 17% | +89% |
| 2021-04-01 | **+109%** ← worst | 0.89 | 19% | +75% |
| **Average** | **+160%** | **0.92** | **20%** | **+93%** |

**Disclosure rule:** Hero stats use the average; Track Record page shows the full distribution. Don't bury the +252% upside, but don't lead with it either.

### Cascade Guard (CG) — validated on clean data

CG is a portfolio-level safeguard. When multiple positions hit their trailing stop on the same day — a rare event signaling cascading market stress — the system pauses all new entries for 10 calendar days. This prevents the "buying into a falling knife" pattern where replacement positions also fail.

**Validated by no-CG ablation (2026-04-28):** ran the full 8-start-date 5y walk-forward with `circuit_breaker_stops=0` (CG never fires) and compared to canonical:

- **CG contributes ~+37 percentage points of return over 5 years (~+3.7 pp annualized)**
- **Sharpe improvement: +0.14**
- **Every start date benefited** — return delta ranged from +3pp (one start that didn't need it much) to +55pp
- Strategy stays fully active >97% of trading days; CG only fires on rare cascade-stress events
- **Per-date variance is wide** (3pp to 55pp) — average is meaningful but individual subscribers' experience varies by entry timing

**What CG does NOT do (corrects the over-fit Apr 19 claim):**
- **Does NOT reduce drawdown.** MDD impact is approximately neutral on clean data (slightly worse: +1.2pp). CG is a *return amplifier*, not a drawdown reducer. Existing positions continue to drawdown during paused windows; CG only prevents new capital deployment into stress.
- The previously-published "+87 percentage points / same MDD" framing came from the corrupted-data Run5 vintage (Apr 19) and is retired.

**Marketing-safe phrasing:** *"Cascade Guard contributes approximately +37 percentage points of return over 5 years by avoiding the pattern where forced re-entries during cascading market stress produce concentrated losses."* Avoid drawdown-protection claims; cite the return contribution and the mechanism only.

### Trade-Level Stats (clean data)

- ~200 trades per 5-year window
- Win rate: **42%**
- Win/loss ratio: **2.5×** (avg winner +18.6% vs avg loser -7.4%)
- Asymmetry is the engine: less than half the trades win, but winners are substantially larger than losers

### Methodology Assumptions (currently disclosed)

- Slippage modeled: 0% (acknowledged bias — slippage is user-execution-specific)
- Commissions modeled: $0 (zero-commission era, fair assumption for retail brokers)
- SPY benchmark: price return only, dividends not reinvested (~1.5-2% annual understatement on SPY side)
- Market impact: none modeled
- Initial capital: $100K
- Execution timing: EOD prices in simulation; live system uses 5-minute polling (see intraday disclosure)
- **NOT applied:** the 15% "friction-adjustment" haircut previously layered on top of simulation results. The walk-forward simulation's realized fills already include rebalance-boundary frictions; further proportional haircuts (taxes, behavioral drag) are user-specific and shouldn't be embedded in the headline number. We publish the walk-forward result directly.

### Strategy Components

**The Ensemble (core product):**
- 7-regime market detection (response logic is currently binary: trade normally / Cascade Guard pause; broader per-regime differentiation is internal-only — see `project_regime_substrategy_decision.md`)
- 3-factor signal requirement (Timing + Momentum Quality + Adaptive Risk)
- Biweekly rebalancing across 4-8 positions
- 12-20% position sizing
- 12-18% trailing stops (tighten after +12% profit)
- Universe: ~6,500 stocks → ~4,000 after liquidity filters (500K daily volume, $15+ price)
- Walk-forward validated across multiple start dates over 5 years

### Bear Ripper / Per-Regime Sub-Strategies — DEFERRED

Evaluated and shelved on 2026-04-28. With only ~5 historical bear-regime events in 11 years, no parameter optimization on bear sub-strategies can avoid catastrophic overfitting. The existing canonical strategy already delivers 20.4% MaxDD on clean data — the original Bear Ripper goal of "reduce MDD from 30% to 20%" was effectively delivered by the data refresh + carry-on CB rule, not by adding a sub-strategy.

If revisited: must use universal rules only (no per-event TPE), and must pass the three-test bar in `project_regime_substrategy_decision.md`.

**Do NOT publish any bear/range-bound sub-strategy numbers.** This is a hard rule.

### Strategies Tested and Rejected (Marketing Asset)
Publish on methodology page with brief rejection reasons. **Most signal services never disclose what they rejected.** This is a credibility moat.

Rejected strategies:
- Pyramiding
- RS Leaders
- Megacap Fallback
- Graduated Re-entry
- Bear Keep %
- Smart Regime Re-entry
- Anti-squeeze Filters

Each one is also a potential newsletter / blog issue. See editorial pipeline.

---

## 16. Strategy Capacity & Monitoring

### The Realistic Subscriber Ceiling
- **Strategy capacity:** ~1,500-2,500 subscribers before collective market impact becomes material (revised upward from initial 1,200 estimate after cohort-dilution analysis)
- **Solo support burden:** ~800 subscribers baseline, stretchable to ~1,500 with automation
- **Regulatory attention:** Increases meaningfully past 1,000-2,000 subscribers
- **Combined practical ceiling:** 1,000-1,500 as a sustainable solo operator

### Cohort Dilution Effect
Subscribers who join on different dates carry different positions on any given day, so not every subscriber acts on every new signal — only the subset with open slots in their 4-8 position portfolio. This dilutes per-signal collective impact by roughly 70-85%.

**Important countervailing effects:**
- New subscribers concentrate activity (zero positions, building up to 6)
- Hot regimes correlate signal pace with re-deployment pace
- **Exits don't dilute** — when a stop fires, every holder exits the same day. Stop cascades during bear regimes are the actual concentration risk.

### VWAP Drift Monitoring (BUILT)
Erik has built monitoring infrastructure that measures post-signal price drift — the gap between published entry price and what was actually achievable in the market during the execution window.

**Key principles:**
- Don't react to single-week data — too noisy
- Track 30-day moving average of drift, month-over-month trend
- Log inputs alongside outputs (stock, dollar volume, regime, day/time, subscriber count) for later decomposition
- **Pre-commit thresholds for action.** When drift exceeds threshold X for N months, response is Y.
- The diagnostic metric is drift-trend-normalized-by-subscriber-count-growth, not absolute drift

### What VWAP Drift Triggers
If collective execution quality degrades materially:
- Raise the liquidity filter
- Stagger signal delivery across subscriber cohorts
- Close new subscriptions until capacity increases
- Raise prices to ration demand

**Capacity headroom should be used for price increases, not subscriber growth at current price.**

### Public Disclosure
Methodology page should mention monitoring exists (already drafted in session notes). Once 6+ months of data, publish quarterly updates in newsletter — *"here's what our data says about execution quality this quarter"* — as differentiating editorial content. (Marketing Rule consideration; specifics through Juris.)

---

## 17. Regulatory & Compliance

### The RIA Question (Highest Priority)
Publishing specific entry/stop/target levels for paying subscribers may constitute "investment advice for compensation" requiring RIA registration. The publishers' exemption (Lowe v. SEC) may apply to RigaCap's impersonal, broadly-distributed signal service, but qualifying requires specific structural conditions.

**The "we are not a registered investment advisor" footer line is NOT a safe harbor.**

This is the FIRST topic with the securities attorney. Cannot charge any subscriber until exemption analysis is complete.

### Marketing Rule Compliance (SEC Rule 206(4)-1)
Applies to:
- Landing page performance claims
- Social media posts (every post, every account)
- Newsletter performance references
- All Social Intelligence Engine outputs
- Email content (drip, broadcast, transactional)
- Personal-account posts about RigaCap

**Non-negotiable for any hypothetical/simulated performance:**
- Prominent labeling as hypothetical (not actual)
- Methodology and assumptions disclosed
- Limitations stated
- Fair and balanced presentation (not cherry-picked)

### Required Disclosures (Drafted, Pending Attorney Review)

**Intraday Execution Disclosure** (full text in `rigacap-session-notes.md`):
Walk-forward simulation uses end-of-day prices. Live execution uses 5-minute polling. Effects in both directions, net unquantified, do not adjust performance figures for either.

**Capacity Disclosure** (full text in `rigacap-session-notes.md`):
Capacity varies by signal. Per-subscriber and collective AUM scenarios disclosed. Monitoring described. Possible adjustments to liquidity filter, signal staggering, enrollment closing, or pricing.

### Social Intelligence Engine — Compliance Gates (Before Scaling)
The engine already exists and produces:
- AI content from real (not walk-forward) trade data
- News-aware messaging
- Branded chart cards via matplotlib
- Admin approval pipeline (24hr + 1hr pre-publish, JWT kill switches)
- Contextual reply engine across 25+ fintwit accounts

**Before scaling further:**
1. Add balanced-content requirement — for every "we called it" post, require one "system was quiet" or "signal didn't work out" post in the same 7-day window
2. Document approval policy formally
3. Audit empirical output quality (sample 100 recent replies, rate them, track cringe rate)
4. Include in attorney review explicitly
5. Standardize bio-level disclosures on all social accounts

### Things That Are Prohibited (Do Not Implement)
- Testimonials from any subscriber, paid or comped (current Marketing Rule restrictions are tight)
- Performance claims that imply specific future returns
- Cherry-picked single-signal showcases without context
- Auto-generated investment advice tailored to individual subscribers
- Family-member endorsements of RigaCap in any marketing context (privilege/conflict disclosure required)

---

## 18. Marketing & Acquisition

### First Principle
**Don't spend on paid acquisition until organic conversion is validated.**

The biggest mistake solo founders make is launching, having no conversion data, running paid ads, getting expensive CAC from non-converting traffic, and concluding "paid doesn't work" — when actually they hadn't yet learned whether the funnel converts at all.

### Funnel Validation Targets (Before Any Paid Spend)
- Landing page conversion: 2-5% of qualified visitors → trial
- Trial-to-paid conversion: 25-50% (premium product target)
- Monthly churn months 1-3: informs realistic LTV

### Channel Priority (In Order)

1. **Content & SEO** (not paid; highest long-term ROI) — newsletter, methodology essays, "strategies tested and rejected" series. Compounds over time. Mostly time, minimal dollar cost.

2. **Targeted X (Twitter) ads** (most efficient paid channel for fintech/quant) — target followers of specific fintwit/quant accounts. CAC $50-150 for trial signups, 30-40% trial-to-paid. Test with $500-1,000 first.

3. **Podcast sponsorships** — quant/value-investing/mid-size investing shows (Meb Faber, Excess Returns, Resolve Riffs). Host-read converts because of trust transfer. $500-5,000 per episode. Track attribution carefully.

4. **Google Search ads** — high-intent queries ("momentum signal service," "quant trading signals"). Expensive but high-intent. Only after funnel proven.

5. **Meta (Facebook/Instagram)** — last on list. Retail-fintech is a minefield on Meta. Strict ad policy. Don't start here.

### Channels to Avoid
- Reddit ads (ad-blindness)
- Investing forum sponsorships / banner ads
- YouTube/TikTok finfluencers outside podcasts
- Marketing agencies / growth consultants at this stage (way too early)

### First-Year Marketing Phasing
- **Months 1-3 (launch + first 100):** Zero paid spend. Acquisition from Social Intelligence Engine, free newsletter, beta-user word-of-mouth, organic. Validate funnel.
- **Months 4-6 (100-300 subs):** Small paid tests, $500-2,000/month. Focus X ads + 1-2 podcast sponsorships.
- **Months 6-12 (300-600 subs):** Scale what works. Budget ~10-15% of MRR.
- **Year 2:** Scale proven channels OR reinvest in content/SEO if nothing paid worked.

### $10K Year-One Allocation
- $2,000: tools and production (email platform, analytics, A/B testing)
- $3,000-4,000: targeted podcast sponsorships and X ads (after funnel validation)
- $4,000: time-protected for content production (offset whatever consulting revenue you skip)

### Bottom Line
For a solo founder in regulated financial category at this price point: **the highest-ROI marketing investment is consistent public writing**, not paid ads. Weekly newsletter, X presence, occasional long-form essays. Compounds and builds the trust paid ads can't buy.

---

## 19. Subscriber Lifecycle

### The Trial Problem (Structural)
RigaCap's distinctive value is "knowing when not to trade." A 7-day trial during a quiet week shows the prospect literally nothing happening, with no information to evaluate the product on.

**Counter-strategies:**
1. Front-load the trial dashboard with non-signal value: methodology page content, recent signal history (last 30-60 days, both signals and quiet days), regime status panel, editorial content
2. Show "recent activity" view that includes quiet-state monitoring: *"In the last 30 days: 4 signals fired, 2 trailing stops triggered, system was in defensive posture for 11 days, current cash allocation 35%"*
3. Show recent fired signals as worked examples (with appropriate Marketing Rule disclosures) so the prospect sees what a signal looks like
4. Trigger drip emails contextually during trial (Day 5 if no signal, etc.)
5. Build re-engagement system to reach back out when signals fire after a quiet trial

### The First 100 Subscribers Are a Research Dataset
The founding cohort is not just early customers. They are:
- Retention data that determines all future product decisions
- Empirical feedback on how the product is actually used vs. how it's marketed
- Source of methodology critiques and feature requests
- Test population for VWAP-drift / capacity scaling
- Eventual source of public references and word-of-mouth (with appropriate disclosure)

**The single most important leading indicator of business viability:** founding-cohort retention at 90 days. 80%+ retention = product works, scaling is execution. 50% retention = something fundamental needs fixing before scaling.

### Family / Inner-Circle Comping Policy
Use a tiered framework:
- **Inner circle** (immediate family, closest friends, Erik's father): Lifetime free or symbolic ($1/month)
- **Extended circle** (extended family, former colleagues, casual friends): Founding-member rate, locked permanently
- **Strangers:** Full rate

**Erik's uncle Juris (also legal counsel):** Treat as inner circle. Free or symbolic. Cannot use as testimonial. Privilege-disclosure if endorsement crosses public.

### Beta-Tester Engagement Pattern
Active beta tester (Erik's uncle, but generally) read newsletter content, formed opinion on methodology choices (12% trailing stop), shared what other tools he uses (IBD, Schwab, Barron's, WSJ, MarketWatch, Squawk Box). Pattern observation:
- He took ~2 months of usage before he could articulate the value proposition in his own words
- The newsletter didn't teach him; it gave him *language* for the relationship he had already built with the product
- This is normal for products where value is structural rather than immediate

**Implication for product:** Conceptual articulation needs to be delivered actively and repeatedly through the early subscriber experience (drip), not just via static content the subscriber may or may not read.

---

## 20. Growth Targets & Phasing

### Revenue Targets (NOT Subscriber Counts)

| ARR | Subs at $129 | State |
|---|---|---|
| $500K | 323 | Early phase |
| $1M | 646 | Sustainable, inside capacity |
| $1.5M | 969 | Near capacity ceiling |
| $2M+ | 1,292+ | Requires tier expansion or price raise |

**Anchor:** $1M ARR in 24 months via ~650 Core subscribers at $129
**Stretch:** $2M+ ARR via Core + Premium tier structure

### Phase Plan
**Phase 1 (months 0-12):** Build Core to $700K-950K ARR
- 500-800 subscribers at $129
- Do not build a second product
- Accumulate live performance data, grow newsletter audience, debug subscription experience

**Phase 2 (months 12-24):** Launch Premium tier
- Options: Signals Plus (with strategy context) / Lower-frequency higher-conviction / Research service
- Priced at $249-349/month
- Target: 200-400 Premium subscribers

**Phase 3 (months 24+):** Decide whether to add a third stream or consolidate
- At $1.5M+ ARR solo, consider whether that's enough
- Options: raise prices, close enrollment to waitlist, launch third product

---

## 21. Technical Stack Notes

### Existing Infrastructure
- DynamoDB (used for various platform data; editorial pipeline will be added here)
- AWS Lambda (presumed for backend handlers)
- Mercury business banking
- Alpaca SIP consolidated feed (data source)
- Server-side matplotlib (Social Intelligence Engine chart cards, 1080×1350)
- Admin approval pipeline (Social Intelligence Engine)
- VWAP drift monitoring (just built, just deployed)

### Frontend Patterns
HTML/CSS reference files in `/mnt/user-data/outputs/` (or wherever they live in the repo):
- `index.html` — landing page, latest pricing and value-prop section
- `about.html` — founder/about page
- `newsletter.html` — newsletter template
- `dashboard-aesthetic.html` — pattern library
- `dashboard-pixel.html` — pixel-accurate dashboard
- `signal-detail.html` — signal detail modal (revised chart palette)
- `logo-exploration.html` — logo color treatments
- `color-exploration.html` — accent color exploration

### Anti-Patterns in Code
- Don't import Tailwind without first asking — the editorial aesthetic uses custom CSS variables, not utility classes
- Don't add component libraries (Material UI, Chakra, etc.) — they fight the editorial aesthetic
- Don't add gradient utilities or "modern fintech" styling presets
- Don't use system-default sans-serifs
- Don't wrap charts in card-with-shadow components
- Don't auto-add icon libraries (FontAwesome, etc.) — RigaCap uses minimal/no icons in editorial surfaces

---

## 22. Operational Decisions

### Done
- LLC formed (Northwest Registered Agent, EIN obtained)
- Mercury business banking opened (pending review)
- Beta product live with small user group
- Social Intelligence Engine built
- VWAP drift monitoring deployed

### In Motion
- Securities attorney consultation (uncle Juris, plus possibly specialized RIA counsel)
- CPA selection (Graphite referred Erik to a tax group for solo-LLC clients; needs to evaluate fit)
- Old LLC disbandment (separate existing entity)
- S-corp election decision (timing-sensitive, depends on filing window)

### Pending Pre-Launch
- Securities attorney signoff on RIA exemption, Marketing Rule compliance, Social Intelligence Engine policies
- Site arithmetic inconsistency fixes (CAGR math, MDD consistency, regime count)
- Pricing update on live site ($39 → $129/$59)
- Accent color update on live site (oxblood → claret #7A2430)
- Logo recolor implementation (drop circle container, two-tone treatment)
- Intraday execution disclosure added to methodology page
- Capacity language softened on methodology page
- Strategies-tested-and-rejected section added to methodology page
- Photo for About page (real photo, not placeholder)
- "What I'm optimizing for" paragraph published in About or methodology
- Bear Ripper out-of-sample validation completed before publishing improved numbers
- Founding seat counter wired to real subscriber count

### Pending Post-Launch
- App UI refresh (kill gradient on Journey strip, white→paper background, typography swap, soften BUY buttons)
- Regime bar redesign to tonal-density visualization
- Stat cards as data strip
- Chart palette applied throughout app
- Drip campaign infrastructure
- Re-engagement sequence infrastructure
- Subscriber email preference management
- VWAP drift threshold pre-commitments
- Quarterly methodology update publication

---

## 23. Legal Counsel

### Primary: Juris Kins (Erik's uncle)
- 30+ years federal and state court litigation experience
- Securities fraud, RICO, antitrust, complex commercial litigation
- Adjacent to securities — strong on what gets litigated, what defenses hold up
- May not have current depth on operational compliance rules (Marketing Rule rewrite 2020, etc.)

**How to use Juris:**
- Strategic and structural review (RIA exemption, performance marketing language, social engine policies)
- Adversarial read of marketing materials ("if I were attacking this, what would I attack?")
- Securities attorney for litigation-defense framing
- Relationship: formal engagement with attorney-client privilege, not casual family advice
- Get recommendations in writing (email is fine) for documentation
- Don't ask him to be everything; pair with junior compliance specialist for granular operational rule-checking

### Areas Requiring Specialized Counsel
- Day-to-day Marketing Rule compliance (specialized RIA counsel)
- SEC examiner protocols
- Multi-state advertising compliance if RigaCap markets nationally

---

## 24. Open Items

### Before Charging Any Subscriber
- [ ] Securities attorney consult complete — RIA exemption, Marketing Rule, Social Intelligence Engine
- [ ] Site arithmetic inconsistencies fixed
- [ ] Pricing updated to $129/$59 on live site
- [ ] Intraday execution disclosure on methodology page
- [ ] Capacity language softened on methodology page
- [ ] Balanced-content requirement added to Social Intelligence Engine

### Before Opening General Subscriptions
- [ ] Bear Ripper out-of-sample validation complete (before publishing improved numbers)
- [ ] VWAP drift threshold pre-commitments documented
- [ ] Real photo for About page
- [ ] "What I'm optimizing for" paragraph published
- [ ] Logo recolor + circle container removed in app nav
- [ ] Drip campaign infrastructure (DR-001 through DR-007 minimum)
- [ ] App UI must-fix items (gradient, white background, typography, BUY buttons)

### Ongoing Discipline
- [ ] Save all generated files locally in version control
- [ ] Build "Strategies Tested and Rejected" section publicly
- [ ] Launch free newsletter ("The Market, Measured") from day one of public availability
- [ ] Set up VWAP-drift quarterly review cadence
- [ ] Self-check at $1M ARR: is $2M+ still what's wanted?

### Weekly / Recurring
- [ ] Sunday 30-min editorial review
- [ ] First-Sunday-of-month 60-min editorial planning
- [ ] Quarterly editorial review

---

## 25. The Founder's Paragraph

This paragraph is the meta-test for any decision that doesn't have an obvious answer. When evaluating any change, feature, partnership, growth tactic, pricing decision, design choice, or content piece, ask: *does this serve this paragraph, or undermine it?* If it undermines, the answer is no, regardless of how attractive the change looks individually.

---

> *I'm building a solo operation that generates $1-2M per year in recurring revenue, run from my desk in Los Angeles, with minimal administrative overhead, serving a sustainable number of subscribers at a premium price point. The product is an honest, methodology-led signal service built from 15 years of quantitative research. I price for the value delivered rather than competing on cost. I scale through discipline and tiering rather than headcount. I say no to opportunities — investment, partnerships, feature requests, growth tactics — that require compromising any of the above. The best version of this business is smaller than most people would advise and more profitable than they'd expect.*

---

## Closing Note for Claude Code (and other AI assistants)

When working on this codebase, default to:

1. **Editorial restraint over feature flair.** If a default UI pattern feels too SaaS-startup, replace it with the editorial alternative. The aesthetic is load-bearing.

2. **Explicit disclosure over plausible deniability.** RigaCap is built on transparency. Any ambiguity in performance claims, methodology assumptions, or capacity disclosures should be resolved toward more disclosure, not less.

3. **The subscriber's experience over the company's metrics.** When optimizing flows, the test is "would this make a subscriber's life better?" not "would this lift conversion?" The two often align, but when they conflict, subscriber experience wins.

4. **Slowness when in doubt.** RigaCap's edge is patience. If a feature, change, or copy decision feels like it's being rushed, slow down. Ask Erik. Wait for legal review. Get it right rather than fast.

5. **Reference this file for non-obvious decisions.** The principles here have been worked through carefully. Re-litigating them in code reviews wastes time. Apply them and move on.

When in doubt: read the founder's paragraph. Then decide.

---

*Last updated: April 2026, during the strategic planning session that produced this file. Update timestamp and section when making material changes.*
