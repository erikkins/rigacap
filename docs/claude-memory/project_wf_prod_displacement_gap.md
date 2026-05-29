---
name: WF service vs production — incumbent displacement parity gap (May 28-29 2026)
description: WF service test methodology lets new candidates displace at period boundaries; production process_entries only enters on vacancies. Marketing numbers reflect WF methodology, not production.
type: project
originSessionId: c3d0833d-cb3f-474f-8dd8-e530f3300c60
---
**Discovery date:** 2026-05-29 (Friday afternoon), during T3 backtester wire-up (Step 2b-3 of T3 productionization).

**The gap:**

Production `model_portfolio_service.process_entries` (line 180) returns immediately when `open_count >= MAX_POSITIONS`. **Production never displaces incumbents** — new positions only enter when an old one exits.

The WF service test methodology that produced T3's published numbers (23.4% ann, 26.4% MDD, 1.00 Sharpe) does NOT match this behavior. Whatever WF service does at period boundaries produces materially more trades and materially better returns than standalone backtester (and production) can reach with vacancy-only entry.

**Evidence (start date 2021-01-04 → 2026-01-04, prod pickle):**

| Methodology | Total return | Sharpe | MaxDD | Trades |
|---|---|---|---|---|
| WF baseline (no T3, monkey-patch infra) | +80.45% | 0.61 | 29.86% | 211 |
| WF + T3 (monkey-patch DD-tighten) | +101.77% | 0.67 | 26.68% | 279 |
| Standalone backtester baseline | +42.23% | 0.46 | 29.51% | 175 |
| Standalone + native T3 (per-bar peak) | +29.22% | 0.35 | 39.66% | 232 |

Standalone baseline is **roughly 2× lower** than WF baseline before T3 enters the picture. Native T3 on standalone HURTS, while monkey-patch T3 on WF HELPS — same lever, opposite outcome, because the underlying entry methodology differs.

**Why we missed it:**

The parity rule ("WF backtest ↔ production signal generation MUST be identical") was historically applied to the **strategy logic** (DWAP, momentum, trails) but never extended to the **orchestration layer** (when/how new positions enter). The same gap probably affects every prior strategy validation done through WF service — Apr 28 baseline (+160% / 0.92 / 20.4%), Run5, Trial 37 (+240% / 0.89 / 24%). All used WF service infrastructure; none were validated against production's vacancy-only entry rule.

**Why:** Without this awareness, marketing claims compound a methodology-level inflation that production can never reach. Live T3 production may land closer to +29% / 5% ann than +101% / 23.4% ann. That's a wholesale story change, not a numbers tweak.

**How to apply:**

**No action this session (Friday 5/29).** Two options on the table:
1. **Add incumbent displacement to production** (preserves marketing, requires real prod code change + hysteresis to avoid churn)
2. **Update marketing to standalone-realistic numbers** (lower published numbers, but honest to what live will do)

User leaning toward option 1 but deferring decision over the weekend. **Do not push to a decision; let it breathe.**

**Current state (frozen):**
- 2b-2 backtester edits APPLIED but DORMANT (`dd_tighten_threshold_pct = 0` default = no-op for all callers; harmless to leave in place).
- Strategy 6 DB row already renamed to T3 (Step 1) and has DD-tighten params in JSON (Step 2a) — those are documentation-only, prod doesn't read them yet.
- 2b-3 (re-validation) PAUSED.
- 2b-4 (DB migration), 2b-5 (prod exits), 2b-6 (user simulator) NOT STARTED.

**Investigation entry points** for resuming:
- `backend/app/services/model_portfolio_service.py:180` — production vacancy-only gate
- `backend/app/services/walk_forward_service.py:1495` — WF service period-boundary universe rerank
- `backend/app/services/walk_forward_service.py:1780-1791` — carry_positions behavior (confirmed positions DO carry; "biweekly force-close" was a misread)
- WF service likely re-ranks candidates per period and somehow drives the extra trades — exact mechanism not yet pinpointed.

**Related published numbers all live in:** `docs/numbers-citations-registry.md`. Any marketing-update path needs to walk that registry.

Backup of pre-T3-rename Strategy 6 row: `/tmp/strategy6_backup_pre_t3_rename.json` (local-only).
