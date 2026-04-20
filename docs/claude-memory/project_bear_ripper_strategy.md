---
name: Bear Ripper — parallel bear-regime sub-strategy
description: Counter-trend strategy running alongside main ensemble during bear regimes. Prototype built and reverted Apr 20 — needs proper parallel architecture with separate capital pool.
type: project
originSessionId: 39ce1e26-1ab7-4fbd-8e9a-6c892d933b00
---
## Bear Ripper

**Status:** Prototype built Apr 20 2026, reverted. Architecture was wrong (nested inside cash mode block). Need to rebuild as proper parallel system.

**Goal:** Lift the weaker 8-date CB start dates (Apr 1: +86%, Apr 15: +106%) and improve avg Sharpe from 0.95 to >1.0.

**Current 8-date CB results (baseline to beat):**
- Average: +204%, 23.2% ann, 0.95 Sharpe, 32% MDD
- Worst: Apr 15 +86% (13.2% ann), Apr 1 +86% (13.1% ann)  
- Best: Jan 4 +385% (34.8% ann) — clear outlier

**Correct architecture (NOT what was built):**
1. Reserve capital upfront: `br_capital = initial_capital * br_allocation_pct` (separate pool, e.g. 20%)
2. Track BR positions in SEPARATE dict (`br_positions`), never mixed with main `positions`
3. BR scan runs every day but only ENTERS when regime is bearish
4. BR exits on own trailing stop (8%) OR when regime improves
5. BR PnL adds to total equity but doesn't affect main strategy's capital
6. Period end: close all BR positions, return capital to pool

**Entry logic:**
- Universe: energy (XOM, CVX, COP, EOG, HAL, MPC), utilities (NEE, DUK, SO), healthcare (JNJ, UNH, ABBV, MRK, LLY), staples (PG, KO, WMT, COST), gold miners (NEM, GOLD, AEM)
- Rank by 20-day relative strength vs SPY
- Must have positive absolute return AND positive relative strength AND above 50-day MA
- Max 2 positions, 10% sizing, 8% trailing stop

**Why prototype failed:**
- Built inside `if in_cash_mode:` block — cash mode never triggered for Apr starts
- BR enabled flag somehow changed main strategy behavior: periods 21-26 returned 0% in BR run vs actual trades in CB-only
- Root cause: likely BR position carry contaminating main strategy slot counting
- All changes reverted from backtester.py and walk_forward_service.py

**Opportunity windows (from Apr 1 start data):**
- 2022 Q2-Q3: 6 months fully idle. Energy names (XOM +5.6%, HAL +9%, EOG +4.7%) were working
- 2024 Q2-Q3: -17.5pp combined underperformance vs SPY
- 2025 Q2: missed 18pp rip
- Even +10% in 2022 Q2-Q3 would meaningfully lift Apr start dates

**How to apply:** Build as clean parallel system in backtester.py. Separate capital pool, separate position dict. Test Apr 1 start date first — must match +86% CB baseline plus any BR gains. Half-day build.
