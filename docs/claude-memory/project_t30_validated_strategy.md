---
name: t30-validated-strategy-jun5-2026
description: "LOCKED Jun 5 2026: the first honestly-validated strategy. 20x4.5% positions, ensemble entry, trail 30%, top-100 survivorship-free. Tier-2 held-out: 13.3% ann / 0.80 Sharpe / 14% MDD / no losing 2yr window / recent-2y +22.4%. Replaces ALL prior (mirage) numbers."
metadata:
  node_type: memory
  type: project
  originSessionId: daad830f-fb74-43b7-b3d5-fc34eed698de
---

**LOCKED Jun 5 2026.** First strategy validated on clean, survivorship-free, split-correct, per-period-WF data with out-of-sample (Tier-2) confirmation. This is the new base; everything before it was measured on corrupted data.

## The config (t30)
- **20 positions × 4.5%** each (≈90% invested) — diversified, NOT the old 6×15%.
- **Ensemble entry** unchanged: DWAP > 1.05×, within 3% of 50-day high, uptrend (>MA20/MA50), vol≥500k, px≥$15. (near-3% confirmed optimal; loosening it only hurts.)
- **Trail 30%** (wide — let winners run; the edge lives in the right tail).
- No profit-lock (it binds and HURTS — caps the right tail).
- Biweekly rebalance, carry positions, top-100 survivorship-free universe (60d-avg-vol + min-price, per-period re-rank).
- Runner: `scripts/pitfwu_wf_periods.py` (reuses prod run_walk_forward_simulation, strategy_id=6/T3 base + overrides).

## Validated numbers (Tier-2 held-out, 10 off-grid start dates, 2y windows)
- **ann mean 13.3% / Sharpe 0.80 / std 5.4pp / MDD 14% (worst 20.9%) / EVERY window positive (+6.3% to +22.4%).**
- **Recent-2y (2024-06→2026): +22.4% / 1.34 Sharpe / 12.3% MDD — clears the North Star in the bull.**
- Costs negligible: 65-103 trades/yr, 0.3-0.9pp drag at 10-20bps (liquid top-100 names).
- t25's 13.6% was OVERFIT — collapsed to 11.4% held-out (non-monotonic trail sweep + std anomaly were the tell). t30 firmed up out-of-sample.

## MULTI-REGIME validated (Jun 5, longhist 2017-2026, 16 windows, 3 downturns)
- **ann 13.1% / Sharpe 0.81 / MDD mean 12.3% (worst 24.1%) / Calmar 1.07 / 94% positive / floor -2.2%.** MATCHES the held-out 13.3%/0.80 → robust across a decade, not a 2022 fluke.
- **COVID handled, not survived:** the window with the full -34% crash (2018-07→2020-07) = 12.6% MDD / +5% ann; windows starting into COVID = +21-29% / Sharpe 1.2-1.8. Diversification + 200MA filter + V-recovery did it. NO fast-crash circuit-breaker needed.
- Clears North Star on RISK (MDD≤20 mean, Calmar≥1); short on return (13 vs 20) + Sharpe (0.81 vs 1.0). Regime-dependence is in the RETURN FLOOR (chop windows +3-9%, trend windows +20-28%), NOT crashes — so regime work targets chop-return (subtle, overfit-prone), not crash defense. N=1-bear problem largely gone (3 downturns now).

## How we got here (the arc)
1. Entry has a REAL but THIN edge (median +0.5-2%/60d, hit-rate 52-58% vs ~50%, high N) — NOT noise. But it caps upside (avoids the lottery tail; that tail isn't reachable by entry tuning — near-high sweep refuted).
2. **Concentration was the disease.** Broad equal-weight captures the qualifier MEAN (~15-23% raw); 6×15% realized only 2.4%. Going 6→20 positions: 2.4%→9.7%, Sharpe 0.30→0.69, worst MDD 31%→20%, erased losing windows. Diversification is the single biggest lever proven.
3. Wide trail adds the rest (lets winners run). Trail is NOT a precision lever (noisy 18-40%); 30% is robust.

## What this KILLS (all mirages — do not cite)
- 50% / 33.6% / 19.3% "M3" numbers; Trial 37 "+240%"; the "26% split-adjusted" heuristic number; every pre-Jun-5 backtest figure. All measured on split-corrupted and/or survivorship-biased and/or single-window-cherry-picked data. See [[critical-backtest-pickle-is-not-split-adjusted-jun-4-2026]].

## Honest marketing frame
NOT "20% annualized." Something like "double-digit through the cycle, market-beating risk-adjusted, no losing 2-year window in clean backtest; stronger in trending markets." True + defensible under the publisher's exemption.

## Levers tested (Jun 8)
- **CONVICTION SIZING — WINNER → "t30c" (validated Jun 8).** Tilt position size by momentum rank at entry (rank1 bigger, last slot smaller; exposure-neutral; `conviction_tilt` in backtester, _conviction_mult). tilt 0.5 multi-regime longhist (2017-2026, 16 windows): **15.6% ann / 0.88 Sharpe / 12.8% mean MDD / 27.8% worst / 94% positive** vs t30 baseline 13.1/0.81/12.3/24.1. = +2.5pp return +0.07 Sharpe, cost = +3.7pp deeper WORST-case DD (concentration deepens ordinary pullbacks, NOT crashes — COVID windows amplified to +31-32%). Tier-2 held-out CONFIRMED (improved OOS: tilt0.3=16.8/0.95/Calmar1.27, tilt0.5=15.6/0.91/worst18.1). Peaks 0.3-0.5, REVERSES at 1.0 (over-concentration). tilt 0.8 worst-MDD 31% (in-sample) = the one to AVOID. **t30c = t30 + conviction tilt 0.5 (or 0.3 for more return, MDD-tail tradeoff).**
- **DISPLACEMENT — DEAD/exhausted (parked).** Bump weakest incumbent for strong fresh signal (PLTR-lockout fix). Tested margin / bull-bear gate (redundant) / trend gate / SAME-SECTOR. Same-sector CONFIRMED the whipsaw mechanism (sector-chasing churn: global 5.8%→samesec 11.6% net) — but best variant still loses risk-adjusted (Sharpe 0.68<0.72, worst-DD 27>24) and is DOMINATED by conviction. "Let winners run, don't churn" held under every angle. Code default-off. cadence/cooldown untested but same churn-reducer class → expected to converge to baseline.
- NEXT lever: universe breadth (top-100 vs 150/200). Then productionize t30c.

## Next (Erik's call Jun 5)
- **Build longer history FIRST, then regimes.** Regime-switching on N=1 bear (2022) is the boss-level overfit; needs multiple cycles. Existing PITFWU bars reach ~2016 → 2018-Q4 + 2020-COVID windows are FREE (just run earlier start dates). Pre-2016 (2008/2011) needs yfinance (Alpaca SIP stops ~2016). [[t30-validated-strategy-jun5-2026]]
- Open: total-return vs price-return (~0.5%/yr for div payers); universe breadth (top-100 vs 150).
