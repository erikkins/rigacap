---
name: session-progress
description: "Live session snapshot (auto-checkpointed ~15min) — what's done, in flight, and next"
metadata:
  node_type: memory
  type: project
  originSessionId: 2dce3134-d861-45c4-a371-80378750f8c0
---

# Session snapshot — Jul 8 2026 — LANDING 2-tier rebuild ~DONE (uncommitted); queue: commit → Track Record → Social engine

## ✅ 21YR WALK-FORWARD NUMBERS (scripts/tier_vintages_21y.py → tier_curves_21y.json; 2007-2026 daily, pre-2016 EXT survivorship-caveat):
- **Preserver: 8.6% / 0.88 Sharpe / −13.2% MaxDD** (≈ market return, ¼ the drawdown)
- **Maximizer: 14.5% / 0.95 / −20.4%** (BEATS S&P 9.8% AND raw-mom 13.2% on return, at ⅓ market's 55% DD)
- Benchmarks: S&P 9.8%/−55%, raw 12mo mom 13.2%/0.69/−57%. Recent-2yr (dial): Preserver 31%/−13%, Maximizer 49%/−17% ("last 2 years"). Curves → Track Record chart.
- Core=7.3% here (vs 8.3% prior canon — reconcile internally; Core stays OUT of ALL public copy per Erik).

## ✅ LANDING (LandingPageV2.jsx, uncommitted since 57abfe8, dev localhost:5173) — CORE NUMBERS FULLY SWAPPED → tier numbers:
- Hero knob (recent 31/49 dial, "last 2 years"), 2-tier Pricing (Opt A), Performance reworked ("Dial your return. Keep the discipline."), table = ROW PER PRODUCT (Preserver/Maximizer 21yr, no Core). Edge section engine+dial. FAQ: returns/Sharpe/flashier/down-year all on tier numbers (Sharpe FAQ flags pre-2016 survivorship caveat since 0.88/0.95 > Buffett 0.79). Advisory "13-20% not 55%". ALL tildes gone, "walk-forward tested" not "backtest", no Core by name/number.
- Erik micro-fixes done: "Long-horizon" capitalized, "better/more" italic, $229 removed, "unlimited real-time"→"every buy&sell call", widows fixed.

## ⭐ LOAD-BEARING RULES (Erik, Jul 8): NO "Core"/t30v or its numbers in public copy. "Walk-forward tested" not backtest. No tildes on numbers. Recent 31/49 = legit "last 2yr" claim; 21yr = honest anchor.

## 🔜 QUEUE (Erik to pick order): (1) COMMIT landing; (2) **Track Record page rebuild + ANIMATED CHART** (3 curves, knob-driven both-or-toggle, Preserver+Maximizer+S&P, NOT Core; data ready in tier_curves_21y.json); (3) **SOCIAL ENGINE revision** (ai_content_service.py — voice not vibing + doesn't know 2-tier/new numbers; needs product context + persona/voice overhaul); (4) Methodology page.
## ⚙️ Also live/pending: both tier SHADOWS recording daily (gate: no tier CHARGES until Maximizer signals live ~1wk); Stripe add-on built; hero "2× recovery" stat NEEDS VERIFY vs curve before deploy.
