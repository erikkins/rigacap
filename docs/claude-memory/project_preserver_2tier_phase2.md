---
name: project-preserver-2tier-phase2
description: RESUME — 2-tier product + Phase 2 Preserver productionization at the live-infra review gate
metadata: 
  node_type: memory
  type: project
  originSessionId: 2dce3134-d861-45c4-a371-80378750f8c0
---

# 2-TIER PRODUCT + PHASE 2 — paused at the live-infra review gate (Jul 2 2026)

Erik asked to "sit for a bit" here. Shareable product overview delivered:
`design/documents/rigacap-2tier-product-overview.{html,png,pdf}` (navy/gold, risk-dial, both tiers + Core engine, honest backtest labels).

## NAMING (LOCKED Jul 7)
Customer-facing: **Preserver** (base) · **Core** (engine, under both) · **Maximizer** (aggressive add-on, dropped the "++"). INTERNAL-ONLY, never public: **`t30v`** (Core's research code) + **`Maximizer++`** (retired) — treat t30v like the recipe. Product overview HTML/PNG/PDF already scrubbed + regenerated. Trademark-check "Maximizer" (maybe "RigaCap Maximizer" lockup).

## THE PRODUCT (decided)
**RISK DIAL, 2 tiers, one engine.** Under both = **Core t30v** (live, 20yr record: 8.3%/0.73/19% 2007-26) — the engine+proof, NOT a separate product.
- **BASE = Preserver** (flagship, on-brand "capital preservation"): t30v + regime-adaptive defense. Daily backtest last-2yr **31%/1.75/-13%**, 2021-26 (incl 2022) **19%/1.33/-13%** (~half the DD in turbulence). **$129/mo, $1,099/yr.** For $250k+ preservers/advisers.
- **ADD-ON = Maximizer++** (aggressive): routes rotating_bull→breakout + momentum-crash vol-brake. last-2yr **49%/1.94/-17%**, 2021-26 **36%/1.61/-20%**. **+$100-120/mo → $229-249/mo** (paid add-on, sub-brand for firewall; separate product only if different audience). Owns momentum-crash tail (tamed not gone).
- Pricing rationale in framing doc; CAUTION: price on DURABLE ~+7pp not the 49% peak.

## PHASE 2 STATUS — port PROVEN FAITHFUL, all offline/safe work DONE (research branch, undeployed, nothing live touched)
Files (backend/app/services/): `preserver_sleeves.py` (detectors+route, signal-parity EXACT), `preserver_signal_service.py` (build_daily_signals routing, validated), `preserver_portfolio.py` (replay_sleeve, PENNY-EXACT vs research simulate), `preserver_service.py` (PreserverBook rule-B, mechanics validated 2634d + run_shadow_day stub). Migration: `backend/migrations/preserver_shadow_tables.sql` (2 tables, additive, idempotent). Design: `design/documents/preserver-productionization-design.md`.

## ⚠️ REVIEW GATE — next steps touch LIVE INFRA, need Erik sign-off (CLAUDE.md migration-first/off-hours)
**2 OPEN DECISIONS for Erik:**
1. ✅ **Book-transition rule** — I recommend **Option B (hold-to-exit + layer)**: no churn on regime flip, positions exit by own hold, new entries from active book. Schema built around it. (Honest caveat: full single-pool Preserver won't PENNY-match research return-stream allocator — success = lands in validated RANGE ~19%/1.33/-13.5, shadow period proves it.)
2. **Schedule the migration** (off-hours). Then sequence: run migration→verify→deploy models+isolated shadow hook (try/except, never aborts live scan)→2-4wk shadow validation→tier field (migration-first)→tier-aware serving→launch.

Also open: t30v-leg-in-rotating should REFERENCE live model-portfolio positions read-only (confirm feasible in shadow). 

## OTHER OPEN THREADS (parked)
- Phase 3: roll 2-tier story across surfaces (landing/emails/social) + clear the ~5 stale social-launch-cards-v2 citations. Landing copy `design/documents/landing-copy-3tier.md` still 3-tier, needs 2-tier update.
- Research branch `research/shape-diversifiers-regime-allocator` NOT merged/pushed; Phase-0 SSOT fix on MAIN (b2b8624). Uncommitted: all the Phase-2 backend files + product HTML + framing/landing/design docs.
- [[project_secret_dossier]] internal blueprint still TODO.
