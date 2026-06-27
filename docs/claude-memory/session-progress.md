---
name: session-progress
description: "Live session snapshot (auto-checkpointed ~15min) — what's done, in flight, and next"
metadata: 
  node_type: memory
  type: project
  originSessionId: 2dce3134-d861-45c4-a371-80378750f8c0
---

# Session snapshot — Jun 27 2026 (Sat)

**Context:** Bull Rider shapes research — survivorship-free PITFWU, two-step (T1 2016-20 / T2 held-out 21-26), local M4 Max, cache `~/pitfwu_cache`. [[project_alpha_maximizer_sleeve_idea]]. Two factories built: `scripts/shape_lab.py` (shapes) + `scripts/exit_lab.py` (exits). Ensemble baseline = REAL prod t30v (`pitfwu_wf_periods.wf(...,20,4.5,30,volw=1.0)`, MDD 17.6/18.5% = advertised).

**ROSTER now 5 shapes (shape_lab):** cup_handle(exit 20d), double_bottom(10d), **pullback_bounce=OMR(5d), vcp(20d), inv_hs(10d)**. Per-shape exits work (hold_panel → simulate). Earlier: per-shape-exit basket (cup+db) held-out blend Sharpe **0.99 @50/50** (t30v 0.90); progression 0.90→0.93→0.95→0.99.

**NEW-SHAPE EDGES (held-out, fwd-20d):** VCP **+1.22% / 56% win** (real, ~= cup's +1.42%). OMR **−0.28%** BUT CONFOUNDED — edge cmd uses fixed 20d horizon; OMR is a 5d trade → unfair, must re-score at its own horizon. inv_hs edge was still printing.

**⭐ ERIK'S KEY QUESTION (open, important):** cup-and-handle (and all shapes) use FIXED param bands — cup = WIN 130d (breadth FIXED), depth 12-35%, handle 3-15%. So we capture ONE SLICE, not the full variance (broad/deep/narrow variants). Detector thresholds are themselves un-validated (like the exit was). 

**NEXT (proposed, awaiting go):** (1) quick-fix `cmd_edge` to score each shape at ITS OWN horizon (fair OMR read — OMR hold=5, etc.), then (2) build a SHAPE-PARAMETER SWEEP (entry analog of the exit factory): parameterize depth/breadth/handle, two-step held-out, find which amplitudes/breadths actually carry edge. Then basket ortho with the good shapes.

**UNCOMMITTED (safe on disk):** scripts/shape_lab.py, exit_lab.py, shapes_*.py, shapes_portfolio.py (hold_panel), pitfwu_veneer.py, pitfwu_wf.py, backend/app/services/backtester.py (equity_curve field, inert/Erik-approved), legacy/sql/ (137 procs). Commit when Erik asks.
