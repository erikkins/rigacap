---
name: session-progress
description: "Live session snapshot (auto-checkpointed ~15min) — what's done, in flight, and next"
metadata:
  node_type: memory
  type: project
  originSessionId: 2dce3134-d861-45c4-a371-80378750f8c0
---

# Session snapshot — Jul 8 2026 — Landing DONE + TrackRecord DONE (page+chart). Next: ForAdvisers → Methodology → Social.

## ✅ CANONICAL NUMBERS (one basis): 21yr (tier_curves_21y.json, DAILY, live t30v pwf.run trail.30/pos20/size.045): **Preserver 8.6%/0.88/−13.2%** · **Maximizer 14.5%/0.95/−20.4%** vs S&P 9.8%/−55%, raw-mom 13.2%/0.69/−57%. $100k→Pres $500k, Max $1.39M, **SPY price-only $535k** (was $763k w/ dividends=BUG, fixed).
## ✅ RECENT 2yr (tier_vintages_daily.py = AUTHORITATIVE clean-window source): **Preserver 31.3%/Sh1.75/Cal2.43/−12.9%** · **Maximizer 48.9%/Sh1.94/Cal2.83/−17.3%** · SPY +19.9%. → rounds to the 31/49 ALREADY on landing dial = CORRECT, do NOT change (I briefly mis-recommended 26.5/58.2 from a bad EXT-curve slice; RETRACTED). Recovery: Preserver 2.0yr vs SPY 4.85 = 2.4× (Max 1.44× → stat is Preserver-specific).

## ✅ LANDING (LandingPageV2.jsx) DONE: all Core gone; tables "RigaCap Preserver/Maximizer" (TM); hero grid 21yr/2×/14.5%; callout Maximizer OUT-earns raw-mom; Ensemble→"engine behind both tiers"/"Regime-adaptive"; CIO line one-line trim; zero tildes.

## ✅ TRACK RECORD (TrackRecordPageV2.jsx @ /track-record) DONE — fully de-Cored: headline grid ($1.39M/$500k/+0.1% 2008/21yr), 21yr table + recent-24mo table (tier numbers), Sharpe callout, per-regime (both tiers, honest 2019 lag), highlights, bear callout.
## ✅ **TierRaceChart.jsx** built+wired (replaced PortfolioRace): log-scale $100k Preserver/Max/S&P, draws L→R (animation bug FIXED — StrictMode mountedRef never reset; +visible-start +1.2s fallback). Features: **hide-not-dim** toggle (Preserve/Both/Maximize), **19 dashed defensive periods** + shaded bands (from regime_series), **animated flags** (2008/COVID/2022), hover-scrub. Data /public/track-record-curves.json (has defensive[] + events[]). Erik testing.
## KEY FRAMING: Preserver ≈ S&P on 21yr growth ($500k≈$535k) but SMOOTHER (¼ drawdown, 2× recovery); Maximizer beats market. That's the true 2-tier story — honest + good optics now that SPY is price-only.

## 🔜 QUEUE: ForAdvisers page (ALL Core — Erik flagged) → Methodology page → SOCIAL ENGINE (ai_content_service.py voice+new numbers). ⭐RULES: no Core/t30v public; walk-forward not backtest; no tildes on numbers; claret+paper. GATE: no tier CHARGES until Maximizer signals live. Commit only when asked. vite :5173 alive.
