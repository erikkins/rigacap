---
name: project-alpha-maximizer-sleeve-idea
description: "Rainy-day idea — use the PITFWU engine a different way to build a separate alpha-maximizer product, fully decoupled from the Ensemble"
metadata: 
  node_type: memory
  type: project
  originSessionId: 2dce3134-d861-45c4-a371-80378750f8c0
---

# Alpha-maximizer sleeve — separate product idea (raised Jun 25 2026)

**Erik's framing (verbatim intent):** "Since we have PITFWU, can we figure out an alpha maximizer sleeve that potentially could be a separate product... but it needs to be completely separate from ensemble that we're doing today. Just want to see if we can use the engine in a different way." Explicitly a **rainy-day / exploratory** item — NOT now.

**The thesis:** RigaCap's live product (Ensemble / t30v) is deliberately **defensive** — "behavioral capital insurance," beats SPY on drawdown, lags in bull runs (see [[memory MEMORY.md positioning canon]] / the analyst A- framing). An **alpha-maximizer** would be the opposite pole: lean into return, accept more drawdown — a different point on the risk curve for a different persona (the "Market Maximizer," graded F for the defensive product per the F/A matrix). Two products = two persona fits, same engine.

**Why the engine can support it:** PITFWU (point-in-time forward-walking universe, split-adjust-at-read) is now the live, survivorship-free data path ([[memory MEMORY.md PITFWU loop closed]]). The backtester/CustomBacktester + walk-forward harness is strategy-agnostic — entry/exit/sizing are parameters. The continuous-analysis work already showed the **return knobs** that the defensive product gives up:
- Raw 12-mo momentum ≈ 28.8% CAGR but ~−52% true daily MDD (from the inversion-campaign forensic) — the high-octane end.
- t30v chose 20×4.5% diversification + wide trail for defense; an alpha sleeve would invert: more concentration, tighter/again different exit, faster rotation, maybe leverage-adjacent universe (currently excluded: TQQQ/SQQQ etc.).
- Levers to sweep: concentration (6×15 vs 20×4.5), ranking horizon, carry vs periodic wholesale rotation (the `nocarry` configs), regime filter on/off, near-high band, max-hold.

**Hard constraints / guardrails:**
- **Completely separate from Ensemble** — own strategy_id/type, own model-portfolio book, own marketing surface. Must NOT contaminate the live defensive track record or its parity (the t30v parity work was hard-won — see [[project_signal_parity_jun13]]).
- Honesty bar: any new product gets the same survivorship-free, continuous-truth validation (no window-mean cherry-picking — that mistake is documented in the Jun-9 reckoning).
- Positioning: would be sold to a DIFFERENT persona; don't blur the "capital preserver" message that the current funnel filters for.

**First concrete step when picked up:** run a walk-forward sweep on PITFWU of the return-maximizing knobs (concentration × horizon × carry × regime) on held-out windows, report CAGR/Sharpe/Calmar/MDD frontier vs t30v and vs raw momentum — see whether there's a defensible "max-alpha" config that isn't just unlevered beta. Related: [[project_t30_validated_strategy]], [[project_inversion_campaign_jun9]], [[project_storage_migration_roadmap]].

## Jun 26 — NAMED + LEGACY-SQL NUGGETS + SHAPES (Erik picked this up)
- **Two poles named:** **Bull Rider** (bull-market max-alpha, ride trends hard) and **Bear Ripper** (bear-market alpha — profit from / time the turn, the key-reversal angle). Complementary SLEEVE to the defensive Ensemble; **research-only, must stay completely separate** from prod Ensemble.
- **Legacy Azure SQL recovered + scripted out:** the original bacpac is at `~/Downloads/stocker-2026-1-29-17-44-2/` (model.xml 1.4MB + Data/ tables). I extracted all **137 stored procedures** → `legacy/sql/procedures/*.sql` + `INDEX.md` (in the repo, untracked). These are the original "throw-it-at-the-wall" entry/exit rules. Nuggets worth porting/testing:
  - `findCupAndHandle` — FULL cup-and-handle detection: 30% upswing (4-6mo) → 20% correction (cup) → handle rises within 15% of old high → ~8% handle pullback → buy on breakout above handle high. **SHAPES are UNEXPLORED — Erik: "to date we haven't looked for cup-and-handle or other shapes."** This is the novel/exciting angle, orthogonal to momentum/DWAP.
  - `CheckwatchSellKeyTrendReversalRetroDate` — key-reversal-day EXIT (today high/low vs yesterday + 52w-high + 200DMAP) → Bear Ripper timing nugget.
  - `CheckWatchBuy10AboveDWAP` — DWAP+10% breakout entry (price>$46, vol>1M, no double-buy) — partly already ported.
- **Research harness exists + runs LOCALLY (separate from prod):** `scripts/pitfwu_wf.py` composes raw S3 parquet → pitfwu_veneer → point-in-time data_cache → runs BacktesterService. Usage `AWS_PROFILE=rigacap python scripts/pitfwu_wf.py <start> <end>`. Friends: `pitfwu_entry_edge.py`, `param_tournament.py`, `tournament_7dates.py`, `bear_window_inspection.py`. `_indicators()` already computes dwap/ma50/ma200/vol_avg/high_52w. ANY long/expensive research MUST checkpoint to disk ([[feedback_never_keep_paid_work_in_memory]]).
- **Proposed first kickoff:** a research-only `scripts/shapes_research.py` (or `bull_rider_research.py`) — port cup-and-handle detection to Python, measure its forward-return EDGE on PITFWU (does buying the breakout beat random/momentum entry?), before building a full strategy. Cheap signal-quality test first, then full WF if the edge is real. Decision pending from Erik: which pole first (Bull Rider/shapes vs Bear Ripper/reversal) — leaning shapes-first (novel + has the legacy spec).
