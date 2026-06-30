---
name: session-progress
description: "Live session snapshot (auto-checkpointed ~15min) — what's done, in flight, and next"
metadata: 
  node_type: memory
  type: project
  originSessionId: 2dce3134-d861-45c4-a371-80378750f8c0
---

# Session snapshot — Jun 30 2026 (Tue) — SHAPE-PARAMETER TPE HARNESS built

**Context:** Bull Rider/Bear Ripper shapes research. Survivorship-free PITFWU, EXT back to 2004. Cache `~/pitfwu_cache`. MODERN-ERA reframe locked (edge since 2017, ~20% bull-amplified, durable ~10-12%; t30v dual story 3%→19.5%). Lessons in play: exit selection uses PORTFOLIO Sharpe/DD NOT per-trade median (vcp trail_30 → -52% DD); reverse-swap must fit SELECTED choices both directions.

**⭐ BUILT: scripts/shape_tpe.py — the TPE harness.** Parameterizes a shape (pullback_ma: depth_min/depth_band/dryup/mom_min/hold), TPE searches, OBJECTIVE=min(Sharpe_A, Sharpe_B) (reverse-swap A=2016-20/B=2021-26 baked in), precomputes per-symbol features once (fast trials ~vectorized), n<30 trades guard. Added bull-regime gate (REGIME="bull", SPY>200MA mask injected per symbol). Works end-to-end (~2min/25-60 trials incl data load).

**⭐⭐ KEY FINDING (harness revealed it): optimizing STANDALONE Sharpe drives TPE to BETA, not a diversifier.** pullback_ma regime-gated best: min-Sharpe 0.73, A 13.6%/0.81/-19.8%, B 16.4%/0.73/-31.5% — BUT n=24,000 signals = "always long uptrends in bull" = momentum beta (~0.6 corr to t30v) = diversifies NOTHING. A diversifier needs positive return AND low corr to t30v, which standalone Sharpe doesn't reward.

**NEXT = OBJECTIVE v2: blend-improvement vs t30v** (cross-validated min across A/B). Per trial: build sleeve curve → align to t30v → measure best t30v+sleeve blend Sharpe MINUS t30v-alone; take min(A,B). Rewards positive+uncorrelated, penalizes the 24k-signal beta blob. Compute t30v once per half + add blend-sweep per trial. THEN re-run the hunt for real orthogonal edge. Reusable for gap_go, bull-mean-reversion. Also pending: Bear Ripper expansion; Bull Rider still alive.

**UNCOMMITTED (safe on disk):** shape_tpe.py + all scripts/*.py, shapes_portfolio.py (exit_specs), shape_lab.py (pullback_ma + trailing plumbing), pitfwu_wf.py, backend/.../backtester.py (equity_curve). Memories: [[feedback_survivorship_free_not_marketing]], newsletter [[project_newsletter_exit_stops_topic]]. Commit when Erik asks.
