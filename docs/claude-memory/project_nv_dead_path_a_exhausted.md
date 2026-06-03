---
name: News-volume signal failed v2 — Path A (counts) exhausted
description: NV1/NV2/NV3/NV1_solo all failed Tier 2 bear-inclusive. NV+M3 made M3 worse. News counts without polarity NLP not a viable entry signal.
type: project
originSessionId: c3d0833d-cb3f-474f-8dd8-e530f3300c60
---
**Date:** Jun 3 2026
**Outcome:** Path A (Alpaca News article counts) FAILED methodology v2. Hypothesis discarded.

**Tier 2 results (2022-01-03 → 2026-05-29, bear-inclusive):**

| Variant | ann | sharpe | mdd | calmar | 4-target |
|---|---|---|---|---|---|
| M3 baseline | 19.31% | 1.09 | 21.53% | 0.90 | 1/4 |
| NV1_solo | 10.65% | 0.70 | 22.07% | 0.48 | 0/4 |
| NV1+M3 (filter) | 9.71% | 0.57 | 38.13% | 0.25 | 0/4 |
| NV2+M3 (boost) | 14.27% | 0.73 | 40.36% | 0.35 | 0/4 |
| NV3+M3 (regime-gated) | 14.87% | 0.79 | 38.36% | 0.39 | 0/4 |

**Key findings:**

1. **NV1_solo is the textbook v2 overfit example.** Tier 1 (26 windows × 2y, 2019-2021) was the best result of any variant ever: mean 30.20% ann / 1.30 Sharpe / 14.93% MDD / 2.15 Calmar, with 17/26 windows passing all 4 targets simultaneously. Tier 2 bear-inclusive completely demolished it — 0/4 metrics passed. This is why Tier 2 exists. Lock this case as the canonical demo of methodology v2's value.

2. **News counts without polarity NLP are not viable for entry.** The "today_pct > 0" proxy for polarity (rejecting same-day bad news where price already cratered) wasn't strong enough to filter out distressed-company news spikes during 2022 bear. NV+M3 amplified MDD from 21.53% to 38-40% — news selection during bear is actively harmful.

3. **NV+M3 destroyed M3.** Don't assume orthogonal signals additively help. Adding NV cut M3's bear-window ann roughly in half and nearly doubled MDD.

**Discipline preserved:** Did NOT tweak failing variants. Did NOT bump threshold from 1.5 to 1.7 to chase Tier 2 numbers. Methodology v2 cardinal rule held: Tier 2 fail → discard whole hypothesis.

**Next legitimate orthogonal-alpha candidates (structurally different, not NV-tweaks):**

- Path B: full sentiment NLP on the existing article corpus (counts + headline polarity score)
- Earnings surprise data (orthogonal information source, polarity built-in)
- Options flow / put-call ratio
- Sector rotation timing using regime classifier
- Pairs trading sleeve as separate strategy

**S3 artifacts (preserved for future Path B):**
- `s3://rigacap-prod-price-data-149218244179/research/news_counts/counts.parquet` — 85,643 rows (100 symbols × 2,565 dates, 2019-06 → 2026-06). Counts only; would need headline+sentiment re-pull for Path B.

**Code state:**
- News-volume backtester wiring intact in `backend/app/services/backtester.py` (helpers + filter/boost/regime modes). Disabled by default (`news_volume_filter_enabled = False`).
- `scripts/ingest_news_counts.py` works (direct REST, SDK strips next_page_token).
- Lambda `native_backtest` handler loads counts.parquet only when NV enabled.

Leave the scaffolding in place — if Path B (sentiment NLP) becomes the next test, the existing wiring + S3 path can be reused.
