---
name: session-progress
description: "Live session snapshot (auto-checkpointed ~15min) — what's done, in flight, and next"
metadata: 
  node_type: memory
  type: project
  originSessionId: 2dce3134-d861-45c4-a371-80378750f8c0
---

# Session snapshot — Jun 29 2026 (Mon) — REAL reverse-swap + trailing exits wired + diverse-shape probe

**Context:** Bull Rider/Bear Ripper shapes research. Survivorship-free PITFWU, EXT back to 2004. Cache `~/pitfwu_cache`. Scripts: shape_lab, exit_lab, three_way_blend, regime_adaptive, robustness, shape_edge_eras, reverse_swap (VACUOUS), real_reverse_swap, t30v_eras. Reframe locked: MODERN-ERA strategy (edge since 2017, ~20% is bull-amplified peak, durable ~10-12%). t30v dual story (21y record + much stronger recently 3%→19.5%).

**⭐ REAL REVERSE-SWAP (real_reverse_swap.py) — has teeth, per-shape EXIT selection, fit A=2016-20 / test B=2021-26 both ways:** vcp & inv_hs AGREE both halves + travel OOS = REAL; cup mild-unstable (time_20 safe default); double_bottom OVERFIT (trail_30 vs time_10 disagree, both decay) = fragile shape. Found vcp's per-trade best = trail_30.

**⭐⭐ KEY LESSON (caught by TESTING): exit selection must use the PORTFOLIO objective (Sharpe/DD), NOT per-trade median.** Wired trailing/target exits into shapes_portfolio.simulate (exit_specs by shape-id, close-based; load() now returns 6 vals incl exit_specs; all callers updated). Set vcp→trail_30 → portfolio Tier-2 DD -52%! (per-trade median lied — ignores correlated tail risk). Reverted vcp→time_20 (DD -33% vs -52%). Trailing infra STAYS (future long-hold trend shapes will want it). NOTE: vcp alone is weak regardless (~0% Tier-2) — single shapes don't carry.

**DIVERSE-SHAPE PROBE:** registered pullback_ma (trend-continuation, buys weakness → orthogonal to breakout cousins). Edge: Tier-1 -0.03% (=baseline), Tier-2 +0.35%, fires 20k× (too loose, not selective). LESSON: bare different-family pattern = NO edge; edge lives in PARAMETERIZATION (Erik's levers), not the bare detector.

**NEXT = SHAPE-PARAMETER TPE HARNESS** (Erik's 3-layer pipeline): parameterize each shape (depth/RS/volume-dryup/MA/turn-strength) → TPE search, OBJECTIVE=portfolio Sharpe/DD (not per-trade!), GATED by reverse-swap (win A→B AND B→A; bonus if edge pre-2016=durable). Reusable for gap_go, bull-mean-reversion. Erik leaning fresh session for this. Also pending: Bear Ripper expansion; Erik NOT giving up on Bull Rider.

**UNCOMMITTED (safe on disk):** all scripts/*.py, shapes_portfolio.py (exit_specs), shape_lab.py (pullback_ma, trailing plumbing), pitfwu_wf.py, backend/.../backtester.py (equity_curve). Memories: [[feedback_survivorship_free_not_marketing]], newsletter [[project_newsletter_exit_stops_topic]]. Commit when Erik asks.
