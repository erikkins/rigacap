---
name: News/sentiment research book COMPLETE — 19 variants, 5 mechanisms, 2 best 2/4
description: Jun 3 2026 — entire news/sentiment book exhausted under v2 methodology. Best results: NV-T1+M3 (ann+sharpe pass, MDD fail) and NV-T1_solo (sharpe+mdd pass, ann fail). No 4/4.
type: project
originSessionId: c3d0833d-cb3f-474f-8dd8-e530f3300c60
---
**Date:** Jun 3 2026 (one-day research sprint)
**Outcome:** News/sentiment research book COMPLETE under v2 methodology. 19 variants across 5 mechanisms. No 4/4 v2 pass found. Two distinct 2/4 candidates.

**Best results recap:**

| Variant | ann | sharpe | mdd | calmar | 4✓ |
|---|---|---|---|---|---|
| M3 baseline | 19.31% | 1.09 | 21.53% | 0.90 | 1/4 |
| **NV-T1+M3 (best ann/sharpe)** | **21.41% ✓** | **1.02 ✓** | 39.77% | 0.54 | **2/4** |
| **NV-T1_solo (best sharpe/mdd)** | 16.48% | **1.08 ✓** | **19.05% ✓** | 0.87 | **2/4** |

**All 5 mechanisms tested:**

| # | Mechanism | Variants | Best 4✓ | Notable |
|---|---|---|---|---|
| 1 | NV1/2/3 — counts entry filter (Path A) | 4 | 0/4 | All dead; counts have no polarity |
| 2 | NV-P1/2/3 — sentiment entry filter (Path B) | 4 | 1/4 (P1_solo MDD) | Haiku $3.73 to score 210k articles |
| 3 | NV-X1/2/3 — sentiment hard exit | 4 | 1/4 (X1_solo MDD record 15.76%) | First MDD pass on bear-inclusive Tier 2 |
| 4 | **NV-T1/2/3 — sentiment asymmetric trail** | 4 | **2/4** | Breakthrough; only mechanism that hit ann+sharpe |
| 5 | NV-S1/2 — sentiment-as-position-sizing | 3 | 1/4 | Redundant with trail; sizing noise broke sharpe |

**Compositional law (proven across 16 news+M3 variants):**
- M3 alone: high ann + sharpe + acceptable MDD → 1/4
- News + M3: ann/sharpe pass possible but MDD ALWAYS ~38-40% (concentration multiplication)
- News + solo: MDD passes but ann stuck at 11-17% (no concentration upside)
- Stacking news mechanisms (sizing on top of trail) does NOT compound

**Cardinal v2 rules preserved:**
- 4 documented overfit cases: NV1_solo Path A, NV-T2+M3 (Tier 1 best ever → Tier 2 worst), NV-S2+T1+M3, NV-P1_solo Path B
- ZERO threshold tweaks after Tier 2 failures
- Every new variant tested was structurally different from prior failures

**S3 cached forever (never re-pull):**
- `research/news_headlines/headlines.parquet` (35 MB, 325k article-symbol rows)
- `research/news_sentiment/articles.parquet` (11 MB, 210k Haiku scores)
- `research/news_sentiment/sentiment_daily.parquet` (300 KB, 85k daily aggregates)

**Total cost:** ~$6 (Haiku scoring) + Lambda within free tier. Plus $2.43 wasted on the no-checkpoint run (driving the new `feedback_never_keep_paid_work_in_memory.md` rule).

**Next legitimate research directions (orthogonal — different data source, not news):**
- Earnings surprises (different data source, polarity built-in)
- Options flow / put-call ratio
- Sector rotation timing using regime classifier
- Mean-reversion sleeve as SEPARATE product (Erik's "symbiotic product" idea)

**Or ship one of the 2/4 with disclosed gap:**
- NV-T1+M3 (21.41% ann, 1.02 sharpe, 39.77% MDD): marketing-friendly headlines, MDD disclosed
- NV-T1_solo (16.48% ann, 1.08 sharpe, 19.05% MDD): risk-adjusted product, ann disclosed
- M3 alone (19.31/1.09/21.53/0.90): simpler, 1/4 just like before research started
