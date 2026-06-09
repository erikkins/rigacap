# PITFWU — Point-In-Time Forward-Walking Universe (design)

> **Status:** design draft, Jun 4 2026. Goal: a survivorship-free, corp-action-correct,
> point-in-time research data layer + backtest semantics, built entirely on the existing
> paid Alpaca SIP subscription (no new vendor, no Zipline migration).

## 1. Why

Two classes of bug surfaced (Jun 4 2026) that quietly corrupt backtests:

1. **Splits not point-in-time.** The current pickle has *raw* split discontinuities
   (AMZN/GOOGL 20:1, NVDA 10:1) → positions held across a split book a phantom −67% to
   −95% loss (inflated M3 bear MaxDD 21.5% → 38%). Even "fully adjusted" data is wrong for
   **price-level logic**: fully back-adjusting bakes *future* splits into past prices, so
   e.g. AAPL early-2019 (raw ~$40) becomes ~$10 adjusted → wrongly fails our **$15
   min-price filter**. Correct = adjusted **as-of-T**, never as-of-today.
2. **Survivorship.** The universe is built from *today's* listed names, so companies that
   delisted/merged/went bankrupt (SIVB, FRC, ATVI, VMW, SGEN, BBBY) are absent entirely —
   the backtest can only "see" winners. Verified: Alpaca SIP **does** return all six dead
   tickers' full history up to delisting. The data was there; we never asked for it.

## 2. Core principles

- **CUSIP is the primary key, not ticker.** Alpaca's corp-actions are CUSIP-keyed. CUSIP
  persists across ticker renames (FB→META, SQ→XYZ) and distinguishes ticker *reuse* (a
  symbol reassigned to a different company = different CUSIP). Stitch price history by CUSIP.
- **Store RAW point-in-time prices.** Never pre-adjust the history. Each backtest date uses
  the actual price that traded that day, adjusted only for corp-actions on/before that date.
- **Corp-actions are simulation events, not data transforms.** A calendar (from Alpaca,
  by CUSIP) drives event handlers applied to *held positions* during the run — the Zipline
  approach, in our own engine.
- **Universe is as-of-T.** Top-N by liquidity recomputed point-in-time, including names that
  later die; IPOs enter when they cross the liquidity threshold.

## 3. Corp-action taxonomy & point-in-time handling

| Event | Alpaca type | Handling in the sim (applied to held positions on the date) |
|---|---|---|
| **Forward split** | `forward_splits` (new/old rate) | shares ×(new/old), price ÷ratio. Value continuous, no phantom loss. |
| **Reverse split** | `reverse_splits` | shares ÷ratio, price ×ratio; fractional → cash. (Often distress — interacts with min-price filter.) |
| **Cash dividend** | `cash_dividends` (rate) | credit cash on ex-date (total-return) OR drop price (price-return). **Decision needed (§6).** |
| **Stock dividend / spinoff** | `stock_dividends` | shares ×(1+rate) or credit spun-off entity's value; adjust parent. |
| **Cash merger** | `cash_mergers` (rate) | **force-close** the position at $rate on effective_date — a *clean exit*, NOT a delist loss. |
| **Stock merger** | `stock_mergers` (acquirer_rate) | convert acquiree→acquirer shares ×rate; continue holding (or exit next rebalance). |
| **Stock+cash merger** | `stock_and_cash_mergers` | convert partial to acquirer stock + credit cash_rate. |
| **Name change** | `name_changes` (old/new symbol, same CUSIP) | none to P&L — the CUSIP key already makes the series continuous across the rename. |
| **Unit split (SPAC)** | `unit_splits` | edge case; our universe largely excludes SPAC units/warrants. |
| **Delisting (bankruptcy / go-private, no merger)** | *absence of further bars + no merger event* | force-close at last traded price (or ~0 for bankruptcy). **This is where REAL losses live** — trailing stop usually exits first, but gap-to-zero is a genuine risk the survivorship-free data finally captures. |
| **IPO** | first available bars | enters the as-of-T universe once it has enough history + liquidity to rank. |
| **Symbol reuse** | different CUSIP, same ticker | CUSIP key keeps them as *separate* series — never stitch across CUSIPs. |

## 4. Architecture

```
Alpaca SIP (paid) ──> [1] Corp-Actions Calendar (by CUSIP, full history)
                 └──> [2] Raw OHLCV per CUSIP (incl. delisted, split=RAW/unadjusted)
                                │
                                ▼
                    [3] Symbol↔CUSIP↔date map (handles renames/reuse)
                                │
                                ▼
        [4] As-of-T Universe builder (top-N by liquidity, point-in-time, survivorship-free)
                                │
                                ▼
        [5] Backtester: reads raw point-in-time prices; on each date applies the
            corp-action event handlers (§3) to held positions before exit/entry logic.
```

- **[1]/[2]** pulled from Alpaca and cached durably (S3 parquet, per the never-refetch rule).
- **[4]** supersedes `_get_top_symbols_as_of` (which currently ranks today's names and fixes
  the universe at the *start* date — both survivorship-biased and not re-ranked).
- **[5]** is the one real engine change: a `apply_corp_actions(date, positions)` step.

## 5. Build plan (on Alpaca; staged) — PARQUET-FIRST

**PITFWU is built on Parquet, not pickle** — it converges with the existing parquet-migration
roadmap (per-symbol/partitioned S3 parquet → point-in-time partial reads, no monolithic OOM),
and the "raw-for-posterity" cache IS that parquet. The legacy pickle is end-of-life; we do
NOT build a new one.

- **Stage 0 — DROPPED (throwaway pickle rebuild).** We already have local proof the split fix
  lands at ~20.6% MaxDD; building a throwaway split-adjusted *pickle* just to re-validate is
  wasted work when the authoritative bench is the parquet layer. Done instead: fixed the latent
  `build_10y_pickle.py` adjustment bug (was RAW → now `Adjustment.SPLIT`) so any future full
  pickle build is at least split-adjusted. **Prod pickle untouched** (builds go to STAGING only).
- **Stage 1 — corp-actions calendar:** pull full `corporate-actions` history (all types) by
  CUSIP, cache to S3. (We already touch this API in Layer-2 hygiene.)
- **Stage 2 — dead-name enumeration (SOLVED — SEC EDGAR, free + exhaustive).** Alpaca's
  enumeration is NOT exhaustive (assets API misses most majors — SIVB/FRC/ATVI absent; the
  corp-actions calendar (27,994 syms) is better but still misses SIVB, REV). The authoritative
  source is **SEC EDGAR Form 25** (notification of removal from listing) + Form 15
  (deregistration) — *legally required* for every delisting, so complete by construction.
  Mechanism: download quarterly `form.idx` (e.g. sec.gov/Archives/edgar/full-index/2023/QTR1/form.idx),
  filter form=`25`/`25-NSE`/`15-12B`/`15-12G` → every delisted company + CIK (~622/qtr,
  ~25-27k/decade). VERIFIED: SVB Financial (SIVB) → Form 25-NSE 2023-05-02 — catches the exact
  name Alpaca missed. Then map CIK↔ticker↔CUSIP (EDGAR submissions + the corp-actions
  symbol/cusip cross-walk we already pulled). Archive the form.idx files to S3 for posterity.
  Use EDGAR `User-Agent` header (contact email) — 403 without it.
- **Stage 3 — raw bar backfill per CUSIP** (incl. delisted; split=raw), S3 parquet.
- **Stage 4 — as-of-T universe builder** + symbol/CUSIP/date map.
- **Stage 5 — engine `apply_corp_actions` step** + point-in-time universe wiring; parity-check
  vs the Stage-0 adjusted pickle on a clean window.
- **Stage 6 — re-run the full battery** on PITFWU; this becomes the authoritative bench.

## 6. Open decisions

- **Total-return vs price-return** (credit dividends or not). Momentum holds are short
  (~2-3mo) so dividend impact is small, but be consistent and disclosed.
- **Dead-name completeness** — confirm the merger/delist calendar + assets API enumerate the
  full historical top-N, or seed from index-constituent history.
- **Stock-merger continuation** — hold the acquirer post-merger, or exit at next rebalance?
- **Reverse-split / min-price interaction** — reverse splits lift sub-$15 names over the
  filter; decide if that's desired (it often flags distress).
- **Rebalance cadence (separate bug):** backtester `_should_rebalance` = **weekly (Fridays)**
  while config/prod say **biweekly (14d)** — reconcile; it changes what "M3" is and the WF↔prod parity.

## 6b. Universe methodology (LOCKED Jun 5)

Goal: re-runs change ONLY the data (survivorship + splits), so we isolate the
bug-fix impact from any methodology drift. Therefore **match production exactly**:

- **Metric:** top-N by **60-day average volume** with MIN_PRICE floor applied at
  the selection date (production `_get_top_symbols_as_of`). NOT the v1 panel's 20d
  dollar-volume (low impact for top-100, but match it to avoid confounds).
- **Per-period re-rank:** production re-selects the universe **every period**
  (walk_forward_service line ~1495, inside the period loop) — point-in-time on the
  ranking, just survivorship-biased on the candidate pool (the pickle). PITFWU
  fixes the candidate pool; keep the per-period re-rank.
- top-100, ETF-excluded (_EXCLUDED_SET).

**Engine state (Jun 5):** the veneer + data are VERIFIED (7/7, 3 cross-checked vs
yfinance). The v1 runner (`scripts/pitfwu_wf.py`) uses the SINGLE-WINDOW backtester
path → fixes the universe at start (does NOT match production per-period) and is
the only path with VB-basket params. The WF-service path re-ranks per-period but
has NO VB params. **Authoritative-bench build = inject PITFWU pool into the
per-period WF path AND plumb cb_pause_basket_* through it.** Parity-critical
(per-period carry-over must match prod) — do it as a focused pass, not a rush.

## 7. Effort

Multi-week data-engineering project. Stage 0 is hours (unblocks re-validation). Stages 1-6
are the durable build. No new data spend; no framework migration (Zipline is the reference
for *how*, not a dependency we take on).
