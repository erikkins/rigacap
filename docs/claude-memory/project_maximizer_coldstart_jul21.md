---
name: project-maximizer-coldstart-jul21
description: "Maximizer vol-brake must warm-start (never cold-start); cold Jun15 launch = -22%, warmed = -12%; cold-start is a general tier launch hazard"
metadata: 
  node_type: memory
  type: project
  originSessionId: 264056a8-f1e5-489c-9140-1fb57bda9825
---

# Maximizer cold-start finding + warm-start requirement (Jul 21 2026)

## Question (Erik): does Maximizer beat SPY? Expected yes.
Answer: NO over the Jun15→Jul20 drawdown window. Faithful replay (scripts/maximizer_backfill.py, pitfwu panel, breakout sleeve, n_pos=15):
- **COLD-start Jun15 (brake off — eq_hist empty <21d, all-fresh pile-in at the top): −22.2%**
- **WARMED (warmup from 2026-05-01 so brake + held book realistic at Jun15): −12.1%** (brake=0.37 at Jun15, 12 positions already held)
- vs Core/Preserver −7.5%, SPY −1.7%.

## Key methodology fix (Erik's catch): DON'T cold-start the vol-brake
The Barroso vol-brake reads the BOOK's own eq_hist; with 0 history it returns 1.0 (no brake) for the first ~21 days — exactly when protection is needed. A continuously-running strategy hits any date with the brake ALREADY warm + positions ALREADY held (aged), not cold-piling into the top. Cold-start test overstated the loss by ~10pp.

## Honest read
Even warmed, Maximizer −12% > Core −7.5% > SPY −1.7% in losses over THIS window. Expected: Maximizer is higher-beta (breakout) → loses more in drawdowns, gains more in rallies (the +63% ttm backtest is the other side). "Beats SPY" is a FULL-CYCLE question, not a 5-week-drawdown one. The live Maximizer shadow looked flat (−1.1%) ONLY because it launched Jul8 post-crash into CASH (held=0 Jul8-13; breakout found nothing to buy).

## PRODUCTION REQUIREMENT (bake into WS3 serving)
When Maximizer goes live, WARM-START the vol-brake — seed eq_hist from the strategy's backtested equity history, NOT cold. Else a bad-timed live launch = the −22% scenario. Same anti-cold-start lesson as Core's Jun-15 concentration pile-in ([[project_sector_cap_regression_jul20]]).

## OPEN
- Erik deciding: write the WARMED −12% Jun15-anchored Maximizer backfill to prod (overwrites live Jul8 shadow rows), or keep live shadow.
- Fair comparison caveat: Core/Preserver −7.5% is ALSO partly cold-start artifact (live book cold-started Jun15; a warmed/continuous book wouldn't have piled into the top either). Offered to quantify warmed Core/Preserver.
