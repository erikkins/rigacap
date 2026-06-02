---
name: Testing methodology v2 — three tiers + held-out cutoff (signed off Jun 1 2026)
description: Strategy backtests follow Tier 1 (hypothesis, in-sample) → Tier 2 (out-of-sample validation, MANDATORY) → Tier 3 (live shadow, recommended). Cutoff 2023-06-01 locks tuning vs validation split. Pickle/cutoff fixed per research cycle.
type: project
originSessionId: c3d0833d-cb3f-474f-8dd8-e530f3300c60
---
**Signed off Jun 1 2026** after the in-sample/out-of-sample reckoning. Replaces all prior testing approaches.

## Full document

`~/rigacap-research/docs/testing_methodology.md` — read for full details. This memory entry is the bind-across-sessions summary.

## Three tiers

1. **Tier 1 — Hypothesis sweep** on TUNING data only (2019-06 → 2021-12, ~2.5y, bull/COVID era). **26 Monday start dates × 2y windows** (starts 2019-06-03 to 2019-11-25). Variant passes if median hits 20% ann / Sharpe ≥1.0 / MDD ≤20% / Calmar ≥1.0 AND ≥20 of 26 windows individually positive.
2. **Tier 2 — Out-of-sample validation** on HELD-OUT data (2022-01-03 → 2026-05-29, ~4.4y, INCLUDES 2022 bear). Single backtest. Variant cannot ship to prod without passing all four targets here. **Tier 2 is the real test** — the bear-inclusive validation is the bar.
3. **Tier 3 — Live shadow** (RECOMMENDED, not required). 4-6 weeks shadow trade comparison. Required when production code path changes (new lever ships); skippable for param-only changes.

## Locked invariants

- **Cutoff: 2022-01-01** (revised Jun 2 2026, ONE-TIME move from 2023-06-01). **Do not move again.** The 2022-01-01 split places the 2022 bear entirely in validation, giving symmetric difficulty and a real bear-survival stress test in held-out data. Reason for the one-time move: original 2023-06-01 cutoff left tuning bear-dominated (every 3y tuning window contained 2022) while validation was bull-only. Found Jun 2 2026 when Tier 1 baseline (9.47% ann) vs Tier 2 baseline (16.73% ann) showed the asymmetry. **Future cutoff moves are prohibited regardless of finding** — under the methodology, you discard the variant or accept results as-is. Moving the cutoff to chase a failed test is the cardinal sin.
- **Pickle: 7y prod pickle (2019-06-03 → 2026-05-29).** Switching pickles starts a new cycle. Don't switch mid-cycle to chase results.
- **Test pickle must match prod pickle range**. Otherwise variant is research-only.
- **Warmup: 26 weeks before each window.** Bar data only, doesn't influence param selection.
- **Standalone backtester is the only honest bench** (WF service results are research-only).

## When to switch cycle (legitimate)

1. Strategy template change requires data current pickle lacks (e.g., bear-mode needs pre-2020)
2. Prod pickle range changes (e.g., parquet migration enables 10y+ in prod → methodology re-binds)
3. Parity contract version bump mandates expanded validation

**NOT legitimate**: "current variants are failing, try longer data" — this is the textbook curve-fitting trap.

## Parquet migration is the gate for 11y testing

The 11y pickle exists locally (`backend/data/all_data_11y.pkl.gz`) but cannot be loaded into prod Lambda (memory cap 3008 MB; 10y already OOMs). Parquet migration unblocks because it supports partial-by-symbol reads.

When parquet ships as primary (per [storage migration roadmap](project_storage_migration_roadmap.md) — currently at Stage 3), revisit this methodology to consider 11y testing. **Until then, 7y prod-equivalent is the testbed.**

## Why this binds

The Friday displacement-gap finding + today's "T3 doesn't help on prod-equivalent" finding cost us weeks of mis-aimed optimization. Methodology v2 exists to never repeat:
- Tier 1 + Tier 2 separation defends against curve-fitting
- Pickle/cutoff locking defends against methodology drift
- Standalone-only defends against parity gaps
- Live shadow (when used) defends against parity gaps the contract missed

## How to apply

- Any new variant test follows Tier 1 → Tier 2 (→ Tier 3 if applicable)
- No variant becomes a production decision without Tier 2 pass
- If a variant fails Tier 2 after passing Tier 1, **discard it** — do not tweak it to "make Tier 2 pass." That's the cardinal sin.
- Don't move the cutoff. Don't switch pickles to chase results.
- Pre-Jun 1 2026 sweep results (all of them — T1/T2/T3/V1-V4/W1-W4/P1-P2/E1-E4/etc.) are **hypothesis-only** under v2. No variant is currently "validated."
