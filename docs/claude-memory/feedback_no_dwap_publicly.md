---
name: Never use "DWAP" in any public-facing UI or content
description: DWAP is an internal term. Publicly use "Weighted Avg" for the indicator and "Breakout" for the threshold crossing.
type: feedback
originSessionId: 39ce1e26-1ab7-4fbd-8e9a-6c892d933b00
---
DWAP (Daily Weighted Average Price) is internal terminology only. Never expose it in the dashboard, charts, emails, social posts, or any subscriber-facing content.

**Why:** It's jargon that means nothing to subscribers and reveals internal implementation details unnecessarily.

**How to apply:**
- Chart legend/tooltip: "Wtd Avg" (the indicator line) and "Breakout" (the +5% threshold)
- Signal metrics: "Breakout %" not "DWAP %"  
- Code comments/internal: DWAP is fine
- Grep for "DWAP" in any frontend file before deploying
