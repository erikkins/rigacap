---
name: Position sizing, filter, and risk management tests — Apr 9-11, 2026
description: Comprehensive A/B testing of position counts, sizing, breakout filters, regime exit rules, pyramiding, profit lock, and bear_keep. TPE optimizer running.
type: project
originSessionId: 7dc69abd-ade1-4ef8-b901-42d3cee7df53
---
## Position Sizing & Filter Tests (Apr 9-10, 2026)

### Final Config: 6@15% / 5% filter
- **Avg 5-year: +208%** (~25% annualized) across 8 start dates
- **Avg Sharpe: 0.88**
- **All years positive, worst case +126%**
- **10-year: +680%** ($10k → $78k), 22% annualized
- MaxDD avg: 30.6% (target: <20%)

### Key Findings

**Breakout Filter:**
- 3% filter (Apr 3 "breakthrough"): REVERTED — caused losing 2023 across all configs
- 5% filter: validated as better, all years positive

**Position Sizing (5-year, Jan 1):**
| Config | Return | Sharpe | MaxDD |
|--------|--------|--------|-------|
| 6 @ 15% | +276% | 0.96 | 28% |
| 8 @ 12% | +194% | 0.93 | 25% |
| 12 @ 8% | +131% | 0.82 | 24% |

Concentration (6@15%) wins over 5 years despite worse 2021.

**Regime Exit:**
- 200MA exit > panic-only (panic had 35-40% drawdowns)
- `bear_keep_pct` (gradual exit) was dead code — fixed Apr 11

**BEAR 30% (keep top 70% during regime exit, 8 dates):**
- Avg: +228%, Sharpe 0.93, MaxDD 30.7%
- 5/8 dates under 30% MaxDD, but Feb 12 (35.9%), Mar 19/Oct 1 (32.2%) still over

**Pyramiding (PYR 25/5/1 = add 5% when up 25%, max 1 add):**
- 5-year avg: +278% (8 dates), best single: +476%
- But Feb 12 MaxDD 37.2%, 10-year MaxDD 34%
- 10-year return: +560% (WORSE than baseline +680%)

**Profit Lock (tighten trailing stop after gains):**
- Lock 15→6%: +210%, worse across the board
- Lock 30→10%: +250%, same MaxDD, less return
- Cuts big winners that drive returns

**RS Leaders Secondary Strategy: ABANDONED**
- RS=2 hit +533% on Jan 1 but failed 7-date validation (-1% on Oct 1)
- Individual stock RS too noisy/sensitive to start date

### TPE Optimizer (Running Apr 11)
50 trials × 4 start dates, optimizing:
1. Maximize avg return
2. Maximize avg Sharpe
3. Minimize worst MaxDD
4. Minimize return spread across dates

Search space: trailing_stop (8-15%), near_50d_high (3-8%), dwap_threshold (3-8%), max_positions (4-8), position_size (10-20%), bear_keep (0-0.5), pyramid (0-40/0-15/0-2), profit_lock (0-40/4-10%)

### Next: MDD Reduction Features (if TPE doesn't find <20% MDD)
1. VIX-adjusted position sizing
2. Drawdown circuit breaker (halve positions when down 15%)
3. Tighter trailing stop in bear regimes (8% vs 12%)
