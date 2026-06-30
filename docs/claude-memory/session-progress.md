---
name: session-progress
description: "Live session snapshot (auto-checkpointed ~15min) — what's done, in flight, and next"
metadata: 
  node_type: memory
  type: project
  originSessionId: 2dce3134-d861-45c4-a371-80378750f8c0
---

# Session snapshot — Jun 30 2026 (Tue) — DURABLE diversifier found + 7-regime wrapper built

**Context:** Shapes research (diversifiers to complement t30v). Survivorship-free PITFWU, EXT to 2004. Cache `~/pitfwu_cache`. Engine: scripts/shape_tpe.py — parameterize shape → TPE → OBJECTIVE v2 = blend-improvement vs REAL t30v (min across A=2016-20/B=2021-26, rev-swap baked in), bull-regime gate, n<30 guard. Lessons: exit selection = PORTFOLIO Sharpe not per-trade; momentum-family=durable-but-correlated, mean-reversion=orthogonal.

**⭐⭐ BREAKTHROUGH — `oversold_bounce` is the FIRST DURABLE orthogonal diversifier.** Deep RSI<15 + 18% drop capitulation reclaim in bull (bull cousin of OMR). Blend-improvement +0.20 A / +0.27 B (BOTH halves → min +0.20). SELECTIVE: n=92/161 (vs pullback_ma's 24,000=beta=+0.00, rejected). Sleeve low-return (1.5-4.4% CAGR) but uncorrelated (best blend wants 70-80% sleeve). LESSON: mean-reversion at the EXTREME (capitulation), not shallow dips, is the durable orthogonal factor.

**⭐ 7-REGIME WRAPPER BUILT (scripts/regime_research.py):** production classifier (app.services.market_regime, 7 regimes) point-in-time across PITFWU, cached `~/pitfwu_cache/regime/`. SURPRISE composition: BOTH eras ~70% rotating_bull (strong_bull RARE 1-5%). My "A=rotating/B=trending" hypothesis WRONG — but truth better: modern mkt is predominantly rotating_bull (choppy uptrend) → explains why capitulation-reversion is durable, shallow-pullback fails, breakouts lumpy. Regimes don't separate ERAS; value is PER-DAY gating, esp bear sub-regimes (panic_crash/recovery/weak_bear) for capitulation shapes.

**NEXT = wire regime label as a TPE-SELECTABLE gate in shape_tpe** (each shape chooses which of 7 regimes it fires in; bear sub-regimes for oversold/OMR) → re-hunt building on oversold_bounce. Then: productize oversold_bounce as a diversifier sleeve; more shapes (range_breakout/gap_go controls). Bear Ripper expansion; Bull Rider alive.

**UNCOMMITTED (safe on disk):** shape_tpe.py (multi-shape: pullback_ma+oversold_bounce, RSI feature), regime_research.py, all scripts/*.py, shapes_portfolio.py (exit_specs), shape_lab.py, pitfwu_wf.py, backend/.../backtester.py. Memories: [[feedback_survivorship_free_not_marketing]], newsletter [[project_newsletter_exit_stops_topic]]. Commit when Erik asks.
