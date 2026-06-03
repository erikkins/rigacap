---
name: Sentiment-exit failed v2 BUT defensive value validated (lowest MDD ever)
description: NV-X1_solo posted 15.76% MDD on bear-inclusive Tier 2 — best of any variant ever. But ann 11.54%, 0/4 targets. News-as-exit dead for hitting 20/20/1/1 directly; defensive value is real.
type: project
originSessionId: c3d0833d-cb3f-474f-8dd8-e530f3300c60
---
**Date:** Jun 3 2026
**Outcome:** Sentiment-exit (NV-X1/X2/X3) FAILED v2 Tier 2 on all 4 targets. BUT NV-X1_solo set a new low MDD record (15.76%) — defensive thesis validated even though variant doesn't ship.

**Tier 2 results (2022-01-03 → 2026-05-29, bear-inclusive):**

| Variant | ann | sharpe | mdd | calmar | 4✓ |
|---|---|---|---|---|---|
| M3 baseline | 19.31% | 1.09 | 21.53% | 0.90 | 1/4 |
| NV-X1+M3 (-0.3, 3d) | 17.55% | 0.88 | 38.61% | 0.45 | 0/4 |
| NV-X2+M3 (-0.5, 1d sharp) | 18.34% | 0.89 | 39.04% | 0.47 | 0/4 |
| NV-X3+M3 (-0.2, 7d slow) | 16.77% | 0.83 | 37.97% | 0.44 | 0/4 |
| **NV-X1_solo (-0.3, 3d)** | 11.54% | 0.82 | **15.76%** | 0.73 | 1/4 ← MDD |

**Major finding — pattern across 12 news variants:**

| Combo | MDD pattern | Ann pattern |
|---|---|---|
| News + M3 | ~38% (broken) | 15-18% |
| News solo | **15-22% (best ever)** | 11-14% |

News IS a real defensive signal but FIGHTS M3's mega-cap concentration. The two cannot stack: M3 = offense via concentration, News = defense via selectivity. Combine them and you get concentrated bets being held even longer through bear (since news doesn't trigger on mega-cap names the same way).

**Erik's "save our ass on losses + loosen on good news" intuition:**
- Defense half (save our ass): **VALIDATED** — NV-X1_solo MDD 15.76 < 20% target, 4.24pp under
- Offense half (loosen on good news): NOT TESTED YET. NV-X1/X2/X3 are binary hard exits, not asymmetric trail. The asymmetric-trail mechanism (`trail_pct = base − sentiment × scale`) is the next legitimate test, structurally different from anything tested.

**Mechanisms still untested with cached Haiku scores:**
- Asymmetric sentiment-aware trailing stop (offense + defense in one continuous mechanism)
- Sentiment-divergence exit (price UP but sentiment DOWN = fake breakout tell)
- Sentiment-momentum (5d slope vs absolute level)
- Sentiment-as-position-sizing at entry (size × sentiment factor)

**Cardinal v2 rule preserved:** All 12 news variants discarded after Tier 2 fail. No threshold/lookback tweaks. Each new variant tested has been structurally different (filter vs boost vs regime-gated vs hard-exit; counts vs sentiment; solo vs M3).

**Total cost summary:**
- Path A counts: $0 (cached)
- Path B sentiment scoring: $3.73 Haiku + $2.43 wasted no-checkpoint run
- 12 variants × 26 Tier 1 + 4 Tier 2 = 320 Lambda invocations, ~$0 (within free tier)
- Total experiment cost: ~$6
