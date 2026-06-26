---
name: session-progress
description: "Live session snapshot (auto-checkpointed ~15min) — what's done, in flight, and next"
metadata: 
  node_type: memory
  type: project
  originSessionId: 2dce3134-d861-45c4-a371-80378750f8c0
---

# Session snapshot — Jun 26 2026

**Context:** Shapes / Bull Rider research ([[project_alpha_maximizer_sleeve_idea]]). Cup-and-handle on survivorship-free PITFWU, two-step (Tier-1 2016-20 / Tier-2 held-out 21-26). Discipline [[feedback_checkpoint_memory_during_session]].

**RESULTS SO FAR (all local M4 Max, ~$0, cache `~/pitfwu_cache` = 386MB):**
1. **Entry edge** (`scripts/shapes_entry_edge.py`): cup-and-handle 20d edge **+1.42% held-out**, stable across both tiers. 40-60d edge was a Tier-1 mirage (gone held-out) — two-step caught it.
2. **Naive-vs-rigorous contrast**: survivorship bias inflates 20d edge — naive 2.38% vs rigorous **1.42%** held-out (**68% too high**); worst in the hard 2022 regime; naive even FABRICATES the long-hold thesis. = the differentiation, proven + marketing-grade.
3. **Strategy baseline** (`scripts/shapes_strategy.py`, 20d time-stop + 10% trail, 15bps): Tier-1 median +1.38%/56% win; **Tier-2 held-out median −0.29%, win 48.9%, mean +1.60%** → tail-driven, marginal naive. **Trail never fired (0%) → exit is doing NOTHING → big room.**

**NEXT (awaiting Erik go): exit-menu TPE.** Erik's point: Ensemble has 1 exit (30% trail); legacy DB had many (up-20/down-8, stairstep ratchet, key-reversal). Build `shapes_tpe.py` = fixed cup-and-handle entry + Optuna(TPESampler) search over EXIT params (trail%, profit target/stop, stairstep, time-stop, key-reversal toggle). **Optimize Tier-1, validate held-out Tier-2** (no overfit; cap param count). Reuse `scripts/tpe_optimizer.py` Optuna pattern. Asked Erik: which exits + #trials (~150 start).

**UNCOMMITTED (on disk, safe):** shapes_entry_edge.py, shapes_strategy.py (new), pitfwu_veneer.py (PITFWU_LOCAL write-through cache), legacy/sql/ (137 procs = idea catalog). Commit when asked.
**After exits:** orthogonality vs ensemble; regime split; then Bear Ripper (H&S/key-reversal) + more shapes (VCP).
