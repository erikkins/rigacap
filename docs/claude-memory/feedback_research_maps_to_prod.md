---
name: feedback-research-maps-to-prod
description: "Research MUST map to production — one warm full-history curve (penny-to-penny w/ prod); only exposure-scaling constructions port, sleeve-capture ones don't"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 264056a8-f1e5-489c-9140-1fb57bda9825
---

# Research MUST map to production (Erik, Jul 21 2026 — top-of-mind for ALL tier/strategy tests)

**Why:** A whole session of tier analysis got muddied because backtests were run on inconsistently-warmed t30v curves (cold-start 2021-01 in one script, 2-mo warm 2020-11 in another) → different "Core" numbers (17.5% vs 14.3%) → apples-to-oranges comparisons + whiplash. Production has YEARS of history and is ALWAYS warm. Research that cold-starts (or warms inconsistently) does NOT describe what production will do.

## THE RULES (apply to every backtest/comparison going forward)
1. **ONE canonical curve, computed over FULL PITFWU history (2016→present), sliced per window** so every measurement window is FULLY WARM. Never cold-start research; never use inconsistent start dates. PITFWU must be **penny-to-penny with prod** (validated on common dates — see [[project_signal_parity_jun13]] / PITFWU loop).
2. **Production is ALWAYS warm-start** (history exists) → warm-start ALL research to match. Cold-start numbers (e.g. Maximizer −22% cold vs −12% warm) are NOT production-representative.
3. **Only EXPOSURE-SCALING constructions port to the single-pool production book** — i.e. "raise cash / scale exposure" (daily return = exposure × core_ret). These reproduce the research return-stream EXACTLY (nothing to capture).
4. **SLEEVE-CAPTURE constructions do NOT port** — anything that must *capture a sleeve's return* (breakout for Maximizer, oversold-bounce for the Preserver tilt). The idealized return-stream flatters them, but the real single-pool book cold-starts a fresh sleeve each episode (buys falling knives) and captures poorly → the research edge evaporates or reverses. Proven twice: Maximizer breakout (research 36% → prod 11.7%) and Preserver oversold-tilt (research win → prod WORSE than Core).
5. **Always VALIDATE a research result by re-running it through the production day-step (or an exposure-scaled formula) on the SAME warm canonical curve BEFORE trusting/marketing it.** If they don't match penny-to-penny, it's a bug or a non-portable construction — find out which.

## Practical: the Preserver overlay (the win that survived)
Preserver = t30v mirror + capitulation CASH overlay = daily return `exposure × core_ret`, exposure=0.25 in capitulation (raise 75% cash), 1.0 else; one-time trim cost on regime flip. This is exposure-scaling → ports penny-to-penny. Book re-implemented this way (was buggy: moved cash daily → thrashed). See [[project_tier_reconciliation_jul21]].
