---
name: session-progress
description: "Live session snapshot (auto-checkpointed ~15min) — what's done, in flight, and next"
metadata: 
  node_type: memory
  type: project
  originSessionId: 2dce3134-d861-45c4-a371-80378750f8c0
---

# Session snapshot — Jun 30 2026 (Tue) — 7-REGIME ALLOCATOR built + EXT-validated (drawdown edge PROVEN)

**Context:** Shapes research → orthogonal diversifiers + regime-adaptive allocation on t30v. Survivorship-free PITFWU, EXT to 2004. Engine shape_tpe.py (TPE, blend-improvement-vs-t30v objective, regime-as-knob via prod 7-regime classifier regime_research.py). Two validated diversifiers: pullback_ma@calm_bull (+0.327), oversold_bounce@bull (+0.232). Modern mkt ~70% rotating_bull. Erik remote (/remote-control).

**⭐⭐⭐ 7-REGIME ADAPTIVE ALLOCATOR (scripts/regime_allocator.py) — the synthesis, WORKS.** Routes offense by live regime: calm_bull→pullback_ma, capitulation(panic_crash/recovery/weak_bear)→oversold_bounce, else(~85%, rotating_bull)→t30v. Capital always deployed (no dead money — fixes static-stack CAGR collapse). On 2016-26: BEATS t30v on CAGR+Sharpe+DD in ALL windows — A 13.0/1.08/-8.3, B 18.9/1.12/-13.4, FULL 17.2/1.25/-10.9 (vs t30v 8.6/0.65/-14, 15.2/0.90/-18, 12.1/0.84/-18.5). core 0% (PURE ROTATION) wins. ≈ Erik's 20%/<20% goal w/ DD margin, consistent across halves.

**⭐ EXT THIRD-HOLDOUT (regime_allocator_ext.py, pre-2016 FROZEN params) = HONEST PARTIAL PROOF:**
- 2009-2012 (25% capitulation): allocator BEATS t30v all 3 axes (5.5/0.64/-8.5 vs 3.1/0.34/-13.2).
- 2013-2015 (calm grind, 4% capitulation): only DD wins; CAGR/Sharpe DRAG (-1.7 CAGR); best=core 100%=just t30v.
- **VERDICT: drawdown reduction is ROBUST/out-of-sample (every window). CAGR boost is CONDITIONAL on volatility/capitulation being present.** Maps to "capital-preserver/thrives-in-turbulence" positioning. Not a free lunch — regime-conditional. (pre-2016 surv-biased → read RELATIVE deltas.)

**NEXT:** (1) find ONE robust core weight across ALL windows 2009→2026 (moderate core ~50-70% guards the 2013-2015 calm-grind drag vs pure rotation). (2) daily-DD confirmation (biweekly understates). (3) re-hunt breakout shapes w/ regime knob. (4) [[project_secret_dossier]] internal blueprint TODO.

**UNCOMMITTED (safe on disk):** shape_tpe.py, regime_research.py, stack_sleeves.py, regime_allocator.py, regime_allocator_ext.py, all scripts/*.py + shapes_portfolio/shape_lab/pitfwu_wf/backtester. Memories: [[feedback_survivorship_free_not_marketing]], [[project_secret_dossier]], [[project_newsletter_exit_stops_topic]]. Commit when Erik asks.
