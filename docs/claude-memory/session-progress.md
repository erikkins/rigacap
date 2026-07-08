---
name: session-progress
description: "Live session snapshot (auto-checkpointed ~15min) — what's done, in flight, and next"
metadata:
  node_type: memory
  type: project
  originSessionId: 2dce3134-d861-45c4-a371-80378750f8c0
---

# Session snapshot — Jul 8 2026 — Core-purge across pages. DONE: Landing, TrackRecord+chart, ForAdvisers. NEXT: Methodology → Social.

## ✅ CANONICAL NUMBERS (one basis, all public copy): 21yr (tier_curves_21y.json, daily, live t30v config): **Preserver 8.6%/0.88/−13.2%** · **Maximizer 14.5%/0.95/−20.4%** vs S&P 9.8%(price)/−55%, raw-mom 13.2%/0.69/−57%. $100k→Pres $500k, Max $1.39M, SPY $535k. Recent 2yr (tier_vintages_daily.py AUTHORITATIVE): **Preserver 31.3%/1.75/Cal2.43/−12.9%** · **Maximizer 48.9%/1.94/Cal2.83/−17.3%** = the 31/49 on landing dial (CORRECT, keep). 2× recovery = Preserver-specific (2.0yr vs SPY 4.85).
## Preserver adviser stats (computed): down-month avg −0.9% (S&P −3.9%), up-month +1.6%, corr-to-S&P 0.51, 5 of 6 worst S&P months in cash.

## ✅ LANDING (LandingPageV2.jsx) DONE. ✅ TRACK RECORD (TrackRecordPageV2.jsx) DONE — all tier numbers, TierRaceChart.jsx wired.
## ✅ **TierRaceChart** (replaced PortfolioRace): Preserve/Both/Maximize toggle (HIDE not dim), log $100k curves, draws L→R (StrictMode animation bug FIXED), 3 wide era-bands (2008/COVID/2022) + dashed defensive line-segments + animated flags, hover-scrub, thin lines (tier 2.2/spy 1.5). SPY made PRICE-ONLY (was total-return $763k BUG → now $535k, Preserver≈S&P but smoother). Data /public/track-record-curves.json (curves+defensive[]+events[]+annual). Erik approved look.
## ✅ FORADVISERS (ForAdvisersPage.jsx) DONE — Preserver-led sleeve: hero −13%, worst-months table (5/6 in cash), asymmetry (−0.9%/+1.6%/0.51 corr), diligence table both tiers 21yr, all backtest→walk-forward. Survivorship-free KEPT (diligence context = OK).

## 🔜 NEXT: **Methodology page** (grep Core 8.3/0.73/19% + backtest) → **SOCIAL ENGINE** (ai_content_service.py: voice not vibing + doesn't know 2-tier/new numbers). Old PortfolioRace still lives at /track-record-v1 (Core/backtest, secondary route — ignore unless linked).
## ⭐ RULES: no Core/t30v public (name or numbers); walk-forward not backtest for OUR numbers; no tildes on numbers; claret+paper; tables use "RigaCap Preserver/Maximizer" (TM). GATE: no tier CHARGES until Maximizer signals live. Commit only when asked. vite :5173 alive. Nothing committed yet (merge research→main when Erik says).
