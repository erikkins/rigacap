---
name: session-progress
description: "Live session snapshot (auto-checkpointed ~15min) — what's done, in flight, and next"
metadata:
  node_type: memory
  type: project
  originSessionId: 2dce3134-d861-45c4-a371-80378750f8c0
---

# Session snapshot — Jul 8 2026 — LANDING done+consistent (uncommitted); IN FLIGHT: Track Record page rebuild; then Social engine

## ✅ 21YR WALK-FORWARD NUMBERS (scripts/tier_vintages_21y.py → tier_curves_21y.json; 2007-2026 daily, pre-2016 EXT survivorship-caveat):
- **RigaCap Preserver: 8.6% / 0.88 / −13.2%** · **RigaCap Maximizer: 14.5% / 0.95 / −20.4%** (Maximizer BEATS S&P 9.8% AND raw-mom 13.2%, at ⅓ market's 55% DD). Benchmarks: S&P 9.8%/−55%, raw mom 13.2%/0.69/−57%. Recent-2yr (dial): Preserver 31%/−13%, Maximizer 49%/−17%. Core=7.3% (INTERNAL, never public).
- **VERIFIED "2× recovery" (longest underwater vs SPY):** Preserver 2.0yr vs SPY 4.85yr = **2.4× (TRUE)**; Maximizer 3.36yr = only 1.44×. So hero "2×" stat MADE PRESERVER-SPECIFIC (honest).

## ✅ LANDING (LandingPageV2.jsx, uncommitted, dev :5173) — ALL Core numbers gone, one consistent basis:
- Hero grid now: '21 yrs' / '2×'(Preserver recovery) / '14.5%'(Maximizer 21yr vs S&P 9.8%). Perf table = **RigaCap Preserver/Maximizer** rows (TM: house-mark+descriptor in tables; plain in body). FAQ returns/Sharpe/flashier/down-year on tier numbers (Sharpe FAQ flags survivorship caveat, "Long-horizon" cap). "Drawdown is the whole game" callout FIXED (was "raw mom higher return illusion" — now false; Maximizer OUT-EARNS raw mom 14.5 vs 13.2). Advisory "13-20% not 55%". Zero tildes.

## ⏳ OPEN Q for Erik (asked, unanswered): the "Chief Innovation Officer/priced like software" line — applied text-balance (clean 2-liner). Offered Option B one-liner (drop "($59/month founding)" parenthetical + max-w-[680px]). Erik to pick A(2-line, current) or B(1-line trim).

## 🔜 IN FLIGHT: **TRACK RECORD REBUILD** (TrackRecordPageV2.jsx @ /track-record, 278ln — ENTIRELY Core numbers: grid +32/2.20/8.3/19, RECENT_ROWS+FOUNDATION_ROWS, 0.73 callout, per-regime rows, highlights, bear callout ALL need tier swap). Centerpiece = ANIMATED CHART: existing `PortfolioRace.jsx` (385ln) fetches `/portfolio-race.json`. Plan: gen frontend curves JSON (Preserver+Maximizer+**S&P**, downsampled, $100k-norm — S&P NOT yet in tier_curves_21y.json, fetch via yfinance like verify script did), knob-driven both-or-toggle, draws L→R 21yr, NO Core.
## THEN: Social engine (ai_content_service.py — voice + new 2-tier numbers) → Methodology page.
## ⭐ RULES: no Core/t30v public; walk-forward not backtest; no tildes on numbers; claret+paper only. GATE: no tier CHARGES until Maximizer signals live (~1wk shadow). Commit only when Erik asks.
