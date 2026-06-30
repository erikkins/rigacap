---
name: project-secret-dossier
description: "TODO — build the internal \"top secret dossier\" documenting ALL working system logic"
metadata: 
  node_type: memory
  type: project
  originSessionId: 2dce3134-d861-45c4-a371-80378750f8c0
---

Erik wants to update the **signal intelligence file + PDF** into a complete **internal "top-secret dossier"** — a single document that explains ALL of our working logic, end to end. The bar: *"if someone got a hold of it, they could duplicate our entire system."* That's the whole point — it's the master blueprint.

**INTERNAL ONLY — never published.** This is the literal opposite of customer-facing copy. Brand rules still hold for anything public: never publish the recipe/coefficients ([[feedback_never_publish_recipe]]); "survivorship-free" stays out of marketing ([[feedback_survivorship_free_not_marketing]]). The dossier itself lives behind the wall (design/documents or similar), clearly marked confidential.

**What it must capture (the full canon):**
- **t30v production strategy** (id 6): 20 positions × 4.5%, 30% trailing stop, vol_weight 1.0, biweekly walk-forward, the 7-regime gate. Entry = DWAP×1.05 timing + momentum-rank quality + near-50d-high/volume confirm. The strategy_adaptive_params t30v_cutover row overrides settings defaults.
- **PITFWU** survivorship-free point-in-time data + adjust-at-read veneer; EXT layer to 2004.
- **Validation methodology** — two-step (Tier1 2016-20 / Tier2 21-26), reverse-swap (fit one half/test other, both directions), portfolio-objective (not per-trade), blend-improvement-vs-t30v objective.
- **Regime engine** — production 7-regime classifier (market_regime.py); modern market is ~70% rotating_bull.
- **The diversifier research** — shape factory (shape_lab), exit factory (exit_lab), TPE harness (shape_tpe) with regime-as-a-knob; findings: pullback_ma@calm_bull (+0.33), oversold_bounce@bull (+0.23), Bear Ripper OMR (bear, 6-bear durable); regime-adaptive switch architecture.
- Key lessons: exit selection = portfolio Sharpe; momentum-family durable-but-correlated vs mean-reversion orthogonal-but-regime-specific; era-fragility = regime-dependence.

**How to apply:** when this work stabilizes, draft the dossier (HTML→PDF like the other design/documents) pulling from session-progress + the project memories. Mark CONFIDENTIAL. Keep it current as the diversifier sleeves productize.
