---
name: Intraday WF validation findings (Apr 30 2026) — pickup tomorrow
description: Production-matched 5-min cadence simulator suggests WF overstates production by ~5 pp annualized. Linear approximation only — needs b-full re-run. Major potential parity gap to characterize before marketing implications kick in.
type: project
originSessionId: 1081317d-f863-470f-ab07-65ddc614e856
---
**What we built (Apr 30 2026 night):**
- `backend/app/services/intraday_cache.py` — Idempotent S3 parquet cache for Alpaca minute bars at `s3://rigacap-prod-price-data-149218244179/intraday/<symbol>/<YYYY-MM-DD>.parquet`. Round-trip canonical (re-reads cache after fresh fetch).
- `backend/app/services/intraday_wf_validator.py` — `IntradayWFValidator` walks each trade minute by minute. Configurable check cadence (default 5-min, matching `model_portfolio_service.process_live_exits`). Smart filter: skips days where stop is mathematically impossible.
- `main.py` handlers: `test_intraday_fetch` (one-shot pipeline test) and `intraday_wf_validation` (bulk job, accepts trades + daily_bars in payload, writes results to S3).
- Local extraction script that pulls trades + daily bars from `/Users/erikkins/CODE/stocker-app/backend/data/all_data_11y.pkl.gz` (4422 symbols, 2016-01-04 → 2026-04-22).

**Results — 249 trailing-stop trades from 11y WF:**

| Cadence | Better/Worse | Median delta | Mean (clean) | Portfolio Δ (15% sizing, linear) | 11y impact |
|---|---|---|---|---|---|
| 1-min (too aggressive) | 182/65 | +2.54 pp | -2.25 pp | -82.57 pp | 21.44% → 20.15% ann (-1.29 pp) |
| **5-min (matches production)** | 172/75 | +1.88 pp | **-7.40 pp** | **-272 pp** | **21.44% → 16.56% ann (-4.88 pp)** |

**Headline: production-matched simulator suggests WF backtest OVERSTATES production performance by ~5 pp annualized.** This is the OPPOSITE of the initial smoke-test reading (which showed intraday "always better"). The flip happened after:
1. Removing data-anomaly outliers (4 trades — FCEL×2, AMRN, NCTY — flash-spike artifacts in minute bars).
2. Switching from 1-min to 5-min check cadence.
3. Switching exit-price from `HWM × 0.88` (trigger) to live-price-at-check (matches production).

**Caveats keeping this from being conclusive:**
- **Linear approximation only.** Doesn't model the cascading effect of earlier exits → freed capital → reallocated at next biweekly rebalance → potentially picks up another winner. Real portfolio-weighted impact (b-full) could be materially different.
- **My simulator may not perfectly match production.** Worth one more code-read of `model_portfolio_service.process_live_exits` to confirm exact semantics.
- **The 10 "winner-cut-short" trades** (IREN, ASTS, RIOT, NVAX, TNDM, MRNA, ASAN, CELH, SNDK, LITE) account for ~70% of the negative impact. Lockout-window or multi-minute confirmation could plausibly recover most of these.

**Tomorrow's decision tree (pickup):**

Three priority options:

1. **Build b-full** — re-run the actual WF backtester with intraday-aware exits baked into the simulation engine. Handles capital reallocation. Definitive answer. ~half-day work.

2. **Verify production code matches simulator** — quick code read of `process_live_exits`. ~30 min. Should do BEFORE b-full so we know we're modeling the right thing.

3. **Cadence sweep** — run validation at 1/3/5/10/30 min cadences. Characterizes the parameter. ~hour. Would inform later TPE work.

Recommended sequence: 2 → 1 → 3.

**Connected work tomorrow / next week:**
- [Intraday data anomalies](project_intraday_data_anomalies.md) — fix the simulation execution model (multi-min confirmation + slippage) before any TPE.
- [CB-in-production wiring](project_cb_production_wiring.md) — closes the OTHER parity gap.
- [Ticker-rename plumbing](project_ticker_rename_plumbing.md) — fix SQ/XYZ duplicates revealed in this work.
- [TPE on intraday parameters](project_intraday_tpe_optimization.md) — only after b-full + univariate sweeps.

**Key files for tomorrow:**
- `/tmp/intraday_wf_full_results.json` — 1-min cadence per-trade results (s3://.../research/intraday_wf_full_249.json)
- `/tmp/intraday_wf_5min_results.json` — 5-min cadence per-trade results (s3://.../research/intraday_wf_full_249_5min.json)
- `/tmp/wf_11y_trades.json` — extracted 410 WF trades for re-use
- `/tmp/intraday_wf_5min.json` — Lambda invocation payload (ready to re-run)

**Marketing implications (to think about, NOT to act on yet):**
The current published numbers (21.5% annualized over 5y / 11y) are based on EOD WF backtest. If b-full confirms a ~5 pp gap, that's a real credibility issue — subscribers experience worse than what the marketing claims. Don't publish anything new pending this resolution. The CB-in-production wiring and intraday-execution fixes are the path to closing the gap rather than restating numbers down.
