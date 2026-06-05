---
name: critical-backtest-pickle-is-not-split-adjusted-jun-4-2026
description: "The prod backtest pickle (s3 prices/all_data.pkl.gz, downloaded Jun3) has RAW unadjusted stock-split discontinuities. Any backtest holding a position across a split books a phantom -67% to -95% loss. Caused the bogus \"M3 bear MDD 38%\" scare; true MDD is ~20.6%. PROD live data IS adjusted — only the pickle is affected, pull-time dependent."
metadata: 
  node_type: memory
  type: project
  originSessionId: daad830f-fb74-43b7-b3d5-fc34eed698de
---

**Date:** Jun 4 2026. Triggered by an unexplained M3 bear-inclusive MaxDD of ~38% (Lambda) / ~34% (local) vs the cited 21.5%.

**ROOT CAUSE (proven):** the backtest pickle's price series is **raw / not split-adjusted.** Every major split in 2022-2026 is a discontinuity:
| Stock | Split | Pickle close jump |
|---|---|---|
| AMZN | 20:1 2022-06-06 | $2447 → $124.79 (19.6×) |
| GOOGL/GOOG | 20:1 2022-07-18 | $2235 → $109 (20.5×) |
| TSLA | 3:1 2022-08-25 | $891 → $296 (3.0×) |
| NVDA | 10:1 2024-06-10 | $1209 → $121.79 (9.9×) |
Plus AAPL/TSLA 2020 splits, WMT, CSX, OXY. Heuristic detector found **9 splits** in the 104-symbol run universe alone.

**Mechanism:** when a backtest HOLDS a position across the split date, the close "drops" ~1/N → fake −67% to −95% trade → 8% trail / 12% trail fires → phantom loss + corrupted momentum/MA/DWAP for ~200 days after. M3 bear-inclusive: the VB basket held AMZN + GOOGL across their 2022 splits → two fake −94% trades (~$17k phantom loss on $100k) → MaxDD inflated 21.5% → 38%.

**PROOF of fix:** split-adjusting the pickle (back-divide pre-split px by N) → M3 bear-inclusive MaxDD **34.4% → 20.6%** (≈ the cited 21.5%); ann **~10% → 26.2%**; sharpe → 1.38; worst basket trades now sane (META −20.8%, no more −94%). The "38% disaster" was NEVER real — and clean data shows the strategy is BETTER (clears 20/20/1/1 North Star locally).

**SCOPE — what's contaminated:** EVERY backtest with a split-crossing hold. All bear-inclusive + split-window results (M3, base, VB ablations, dynamic basket, 2019-21 Tier-1 with the Aug-2020 AAPL/TSLA splits). The recent 50.2% reproduced clean only BY LUCK (nothing held NVDA across its 2024-06-10 split). **All prior research-pickle numbers are suspect until re-run on adjusted data.**

**NOT affected: production.** Erik confirmed (Jun 4) prod live data IS split-adjusted — only the backtest pickle is raw, and it's pull-time dependent (the Jun-2 pickle that gave the original 21.5% was apparently adjusted; the Jun-3 prod pickle is not). Likely cause: Alpaca daily bars need `adjustment='all'`; pickle built/pulled raw.

**PITFWU is buildable on existing Alpaca (no vendor) — verified Jun 4:** Alpaca SIP returns delisted tickers' full history (SIVB/FRC/ATVI/VMW/SGEN/BBBY all 6/6, up to delisting). Alpaca Corporate Actions API (`/v1/corporate-actions`) returns the FULL CUSIP-keyed calendar: forward/reverse splits, cash/stock/stock+cash mergers, name_changes, cash/stock dividends, unit_splits. Design doc: `docs/pitfwu-design.md`. Principles: CUSIP primary key (handles renames/reuse); RAW point-in-time prices; corp-actions as SIM EVENTS (Zipline approach, our own engine — Erik wants no Zipline/QuantRocket migration). Erik's key insight: fully-adjusting bakes FUTURE splits into past prices → breaks the $15 min-price filter (AAPL 2019 raw ~$40 → ~$10 adjusted → wrongly excluded). Correct = adjusted as-of-T.

**SURVIVORSHIP ENUMERATION SOLVED — SEC EDGAR (free, exhaustive), NO vendor (Jun 4):** Alpaca enumeration is NOT exhaustive (assets API misses SIVB/FRC/ATVI…; corp-actions calendar 27,994 syms catches most but still misses SIVB/REV). Authoritative source = **SEC EDGAR Form 25** (removal-from-listing) + Form 15 (deregistration) — legally required per delisting → complete by construction. Download quarterly `form.idx` (sec.gov/Archives/edgar/full-index/{yr}/QTR{n}/form.idx), grep form `25`/`25-NSE`/`15` → ~622 delistings/qtr, ~25-27k/decade, with company+CIK. VERIFIED catches SIVB (Form 25-NSE 2023-05-02) — the name Alpaca missed. Map CIK↔ticker↔CUSIP via EDGAR submissions + Alpaca corp-actions cross-walk. EDGAR needs User-Agent header (403 without). Stage-1 corp-actions calendar already cached: `s3://…/pitfwu/corp_actions/calendar.parquet` (367k events). Erik's "save raw for posterity" = durable S3 parquet default for all pulls.

**ALSO found:** backtester `_should_rebalance` = WEEKLY (Fridays) but config/prod = biweekly(14d) — real cadence inconsistency to reconcile. Universe: top-100 beat top-200 (Jun-1, 10.4 vs 8.8 ann) but on buggy pickle.

**FIX PATH:** (1) rebuild backtest pickle properly split-adjusted (Alpaca adjustment='all' or splits feed — NOT a heuristic) and verify discontinuities vanish; (2) re-run the FULL due-diligence battery on Lambda (authoritative); (3) build **PITFWU** (point-in-time forward-walking universe) as the durable fix — bakes in corp-actions + delisted names + point-in-time membership, solving splits AND survivorship ([[project_vb_ablation_verified_jun4]] survivorship finding) at once. **Marketing frozen until the clean re-run.** Supersedes the alarmist "real MDD is 38%, stop citing 21.5%" claim — 21.5% was RIGHT.
