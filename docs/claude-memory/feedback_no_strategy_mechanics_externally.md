---
name: Don't reveal strategy mechanics in external content
description: Never expose specific thresholds, indicator names, or parameter values (e.g. "5% above 200-day weighted average", "12% trailing stop", "top 6 by momentum score") in user-facing content. Keep it conceptual.
type: feedback
originSessionId: 39ce1e26-1ab7-4fbd-8e9a-6c892d933b00
---
External content should describe WHAT the system does conceptually, not HOW it works mechanically.

**Why:** Revealing specific thresholds and indicator math gives away the strategy's edge. Competitors can replicate. Also, specific numbers sound intimidating to everyday investors — they want "the system catches breakouts" not "price crossed 5% above its 200-day weighted average."

**How to apply:**
- ❌ "Price crossed 5% above its 200-day weighted average" → ✅ "The system detected a confirmed breakout"
- ❌ "12% trailing stop from high water mark" → ✅ "An adaptive trailing stop that follows the price up"
- ❌ "Top 6 by composite momentum score (10d×0.5 + 60d×0.3 - vol×0.2)" → ✅ "Ranked by momentum strength"
- ❌ "SPY below 200-day moving average triggers cash mode" → ✅ "The regime filter detects when the broad market turns defensive"
- ❌ "DWAP threshold of 5%" → ✅ "Breakout confirmed"
- OK to say general concepts: "momentum ranking," "trailing stop," "market regime filter," "breakout detection," "volume confirmation"
- NOT OK to say specific numbers: percentages, lookback windows, position counts, score formulas

**Where this applies:**
- Blog posts, landing page, emails (daily digest, Market Measured, social)
- Track record page, investor report, design documents
- "We Called It" case studies — describe the OUTCOME not the exact trigger math

**Where specifics ARE OK:**
- CLAUDE.md, memory files, admin emails, internal docs
- Code comments
- The dashboard itself (subscribers already pay for the signals — showing "Breakout +5.2%" is the product)
