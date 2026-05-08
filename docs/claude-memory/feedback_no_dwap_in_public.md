---
name: DWAP is DEPRECATED externally + NEVER reveal strategy formula thresholds
description: DWAP is deprecated for any externally-visible context. Plus a related rule we've reconfirmed multiple times: never publish the actual formula thresholds (200-day weighted average, 5% breakout, 50-day high, 1.3× volume, etc.) in user-facing copy. Use "momentum," "breakout trigger," and other genre terms.
type: feedback
originSessionId: 1081317d-f863-470f-ab07-65ddc614e856
---
## RULE 1 — DWAP IS DEPRECATED

The term "DWAP" must NEVER appear in:
- Social posts (any platform)
- Marketing copy / landing page / blog posts
- Subscriber emails (body or subject)
- Investor or technical-architecture or signal-intelligence docs (any `design/documents/*.html`)
- Any subscriber-visible UI label
- Any beta-tester guide or marketing playbook

Code field names (`signal.dwap`, `pct_above_dwap` in API contracts) and admin-only UI are fine. **Anything else is a violation.**

## RULE 2 — NEVER REVEAL SPECIFIC NUMBERS

**This rule was set a long time ago, has been violated repeatedly, and the user (May 8 2026) is rightly furious about it. Treat as load-bearing.**

The line is **specific numeric give-aways**, not vocabulary. Generic terms ("breakout trigger," "momentum," "regime," "ensemble") are fine — that's the editorial register the brand wants. Numbers tied to entry rules are the violation.

Do NOT publish ANY of these specifics in any externally-visible copy:
- "200-day weighted average" or any specific moving-average length tied to the entry rule
- "5% breakout window" or any specific breakout-threshold percentage
- "Within 5% of a 50-day high" or any specific recency-of-high window
- "1.3× volume" or any specific volume-confirmation multiplier
- "Top decile of momentum" — rank thresholds count as numeric specifics
- "10-day + 60-day momentum composite" or any specific lookback-window pair
- Any number that shows up in `strategy_definitions` parameters

These specifics are competitive moat. Knowing them lets a competitor reproduce the strategy. The "we have a proprietary system" framing is a meaningful brand asset that collapses the moment numbers leak.

**Acceptable vocabulary (no numbers attached):**
- "Proprietary breakout trigger" — fine
- "Momentum-confirmed breakout" — fine
- "Ensemble of timing, momentum, and risk" — fine
- "Leading momentum" / "names already proving strength" — fine
- "Multi-factor entry gauntlet" — fine
- "The system reads timing, momentum quality, and risk regime" — fine
- "When all three align, the system signals" — fine

**Editorial-register punch lines that read better than the dry technical version (May 8 2026 example):**
- "Wait for the right breakout. Don't chase."
- "Buy strength, not hope. Leaders, not laggards."
- "Read the regime first. Some weeks, the answer is cash."

These say what each pillar PROTECTS AGAINST without revealing thresholds. Stronger than dry "I. Timing / II. Quality / III. Risk" lists.

## How to apply (when writing ANY external copy)

Before you ship a sentence about how the system works, scan it for:
1. ❌ "DWAP" / "Daily Weighted Average Price" — banned everywhere external
2. ❌ Any specific number in proximity to "moving average," "breakout," "high," "volume" — banned
3. ❌ Specific lookback windows (10-day, 60-day, 200-day, 50-day, etc.) — banned in entry-rule context
4. ❌ Rank thresholds ("top decile," "top 5%," "top 100") — banned

If a sentence describes WHAT the system does (e.g., "stays in cash during panic regimes") that's fine. If it describes HOW (e.g., "buys when price crosses above the 200-day average and is within 5% of a 50-day high") it's a violation.

## Repeat-incident record

**May 8 2026:** Three card-3 launch posts went live on Twitter (post 548), Instagram (post 549), Threads (post 550) with both rule violations. Twitter+Threads had explicit "DWAP cross." Instagram had "200-day weighted average... within 5% of 50-day high. Volume is confirming." All three deleted by the user same day. Source code (`SocialTab.jsx` + `main.py:schedule_launch_sequence`) and the public `/methodology` page were rewritten with the safe substitutes above.

## Connected files (audit clean as of May 8 2026)

- `design/documents/rigacap-investor-report-v2.html` — clean
- `design/documents/rigacap-signal-intelligence.html` — clean
- `design/documents/rigacap-technical-architecture.html` — clean
- `frontend/src/components/SocialTab.jsx` (LAUNCH_POSTS) — clean
- `frontend/src/MethodologyPage.jsx` — clean
- `backend/main.py` (`schedule_launch_sequence` handler) — clean

Code field names + admin-only surfaces continue to use DWAP internally.
