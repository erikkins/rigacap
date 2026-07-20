---
name: project-sector-cap-regression-jul20
description: Live Core book down 7% from sector-concentration; sector cap validated May-24 but OFF for marketing-baseline parity; resolution = cap as Preserver overlay
metadata: 
  node_type: memory
  type: project
  originSessionId: 264056a8-f1e5-489c-9140-1fb57bda9825
---

# Sector cap: the live −7% cause, why it's OFF, and the fix path (Jul 20 2026)

## The problem
Live Core (t30v) model portfolio Jun15→Jul17: **$100k→$92,785 = −7.2% vs SPY −1.5%** (down 7% in a ~flat market), now 51% cash. All 9 closed trades = trailing_stop, −21% to −30% FROM ENTRY (P&L correct, NOT a bug). Day-1 book (Jun 15) held **7 "Technology" names** (MU/INTC/MRVL/SNDK/TSM/CIFR/CORZ) + 2 crypto-miner "Financial Services" (WULF/RIOT) + NBIS — one correlated theme that then corrected together. Wide 30% trail amplified the giveback.

## Root cause = sector concentration; the lever exists and WAS validated
- `MOMENTUM_SECTOR_CAP=0` (config.py:107) → `cap≤0 = DISABLED`, no per-sector limit → ranker piled into the hottest theme.
- **This lever was VALIDATED + SHIPPED May 24 2026** (see [[project_sector_cap_breakthrough]]... i.e. docs/claude-memory/project_sector_cap_breakthrough.md): cap=6 over 52 weekly starts → median Sharpe 0.83→1.16, MaxDD 33.5%→15.5%, Calmar 0.65→1.34. The breakthrough doc's diagnosis is verbatim what happened live ("60%+ of buy_signals in 1-2 sectors; when tech rolled over, portfolio took the full hit").

## WHY it's off (Erik's hunch was RIGHT — not an accidental regression)
config.py:97-113 is pinned to **"Apr 28 marketing-baseline parity"** (commit 0055177, May 18). Cap comment: `# NOT REVERTED — same uncertainty as scoring weights`. The **publicly-marketed t30v 20-yr track record was produced WITHOUT a sector cap**, and they weren't certain which exact config reproduced it → restored the conservative baseline (cap=0) and left the cap off "until a verification WF run confirms reproduction." Turning cap ON for Core → live book stops matching the marketed numbers → full marketing re-baseline. (config.py defaults MAX_POS=6/trail=12 are vestigial for live t30v, which overrides via strategy_adaptive_params t30v_cutover row; but sector cap is read from settings.MOMENTUM_SECTOR_CAP by the scanner → live = 0.)

## VALIDATION RESULT (Jul 20) — ❌ CAP DOES NOT HELP t30v; leave OFF. Erik's "cap as Preserver overlay" idea = DON'T (data says no).
scripts/sector_cap_t30v_sweep.py → pwf.run (scripts/pitfwu_wf.py, added `sector_cap` param) at t30v config (trail=0.30/max_pos=20/size=0.045), caps {0,3,6,8}, 2021-01-04→2026-05-29, survivorship-free PITFWU panel. Cap method = walk_forward_service list-order per-sector filter (the validated May-24 method). Needs /tmp/sectors_cache.json (from s3://rigacap-prod-price-data-149218244179/universe/sectors_cache.json).

| cap | ann% | Sharpe | MaxDD% | Calmar | total% |
|---|---|---|---|---|---|
| **0 (live)** | **17.49** | **1.10** | **23.62** | **0.74** | **138.6** |
| 3 | 13.14 | 0.89 | 26.63 | 0.49 | 94.7 |
| 6 | 14.42 | 0.95 | 27.64 | 0.52 | 106.8 |
| 8 | 14.99 | 0.98 | 26.52 | 0.57 | 112.5 |

cap=0 wins on EVERY metric incl drawdown (capping RAISED MaxDD). OPPOSITE of the old-strategy breakthrough: t30v runs 20 pos + wide 30% trail → already diversified; capping just evicts the high-momentum leaders that drive return, no DD benefit. So the config "same uncertainty" caution was correct.

## FOLLOW-UP (Jul 20) — PER-REBALANCE ENTRY THROTTLES (Erik's "daily sector cap" idea, distinct from static cap)
Built additive backtester attrs (backtester.py, disabled-by-default 0): `max_sector_entries_per_rebalance` (cap same-sector NEW entries/rebalance) + `max_entries_per_rebalance` (entry pacing). Wired via pitfwu_wf.run(max_sector_entries=, max_entries_per_rebalance=) + bt.symbol_sectors from /tmp/sectors_cache.json. Driver: scripts/entry_throttle_multistart.py (10 quarterly starts 2021-24, 3y windows — surfaces cold-start-into-rotation that aggregates hide).

Distribution (10 starts, 3y): baseline ann med 5.55/min 2.35, sharpe 0.41, mdd med 22.9/max 35.2. sec-entry=2 & =3 WORSE on everything (reject — benches momentum leaders). **sec2+pace8: worst-case mdd 35.2→32.1 (~9% better), worst-case ann 2.35→2.45, median ann 5.55→5.06, sharpe 0.41→0.38** = modest DEFENSIVE tilt (give a little median for better tails) → fits PRESERVER mandate, NOT Core. KEY: PACING is the helpful ingredient, sector-cap the harmful one. NEXT (offered): test PACING-ALONE {6,8,10} (combo suggests it may be cleaner win w/o the cap's drag). Caveat: 3y windows are 2022-bear-heavy (low absolute returns).

## ⭐ PACING-ONLY = THE CLEAN LEVER (Jul 20). pace=8 PARETO-BEATS baseline on ALL 6 metrics.
Distribution (10 starts, 3y windows): baseline ann med 5.55/min 2.35, sharpe 0.41/0.22, mdd med 22.86/max 35.23.
**pace=8: ann med 6.03/min 2.87, sharpe 0.43/0.25, mdd med 22.38/max 33.91 — better on EVERY metric (median+worst-case return, median+min Sharpe, median+max MaxDD).** pace=6 too aggressive (one worst-case start hurt), pace=10 barely binds. Why: all-in-one-day sets whole book's cost basis on one day (often a momentum local-top); pacing DCAs entries over ~3 rebalances → less single-day timing risk + adapts to rotation. DIRECTLY fixes the live −7% (would've bought ~8 not 20 on Jun 15). Config = max_entries_per_rebalance=8, sector cap OFF (sector cap always hurts).
Caveats: 10 starts / 2022-heavy 3y windows (confirm on wider + bull window); pitfwu/ensemble proxy path — productionizing needs pacing wired into LIVE entry path (currently backtester-only, default-off). RECO: include pace=8 in PRESERVER (own numbers, no parity issue); Core would improve too but re-opens marketing-baseline-parity (marketed t30v had no pacing → re-baseline). Offered wider confirmation sweep before locking.

## CONCLUSIONS
- **Don't add sector cap** (Core: breaks marketing parity for zero gain; Preserver: same engine → hurts there too).
- **Live −7% is NOT fixable via cap** — it's t30v's normal concentrated-momentum drawdown (5-week single-theme correction). Full-5y same concentration = 17.5%/yr; leaders carry it. "Premium paid in drawdowns" already owns this.
- **Real concentration defense = Preserver's SLEEVES (defensive regime routing), not a blunt cap.**
- Caveats: single 5y (momentum-favorable) window; breakthrough used 52 starts; this caps by dollar-vol order vs live scanner's momentum-rank cap. Direction strong+consistent across 3/6/8. Offered Erik a 52-start confirmation sweep before fully closing.
