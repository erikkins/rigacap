---
name: Cluster-day vs isolated-day entry A/B test
description: Test whether biweekly-rebalance days with 3+ simultaneous entries systematically underperform isolated fresh-signal days. ~30-60 min query against the WF trade history. Tag: research follow-up, week of May 11-18 2026.
type: project
originSessionId: c3d0833d-cb3f-474f-8dd8-e530f3300c60
---
**Why:** May 6 2026 rebalance fired five entries simultaneously (IREN, RIOT, CIFR, GOOG, AMZN), totalling 7 May signals through May 7 against a published claim of "3-4 high-conviction signals per month." User flagged the implicit concern: are cluster-day entries (3+ same-day) buying breakouts that are already too far extended to perform? The strategy is by design a momentum/breakout entry — "we're late" is baked into the thesis — but cluster-day clustering may compound the lateness in a measurable way.

**How to apply:** Tag this as a research follow-up for the week of May 11-18 2026. Don't act on it without data. The 2.51× win/loss ratio means individual cluster picks can underperform without breaking the strategy — the question is whether *the cohort as a whole* lags isolated entries enough to justify a tweak (partial sizing on cluster days, staggered fills, or skip-the-cluster threshold).

## The test

1. Pull all walk-forward trade entries from the canonical clean-data run (`/tmp/wf_5y_8dates_*` artifacts or rerun WF if needed).
2. Group entries by their entry date; tag each as `cluster` (3+ entries that day) or `isolated` (1-2 entries that day).
3. Compute average forward returns for each cohort over multiple horizons: +5d, +14d (one rebalance window), +30d, +60d, exit-realized.
4. Also compute Sharpe-like ratio per cohort to capture both return and consistency.

## Decision rule

- **Within rounding (~1pp on the 14d horizon):** strategy is working as designed; close the question.
- **Cluster cohort lags isolated by 2-3+ pp on 14d:** worth testing partial sizing on cluster days (e.g. enter 5 of 6 candidates, hold a slot for 1-2 weeks for fresh isolated fires).
- **Cluster cohort lags by 5+ pp:** investigate staggered fills (enter cluster picks across 2-3 days) or a cluster-threshold gate that defers some entries.

## Connected

- Live May 2026 cluster (May 6 entries: IREN, RIOT, CIFR, GOOG, AMZN) provides real-money observation of one cluster cohort. Watch their 14d, 30d, 60d performance vs the May 1 isolated entries (GOOG, GOOGL).
- Per-regime sub-strategy decision (deferred Apr 28) — if cluster-day underperformance correlates with regime, may bring that conversation back.
