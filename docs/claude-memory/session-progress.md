---
name: session-progress
description: "Live session snapshot (auto-checkpointed ~15min) — what's done, in flight, and next"
metadata: 
  node_type: memory
  type: project
  originSessionId: 2dce3134-d861-45c4-a371-80378750f8c0
---

# Session snapshot — Jul 1 2026 (Wed) — marketing draft + BREAKOUT hunt (biggest lift yet)

**Context:** Shapes research → 7-regime adaptive allocator on t30v (FULLY validated last session: cross-half TPE, EXT holdout, all-weather, daily-DD). Engine shape_tpe.py (blend-improvement-vs-t30v objective, regime-as-knob). Diversifiers: pullback_ma@calm_bull(+0.327), oversold_bounce@bull(+0.232). Allocator = pure regime rotation. Erik remote.

**✅ MARKETING FRAMING drafted:** `design/documents/maximizer-vs-preserver-framing.md`. One engine/two modes: **Maximizer** (t30v, ~37% last-2yr) vs **Preserver** (allocator, halves DD in turbulence, small cost in calm). Lead with last-2yr (not 20yr=research credibility); honest tradeoff; self-selection not filtration; NEVER recipe; survivorship-free not a tagline. Status draft, allocator still research-stage.

**⭐⭐ BREAKOUT HUNT = BIGGEST blend-improvement yet: +0.369** (beats pullback +0.327, oversold +0.232). Added parameterized `breakout` shape to shape_tpe (buffer/vol_mult/mom_min/hold + hi50_1 feature). Winner: **regime='rotating_bull'** (the DOMINANT ~70-85% regime), buffer 1.4%/vol×1.38/hold29; sleeve 22.7%A/39.8%B CAGR, Sharpe 1.17/1.27; top-6 all rotating, tight. HONEST READ: it's "a BETTER momentum engine in rotating_bull" not a diversifier (blend wants 90% of it = replacing t30v, not diversifying). Momentum-family + likely MODERN-ONLY (breakouts had 0 edge pre-2016) → EXT holdout MANDATORY. 39.8% CAGR flattered by regime gate dodging 2022.

**⏸️ IN FLIGHT (built, Erik STOPPED the run — awaiting his call):** `regime_allocator_v2.py` — routes rotating_bull→breakout (instead of t30v). THE "push further" test: if breakout beats t30v in the ~85% rotating regime, whole-system return could jump. Windows A/B/full. **NEXT: run v2 + EXT-validate breakout (the skeptic's test, since modern-only).**

**UNCOMMITTED (safe on disk):** shape_tpe.py (+breakout), regime_allocator_v2.py, maximizer-vs-preserver-framing.md, all prior scripts. Memories: [[feedback_survivorship_free_not_marketing]], [[project_secret_dossier]], [[project_newsletter_exit_stops_topic]]. Commit when Erik asks.
