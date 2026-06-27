---
name: session-progress
description: "Live session snapshot (auto-checkpointed ~15min) — what's done, in flight, and next"
metadata: 
  node_type: memory
  type: project
  originSessionId: 2dce3134-d861-45c4-a371-80378750f8c0
---

# Session snapshot — Jun 27 2026 (Sat)

**Context:** Shapes research → now TWO SLEEVES: **Bull Rider** (offense in up-mkts) + **Bear Ripper** (offense in down/vol mkts), both complementing the defensive t30v core. Survivorship-free PITFWU, two-step (T1 2016-20 / T2 held-out 21-26), local M4 Max, cache `~/pitfwu_cache`. [[project_alpha_maximizer_sleeve_idea]]. Factories: `scripts/shape_lab.py` (shapes, per-shape exits via hold_panel) + `scripts/exit_lab.py` (exit sweep). Ensemble baseline = REAL prod t30v (`pitfwu_wf_periods.wf(...,20,4.5,30,volw=1.0)`, MDD 17.6/18.5%=advertised; enabled by additive `BacktestResult.equity_curve`).

**SHAPE ROSTER + held-out edges:** cup_handle +1.42% (exit time_20), inv_hs +1.30% (time_20), vcp +1.22% (sweep: likes trail_30/volstop ~+1.36%!), double_bottom +0.96% (time_10). = **Bull Rider 4 (validated).** Per-shape-exit basket(cup+db) held-out blend Sharpe 0.99@50/50 (t30v 0.90).

**⭐ OMR FINDING (Erik's regime hypothesis — SIGN flipped, instinct right):** OMR (mean-rev dip-buy) is FLAT held-out overall, BUT split by market regime (SPY vs 200MA, `scripts/omr_regime_test.py`): **bear-regime OMR has STABLE positive edge** (+0.63% T1, +0.96% T2 @10d, 53-55% win); bull-regime decayed (+0.87→+0.15). All-signals flat because bull signals (6369) swamp bear (976). Mean-reversion fades overreaction → works in volatile/bear, dead in calm bull. → **OMR = Bear Ripper specimen #1 (bear-gated), NOT Bull Rider.**

**NEXT (proposed, awaiting go): build REGIME-GATING into the factory** — the one missing primitive serving BOTH sleeves: a PiT market-regime series (SPY>200MA to start; 7-regime engine later) + `regime=` slot in @register_shape + gate in load(). Then: (1) Bull Rider clean 4-shape basket w/ swept exits, (2) bear-gated OMR sleeve-level edge, (3) endgame = 3-way blend t30v+BullRider+BearRipper vs t30v.

**UNCOMMITTED (safe on disk):** scripts/shape_lab.py, exit_lab.py, omr_regime_test.py, shapes_*.py, shapes_portfolio.py (hold_panel), pitfwu_veneer.py, pitfwu_wf.py, backend/app/services/backtester.py (equity_curve), legacy/sql/. Commit when Erik asks.
