---
name: session-progress
description: "Live session snapshot (auto-checkpointed ~15min) — what's done, in flight, and next"
metadata: 
  node_type: memory
  type: project
  originSessionId: 2dce3134-d861-45c4-a371-80378750f8c0
---

# Session snapshot — Jun 26 2026 (Erik pausing — laptop closing)

**Context:** Bull Rider shapes research, survivorship-free PITFWU, two-step (Tier-1 2016-20 / Tier-2 held-out 21-26). Local M4 Max, ~$0, cache `~/pitfwu_cache` (~386MB). [[project_alpha_maximizer_sleeve_idea]].

**RESEARCH ARC (all two-step-validated, results saved in scripts/*_results.json):**
1. Entry edge: cup-and-handle 20d edge **+1.42% held-out**, stable. 40-60d = Tier-1 mirage.
2. Naive-vs-rigorous: survivorship bias inflates 20d edge to 2.38% (real 1.42%, 68% too high) = differentiation proven.
3. Exit TPE (800 trials, resumable `scripts/shapes_tpe.db`): **STOPS HURT** (whipsaw); exit not the lever.
4. Entry-quality sweep: KEY REFRAME — entry fine (pure 20d hold: held-out median +1.32%, win 54%), stops were the problem. Gates (vol/trend/mom) don't robustly help held-out.
5. Portfolio sim (`shapes_portfolio.py`, N=15/HOLD=20): **standalone ~SPY-to-worse held-out** (13.3%/0.73/-28.6% vs SPY 14.2%/0.87/-25.4%). Not a flagship.
6. Orthogonality (`shapes_orthogonality.py`): BullRider↔SPY corr **0.55** (VALID, low — not just beta). Blend looked additive BUT used a BROKEN ensemble PROXY (-37.5% DD — Erik caught it; NOT the real ~19% product).

**KEY INSIGHT (Erik's Q "why is cup-and-handle popular if returns meh?"):** because the famous evidence is survivorship+hindsight (what our rigor strips) AND experts add fundamentals/RS/discretion/market-timing — the bare geometry is ordinary. We haven't tried stricter detection or overlays. The PIPELINE is the asset; cup-and-handle is specimen #1.

**IN FLIGHT — 2 tasks when Erik returns:**
A. **FIX orthogonality with REAL ensemble** — BLOCKED: `BacktestResult` doesn't expose the daily equity curve. FIX = add `equity_curve: List = field(default_factory=list)` to the BacktestResult dataclass (backend/app/services/backtester.py ~line 138) + set it in run_backtest (~line 2890 builds local `equity_curve`; pass/assign it onto the result). Then `pitfwu_wf.run()` already returns it (getattr-guarded), and `shapes_orthogonality.real_ensemble_equity()` works. Real ensemble DD should be ~20-30% (sanity-check it's NOT -37%). NOTE: pitfwu_wf config = 12% trail/6pos (M3), not exact t30v 30%/20pos — fine for correlation, note it.
B. **register-shape refactor** — make detectors pluggable (registry: name→fn) so any shape runs the whole entry-edge→portfolio→orthogonality pipeline. Then add a REVERSAL shape (double-bottom / inverse-H&S = Bear Ripper) — highest priority (most likely orthogonal/additive). Then VCP/flags (momentum-family, less additive).

**UNCOMMITTED (on disk, safe):** scripts/shapes_{entry_edge,strategy,tpe,entry_quality,portfolio,orthogonality}.py (all new), pitfwu_veneer.py (PITFWU_LOCAL write-through cache), pitfwu_wf.py (equity_curve getattr line), legacy/sql/ (137 procs). Commit when Erik asks.
