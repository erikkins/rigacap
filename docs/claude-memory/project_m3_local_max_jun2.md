---
name: M3 is the local max — best balanced variant after 22-variant search (Jun 2 2026)
description: After 2 days of v2-disciplined Lambda testing of 22 variants, M3 (VIX>30 mega-cap basket) is the closest balanced result to 20/20/1/1 North Star. Tier 2 ann 19.31 / Sharpe 1.09 / MDD 21.53 / Calmar 0.90. Disproof tests confirmed mega-cap selection IS the alpha. Closing the gap likely needs orthogonal alpha (data investment).
type: project
originSessionId: c3d0833d-cb3f-474f-8dd8-e530f3300c60
---
## The result

**M3 alone — closest to North Star after 22 variants:**

| Metric | M3 (Tier 2 validation 2022-01 → 2026-05) | North Star | Gap |
|---|---|---|---|
| Annualized | **19.31%** | ≥20% | -0.69pp |
| Sharpe | **1.09** | ≥1.0 | ✅ PASS |
| MaxDD | 21.53% | ≤20% | +1.53pp over |
| Calmar | 0.90 | ≥1.0 | -0.10 |

**Verdict per v2 methodology: FAIL** (need all 4 to pass). But ann + Sharpe both close or passing; MDD just over; Calmar a math consequence of MDD.

Per Erik (EOD Jun 2): "M3 is actually a very good product." Treat as the locally-best shippable strategy candidate if orthogonal-alpha work doesn't yield more.

## M3 exact configuration

```
TRIGGER:  VIX crosses above 30 today (today > 30, prev day ≤ 30)
SYMBOLS:  NVDA, TSLA, AAPL, MSFT, AMZN, GOOGL, META (7 mega-caps)
SIZE:     10% of current cash per basket position
TRAIL:    8% per basket position (own trail, exits independently)
PARALLEL: Runs alongside main strategy, doesn't count against max_positions
SURVIVES: Regime cash mode (basket designed for bear conditions)

OTHER STRATEGY PARAMS:
  trail_stop_pct = 12.0
  max_positions = 6
  position_size_pct = 15.0
  dwap_threshold_pct = 5.0
  near_50d_high_pct = 3.0
  short_momentum_days = 5
  long_momentum_days = 60
  composite weights = 0.3 / 0.2 / 0.15
  universe = top 100 by 60-day volume
```

## Disproof tests confirmed M3's alpha is mega-cap-specific

| Variant | T2 ann | Verdict |
|---|---|---|
| **D1: SPY-only basket** (same trigger, broad-market basket) | 14.62 | M3 loses ~5pp without mega-caps → mega-cap selection IS the alpha |
| **D2: defensives basket** (JPM JNJ PG XOM KO) | T1 20.00 ✅ but **T2 8.01** ❌ | Textbook overfit. Defensive blue chips loved 2019-2021, failed 2022+. **Methodology v2 caught it.** |

## 22 variants exhausted: the Pareto front is found

Across all tests, every variant landed in one of three buckets:
1. **Defensive lever (size cuts)** → hurts annualized: V1/DD1/VD1, B1/B2, A1
2. **Return booster** → ann jumps but MDD explodes 36-38%: MS1/MS2/MS3, MA1/MA2, LK1
3. **No-effect lever** → identical to baseline: M1 (CB-trigger basket — fires too rarely)

**M3 sits on the Pareto frontier — best you can do with current backtester capabilities.**

## What this means for the path to 20/20/1/1

Parameter mining within the current strategy template is exhausted. The remaining 0.69pp ann + 1.53pp MDD gap requires **orthogonal alpha** — new entry features not derived from price:

| Source | Status | Data acquisition cost |
|---|---|---|
| **Sector relative strength** | High-confidence next move | Finish sector data backfill (task #38) — partial cache already exists |
| News/sentiment | Have Alpaca News (Benzinga) | Build ingestion pipeline ~1-2 weeks |
| Earnings momentum | Don't have EPS data | FMP/AV subscription + multi-week ingest |
| Analyst ratings | Don't have | Paid API + multi-week |
| Options flow (IV, P/C) | Have Alpaca Options | Heavy data + interpretation work |

**Sector RS is the cheapest first step.** Finish task #38, then build a sector-RS entry filter as next variant.

## What we shouldn't do tomorrow

- Don't tweak M3 params (parameter mining within local max)
- Don't test more defensive sizing variants (all hurt)
- Don't test more return-booster overlays on M3 (all blew MDD)
- Don't pivot to a totally different strategy template without strong reason — M3 is genuinely good

## What to do tomorrow

1. **Build sector data backfill** (~1 day per memory task #38) — unlocks sector-RS variant
2. **Test sector-RS as entry-filter addition** — stack on baseline AND on M3
3. **If sector RS doesn't close gap**, explore Alpaca News for sentiment-driven entries
4. **Parallel: ship M3 to production** as the active strategy (Strategy 6 row update). Update marketing numbers to 19.31% / 1.09 / 21.53 / 0.90 honestly.

## Methodology v2 worked

The disciplined Tier 1 → Tier 2 separation caught overfit variants (D2 most obviously) that would have shipped under old WF methodology. The Lambda runtime + locked 2022-01-01 cutoff + 2y tuning windows + cardinal-sin enforcement (no tweaking failed variants to pass) all paid off.

Total 22 variants tested with zero curve-fitting violations.
