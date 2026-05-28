---
name: Strategy 6 provenance — Apr 28 Canonical → T3 rename
description: Historical context for DB row 6 before May 28 2026 rename. Captures Apr 28 baseline numbers and the 11y-pickle 8-date sweep reference.
type: project
originSessionId: c3d0833d-cb3f-474f-8dd8-e530f3300c60
---
DB row 6 (`strategy_definitions.id=6`) was originally added May 21 2026 as the **"DWAP+Momentum Ensemble (Apr 28 Canonical)"** reference row. On May 28 2026 it was repurposed as the **T3** production strategy (`DWAP+Momentum Ensemble — T3`).

**Old description (overwritten May 28 2026):**
> Canonical Apr 28 2026 baseline params, post-clean-data validation. Reproduces +160% / 0.92 / 20.4% on 11y pickle 8-date sweep. Reference row — is_active=false to avoid duplicate-active in production.

**Why:** The "is_active=false" claim was already stale by the time of rename (row had been flipped to True). The "+160% / 0.92 / 20.4% on 11y pickle 8-date sweep" line is useful provenance — it documents the Apr 28 published-canonical numbers that the marketing site referenced before the T3 update.

**How to apply:** If anyone digs into row 6's history (params drift, marketing-numbers archaeology), the Apr 28 canonical baseline was: 5y total +160%, Sharpe 0.92, MaxDD 20.4%, 11y pickle, 8-date sweep. T3 (May 28 2026) supersedes those numbers with 52-Monday-sweep, prod-pickle values: Sharpe 1.00, ann 23.4%, MaxDD 26.4%, Calmar 0.81.

Backup of full pre-rename row state: `/tmp/strategy6_backup_pre_t3_rename.json` (local-only; not committed).
