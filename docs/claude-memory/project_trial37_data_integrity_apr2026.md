---
name: Trial 37 was optimized on partially-corrupted data (Apr 14 2026)
description: Critical finding that Trial 37's advertised +240% baked in artifact-inflated returns from unadjusted stock splits; TPE re-optimization needed on clean data
type: project
originSessionId: 39ce1e26-1ab7-4fbd-8e9a-6c892d933b00
---
## The Finding

On Apr 14 2026, extensive data-hygiene work revealed that the Trial 37 optimization campaign ran against a pickle containing at least **79 unadjusted forward stock splits** (including major names: NVDA, CMG, WMT, AVGO, GOOG, GOOGL, AMZN, SHOP, SMCI, LRCX, COKE, NOW, and ~67 others).

The unadjusted splits created **artifact trades** where:
- Pre-split price ($1000 NVDA June 4, 2024) "crashed" to post-split price ($100 June 10)
- Trailing stop fired on the -90% "loss"
- Or reverse: stocks held through splits appeared to have artifact GAINS
- Either way, PnL calculations mixed pre- and post-split price bases

Trial 37's TPE optimizer treated these artifact outcomes as real signal, and selected parameters that happened to ride on them.

## Impact on Marketing Claims

| Claim | Advertised | Reality on clean data (Apr 14 2026 test) |
|---|---|---|
| 5-year return | +240% avg | +140% avg (Trial 37 params on fully-clean data) |
| Sharpe | 0.89 | 0.72 |
| MaxDD | 24% | 28.6% |

**The +240% was not achievable honestly with the advertised params.** Re-optimization (new TPE run on clean data) is required to find new params that produce honest results.

## What Clean Data Means

"Clean pickle" = every symbol's OHLCV series is fetched from Alpaca with `Adjustment.SPLIT`. No mixed adjustment states. No date-alignment mismatches.

**Not yet addressed at this memory snapshot:**
- Dividend adjustments (we use SPLIT only, not ALL)
- Spinoffs (separate ticker created — not captured by SPLIT adjustment)
- Mergers / cashouts
- Ticker reuses (old delisted entity's data stuck with symbol of new entity)

## What to Do Going Forward

1. **Never again optimize parameters against raw-fetched data.** Change `market_data_provider.py` to use `Adjustment.SPLIT` permanently.
2. **Full universe refetch** with split adjustment before any TPE run.
3. **Layer 2 corp-actions pipeline** (nightly Alpaca corp-actions poll + force refetch affected symbols) to keep data clean ongoing.
4. **New TPE run on clean data** to find honest-baseline params.
5. **Update all advertised numbers** only after clean-data optimization completes.

## How This Was Discovered

- Mar 20 → Apr 13 2026: 3.5-week live signal drought from indicator-strip bug (separate issue, fixed)
- Apr 14 2026: Investigated why Trial 37 MDD was 34% instead of advertised 24%
- Found NVDA's unadjusted June 2024 10:1 split causing -90% artifact trades
- Extended hunt revealed 79 splits total in the tradeable universe
- Running Trial 37 on cleaned data showed +140% return — below the +240% claim
- Concluded: params were selected against artifact-heavy data; they don't carry to clean reality

## Preserved Sessions/Commits for Reference

- Commit 04851e8: Path B abrupt-jump data-quality filter
- Commit c1ae4b1: Alpaca corp-actions test handler + refetch_split_adjusted Lambda
- Session 39ce1e26: full Trial 37 re-validation + data hygiene discovery

## Key Lesson

**All backtest-derived marketing claims must be validated on genuinely-clean data**, not on whatever state the pickle happens to be in. Before any future TPE campaign, confirm:
1. Full universe is in `Adjustment.SPLIT` state
2. No symbols have abrupt jumps > 65% in rolling 252-day windows
3. All symbols' last-date aligns
4. Path B corruption filter is active

Skip any of these and the optimizer will find params that exploit artifacts rather than real alpha.
