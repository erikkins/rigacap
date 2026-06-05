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

**FIX PATH:** (1) rebuild backtest pickle properly split-adjusted (Alpaca adjustment='all' or splits feed — NOT a heuristic) and verify discontinuities vanish; (2) re-run the FULL due-diligence battery on Lambda (authoritative); (3) build **PITFWU** (point-in-time forward-walking universe) as the durable fix — bakes in corp-actions + delisted names + point-in-time membership, solving splits AND survivorship ([[project_vb_ablation_verified_jun4]] survivorship finding) at once. **Marketing frozen until the clean re-run.** Supersedes the alarmist "real MDD is 38%, stop citing 21.5%" claim — 21.5% was RIGHT.
