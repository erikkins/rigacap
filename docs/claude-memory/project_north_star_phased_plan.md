---
name: North Star + phased plan (Jun 1 2026) — strategy/parity/marketing reconciliation
description: Locked-in goal (20/20/Sharpe ≥1/Calmar ≥1), 4-phase plan, 6-question discussion framework, and Phase 0 baseline parameters. Anchors all subsequent strategy + marketing work.
type: project
originSessionId: c3d0833d-cb3f-474f-8dd8-e530f3300c60
---
**Established Jun 1 2026, lunchtime.** After the bug-fixing sprint (scanner staleness, STR exits backfill, May 29 entry corrections, live RIOT retroactive close, STR-CB removal) and the WF↔prod displacement-gap finding, Erik named the North Star explicitly and committed to a slow phased unpeel.

## North Star (load-bearing — every step must serve this)

Systemic, disciplined momentum-based stock signal system. Walk-forward tested on the production pickle. Targets:
- **Annualized return: 20%**
- **MaxDD: ≤20%** (ideal)
- **Sharpe: ≥1.0**
- **Calmar: ≥1.0** (annualized / MaxDD)

**Whatever we test in WF, production MUST replicate.** Parity is sacrosanct — no published number is honest if there's an unresolved WF↔prod mechanism gap.

## Phased plan

| Phase | Purpose | Status |
|---|---|---|
| **Phase 0** | Establish ground truth: pickle integrity + parity contract + honest baseline run (no T3, no displacement, top-100 universe, prod-equivalent standalone backtester) | **STARTED Jun 1** |
| **Phase 1** | Pick a target reality: compare honest baseline to 20/20/1/1. Decide gap-closing approach (add levers to prod, retune, or adjust target) | After Phase 0 |
| **Phase 2** | Buy-signal definition unification (the six-question decision tree below) — only after strategy is locked | After Phase 1 |
| **Phase 3** | Subscriber-facing surfaces (dashboard, newsletter, STR, monthly recap, marketing) aligned to unified definition — only after Phase 2 | After Phase 2 |

## The six-question decision tree (Phase 2)

DO NOT touch these until Phase 0 + 1 are done. They are conceptual; resolving them before the empirical foundation is set will produce copy that doesn't match what the code delivers.

| # | Question | Resolves |
|---|---|---|
| 1 | What does "buy signal" mean to a subscriber? (the promise) | Marketing voice, dashboard semantics, newsletter framing |
| 2 | What does "buy signal" mean in code/process? (entry, scoring, displacement, position cap, "fresh") | The data flow we actually implement |
| 3 | Are #1 and #2 the same thing? | The honesty gap subscribers experience |
| 4 | What's the parity contract between WF backtest and production? | The validity of any published performance number — RESOLVED IN PHASE 0 |
| 5 | Given the locked parity contract, what does the system ACTUALLY deliver on the prod pickle? | The real, defensible performance claim — RESOLVED IN PHASE 0 |
| 6 | Is 20/20/1/1 achievable from #5? If not, what changes? | Lever additions, target adjustments, or retuning — RESOLVED IN PHASE 1 |

Cascade: Q4 → Q5 → Q6 (empirical) feeds Q1/Q2/Q3 (conceptual) so we don't write copy the code can't back.

## Phase 0 baseline parameters (locked Jun 1)

| Parameter | Value | Why |
|---|---|---|
| Pickle | `/tmp/parity_test/prod_after_refetch.pkl.gz` | Same as recent sweeps |
| Universe | **Top 100 by liquidity** (PROD setting) | matches `SIGNAL_UNIVERSE_SIZE=100`; prior sweeps used 200 = quiet inflation |
| Strategy ID | 6 (active, base params only) | DB row 6, ignore DD-tighten params (prod doesn't read) |
| max_positions | 6 | Strategy 6 |
| position_size_pct | 15.0 | Strategy 6 |
| dwap_threshold_pct | 5.0 | Strategy 6 |
| near_50d_high_pct | 3.0 | Strategy 6 |
| trailing_stop_pct | 12.0 | Strategy 6 |
| short_momentum_days | 5 | Strategy 6 / config default |
| Composite weights | 0.3 / 0.2 / 0.15 | Strategy 6 |
| **DD-tighten (T3)** | OFF (threshold=0) | not in prod yet |
| **Displacement** | OFF (standalone backtester = vacancy-only = prod equivalent) | the Friday displacement-gap finding |
| Start dates | 52 Mondays | `/tmp/dates_52mon_prod.txt` |
| Window | 5 years per start | Standard |
| Backtester | **Native standalone**, single `run_backtest` call per date | No WF-service chunking, no monkey-patch — pure prod equivalence |

**Why this is the honest run:** the 23.4% / 26.4% / 1.00 figures the marketing site currently references came from WF-service-orchestrated runs with biweekly period-boundary mechanics + top-200 universe. Production has neither. The Phase 0 baseline replaces those figures as the defensible starting truth.

**Single-date preview** (2021-01-04 start, ran Jun 1 morning, top-200 universe, no T3): +42.23% total / +7.30% ann / 0.46 Sharpe / 29.5% MDD / 175 trades. Full 52-mon top-100 sweep likely lands similar or modestly lower.

## Why this matters

- Memory of "Trial 37 was over-fit to corrupted pickle" → strategy claims must be re-tested honestly when underlying assumptions shift
- Memory of "Run5 parity drift" → marketing claimed Apr 28 baseline for 4 weeks while prod ran Run5 over-fit params; the parity rule was violated
- Today's findings → 3 more divergences (scanner staleness, displacement gap, multi-source data drift)
- Pattern: every time we don't enforce parity, marketing eventually has to retract. Cheaper to enforce up front.

## How to apply

- Before ANY new strategy claim, run on prod-equivalent standalone backtester with top-100 universe and Strategy 6 base params
- Before ANY surface alignment work (Phase 2), the Phase 0 baseline number and the Phase 1 lever decision must be locked
- Watch for "WF said X, prod will deliver Y" wherever Y < X. If you find one, escalate — don't accommodate.

## Connected memory

- [WF↔prod incumbent-displacement gap](project_wf_prod_displacement_gap.md) — Friday's finding that produced this conversation
- [Trial 37 over-fit](project_trial37_overfit_clean_data.md) — prior parity violation
- [Run5 parity drift lesson](project_run5_parity_drift_lesson.md) — marketing-numbers cycle
- [WF↔prod parity rule (feedback)](feedback_wf_prod_parity.md) — long-standing rule, now extended to orchestration mechanisms (not just strategy logic)
- [Numbers citations registry](project_numbers_citations_registry.md) — every surface that cites perf numbers; walk this when Phase 1 numbers change
