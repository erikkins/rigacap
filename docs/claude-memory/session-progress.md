---
name: session-progress
description: "Live session snapshot (auto-checkpointed ~15min) — what's done, in flight, and next"
metadata: 
  node_type: memory
  type: project
  originSessionId: 2dce3134-d861-45c4-a371-80378750f8c0
---

# Session snapshot — Jun 30 2026 (Tue) — 7-REGIME ALLOCATOR fully validated (incl DAILY DD)

**Context:** Shapes research → 7-regime adaptive allocator on t30v. Survivorship-free PITFWU. Two TPE-validated diversifiers: pullback_ma@calm_bull (+0.327), oversold_bounce@bull (+0.232). Allocator (scripts/regime_allocator*.py) = PURE ROTATION: calm_bull→pullback, capitulation(panic/recovery/weak_bear)→oversold, else(~85% rotating_bull)→t30v. Erik remote.

**VALIDATION COMPLETE (4 layers all passed):**
1. Cross-half TPE (objective=blend-improvement vs t30v, min A/B).
2. EXT pre-2016 third-holdout (frozen params): DD-reduction robust ALL windows; CAGR boost CONDITIONAL on volatility (2009-12 won all axes; 2013-15 calm-grind only DD).
3. All-weather (regime_allocator_allweather.py, 4 windows 2009-2026): PURE ROTATION (core 0%) is robust pick — best worst-window Sharpe 0.61, beats t30v on DD 4/4 windows + Sharpe 3/4 (loses only calm 2013-15 on return). No core dilution needed.
4. ⭐ DAILY-DD (regime_allocator_daily.py, single-backtest daily t30v proxy): 2021-26 t30v daily DD=-23.7% (biweekly understated -17.6%) → ALLOCATOR -13.5% = nearly HALVED, <20% CONFIRMED at daily res.

**⭐ MARKETING READ (Erik's framing: future~recent past, lead with last 2yr not 20yr):** LAST 2YR (2024-26) = t30v 36.7%/1.91/-14.7%, allocator 32.2%/1.80/-12.9%. Recent 2yr is the HEADLINE (vs 20yr ~9%). CATCH: last 2yr was CALM bull (5% capitulation) → t30v ALONE edged allocator on return; allocator's edge needs turbulence. = PRODUCT FORK: "Maximizer"=t30v alone (~37% recent), "Preserver/all-weather"=allocator (halves DD in turbulence, small cost in calm).

**NEXT (proposed, Erik to confirm):** draft side-by-side "Maximizer vs Preserver" marketing framing (recent-2yr headline + honest turbulence tradeoff). Also: re-hunt breakout shapes w/ regime knob; [[project_secret_dossier]] internal blueprint.

**UNCOMMITTED (safe on disk):** all scripts/*.py incl shape_tpe, regime_research, stack_sleeves, regime_allocator(_ext/_allweather/_daily), shapes_portfolio, shape_lab, pitfwu_wf, backtester. Memories: [[feedback_survivorship_free_not_marketing]], [[project_secret_dossier]], [[project_newsletter_exit_stops_topic]]. Commit when Erik asks.
