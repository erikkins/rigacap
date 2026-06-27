---
name: session-progress
description: "Live session snapshot (auto-checkpointed ~15min) — what's done, in flight, and next"
metadata: 
  node_type: memory
  type: project
  originSessionId: 2dce3134-d861-45c4-a371-80378750f8c0
---

# Session snapshot — Jun 27 2026 (Sat) — REGIME-ADAPTIVE BREAKTHROUGH + robustness/daily checks

**Context:** Multi-day Bull Rider / Bear Ripper shapes research. Survivorship-free PITFWU, two-step, local M4 Max, cache `~/pitfwu_cache` (~1GB incl EXT). Erik north star: 20% CAGR / <20% MaxDD / >1 Sharpe / >1 Calmar. Scripts: shape_lab.py, exit_lab.py, three_way_blend.py, regime_adaptive.py, robustness.py, omr_regime_test.py.

**⭐⭐ THE WIN — REGIME-ADAPTIVE SWITCH (regime_adaptive.py):** route OFFENSE by regime — UNCAPPED Bull Rider when SPY>200MA, Bear Ripper when SPY<200MA, on a t30v core. HELD-OUT (2021-26) 20% core/80% offense = **20.1% CAGR / 1.05 Sharpe / -18.0% MaxDD / 1.12 Calmar = ALL 4 GOALS HIT, out-of-sample.** Beats t30v (15.3/0.90/-17.6) on every axis. Static blends never could (always traded return for safety). Uncapping bull offense added the missing ~4pts CAGR; switch sidesteps Bull Rider's bear-bleed.

**⚠️ TWO HONESTY CAVEATS (under active test):**
1. **Full period (2016-26) only ~13% CAGR** — 20% is NOT uniform; strong in 2021-26, muted earlier → maybe window-specific. RUNNING NOW: `robustness.py` (task `bv3vl3nvr`) tests regime-adaptive across 5 rolling windows 2009-2026 (EXT) — does it hit ~18-20% CONSISTENTLY or only 2021-26? Prints a row per window. THE decider.
2. **MaxDD is BIWEEKLY-APPROX → understates true daily DD.** Daily test: single-backtest t30v daily MaxDD = **23.7%** vs walk-forward biweekly 17.6%. So "<20%" blend claims are optimistic; true daily DD deeper. Mix of resolution + single-vs-walkforward strategy diff. Clean daily PROD t30v needs walk_forward_service to emit daily equity (deferred, deeper change). `pitfwu_wf.run()` now takes trail/max_pos/size params (daily single-backtest t30v).

**NEXT:** read robustness scorecard when `bv3vl3nvr` lands → if consistent ~20% = productize; if not = harden the regime signal (crude SPY-200MA → use the 7-regime engine). Then daily-MaxDD confirmation. Trust CAGR/Sharpe (solid biweekly), treat MaxDD as approx.

**UNCOMMITTED (safe on disk):** all scripts/*.py shapes work, shapes_portfolio.py (hold_panel+caps), pitfwu_veneer.py, pitfwu_wf.py (params), backend/app/services/backtester.py (equity_curve), legacy/sql/. Newsletter draft [[project_newsletter_exit_stops_topic]]. Commit when Erik asks.
