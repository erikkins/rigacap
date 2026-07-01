---
name: session-progress
description: "Live session snapshot (auto-checkpointed ~15min) — what's done, in flight, and next"
metadata: 
  node_type: memory
  type: project
  originSessionId: 2dce3134-d861-45c4-a371-80378750f8c0
---

# Session snapshot — Jul 1 2026 (Wed) — breakout pushes return but breaks DD discipline → 3 tiers

**Context:** Shapes research → 7-regime adaptive allocator on t30v (validated last session). Engine shape_tpe.py (blend-improvement objective, regime-as-knob). Diversifiers: pullback_ma@calm_bull(+0.327), oversold_bounce@bull(+0.232). Allocator = pure regime rotation. Erik remote.

**✅ MARKETING FRAMING drafted** `design/documents/maximizer-vs-preserver-framing.md` (Maximizer=t30v vs Preserver=allocator; lead last-2yr, honest tradeoff, no recipe).

**⭐ BREAKOUT shape (added to shape_tpe): biggest blend-improvement +0.369 @ regime=rotating_bull** (dominant ~70-85% regime), high-return sleeve. v2 allocator (regime_allocator_v2.py) routes rotating_bull→breakout: MODERN 2016-20=30.3%/1.48/-12.6, 2021-26=41.3%/1.42/-16.0 (≈DOUBLES v1). EXT holdout: modern-only-ish (helped calm 2013-15, HURT volatile 2009-12).

**⭐⭐ PRESSURE TEST (breakout_pressure.py — walk-forward + costs) = SHARP VERDICT:**
- WALK-FORWARD OOS (re-opt on past, test next unseen yr): stitched **33.9% CAGR / 1.14 Sharpe / MaxDD −33.5%**. Years lumpy (2020 +59%, 2021 +4%/−31%, 2025 +85%). Params unstable across folds.
- COSTS: 15bps→29.6%, 30bps→27.1%, 50bps→23.9% (Erik right — costs cost ~6pts, NOT the dealbreaker; commissions dead, this is spread+slippage+self-impact which taxes breakout-chasing specifically).
- **THE MIRAGE WAS DRAWDOWN, NOT RETURN.** Return mostly REAL (~30% OOS after costs, down from static 41%). But true OOS DD = −33% (not the −16% biweekly showed). Breakout = high-return HIGH-RISK momentum engine.

**PRODUCT = 3 HONEST TIERS (risk dial, same engine):** t30v (base) → **v1 Preserver** (rot→t30v, ~19%/−13%, all-weather) → **v2 Maximizer++** (rot→breakout, ~30% OOS/−33%, aggressive-growth; CANNOT be sold as capital-preservation).

**NEXT (Erik to pick):** (a) lock 3-tier framing into the doc, or (b) keep pushing — tame breakout's −33% (drawdown guard / trailing stop / position cap on the breakout sleeve). Also pending: [[project_secret_dossier]].

**UNCOMMITTED (safe on disk):** shape_tpe.py(+breakout), regime_allocator_v2.py, breakout_pressure.py, maximizer-vs-preserver-framing.md, all prior. Memories: [[feedback_survivorship_free_not_marketing]], [[project_secret_dossier]], [[project_newsletter_exit_stops_topic]]. Commit when Erik asks.
