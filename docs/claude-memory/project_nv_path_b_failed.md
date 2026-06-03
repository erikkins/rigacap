---
name: News-sentiment Path B failed v2 — news exhausted as entry signal
description: Haiku-scored sentiment improved over today_pct proxy but still failed v2 Tier 2. NV-P1_solo notable: first variant ever to pass MDD on bear-inclusive Tier 2 (17.82%).
type: project
originSessionId: c3d0833d-cb3f-474f-8dd8-e530f3300c60
---
**Date:** Jun 3 2026
**Outcome:** Path B (Claude Haiku polarity scoring) FAILED methodology v2. ALL FOUR variants 0/4 on Tier 2.

**Tier 2 results (2022-01-03 → 2026-05-29, bear-inclusive):**

| Variant | ann | sharpe | mdd | calmar | 4✓ |
|---|---|---|---|---|---|
| M3 baseline | 19.31% | 1.09 | 21.53% | 0.90 | 1/4 |
| NV-P1+M3 (sent filter) | 12.83% | 0.67 | 38.30% | 0.33 | 0/4 |
| NV-P2+M3 (sent boost) | 18.36% | 0.89 | 37.92% | 0.48 | 0/4 |
| NV-P3+M3 (regime-gated) | 15.56% | 0.77 | 37.94% | 0.41 | 0/4 |
| **NV-P1_solo** | 12.14% | 0.83 | **17.82%** | 0.68 | 1/4 ← MDD |

**Key findings:**

1. **Path B beat Path A on every variant comparison.** Haiku sentiment IS a better polarity proxy than today_pct price-direction. But the improvement was 2-3pp annualized, not the 8-10pp needed to clear v2.

2. **NV-P1_solo is the FIRST variant in 30+ tests to pass MDD ≤ 20% on bear-inclusive Tier 2** (17.82%, vs 20% target). Real safety improvement. But ann is 12.14% (vs 20% target), 8pp short. The variant is "safer M3" not "better M3."

3. **Adding news to M3 doubles MDD.** Both Path A and Path B: M3 alone 21.53% MDD → M3+any-news ~38% MDD. Multiplicative concentration: basket + news filter both select similarly during stress. Cannot combine the two without paying for it.

4. **Sentiment distribution looks healthy.** 22,205 articles scored positive (10.5%), 10,220 negative (4.8%), 178,545 neutral (84.6%), mean +0.040. The Haiku scoring is sane — most articles are commentary, only 15% direct directional events.

**Cost:** $3.73 (Haiku) + $2.43 (lost from prior in-memory run, now safeguarded by checkpointing).

**S3 artifacts (preserved for future hypotheses):**
- `s3://rigacap-prod-price-data-149218244179/research/news_headlines/headlines.parquet` (35 MB, 325,775 article-symbol rows)
- `s3://rigacap-prod-price-data-149218244179/research/news_sentiment/articles.parquet` (11 MB, 210,970 scored articles)
- `s3://rigacap-prod-price-data-149218244179/research/news_sentiment/sentiment_daily.parquet` (300 KB, 85,643 daily aggregates)

**Hypotheses NOT yet tested with cached sentiment (no re-pull needed):**
- Sentiment as **EXIT** signal (close positions on neg sentiment spike, not entry filter)
- Sentiment as **POSITION-SIZING modifier** (cut size when sentiment-mean < -0.5)
- Sentiment-divergence (price up, sentiment down → bearish setup)
- Sentiment-momentum (trailing 5d sentiment slope)

**Cardinal v2 rule preserved:** Did NOT tweak threshold/lookback/weight after Tier 2 failures. News-as-entry-signal is fully exhausted under v2 testing.

**Net state after Jun 3 2026:**
- M3 remains the best v2-compliant variant (1/4 targets, smallest gaps)
- News entry signal: DEAD (both Path A counts and Path B sentiment)
- Next legitimate orthogonal mechanisms: sentiment-as-EXIT, sentiment-as-SIZE, earnings surprises, options flow, mean-reversion sleeve as separate product
