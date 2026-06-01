---
name: A1 concentration failed Tier 1 — signal quality is the bottleneck (Jun 1 2026)
description: First v2-compliant variant (4×22% + T3) FAILED dramatically. Concentration alone destroys the strategy because signal quality isn't differentiated by rank. Tomorrow's hypothesis space must target signal quality (Categories D, E) not sizing.
type: project
originSessionId: c3d0833d-cb3f-474f-8dd8-e530f3300c60
---
**Logged Jun 1 2026 EOD.** First variant tested under v2 methodology. Result was educational, not encouraging.

## What we tested

**A1: Concentration 4 positions × 22%, T3 on (DD≥10% → trail 8%), baseline entry params (DWAP 5%, near-50d 3%), top-100 universe.**

Hypothesis: concentrating from 6×15% to 4×22% amplifies high-conviction picks and closes the 9pp gap to the 20% annualized target.

## Tier 1 result on TUNING data (52 Mondays × 3y windows)

| Metric | A1 | Baseline (6×15% no T3) | Δ | Target | Verdict |
|---|---|---|---|---|---|
| Annualized | 5.96% | 10.84% | **-4.88pp** | ≥20% | FAIL |
| Sharpe | 0.39 | 0.77 | -0.39 | ≥1.0 | FAIL |
| MaxDD | 29.70% | 17.45% | **+12.25pp** | ≤20% | FAIL |
| Calmar | 0.20 | 0.65 | -0.45 | ≥1.0 | FAIL |
| Positive windows | 38/52 | 52/52 | -14 | ≥40/52 | FAIL |

14 windows went NEGATIVE. 23 windows had MDD ≥ 30%. A1 didn't just miss target — it broke the strategy.

## The lesson — bottleneck identified

Concentration is DESTRUCTIVE to current strategy. Halving diversification and amplifying per-pick capital makes returns worse AND drawdowns worse simultaneously. There's no upside.

**Direct implication: the signal at rank 4 isn't meaningfully higher conviction than at rank 6.** The composite score doesn't differentiate top picks well enough to justify concentrating into them. So "concentration" just amplifies undifferentiated signal noise = more variance = both lower return and higher MDD.

**Saturday's "fewer better signals" direction needs reframing**: "fewer" alone is destructive. The work is **"better" first**. Until top-ranked signals can be shown to materially outperform mid-ranked, concentration variants will continue to fail.

## Implications for the hypothesis backlog

**Do not retry under current signal-quality regime:**
- A2 (3×30% even more concentrated) — would fail worse
- A3 (5×18% mild) — likely marginal at best
- Volatility-scaled sizing — same root cause
- Pyramid into winners — same

**Worth exploring (target the actual bottleneck):**
- **Category D — new entry feature** that differentiates top picks: earnings momentum, sector relative strength, volume-pattern accumulation, news/sentiment shock, cross-asset rotation indicator
- **Category E — regime sub-strategies**: current strategy may be over-fit to one regime. Different selection logic per market regime (rotating_bull vs strong_bull vs weak_bear etc) could lift quality conditionally
- **Universe filter quality** — top-100 by liquidity might be too coarse. Volume × ATR ranking, or sector-balanced selection, or stricter "leadership" filter could raise the average quality before any concentration test
- **Composite score reweighting** — currently 0.3 × short_mom + 0.2 × long_mom − 0.15 × vol. The fact that rank 4 ≈ rank 6 in expected return suggests these weights don't surface real edge. Re-weight or add new factors.

## Methodology v2 worked — recording the win

A1 was the first v2-compliant test. The framework correctly killed it in ~5 min wall clock with a clear FAIL verdict on all 4 targets + the consistency criterion. Pre-v2 we might have spent days trying A1 variants ("maybe with tighter trail?" "maybe with different entry?"), tweaking until something looked OK on the same data. **The cardinal sin (tweaking to make a failed variant pass) was avoided.**

Continue: discard A1, generate next hypothesis in Categories D/E/universe-filter.

## How to apply

- Don't open new concentration/sizing variants until signal quality is demonstrably differentiated
- Next-up variants should target the WHY rank 4 ≈ rank 6 in expected return
- Use INDEX.md (`~/rigacap-research/sweeps/INDEX.md`) to avoid retesting A1-class hypotheses
- Tier 1 sweeps run in ~5 min; cheap to test broadly — but only in categories that target the actual bottleneck
