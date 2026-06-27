---
name: session-progress
description: "Live session snapshot (auto-checkpointed ~15min) — what's done, in flight, and next"
metadata: 
  node_type: memory
  type: project
  originSessionId: 2dce3134-d861-45c4-a371-80378750f8c0
---

# Session snapshot — Jun 27 2026 (Sat)

**Context:** TWO SLEEVES complementing defensive t30v: **Bull Rider** (up-mkt offense) + **Bear Ripper** (down/vol offense). Survivorship-free PITFWU, two-step (T1 2016-20 / T2 held-out 21-26), local M4 Max, `~/pitfwu_cache`. Factories: `scripts/shape_lab.py` + `scripts/exit_lab.py`. Ensemble baseline = REAL prod t30v via `pitfwu_wf_periods.wf(...,20,4.5,30,volw=1.0)` (MDD 17.6/18.5%=advertised).

**REGIME-GATING BUILT (this session):** `bull_regime(end)` = SPY>200MA (PiT); `@register_shape(..., regime="bull"|"bear"|None)`; gate applied per-shape in `load()`. OMR now `regime="bear"` (Bear Ripper #1), hold 10. inv_hs exit fixed to hold 20 (sweep winner).

**SHAPE ROSTER:** Bull Rider 4 = cup_handle(t20)+vcp(t20)+double_bottom(t10)+inv_hs(t20), all held-out edge +0.96..+1.42%. Bear Ripper = pullback_bounce/OMR (bear-gated, mean-rev). Earlier cup+db blend w/ t30v held-out Sharpe 0.99@50/50.

**IN FLIGHT (task b90ks4dww, partial):** standalone portfolio: Bull Rider 4-basket Tier-2 held-out CAGR 8.1%/Sharpe 0.45/MaxDD -43.7% — WEAKER standalone than cup+db (vcp/inv_hs added drawdown). BUT standalone ≠ verdict; the t30v BLEND (ortho) is. Bear Ripper OMR Tier-1 -0.6%/0.03 (expected — T1 mostly bull, gated off); Tier-2 (2022-bear, where it should earn keep) still computing.

**NEXT:** run ORTHO (vs real t30v) for (a) Bull Rider 4-basket and (b) bear-gated OMR — the blend is the real test. Then 3-way blend t30v+BullRider+BearRipper. Possibly trim the 4-basket (vcp/inv_hs hurt standalone DD) or only count their blend contribution.

**Also re-explained to Erik (he asked twice):** time-stop > trailing stop because at SHORT horizon price moves = NOISE (whipsaw), edge is TIME-bounded; t30v's 30% trail works only because it holds MONTHS where drops = real trend breaks. Match exit to whether price carries info at the horizon.

**UNCOMMITTED (safe on disk):** scripts/shape_lab.py, exit_lab.py, omr_regime_test.py, shapes_*.py, shapes_portfolio.py (hold_panel), pitfwu_veneer.py, pitfwu_wf.py, backend/app/services/backtester.py (equity_curve), legacy/sql/. Commit when Erik asks.
