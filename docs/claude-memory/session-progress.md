---
name: session-progress
description: "Live session snapshot (auto-checkpointed ~15min) — what's done, in flight, and next"
metadata: 
  node_type: memory
  type: project
  originSessionId: 2dce3134-d861-45c4-a371-80378750f8c0
---

# Session snapshot — Jun 30 2026 (Tue) — TPE harness + objective-v2 (orthogonality) WORKING

**Context:** Bull Rider/Bear Ripper shapes research. Survivorship-free PITFWU, EXT back to 2004. Cache `~/pitfwu_cache`. MODERN-ERA reframe locked. Lessons: exit selection uses PORTFOLIO Sharpe NOT per-trade median (vcp trail_30→-52%); reverse-swap fits SELECTED choices both directions.

**⭐ shape_tpe.py — diversifier-hunting engine, WORKING.** Parameterizes a shape (pullback_ma: depth_min/depth_band/dryup/mom_min/hold), bull-regime gate (REGIME="bull"), precomputed features (fast trials), n<30 guard. OBJECTIVE v2 = **blend-improvement vs REAL t30v** (best t30v+sleeve blend Sharpe MINUS t30v-alone, cross-validated min across A=2016-20/B=2021-26). Rewards positive+ORTHOGONAL, penalizes beta (v1's min-Sharpe drove to 24k-signal beta blob). t30v ref built once per half (real_ensemble_equity).

**⭐⭐ KEY FINDING (objective v2, 80 trials on pullback_ma): min blend-improv = +0.00 → REJECTED, but the WHY is gold.** pullback_ma in A 2016-20: +0.15 to +0.32 Sharpe to the blend (orthogonal! best blend core 10-40%, sleeve 13-20% CAGR) — but B 2021-26: +0.00, sleeve LOSES money (-4% CAGR). Buy-the-dip diversifies GREAT in 2016-20, DEAD in 2021-26 (2022 bear + 2023-25 breakout rally killed it). **PATTERN: momentum-family = durable-but-CORRELATED; mean-reversion-family = ORTHOGONAL-but-era-fragile.** Diversification IS real+findable (+0.32 proves it); durability is the wall. → Bear Ripper (opposite-REGIME, held 6 bears) stays the standout; regime-adaptive SWITCH is right architecture (rotate, don't seek durable diversifier).

**NEXT = keep hunting via objective v2:** generalize harness to swap shapes; run `oversold_bounce` (bull cousin of OMR — best shot at orthogonal+durable), then range_breakout/gap_go (momentum controls — expect durable-but-correlated). Test the pattern, don't assume. Also pending: Bear Ripper expansion; Bull Rider alive.

**UNCOMMITTED (safe on disk):** shape_tpe.py + all scripts/*.py, shapes_portfolio.py (exit_specs), shape_lab.py (pullback_ma+trailing), pitfwu_wf.py, backend/.../backtester.py (equity_curve). Memories: [[feedback_survivorship_free_not_marketing]], newsletter [[project_newsletter_exit_stops_topic]]. Commit when Erik asks.
