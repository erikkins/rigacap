---
name: Run5 over-fit drift — production-WF parity audit cadence
description: For 4 weeks (Apr 19 → May 18 2026), production ran Run5 over-fit params while marketing claimed Apr 28 baseline. Drift uncovered May 18. Lesson: every commit that touches strategy params must trigger a parity audit.
type: project
originSessionId: c3d0833d-cb3f-474f-8dd8-e530f3300c60
---
## The drift

- **Apr 19 2026** (commit `6231186`): "Deploy Run5-optimized strategy params to production." Changed `config.py` to 14% trailing stop / 7% near-50d-high / 4 max positions / 20% size / 5.5% DWAP. Claimed +297.8% / 1.10 Sharpe / 29.97% MaxDD.
- **Apr 28 2026**: Generated marketing baseline via `scripts/launch-5y-8dates.sh` → +160.22% / 21.5% ann / 0.92 Sharpe / 20.4% MaxDD across 8 start dates. Used `local_wf_runner.py` CLI defaults (12% / 3% / 6 / 15% / 5.0%), DIFFERENT from config.py.
- **Apr 29 2026** (commit `9ac87f1`): "Refresh performance citations to clean-data walk-forward (2026-04-28 vintage)." All subscriber-facing marketing copy updated to +160% numbers. Commit explicitly says: *"Replaces the over-fit Trial 37 / Apr 19 Run5 numbers."*
- **Production code (config.py): NEVER ROLLED BACK.** Ran Run5 over-fit values for 4 weeks while marketing claimed a different, more conservative strategy.
- **May 18 2026** (commit `0055177`): Drift uncovered. Config rolled back to Apr 28 baseline.

## Concrete cost observed

IREN entered May 6 at $60.98. Under Run5+regime params (rotating_bull → 14% stop on $61.20 HWM = $52.63), held through May 15 close of $52.94 (+$0.31 margin above stop). Under canonical 12% fixed stop, stop = $53.86, May 15 close FIRES at $52.94. Under canonical rules IREN exits May 15 at -13.2%; under Run5 rules it stayed in, kept dropping, and actually exited May 18 at -17.3%. **Confirmed drift cost on this single position: 4.1 percentage points (May 18 measurement).**

Plus the slot was occupied for an extra 3 trading days that, under canonical rules, would have been freed for whatever fresh signal qualified next. We CANNOT cleanly reconstruct what would have filled it (would require replaying canonical-rule scans across May 15-18).

## Lesson

Any commit that touches strategy params — `config.py`, `market_regime.py`, `model_portfolio_service.py` constants, strategy DB seeds — must trigger a parity audit:

1. **What numbers does marketing claim?** (`docs/numbers-citations-registry.md`)
2. **Which WF run those came from?** (commit/script reference)
3. **Do production params bit-for-bit match that run?**
4. **If not, either rollback the code OR re-validate WF and update marketing claims.**

The mistake here was a one-way update: marketing got refreshed, code didn't get rolled back. **Both must move together, or one becomes a lie.**

## Process change

- **Weekly parity audit**: every Friday, walk through canonical_numbers.json → registry → config.py → confirm match. Catch drift early.
- **Pre-commit gate on params**: any PR touching `config.py:Trading strategy` or `market_regime.py:_REGIME_PARAMS` should require a verification-WF Lambda invoke before merge.
- **Track Record sim IDs are part of this audit**: confirmed May 18 that sims 922-930 (currently powering the public Track Record page) are STALE — inflated numbers vs the canonical Apr 28 baseline. Need to regenerate 8 sims under canonical params and update `TRACK_RECORD_SIM_IDS`.

## Connected

- `feedback_wf_prod_parity.md` — the original parity rule the drift violated
- `docs/numbers-citations-registry.md` — single-source-of-truth for marketing numbers
- `scripts/launch-5y-8dates.sh` — the canonical 8-date launcher
- `scripts/local_wf_runner.py` — the underlying runner whose CLI defaults define canonical params
- Commits: `6231186` (Run5 deploy), `9ac87f1` (marketing refresh), `0055177` (May 18 rollback)
