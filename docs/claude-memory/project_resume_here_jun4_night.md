---
name: resume-pointer-jun-4-2026-night-pitfwu-build-in-flight
description: "End of a marathon session. Started as \"fix stale landing-page numbers\", became \"the research pickle is silently corrupted (splits + survivorship); build a parquet-native point-in-time data foundation\". PITFWU bar backfill running in background at sign-off (7:26 PM PDT Jun 4)."
metadata: 
  node_type: memory
  type: project
  originSessionId: daad830f-fb74-43b7-b3d5-fc34eed698de
---

**Sign-off:** Jun 4 2026 ~7:26 PM PDT. Erik done for the night; ping with backfill result next session.

## BAR BACKFILL — COMPLETED (Jun 4 ~late PM, exit 0)
- **21,163 symbol parquets** (~1.2 GB) at `s3://rigacap-prod-price-data-149218244179/pitfwu/bars/{symbol}.parquet`. Raw/point-in-time daily bars 2015→2026. Dead names captured (SIVB→2023-03-09, FRC→2023-04-28, ATVI, VMW confirmed).
- **Coverage gap: 21,163 of 31,373 master symbols got bars (~10k missing).** Two causes: (1) non-equity instruments in the master list (warrants/units/foreign/never-traded — no bars, fine); (2) **BATCH-POISONING BUG** — Alpaca returns HTTP 400 for the WHOLE 50-symbol batch if ONE symbol is invalid (e.g. "invalid symbol: XZW0"), so valid symbols sharing a poisoned batch got skipped. **FIX for re-run:** on a 400, retry the batch symbol-by-symbol (or smaller chunks) to isolate the bad one and salvage the rest. Gap is mostly immaterial for top-100 (core + major delistings all captured), but close it before claiming "complete".
- Re-run to fill gaps: recreate the backfill script (it's resumable — skips the 21k already done) with the symbol-by-symbol 400-retry fix.

## DATA FOUNDATION BUILT THIS SESSION (all on S3, durable)
- `pitfwu/corp_actions/calendar.parquet` — 367k Alpaca corp-actions (CUSIP-keyed: splits/reverse/dividends/mergers/name_changes/spinoffs/worthless_removals) + raw/ + by_year/.
- `pitfwu/delistings/form25_15.parquet` — SEC EDGAR Form 25/15 enumeration (20,064 Form-25 delistings, 6,062 dead CIKs). Clean delisting filter = form in {25,25-NSE,25-NSE/A,25/A} (exclude 253G Reg-A false positives). SIVB verified caught (Alpaca missed it).
- `pitfwu/universe/master_tickers.parquet` — 31,373 ticker union (corp-actions ∪ pickle ∪ Alpaca-active).
- Design doc: `docs/pitfwu-design.md`. Memory: [[project_pickle_split_bug_jun4]].

## THE BIG FINDING (see [[project_pickle_split_bug_jun4]])
Backtest pickle is NOT split-adjusted → positions held across a split book phantom −67..−95% losses. The scary "M3 bear-inclusive MDD 38%" was THIS artifact; split-adjusted it's ~20.6% (the cited 21.5% was RIGHT). **PROD live data IS adjusted — pickle only.** Survivorship ALSO confirmed (SIVB/FRC/ATVI absent from pickle). PITFWU (parquet, raw bars + corp-actions events + as-of-T universe + EDGAR dead-names) fixes both, free, no vendor. **ALL bear-inclusive research numbers SUSPECT until re-run on PITFWU.**

## NEXT STEPS (post-backfill)
1. Verify bar backfill completion.
2. As-of-T universe builder (point-in-time top-N by liquidity from raw bars).
3. Engine `apply_corp_actions` step (Zipline-style sim-time split/merger/delist handling).
4. **Authoritative battery re-run on clean data → UNFREEZES marketing.** Re-test: M3 bear-incl (expect ~20.6 MDD), recent 50.2, VB ablation, dynamic basket, AND re-open "news DEAD" verdict + universe-size + rebalance (all measured on buggy data).
5. Low-pri: CIK→ticker enrichment for ~4,639 dead-CIK micro-cap tail (doesn't affect top-100).

## OTHER LIVE THREADS (tasks #1-8)
- **VB shipped to prod** (commits 45e3a20 + 1ae73dd, deployed): `model_portfolio_service` basket overlay (VIX>30 → 7 mega-caps, 10%/8% trail, position_kind='basket'). M3 = base + VB is the flagship, basket INCLUDED (no add-on tier — VB-alone is a fair-weather trap). Backtester dynamic-basket support also deployed (research, default-off).
- **UNCOMMITTED:** `scripts/build_10y_pickle.py` adjustment fix (RAW→Adjustment.SPLIT) — local edit, not committed. Commit when convenient (it's the source of the raw-split pickle bug).
- **UI mockups rendered** `design/mockups/` (3bucket-newfirst + daily-dashboard-context) — awaiting Erik review. 3-bucket order LOCKED: New→Open→Approaching (New first). **VB card must scrub "VIX 30" — Erik: never reveal the trigger on screen.**
- **Frontend M3-number surgery (task #5): GATED** on clean re-validation. Do NOT touch landing/track-record/blog numbers until PITFWU re-run.
- Open decisions: total-return vs price-return (dividends); **weekly-vs-biweekly rebalance bug** (backtester `_should_rebalance`=weekly-Fridays vs config/prod=biweekly).
- VB prod parity replay (task #3) still pending.

**Marketing numbers (if needed before re-validation — but DON'T publish):** M3 bear-incl ~19-21% ann / ~1.0-1.1 Sharpe / ~20.6% MDD (clean); recent-2y 50.2/2.22/17.7. Supersedes Trial-37 (+384%) and Apr-28 (+160%) which are STALE on live LandingPageV2/TrackRecordV2/blogs.
