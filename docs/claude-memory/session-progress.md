---
name: session-progress
description: "Live session snapshot (auto-checkpointed ~15min) — what's done, in flight, and next"
metadata: 
  node_type: memory
  type: project
  originSessionId: 2dce3134-d861-45c4-a371-80378750f8c0
---

# Session snapshot — Jun 27 2026

**Context:** Bull Rider shapes research — survivorship-free PITFWU, two-step (Tier-1 2016-20 / Tier-2 held-out 21-26), local M4 Max, cache `~/pitfwu_cache`. [[project_alpha_maximizer_sleeve_idea]]. Vision: Bull Rider = a basket of orthogonal shapes, per-shape exits, blended as a complement to t30v.

**TWO FACTORIES BUILT + WORKING (`scripts/shape_lab.py` + `scripts/exit_lab.py`):**
- shape registry `@register_shape(name, exit=...)`; commands `list|edge|portfolio|ortho`; basket = OR of shapes; per-shape exits via a hold panel threaded into `shapes_portfolio.simulate(hold_panel=)`. Shapes: cup_handle (exit 20d), double_bottom reversal (exit 10d).
- exit registry `@register_exit`; `sweep` crosses entry×exit, two-step, held-out. 10 exits (time_10/20/40, trail_10/20/30, tgt20_stop8, stairstep, keyrev_60, volstop_20).

**KEY RESULTS (held-out):**
- Exit sweep: **exits are PER-SHAPE.** cup→time_20 best (+1.19% med); double_bottom→time_10 best (+1.06%). EVERY stop whipsaws (all negative held-out median; tgt20_stop8 worst −8.15%). Time-exits dominate short-horizon breakouts.
- Per-shape-exit basket vs REAL t30v: best blend **Sharpe 0.99 at 50/50** (t30v alone 0.90). Progression as we added shape+exits: 0.90→0.93(cup)→0.95(+db shared)→**0.99(+db per-shape)**. Standalone DD tightened −37→−34.5%.
- **Ensemble leg = REAL prod t30v** (`pitfwu_wf_periods.wf(...,20,4.5,30,volw=1.0)`, MDD 17.6/18.5% = advertised ~19%). Enabled by additive `BacktestResult.equity_curve` field (inert, Erik-approved).

**WHY TIME-EXIT > STOPS (Erik's "make it make sense", answered):** edge is TIME-bounded (~10-20d drift, decays); stops trigger on intraday NOISE (volatile momentum names dip→recover), realizing whipsaw losses with no upside gain. Time-exit = minimum-assumption, edge-matched. Contrast: t30v's 30% trail works because it holds MONTHS (real trend breaks). Same firm, opposite horizons, opposite right exit.

**NEXT (open):** add more orthogonal shapes (the lever); maybe stacked exits; eventually a daily t30v curve for exact blend MDD (currently biweekly-approx). UNCOMMITTED (safe on disk): scripts/shape_lab.py, exit_lab.py, shapes_*.py, shapes_portfolio.py (hold_panel), pitfwu_veneer.py, pitfwu_wf.py, backend/app/services/backtester.py (equity_curve), legacy/sql/. Commit when Erik asks.
