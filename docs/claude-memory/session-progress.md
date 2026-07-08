---
name: session-progress
description: "Live session snapshot (auto-checkpointed ~15min) — what's done, in flight, and next"
metadata:
  node_type: memory
  type: project
  originSessionId: 2dce3134-d861-45c4-a371-80378750f8c0
---

# Session snapshot — Jul 8 2026 — CORE-PURGE nearly complete across ALL surfaces. Blog sweep running (bg). SSOT updated.

## ✅ CANONICAL (SSOT = docs/numbers-citations-registry.md §1, updated to 2-tier + §5 vintage 2026-07-08): 21yr **Preserver 8.6%/0.88/−13%** · **Maximizer 14.5%/0.95/−20%** vs S&P 9.8%(price)/−55%, raw-mom 13.2%/−57%. $100k→Pres $500k/Max $1.39M/SPY $535k. Recent 2yr **Preserver 31.3%/1.75/2.43/−12.9%** · **Maximizer 48.9%/1.94/2.83/−17.3%** (=dial 31/49). 2008 both ~flat vs S&P −37%. Recovery Pres 2.0yr vs SPY 5.4 (Pres-specific 2×). Rolling-win-vs-SPY: Pres 37/23/16%, Max 54/51/48%. Preserver adviser: −0.9% down-mo/+1.6% up-mo/0.51 corr/5-of-6-worst-in-cash. Core/t30v 7.3%/0.76/−18% = INTERNAL ONLY.

## ✅ DONE (all uncommitted, dev :5173): PAGES — Landing, TrackRecord(+TierRaceChart w/ hide-not-dim toggle, dashed defensive, flags, SPY price-only $535k, animation fixed), ForAdvisers, Methodology. BACKEND CONTENT — ai_content_service.py (social, model=claude-sonnet-5 upgraded from 4-6), email_service.py (welcome+full trial drip: 2008/record-table/Buffett-caveat/facts-table → tier nums), newsletter_generator_service.py (PERFORMANCE guardrail + 5 seeds), engagement_service.py (canon block). All backend compiles; all say "walk-forward" not "backtest".

## 🔄 IN FLIGHT: blog sweep subagent (id aef151d9549bd9d8e, bg) purging 7 blog pages (Blog2022Story/HonestBacktest/TrailingStops/WalkForwardResults/MarketRegimeGuide/Backtests/Index). Will notify on completion — check its report + verify vite compiles.

## 🔜 REMAINING (Erik to decide): (a) deprecated v1 routes still have Core nums (PortfolioRace.jsx=/track-record-v1, TrackRecordPage.jsx, TrackRecord10YPage.jsx — not nav-linked); (b) design-doc PDFs (investor-report, messaging-frameworks, signal-intelligence etc. — internal/investor, listed stale in SSOT §3.1); (c) SSOT §3 surface-status table itself is stale meta. social_content_service.py template fallback = clean.
## ⭐ RULES: no Core/t30v public; walk-forward not backtest; no tildes on numbers; claret+paper; tables "RigaCap Preserver/Maximizer". Sharpe>Buffett(0.79) ALWAYS pair survivorship caveat. GATE: no tier CHARGES until Maximizer signals live. Commit only when asked (merge research→main). NOTHING committed yet.
