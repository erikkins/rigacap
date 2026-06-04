---
name: Surface work decisions locked Jun 4 2026
description: 3-bucket naming, VB ship-this-week, personal portfolio framing locked. Implementation in flight.
type: project
originSessionId: c3d0833d-cb3f-474f-8dd8-e530f3300c60
---
**Date:** Jun 4 2026 (Thursday morning)

**Locked decisions for surface unification + VB launch:**

1. **3-bucket signal taxonomy: `Approaching` / `New` / `Open`**
   - Approaching: 3-5% above DWAP, not yet qualifying
   - New: all criteria pass + DWAP crossover ≤ 5 days ago (replaces "Buy Signals" fresh)
   - Open: all criteria pass + crossover > 5 days ago (replaces "Monitoring")
   - All 3 surfaces (web dashboard, daily email, mobile) must use same buckets + counts

2. **Volatility Basket (VB) — ship to production THIS WEEK**
   - Mechanism: VIX cross-up above 30 fires basket of 7 fixed mega-caps (NVDA, TSLA, AAPL, MSFT, AMZN, GOOGL, META) at 10% of available cash each, 8% trail
   - Static list (not dynamically generated per event)
   - Separate UI component on dashboard + email
   - Subscribers can mirror VB in their accounts same as main signals

3. **Personal Portfolio tracking framing: STRONGLY RECOMMEND**
   - Existing feature (verified May 8 2026): users input positions → get sell alerts on THEIR holdings
   - Most subscribers don't realize this exists — major value-add gap
   - Persistent dashboard CTA, onboarding step, welcome email mention

**Strategy public name:** RigaCap Momentum Strategy (internal research code M3)

**Marketing numbers locked (per project_m3_distribution_breakthrough.md):**
- Headline (bear-inclusive 4.5y): 19.3% annualized
- Typical 2y window mean: 33.6% annualized
- Pass rate (ann ≥ 20%): 22/26 windows = 85%
- Recent 2y (2024-06 → 2026-05): 50.2% / 1.7-2.2 Sharpe / 17.7% MDD / 4/4 v2 pass
- ALL THREE numbers used together with full context, not cherry-picked

**Work tracks created (Jun 4 onwards):**
- 3-bucket unification (task #59)
- VB productionization (new task)
- Personal Portfolio CTA prominence (new task)
- Strategy detail page rewrite (new task)
- Blog/content refresh with new numbers (new task)
