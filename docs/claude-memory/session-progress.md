---
name: session-progress
description: "Live session snapshot (auto-checkpointed ~15min) — what's done, in flight, and next"
metadata:
  node_type: memory
  type: project
  originSessionId: 2dce3134-d861-45c4-a371-80378750f8c0
---

# Session snapshot — Jul 8 2026 — Multi-page Core-purge + Track Record chart. Landing done; TrackRecord ~90%; ForAdvisers/Methodology/Social queued.

## ✅ 21YR NUMBERS (scripts/tier_curves_21y.json; DAILY, live t30v config pwf.run trail .30/max_pos 20/size .045): RigaCap Preserver 8.6%/0.88/−13.2% · Maximizer 14.5%/0.95/−20.4% (BEATS S&P 9.8% & raw-mom 13.2%, at ⅓ mkt's 55%DD). $100k→Preserver $500k, Maximizer $1.39M, SPY $763k. 2008 both +0.1% vs SPY −36%. Recovery: Preserver 2.0yr vs SPY 4.85 = 2.4× (Maximizer only 1.44×→stat is Preserver-specific).

## ⚠️ OPEN DECISION (asked Erik, UNANSWERED) — RECENT-24mo numbers don't reconcile. Landing dial = **31%/49%** (old tier_vintages.py: BIWEEKLY + real_ensemble_equity). New 21yr-daily last-24mo = **Preserver 26.5%/Sh2.15/−9.2%, Maximizer 58.2%/Sh2.11/−12.5%** (uses LIVE config → more faithful + consistent). MY REC: switch dial+recent-table to 26.5/58.2 (Preserver lower but honest, Maximizer stronger). Dial DDs −13/−17 → −9/−13 too. Awaiting Erik's OK to swap.

## ✅ LANDING (LandingPageV2.jsx) DONE: all Core gone, table rows "RigaCap Preserver/Maximizer" (TM: house-mark+descriptor in tables), hero grid 21yr/2×/14.5%, "drawdown is whole game" callout fixed (Maximizer OUT-earns raw mom), Ensemble refs→"engine behind both tiers"/"Regime-adaptive", CIO line→one-line full-width trim (dropped $59 parenthetical). Zero tildes.

## 🔨 TRACK RECORD (TrackRecordPageV2.jsx @ /track-record) ~90% de-Cored:
- NEW **TierRaceChart.jsx** built+wired (replaced PortfolioRace): log-scale $100k curves Preserver/Maximizer/S&P, draws L→R on scroll, Preserve/Both/Maximize dial toggle, hover-scrub. **Animation bug FIXED** (StrictMode was cancelling rAF; now starts-if-visible + mountedRef-safe). Data /public/track-record-curves.json (978wk pts + annual).
- ✅ swapped: headline grid, 21yr table, Sharpe callout, per-regime rows (both tiers, real per-yr incl honest 2019 lag), highlights, bear callout. ⏳ ONLY recent-24mo RECENT_ROWS table + its intro (ln24-26,153) left = BLOCKED on the decision above.

## 🔜 QUEUE: ForAdvisers page (ALL Core data — Erik flagged) → Methodology page → SOCIAL ENGINE (ai_content_service.py voice+new numbers). Erik proofreading landing live, feeding fixes.
## ⭐ RULES: no Core/t30v public; walk-forward not backtest; no tildes on numbers; claret+paper. GATE: no tier CHARGES until Maximizer signals live. Commit only when asked. vite dev :5173 alive.
