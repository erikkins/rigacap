---
name: session-progress
description: "Live session snapshot (auto-checkpointed ~15min) — what's done, in flight, and next"
metadata: 
  node_type: memory
  type: project
  originSessionId: 2dce3134-d861-45c4-a371-80378750f8c0
---

# Session snapshot — Jun 26 2026

**Context:** Bull Rider shapes research, survivorship-free PITFWU, two-step (Tier-1 2016-20 / Tier-2 held-out 21-26). Local M4 Max, ~$0, cache `~/pitfwu_cache`. [[project_alpha_maximizer_sleeve_idea]].

**RESEARCH ARC (all two-step-validated, results in scripts/*_results.json):**
1-4. Cup-and-handle entry edge +1.42% held-out; survivorship contrast (naive 2.38% vs real 1.42%); exit TPE → STOPS HURT (whipsaw); entry-quality sweep → entry fine (pure 20d hold: median +1.32%/win 54%), gates don't robustly help.
5. Portfolio sim: standalone ≈SPY held-out (13.3%/0.73/-28.6%). Not a flagship.
6. **Orthogonality FIXED with REAL defensive ensemble (DONE this session):** Erik caught the -37.5% was a broken PROXY. Fixed by exposing `BacktestResult.equity_curve` (see below). **Result FLIPS positive:** real ensemble corr to BullRider only **0.43-0.50** (proxy overstated at 0.65). **Blend beats both standalones:** held-out 50/50 Sharpe **0.81** (vs 0.72/0.68); full-period 50/50 Sharpe **1.03** + MaxDD cut to **-21.5%** (from -30.6%). **Bull Rider IS a genuine diversifier** as a sleeve, not standalone.

**KEY CODE CHANGE (Erik approved "additive plumbing, defaults, 100% repeatable"):** added `equity_curve: List[Dict] = field(default_factory=list)` to BacktestResult (backend/app/services/backtester.py ~line 168) + `equity_curve=equity_curve` in constructor (~2923) + popped in to_dict (API payload unchanged, byte-identical). PROVABLY INERT — ensemble logic/numbers untouched (smoke: real ensemble MDD 17.9% short / -17.4% full = matches ~19% advertised). pitfwu_wf.run() returns it via getattr. NOTE: pitfwu_wf uses M3 config (12% trail/6pos), not exact live t30v (30%/20) — direction robust, exact blend ratio would shift.

**NEXT (Erik asked, building next): register-shape refactor (task B)** — pluggable detector registry so any shape runs the whole entry-edge→portfolio→orthogonality pipeline; then add first REVERSAL shape (double-bottom / inverse-H&S = Bear Ripper) — most likely orthogonal/additive. Strategic: ordinary momentum shape already diversifies well → orthogonal shapes could be stronger complements.

**UNCOMMITTED (on disk, safe):** scripts/shapes_*.py (6 new), shapes_entry_quality, pitfwu_veneer.py (PITFWU_LOCAL cache), pitfwu_wf.py (equity_curve line), backend/app/services/backtester.py (equity_curve field), legacy/sql/ (137 procs). Commit when Erik asks.
