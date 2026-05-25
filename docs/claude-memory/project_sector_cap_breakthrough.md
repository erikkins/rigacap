---
name: Sector cap = THE breakthrough lever — validated production-ready May 24 2026
description: MOMENTUM_SECTOR_CAP=6 (top 6 candidates per GICS sector) validated across 52 weekly start dates. Median Sharpe 1.16, Calmar 1.34, MaxDD 15.5%. Worst path Sharpe 0.93. The lever we'd been hunting all weekend.
type: project
originSessionId: c3d0833d-cb3f-474f-8dd8-e530f3300c60
---
## The result

**MOMENTUM_SECTOR_CAP=6 alone** delivers what 5 days of stop/sizing/regime/VIX/TPE experiments could not.

**52-Monday distribution (cap=6, 11y pickle, Date 2021-01-04 → 2021-12-27 weekly Mondays):**

| Metric | min | P10 | P25 | **median** | P75 | P90 | max |
|---|---|---|---|---|---|---|---|
| Return (5y) | 98% | 110% | 116% | **132%** | 144% | 148% | 149% |
| Annualized | ~15% | ~16% | ~17% | **~18%** | ~20% | ~20% | ~20% |
| Sharpe | 0.93 | 1.05 | 1.10 | **1.16** | 1.21 | 1.27 | 1.30 |
| MaxDD | 12.3% | 12.3% | 12.3% | **15.5%** | 15.5% | 15.7% | 17.2% |
| Calmar | 0.95 | 1.03 | 1.18 | **1.34** | 1.45 | 1.48 | 1.69 |

**Win rates:**
- Sharpe ≥ 1.0: **50/52 (96%)**
- Calmar ≥ 1.0: 49/52 (94%)
- MaxDD ≤ 20%: **52/52 (100%)**

## vs everything else we tried

| variant | median Sharpe | median MaxDD | median Calmar |
|---|---|---|---|
| canonical (no cap) baseline | 0.83 | 33.5% | 0.65 |
| t15/s8 (DD-tighten trail) | 0.91 | 27.6% | 0.89 |
| **cap=6 ⭐** | **1.16** | **15.5%** | **1.34** |
| cap=3 | 1.14 | 13.2% | 1.27 |

Cap=6 wins on every metric except MaxDD ceiling (cap=3 has tighter MaxDD band but one outlier path drops to Sharpe 0.55 — cap=6 has no path-failure mode).

## Why this is the lever

The strategy's structural weakness was concentration risk. On any given day, 60%+ of buy_signals were in 1-2 sectors (typically tech). When tech rolled over, the portfolio took the full hit. All exit-side levers (stops, sizing) attacked the SYMPTOM, not the CAUSE. Sector cap attacks the cause: enforce top-6-per-sector at the candidate filter so the portfolio CAN'T end up concentrated.

It also makes DD-tighten (t15/s8) almost vestigial: during the cap=6 sweep, t15/s8 fired on only 27/52 dates and only 1-2 periods each. Sector cap kept MaxDD low enough that the safety net was rarely needed.

## What was needed to make it work (infrastructure)

1. **Sector data backfill** (`scripts/backfill_sectors.py`): bulk yfinance `.info` fetch for all 4621 symbols, cached to `s3://rigacap-prod-price-data-149218244179/universe/sectors_cache.json`. 95% coverage (4412 with sector).
2. **stock_universe_service merge** (`backend/app/services/stock_universe.py`): `_merge_sectors_cache()` loads sectors_cache.json from S3 (with local /tmp fallback for cross-account local AWS profile) and merges into `symbol_info`. Auto-called from `ensure_loaded()`. Idempotent.
3. **`MOMENTUM_SECTOR_CAP=6`** in `config.py`. Scanner already had the filter code (lines 718-734) — just needed the value lifted from 0.

## Production rollout

**Shipped May 24 2026**: MOMENTUM_SECTOR_CAP 0 → 6 in `backend/app/core/config.py`. Sector data infra shipped earlier same day.

**First production scan with new cap**: Tuesday May 26 2026, 4:30 PM ET (Mon = Memorial Day holiday). Wednesday morning subscribers see diversified signals.

**Existing positions unaffected** — sector cap only filters NEW entries.

## Marketing-numbers implications

OLD canonical claim (Apr 28 baseline): +160% / Sharpe 0.92 / MaxDD 20.4% / Calmar ~0.85.
NEW reality (cap=6, 52-Monday median): +132% / Sharpe 1.16 / MaxDD 15.5% / Calmar 1.34.

Return is slightly lower in median terms (132 vs 160) but the distribution is much tighter — worst-case +98% vs the canonical's much wider spread. Risk-adjusted, this is a clear win:
- Sharpe up 0.83→1.16 (+39%)
- MaxDD cut 33%→15% (-55%)
- Calmar up 0.65→1.34 (+106%)

The Sunday newsletter P.S. tease ("research metric improved by roughly a third") drastically UNDERSTATES the result. Calmar nearly doubled.

## Process lessons

1. Run TONS of single-date experiments cheaply before committing to 52-Monday sweeps. Cap=2/3/4/5/6 single-date told us almost everything we needed.
2. **Sector data was missing infra** that we discovered AT THE SAME TIME as the lever finding. The two unblocked each other.
3. The parallelism unlock (skip-DB-writes flag) was the FORCE MULTIPLIER. Without it the cap=3 + cap=6 validation would've taken 6+ hours serially instead of 2 in parallel.
4. The simplest lever (one config integer change) was the answer — after a week of complex stop/sizing/regime/VIX/TPE experiments. Always check the obvious thing first.
