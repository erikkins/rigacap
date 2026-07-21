---
name: feedback-slow-down-verify
description: "SLOW DOWN — verify code/data paths before concluding; don't dress assumptions as conclusions; one careful step at a time"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 264056a8-f1e5-489c-9140-1fb57bda9825
---

# SLOW DOWN, don't assume (Erik, Jul 21 2026 — he was losing patience)

**What happened:** In one afternoon I made a chain of confident-but-wrong calls on the Maximizer breakout gap — "survivorship bias" (twice), "universe breadth", "research data (shape_tpe) is biased" — each stated as a conclusion, each WRONG, each caught by Erik not me. Root cause was MY own buggy validation (wrong universe function: used `universe_asof(fixed 600)` when research/prod use `universe_asof_prod(d,300,15)[:100]` point-in-time). Plus a made-up import. The rushing eroded trust and wasted his patience.

**Why it matters:** Erik is effectively managing me like a dev; the value is only there if my conclusions are trustworthy. A fast wrong answer is worse than a slow right one — it sends us chasing artifacts and he has to rein me in every time.

**How to apply (every analysis, esp. research↔prod):**
- READ the actual code/data path FIRST (e.g., what does `shape_tpe.load_data` load? → `pitfwu_veneer`, same as prod). State it as fact ONLY after verifying — never a hypothesis dressed as a conclusion.
- Say plainly what I KNOW vs what I'm GUESSING. Flag guesses as guesses.
- One careful step at a time. Don't fire off a flurry of scripts each baked on an unverified assumption.
- When a result surprises, first suspect MY OWN test/script (universe, data source, window, construction mismatch) BEFORE blaming the strategy/data. Diff the pipelines.
- Pairs with [[feedback_research_maps_to_prod]] (verify penny-to-penny; feasible-only).
