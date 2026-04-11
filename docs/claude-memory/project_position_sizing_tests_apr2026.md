---
name: Position sizing & filter tests — Apr 9-10, 2026
description: Comprehensive A/B testing of position counts, sizing, breakout filters, and regime exit rules. 6@15%/5% confirmed as optimal.
type: project
originSessionId: 7dc69abd-ade1-4ef8-b901-42d3cee7df53
---
## Position Sizing & Filter Tests (Apr 9-10, 2026)

### Motivation
Explored whether more positions (8, 10, 12, 15) at smaller sizes would reduce variability and improve returns. Also tested panic-only regime exit (vs SPY < 200MA) and 3% vs 5% breakout filter.

### 2021-Only Position Sizing (1-year, Jan 1 start)
| Config | Return | Sharpe | MaxDD |
|--------|--------|--------|-------|
| 6 @ 15% | +22.5% | — | — |
| 8 @ 12% | +39.7% | 1.19 | 15.6% |
| 10 @ 10% | +22.4% | 0.78 | 16.9% |
| 12 @ 8% | +45.4% | 1.34 | 14.4% |
| 15 @ 6% | +39.3% | 1.37 | 13.5% |

**Conclusion:** More positions helped in 2021 (Rotating Bull), but this didn't hold over 5 years.

### Panic-Only vs 200MA Exit (5-year, Jan 1 start)
| Config | Return | Sharpe | MaxDD |
|--------|--------|--------|-------|
| 6@15% / 200MA | +151.3% | 0.73 | ~20% |
| 6@15% / panic-only | +151.3% | 0.73 | 39.6% |
| 12@8% / 200MA | +131.4% | 0.82 | 24.4% |
| 12@8% / panic-only | +79.6% | 0.56 | 35.0% |

**Conclusion:** Panic-only consistently worse — higher drawdowns, similar or lower returns. 200MA exit protects capital better. Keep 200MA.

### 3% vs 5% Breakout Filter (5-year, Jan 1 start)
| Config | Return | Sharpe | MaxDD | 2023 |
|--------|--------|--------|-------|------|
| 6@15% / 3% | +242% | 0.95 | 27% | -11.3% |
| 6@15% / 5% | +277% | 0.96 | 28% | +1.3% |
| 8@12% / 3% | +194% | 0.93 | 25% | -19.8% |
| 8@12% / 5% | +152% | 0.76 | 32% | -8.1% |

**Conclusion:** 3% filter creates a losing 2023 across all configs. 5% filter keeps all years positive. The Apr 3 "breakthrough" (3% filter) was overfitting to 7 closely-spaced Jan/Feb start dates.

### 7-Date Validation — Final Comparison
**8@12% / 3% (7 random dates, 2021-2026):**
- Avg: +160.6% | Sharpe: 0.92 | MaxDD: 23.8%
- Range: +84% to +267% (183pp spread)
- Better Sharpe and lower drawdown

**6@15% / 5% (same 7 dates, 2021-2026):**
- Avg: +198.7% | Sharpe: 0.87 | MaxDD: 30.6%
- Range: +126% to +331% (205pp spread)
- Higher returns, better worst case (+126% vs +84%)

### Final Decision: 6@15% / 5% filter
- Higher absolute returns (+199% avg vs +161%)
- Better worst case (+126% vs +84%)
- All years positive with 5% filter
- Slightly higher drawdown (31% vs 24%) — acceptable tradeoff

### Key Lessons
1. **2021 short-term tests are misleading** — 12@8% won handily in 2021 alone but lost over 5 years
2. **The tournament "breakthrough" (3% filter) was overfitting** — looked great on 7 Jan/Feb start dates but created a losing 2023
3. **Single start date tests are dangerous** — always validate across multiple dates
4. **200MA exit > panic-only** — even though it sometimes exits too early (like LYB), the drawdown protection is worth it
5. **Concentration wins over diversification** in trending markets (2024-2025), which outweighs the choppiness penalty in 2021/2023

### RS Leaders Secondary Strategy (ABANDONED Apr 10 2026)

**Concept:** Fill 2 reserved slots with top stocks by 6-month relative strength vs SPY. No breakout filter — just the strongest names above 50-day MA. Intended to capture narrow-leadership rallies (like 2023's Mag 7) that the ensemble misses.

**Implementation:** Added `rs_leaders_slots` param to backtester + WF service. RS positions entered after primary ensemble fills its reserved slots. Tested with separate trailing stop widths (12%, 15%, 18%, 20%).

**Results — Single Start Date (Jan 1, 2021):**
| RS Slots | Positions | Return | Sharpe | MaxDD |
|----------|-----------|--------|--------|-------|
| 0 | 6 @ 15% | +276% | 0.96 | 28% |
| 1 | 7 @ 14.3% | +217% | 0.87 | 27% |
| 2 | 8 @ 12.5% | +533% | 0.99 | 28% |
| 3 | 9 @ 11.1% | +485% | 0.83 | 35% |
| 4 | 10 @ 10% | +348% | 0.76 | 48% |

RS=2 looked spectacular on Jan 1 (+533%, all years positive).

**Results — 7-Date Validation (FAILED):**
| Start | Return |
|-------|--------|
| Jan 15 | +193.6% |
| Feb 12 | +19.7% |
| Mar 19 | +31.0% |
| Apr 23 | +188.1% |
| Jun 4 | +158.5% |
| Aug 13 | (errored) |
| Oct 1 | **-1.0%** |

The +533% was an outlier — Jan 1 happened to get RS leaders in early during a thin volume period. Other start dates saw marginal or negative impact. Oct 1 was negative.

**RS Trailing Stop Width Test:** 12%, 15%, 18%, 20% — all produced identical results (+533%). RS positions exit via regime (200MA) or sharp drops, not trailing stops. Stop width is irrelevant.

**Why RS Failed Across Dates:**
- Primary ensemble always finds 100+ candidates — RS only helps when primary can't fill its slots
- Jan 1 was special (holiday thin volume = fewer ensemble candidates = RS got slots)
- RS introduces high-beta names that amplify drawdowns without consistent upside

**Conclusion:** RS Leaders is not production-ready. The concept of augmenting ensemble during narrow-leadership markets is sound, but individual stock RS is too noisy. Future exploration: sector momentum ETFs or conditional activation based on breadth metrics.

### Other Strategy Ideas (Not Yet Tested)
- **Sector momentum rotation** — buy top 2-3 sector ETFs by momentum instead of individual stocks
- **Mean-reversion in bull regimes** — buy oversold names bouncing off support
- **Conditional activation** — only switch strategies when breadth is below a threshold
