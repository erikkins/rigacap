---
name: session-progress
description: "Live session snapshot (auto-checkpointed ~15min) — what's done, in flight, and next"
metadata: 
  node_type: memory
  type: project
  originSessionId: 2dce3134-d861-45c4-a371-80378750f8c0
---

# Session snapshot — Jun 27 2026 (Sat) — END OF A MARATHON SHAPES SESSION

**Context:** Multi-day Bull Rider / Bear Ripper shapes research complementing defensive t30v. Survivorship-free PITFWU, two-step, local M4 Max, cache `~/pitfwu_cache` (now ~1GB incl EXT). Erik north star: **20% CAGR / <20% MaxDD**.

**BUILT (all uncommitted, safe on disk):** `scripts/shape_lab.py` (shape factory: registry, regime-gating `regime=bull|bear`, per-shape exits via hold_panel, per-shape CAPS via shape_panel+cap_per_shape), `exit_lab.py` (exit factory + sweep), `omr_regime_test.py`, `three_way_blend.py`. `shapes_portfolio.simulate` now supports hold_panel + shape caps. EXT layer (`v.EXT=True`, ~21y back to 2004-12, 6 bears) verified working; pre-2016 survivorship-biased (label).

**⭐ THE HONEST VERDICT (three_way_blend, held-out vs full):** **20%/<20% NOT reached with a STATIC blend.** Ceiling ~15% CAGR within DD budget. KEY: which sleeve helps FLIPS by regime — Full-period (bull-heavy): Bull Rider star (14%/0.90, optimizer wants 70%), Bear Ripper≈0. Held-out (incl 2022): Bull Rider dead weight (0%), Bear Ripper the diversifier (corr −0.00 to t30v; 50/50 → Sharpe 1.06, MaxDD −8.9% halved). Sleeves = risk-shaping/regime-specialized, not a path to 20% CAGR. Bull Rider per-shape caps helped DD (−43.7→−33.8) but didn't fix Sharpe (still correlated factor).

**⭐ NEXT (the compelling move): REGIME-ADAPTIVE allocation** — Bull Rider in bull regime, Bear Ripper in bear regime, driven by the existing 7-regime engine. Static blend can't win both regimes; switching might capture Bull's bull-CAGR + Bear's bear-protection = real shot at 20%/<20%. Build this first next session.

**Validated facts:** Bear Ripper durable across 6 bears/2 eras (bear-OMR +0.5-0.9%/53-57% win). Bull Rider shapes (cup/vcp/db/inv_hs) all +0.96-1.42% held-out edge but CORRELATED to t30v (~0.59). Exit truth: time-stops beat trailing (noise at short horizon). Real t30v = `pitfwu_wf_periods.wf(...,20,4.5,30,volw=1.0)` MDD 17.6/18.5%=advertised.

**Other:** newsletter draft saved [[project_newsletter_exit_stops_topic]] (future issue, not Jun 28). Curiosity backlog: Bull/Bear Ripper as standalone product. backend/app/services/backtester.py has the additive equity_curve field. Commit all when Erik asks.
