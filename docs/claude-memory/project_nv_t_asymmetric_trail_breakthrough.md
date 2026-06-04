---
name: NV-T asymmetric sentiment trail — first variants to pass 2/4 v2 targets
description: Sentiment-aware continuous trail modifier. NV-T1+M3 first variant ever to pass ann≥20% AND sharpe≥1.0 on bear-inclusive Tier 2. NV-T1_solo first to pass sharpe AND mdd simultaneously.
type: project
originSessionId: c3d0833d-cb3f-474f-8dd8-e530f3300c60
---
**Date:** Jun 3 2026
**Outcome:** Asymmetric trail mechanism produces FIRST 2/4 v2 results. Still no full 4/4 pass.

**Mechanism:** `effective_stop_pct = base − (sentiment_mean × scale)`, clamped to [min, max].
- Positive sentiment → wider trail (let winner run on good news)
- Negative sentiment → tighter trail (cut faster on bad news)
- Composes AFTER profit_lock and DD-tighten so defensive overrides still win when tighter

**Tier 2 results (2022-01-03 → 2026-05-29, bear-inclusive):**

| Variant | ann | sharpe | mdd | calmar | 4✓ |
|---|---|---|---|---|---|
| M3 baseline | 19.31% | 1.09 | 21.53% | 0.90 | 1/4 |
| **NV-T1+M3 (scale=8, 3d)** | **21.41% ✓** | **1.02 ✓** | 39.77% | 0.54 | **2/4** |
| NV-T2+M3 (scale=16, 3d) | 12.76% | 0.65 | 39.51% | 0.32 | 0/4 |
| NV-T3+M3 (scale=8, 7d) | 21.42% ✓ | 0.99 | 40.82% | 0.52 | 1/4 |
| **NV-T1_solo (no M3)** | 16.48% | **1.08 ✓** | **19.05% ✓** | 0.87 | **2/4** |

**Three major findings:**

1. **NV-T1+M3 is the FIRST variant ever to pass ann + sharpe simultaneously on bear-inclusive Tier 2.** +2.1pp ann over M3 baseline (19.31 → 21.41), sharpe holds at 1.02. Erik's "loosen on good news" intuition validated — letting winners run wider when sentiment is positive captures real alpha.

2. **NV-T2 (aggressive scale=16) is the canonical Tier 1 → Tier 2 overfit demo.**
   - Tier 1: 27.76/1.09/20.02/1.40, 15/26 four-target passes (best ever)
   - Tier 2: 12.76/0.65/39.51/0.32, 0/4 (worst)
   - Use this case to defend the v2 testing methodology in any future "but it worked in tuning" debate. NV1_solo Path A and NV-T2 are the two canonical overfit cases.

3. **NV-T1_solo passes sharpe + mdd simultaneously** (1.08 / 19.05%). First variant to pass MDD with a passing sharpe — the defensive intuition fully works without M3 dragging MDD up. Ann short by 3.5pp.

**Pattern across all 16 news variants tested today:**

| Base | News mechanism | MDD pattern | Ann pattern |
|---|---|---|---|
| M3 | counts entry filter (NV1/2/3) | ~38% (broken) | 15-18% |
| M3 | sentiment entry filter (NV-P1/2/3) | ~38% | 15-18% |
| M3 | sentiment hard exit (NV-X1/2/3) | ~38% | 17-18% |
| M3 | sentiment asymmetric trail (NV-T1/3) | ~40% | **21%** |
| Solo | any news variant | **15-22% (best)** | 11-16% |

**Composition lesson:**
- M3 = offense via concentration → high ann, high MDD
- Any news signal solo = good defense → low MDD, low ann
- They DO NOT combine — M3 + news ALWAYS produces ~38-40% MDD across 16 variant types

**Cardinal v2 rule preserved:** NV-T2 dead (Tier 1 → Tier 2 collapse). All others recorded as-is — NOT tweaking T1+M3 thresholds to chase the MDD or calmar gap (would be Tier 2 leakage).

**Net state after Jun 3 2026:**
- Best v2 result: TWO variants at 2/4 (NV-T1+M3 hits ann+sharpe, NV-T1_solo hits sharpe+mdd)
- No 4/4 pass yet — North Star unattained
- News research book complete on entry/exit/trail mechanisms
- M3 alone (1/4) was Erik's call from yesterday as "very good product" — NV-T1+M3 is now marginally better on returns headline (ann 21.41 vs 19.31)

**Cost this entire research session:** ~$6 in Haiku scoring + Lambda invocations within free tier.
