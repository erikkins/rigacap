---
name: session-progress
description: "Live session snapshot (auto-checkpointed ~15min) — what's done, in flight, and next"
metadata: 
  node_type: memory
  type: project
  originSessionId: 2dce3134-d861-45c4-a371-80378750f8c0
---

# Session snapshot — Jun 26 2026

**Context:** Shapes/alpha-sleeve research ([[project_alpha_maximizer_sleeve_idea]]). Erik back on wifi; first edge run EXECUTING NOW. Discipline [[feedback_checkpoint_memory_during_session]].

**Earlier today (shipped):** Ads endpoint live (Google Ads Script→/ads/ingest→S3→app hourly); MRR excludes test+comped subs (→$0) + Comped card; Ads "updated Xm ago".

**RUNNING NOW — cup-and-handle edge test:**
- Cmd: `PITFWU_LOCAL=~/pitfwu_cache AWS_PROFILE=rigacap backend/venv/bin/python scripts/shapes_entry_edge.py` (background task `b3pneu0tu`; watcher `biydvu6ws` polls cache/bars/tiers, breaks on "saved →"). Erik wants ongoing status updates.
- Detector FIXED (handle window excluded today; AAPL smoke=6 sane breakouts/9y). Two-step: Tier-1 (2016-2020) + Tier-2 held-out (2021-2026), checkpoints each → `scripts/shapes_entry_edge_results.json`.
- Phase when last checked: downloading ~2GB cache (panels first, 214MB in), compute not started. Output stdout empty until universe built.
- Reads edge = median forward return of breakout days vs baseline @ 5/10/20/40/60d. Cost ~$0 (local M4 Max compute; one-time S3 egress).

**Next after results land:** interpret Tier-1 vs Tier-2 stability; then add the **naive (survivorship-biased) vs rigorous (PiT) CONTRAST** = the differentiation deliverable (Erik's framing: moat is PITFWU rigor, not "find cups"). Then more shapes (VCP, H&S/key-reversal=Bear Ripper), orthogonality vs ensemble, regime split.

**UNCOMMITTED (on disk, safe):** `scripts/shapes_entry_edge.py` (new), `scripts/pitfwu_veneer.py` (PITFWU_LOCAL write-through cache), `legacy/sql/` (137 extracted procs). Commit when Erik asks. Legacy procs = idea catalog only (rewrite modern, don't trust legacy math).
