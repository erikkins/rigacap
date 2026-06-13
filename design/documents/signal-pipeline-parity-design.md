# Signal Pipeline Parity — Design Doc
*Draft, Jun 13 2026. NOT deployed. Goal: prod live book = t30v validated bench, exactly. One scan/day, one canonical signal set, every consumer reads it.*

## The problem (two distinct bugs, both confirmed Jun 13)

### Bug 1 — Cache degradation between two scans
The daily scan runs TWO evaluations:
1. `scanner_service.scan()` early in the pipeline → finds raw DWAP signals (Thu 60, Fri 64), stored to DB.
2. `compute_shared_dashboard_data()` ~5 min later → runs its OWN `scan()` + `rank_stocks_momentum()` to build `buy_signals`.

Between them, the **pickle-export step strips indicator columns** (`dwap`, `ma_50`, …) from the in-memory `data_cache` to shrink the export (known prior behavior). So scan #2 runs on degraded data and produces **0 buy_signals**.

**Evidence:** Fri Jun 12 prod wrote `buy_signals: 0`. A clean cold-reload rebuild of the SAME pickle (`export_dashboard_cache`) produced **24**. Thu Jun 11 snapshot also `0` on a Nasdaq +3.4% day. Wed Jun 10 was legitimately low (SPY −4.2%, only 5 raw signals) — not this bug.

### Bug 2 — Parity break: missing the near-high quality filter
Even when the dashboard DOES produce signals, its entry set ≠ the bench's:

| | Filter | Ranking | Jun 12 result |
|---|---|---|---|
| **t30v BENCH** | 5% DWAP **AND `passes_quality`** (price>MA20,MA50 AND **within 3% of 50-day high**) | momentum **composite** | **3 names**: WULF, BAC, VZ |
| **LIVE (dashboard→process_entries)** | 5% DWAP AND **top-30 momentum membership** (no near-high) | **`ensemble_score`** (Formula-B signal-strength, r=0.083) | **20 names**: MRVL, INTC, ARM, KLAC… |

Agreement: **2 of 20.** The live path drops Factor 3 (near-high "confirmation") and ranks by a display heuristic, not momentum. The top-30-momentum proxy ≈ near-high on trending days but **diverges hard when momentum leaders pull back** (exactly Jun 12, post-slide) — it buys the dip where t30v waits for confirmation.

**Erik's corroboration:** a long-held sense that the system surfaced too many buys. 3 (not 25) on a choppy day is what a selective momentum algo should do. The fix aligns behavior with the stated product.

## Target architecture

**One canonical evaluation per day → one persisted signal set → all consumers read it.**

```
DAILY SCAN (worker, 4:30 PM ET)
  1. fetch/settle data (unchanged)
  2. compute_canonical_signals()   <-- THE single evaluation, on CLEAN cache
        -> persist to: dashboard.json (S3) + ensemble_signals (DB, audit) + snapshot
  3. process_entries()  reads dashboard.json  (NO re-scan)
  4. pickle export       (strips a COPY, never the in-memory cache used above)
  5. emails / frontend   read dashboard.json
```

### The canonical entry set (must equal t30v backtester ensemble entry, verbatim)
For each symbol in the **top-100-by-volume universe** (`SIGNAL_UNIVERSE_SIZE=100`):
1. `pct_above_dwap >= 5%` (DWAP_THRESHOLD_PCT)
2. `volume >= MIN_VOLUME` (500k), `price >= MIN_PRICE` ($15)
3. `_is_data_quality_ok(df)`
4. **`passes_quality`** = `price > MA20 AND price > MA50 AND dist_from_50d_high >= -3%`  ← the missing filter
Then: **rank by momentum composite** (`short_mom*0.3 + long_mom*0.2 - vol*0.15`), descending; take **top `max_positions` (20)** that fit capital; size by inverse-vol (vol_weight=1.0).

`ensemble_score` and `is_fresh` are retained as **display badges only** — never selection keys.

## Consumer changes
- **`compute_shared_dashboard_data`**: add the `passes_quality` gate to `buy_signals`; rank `buy_signals` by momentum composite (not `ensemble_score`). (Watchlist = approaching-DWAP unchanged.) This makes the dashboard the single source.
- **`process_entries`** (already dropped `is_fresh` Jun 12): keep reading `dashboard.json`; sort candidates by momentum composite to match bench; no quality re-check needed (dashboard already gated). Confirm it does NOT re-scan.
- **Daily-scan pipeline ordering**: run `compute_canonical_signals` BEFORE the pickle-export strip — OR make the strip operate on a copy so the live cache keeps its indicators. (Bug-1 fix.)
- **Email digest**: already reads dashboard cache (Jun 12). No change beyond inheriting the corrected set.
- **Frontend**: reads dashboard.json. The buy-card list shrinks (feature, not regression).

## Risks & validation (MUST pass before deploy)
1. **Backtester replay parity test**: for N historical dates, assert `compute_canonical_signals(date)` == t30v backtester's entry set for that date (same names, same order). This is the acceptance gate — automate it.
2. **Universe parity**: confirm prod's `get_top_liquid_symbols(100)` == the research bench's top-100 construction (same liquidity measure, same as-of logic). Open question — verify.
3. **Cache-ordering fix**: after reordering, re-run a full scan locally and confirm signals != 0 on an up day.
4. **Smoke**: rebuild Fri Jun 12 → expect **3 names** (WULF, BAC, VZ), not 0, not 24.
5. **No-look-ahead**: the canonical scan uses only as-of-close data (it already does).

## Rollout sequence
1. **HOLD entries** — book stays flat (entry path paused / undeployed) until this lands & is reviewed. Do NOT let Mon 4:30 deploy capital on the current (non-parity) logic.
2. Build `compute_canonical_signals` + the passes_quality/ranking changes; wire one-scan ordering.
3. Run the backtester-replay parity test (acceptance gate) + smoke.
4. Erik review of the diff + a sample day's output.
5. Deploy off-hours; verify next scan produces a bench-matching set.
6. Backfill note: the live record's Jun 11–12 entries are void (book was flat anyway); the true record effectively starts at first parity-correct scan.

## Open questions for Erik
- Universe parity (research bench vs prod top-100) — verify before trusting the replay test.
- Live-record start date: do we date it from the first parity-correct scan, and say so publicly? (Honesty: the Jun 11 "Day 1" was a bugged zero.)
- Marketing: the "0 buys = discipline" posts/threads — anything to correct? (Likely nothing public claimed specific positions; verify.)
