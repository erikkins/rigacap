---
name: session-progress
description: "Live session snapshot (auto-checkpointed ~15min) — what's done, in flight, and next"
metadata: 
  node_type: memory
  type: project
  originSessionId: 2dce3134-d861-45c4-a371-80378750f8c0
---

# Session snapshot — Jun 26 2026

**Context:** Bull Rider shapes research — survivorship-free PITFWU, two-step (Tier-1 2016-20 / Tier-2 held-out 21-26), local M4 Max, cache `~/pitfwu_cache`. [[project_alpha_maximizer_sleeve_idea]]. Vision (Erik): Bull Rider = a BASKET of multiple orthogonal shapes, not just C&H; exits may be shared/per-shape/stacked — unknown yet.

**KEY VALIDATION DONE:** orthogonality now uses the REAL prod t30v (`pitfwu_wf_periods.wf(start,end,20,4.5,30,volw=1.0)`, strategy_id 6) — standalone MDD **17.6%/18.5% = matches advertised ~19%**. Enabled by adding `equity_curve` field to BacktestResult (additive/inert, popped in to_dict, Erik-approved). Cup-and-handle held-out: a ~25% sleeve nudges t30v Sharpe 0.90→0.93, flat DD (modest but real); full 50/50 Sharpe 0.99. Bull Rider keeps its OWN logic (don't force ensemble mechanics — Erik corrected my over-think).

**⭐ SHAPE FACTORY BUILT (`scripts/shape_lab.py`):** registry `@register_shape(name)` + detector(o,h,l,c,vol)->bool[]; commands `list|edge|portfolio|ortho <shape1,shape2,...>`; basket = OR of shapes; shared 20d time-exit (registry has per-shape `exit` slot for later). Specimen #1 cup_handle, #2 **double_bottom (reversal — orthogonal candidate)**. double_bottom held-out edge = **+0.96%, win 53.5%, n=579** (works!). Reuses simulate/perf (shapes_portfolio) + real_ensemble_equity (shapes_orthogonality, lazy import).

**IN FLIGHT:** basket ortho `cup_handle,double_bottom` vs real t30v running (task `bxqikcx08`) — tests if adding the reversal shape diversifies t30v MORE than cup alone (the multi-shape payoff).

**NEXT (Erik's idea, agreed pending basket result): EXIT FACTORY** — symmetric `@register_exit` registry (menu already exists in shapes_tpe.exit_sim: trail/hard-stop/target/stairstep/key-reversal/time/vol-gate). A `sweep` crosses entry×exit, two-step, held-out → answers shared-vs-per-shape-vs-stacked empirically ("blind to entry"). GUARDRAIL: exits overfit viciously (TPE tail-chased) → MUST be two-step + robust (Sharpe) objective.

**UNCOMMITTED (on disk, safe):** scripts/shape_lab.py + shapes_*.py (7), pitfwu_veneer.py (cache), pitfwu_wf.py, backend/app/services/backtester.py (equity_curve field), legacy/sql/ (137 procs). Commit when Erik asks.
