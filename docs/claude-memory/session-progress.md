---
name: session-progress
description: "Live session snapshot (auto-checkpointed ~15min) — what's done, in flight, and next"
metadata: 
  node_type: memory
  type: project
  originSessionId: 2dce3134-d861-45c4-a371-80378750f8c0
---

# Session snapshot — Jun 30 2026 (Tue) — REGIME-AS-KNOB CRACKED IT: 2 durable diversifiers

**Context:** Shapes research (orthogonal diversifiers to complement t30v). Survivorship-free PITFWU, EXT to 2004. Engine: scripts/shape_tpe.py — parameterize shape → TPE → OBJECTIVE v2 = blend-improvement vs REAL t30v (min across A=2016-20/B=2021-26, rev-swap baked in). Multi-shape (pullback_ma, oversold_bounce), RSI feature. Now n_startup=40, regime is a TPE KNOB.

**⭐ REGIME-AS-TPE-KNOB built (REGIME_GATES: all/bull/rotating/chop/calm_bull/bear/capitulation/recovery, strict SUPERSET — 'all'=no gate so can't hurt optimum).** Uses scripts/regime_research.py (production 7-regime classifier, point-in-time, cached `~/pitfwu_cache/regime/`). Per-symbol regime label injected in load_data; np.isin gate in detect; categorical knob in objective. v.EXT save/restore added to regime_series.

**⭐⭐⭐ TWO DURABLE ORTHOGONAL DIVERSIFIERS FOUND (both halves, robust):**
1. **pullback_ma @ `calm_bull` = +0.327 blend-Sharpe** (was +0.00 UNGATED → regime knob RESCUED it; top-6 all calm_bull, identical params: depth 3-9%, mom_min 0.46, hold 40; sleeve 11.8%A/5.1%B CAGR — decent RETURN too). CONFIRMS thesis: era-fragility WAS regime-dependence. Dip-buying works in CALM LOW-VOL TRENDS, drowned by chop/bear otherwise.
2. **oversold_bounce @ bull/all = +0.232** (deep RSI<15 capitulation, regime-AGNOSTIC = stock-level selective; 250-trial confirmed). Small-n caveat (n31-63).
They fire in DIFFERENT regimes → should STACK not overlap.

**NEXT:** (1) STACK t30v + pullback@calm_bull + oversold — do lifts add? (2) EXT pre-2016 third-holdout on both winners (B n=42 thin). (3) re-hunt breakout shapes (cup/vcp) WITH regime knob (maybe want strong_bull). Method note: regime knob is superset → never rerun without it; read WHICH gate winner picks to know if regime mattered.

**UNCOMMITTED (safe on disk):** shape_tpe.py, regime_research.py, all scripts/*.py, shapes_portfolio.py, shape_lab.py, pitfwu_wf.py, backend/.../backtester.py. Memories: [[feedback_survivorship_free_not_marketing]], newsletter [[project_newsletter_exit_stops_topic]]. Commit when Erik asks.
