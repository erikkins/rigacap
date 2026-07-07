# Preserver Productionization — Shadow Wiring + Migration Design (FOR REVIEW)

*Phase 2 of the 2-tier product. The prod port is done and proven faithful (detectors =
signal-exact vs research; `preserver_portfolio.replay_sleeve` = penny-exact vs
`shapes_portfolio.simulate`). This doc specifies the **first steps that touch live infra**
— a new table, a DB migration, and a shadow hook in the daily scan — for sign-off before
anything is applied. Nothing here is live yet.*

## 0. Safety principles (from CLAUDE.md)
- **Never touch the t30v path.** Preserver is a *parallel* table + builder; the live
  `ensemble_signals` / dashboard / `process_entries` flow is untouched.
- **Migration-first.** Create the tables via migration SQL, verify columns exist, *then*
  deploy the SQLAlchemy models + wiring in a second commit. Never model+migration together.
- **Shadow before serve.** The daily-scan hook only *records*; nothing is served to any user
  until a shadow period validates the live equity lands in the research range.
- **Fully isolated hook.** The shadow step is wrapped so its failure can *never* abort or
  alter the live daily scan (try/except, logged, non-fatal).
- **Off-hours** for the migration; not during the 4 PM ET scan window.

## 1. The book-transition rule (design decision — RECOMMENDED: hold-to-exit + layer)
When the regime flips (e.g., rotating_bull → weak_bear), the active source changes
(t30v → oversold). What happens to held positions?

- **Option A — hard rotate:** liquidate the old book, buy the new. Clean, but churns the
  whole book on every regime flip → high turnover, transaction costs, tax events.
- **✅ Option B — hold-to-exit + layer (RECOMMENDED):** keep existing positions until their
  natural exit (per-sleeve `hold` / t30v's own exits); *new* entries come only from the
  current regime's book. The book rotates gradually as old positions expire and
  new-regime names enter.

**Why B:** realistic, low-turnover, tax-friendlier, and it *smoothly approximates* the
research routing — during a flip to capitulation you hold t30v names until they expire while
layering in the (rare) oversold names, ending mostly in the regime-appropriate book.

**Honest caveat (important):** the research validated the Preserver via **return-stream
routing** (three books run continuously; realize the active one's daily return). A *real
single-capital-pool* Preserver with hold-to-exit is a **new construction** — so its equity
will be *close to* but **not penny-identical** to the research allocator curve. The
penny-exact proof covers the *sleeve mechanics*; the full single-pool Preserver's job in
shadow is to land in the **validated range** (≈19% / 1.33 / −13.5% daily 2021–26), not to
match to the cent. If we ever want an exact-match construction, that's Option A + always-on
parallel books — heavier, and not recommended.

## 2. Storage schema (new tables — additive, migration-first)

**`preserver_signals`** — the daily routed BUY candidates (mirrors `ensemble_signals`
shape, plus source/regime):

| column | type | notes |
|---|---|---|
| id | PK | |
| signal_date | Date, idx | |
| symbol | String(10), idx | |
| price | Float | |
| source | String(20) | `t30v` / `pullback_ma` / `oversold_bounce` |
| regime | String(20) | the 7-regime label that day |
| dollar_volume | Float | selection key |
| hold_days | Int | sleeve hold (informational for the book) |
| status | String(20) default 'active', idx | active/invalidated |
| created_at | DateTime | |
| — unique `(signal_date, symbol)` | | |

**`preserver_book_snapshots`** — daily snapshot of the shadow held book + equity (lets us
track live Preserver equity vs the research range over the shadow period):

| column | type | notes |
|---|---|---|
| id | PK | |
| snapshot_date | Date, unique idx | |
| regime | String(20) | |
| active_source | String(20) | which book drove entries today |
| equity | Float | mark-to-market book value |
| positions_json | JSON | [{symbol, source, shares, entry_price, exit_date}] |
| created_at | DateTime | |

Migration = two `CREATE TABLE` statements (idempotent `IF NOT EXISTS`), runnable via the
existing `{"run_migration": true}` worker path.

## 3. Daily-scan wiring point (shadow, isolated)
In `backend/main.py` `_run_daily_scan`, **after** `compute_shared_dashboard_data` returns
(regime + t30v `buy_signals` + `scanner_service.data_cache` all ready), add an isolated block:

```python
# --- SHADOW: Preserver tier (additive, NOT served; must never break the live scan) ---
try:
    regime = data['regime_forecast']['current_regime']
    preserver_service.run_shadow_day(
        db, today_et, regime,
        t30v_signals=data['buy_signals'],
        data_cache=scanner_service.data_cache,
    )
except Exception as e:
    logger.warning(f"[PRESERVER-SHADOW] non-fatal: {e}")  # never re-raise
```

`run_shadow_day` (new `preserver_service.py`): `route(regime)` → build today's entry
candidates (`build_daily_signals`) → advance the held book one day (exits by hold + fill
free slots from candidates under rule B) → persist `preserver_signals` + a
`preserver_book_snapshots` row. Reuses the already-validated `preserver_sleeves` /
`preserver_portfolio` logic; the t30v book source in rotating regimes reuses the live
`buy_signals` / existing model-portfolio positions (no recompute).

## 4. Rollout sequence
1. **Migration** (off-hours): create the two tables via `run_migration`; verify columns.
2. **Deploy models + `preserver_service` + the isolated hook** (shadow only).
3. **Shadow period (~2–4 weeks):** daily snapshots accumulate; confirm the live Preserver
   equity/return/DD tracks the research range (≈19% / 1.33 / −13.5% recent). Spot-check that
   rotating-bull days == t30v book, and sleeve days enter the expected names.
4. Only then: tier field on users (migration-first) → tier-aware serving → public 2-tier launch.

## 5. Open items / risks
- **Book-transition = Option B** pending your ✅.
- t30v-book-in-rotating: cleanest is to *reference the live t30v model-portfolio positions*
  rather than re-simulate — confirm we can read them read-only in the shadow.
- Shadow equity won't penny-match research (single-pool vs return-stream) — success = lands
  in the validated *range*, not exact.
- Regime label source: use the same `data['regime_forecast']['current_regime']` the live
  scan already computes (hysteresis-stable), so shadow and any future serve agree.
