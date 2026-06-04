---
name: Stale-number marketing audit — Jun 4 2026
description: Pages claiming superseded numbers that need surgery this week. Trial 37 over-fit (1.19/384%) and Apr 28 canonical (160%/0.92/20.4%) still live in public copy.
type: project
originSessionId: c3d0833d-cb3f-474f-8dd8-e530f3300c60
---
**Date:** Jun 4 2026
**Found via:** grep audit before bucket/VB unification work

**Stale numbers actively claimed in public surface — REQUIRES UPDATE:**

| File | Current claim | Issue |
|---|---|---|
| `frontend/src/LandingPage.jsx` | "+384% over 5 years, ~37% annualized, 1.19 Sharpe" | Trial 37 numbers — invalidated by corrupted-pickle finding |
| `frontend/src/BlogWalkForwardResultsPage.jsx` | "+160% avg return, 0.92 Sharpe, 20.4% max drawdown" | Apr 28 canonical — superseded by v2-validated M3 |
| `frontend/src/TrackRecordPage.jsx` | Avg Sharpe 0.92 | Apr 28 (superseded) |
| `frontend/src/TrackRecordPageV2.jsx` | Avg Sharpe 0.92 | Apr 28 (superseded) |
| Multiple meta/OG tags in blog SEO | Same Apr 28 numbers | SEO + social previews broadcasting wrong claims |

**v2-validated numbers to use as replacements:**
- Bear-inclusive 4.5y: 19.3% ann / 1.09 Sharpe / 21.53% MDD / 0.90 Calmar
- Tier 1 mean across 26 windows: 33.6% ann / 1.23 Sharpe / 22.18% MDD / 1.53 Calmar
- 85% of windows hit ann ≥ 20% (22/26)
- Recent 2y (2024-06 → 2026-05): 50.21% ann / 2.22 Sharpe / 17.69% MDD / 2.84 Calmar — first 4/4 v2 PASS

**Blog inventory (11 posts):**
- BlogMarketCrashPage.jsx
- BlogWeCalledItMRNAPage.jsx
- Blog2022StoryPage.jsx — 2022 bear narrative, historical, OK as-is
- BlogMarketRegimeGuidePage.jsx
- BlogWeCalledItTGTXPage.jsx
- BlogTrailingStopsPage.jsx
- BlogMarketRegimesPage.jsx
- BlogIndexPage.jsx
- **BlogMomentumTradingPage.jsx** — needs surgery (currently uses old strategy framing)
- **BlogWalkForwardResultsPage.jsx** — heavy on stale 160%/0.92 numbers, needs surgery
- BlogBacktestsPage.jsx

**Net-new blog posts to draft this week:**
1. "How the RigaCap Momentum Strategy Works" (using plain-English explainer + 3-bucket taxonomy from Jun 4 decision)
2. "Why We Test on Bear-Inclusive Data" (methodology differentiator — the discipline IS the product)
3. "Introducing the Volatility Basket" (NEW UI concept launch announcement)
