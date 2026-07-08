---
name: session-progress
description: "Live session snapshot (auto-checkpointed ~15min) — what's done, in flight, and next"
metadata:
  node_type: memory
  type: project
  originSessionId: 2dce3134-d861-45c4-a371-80378750f8c0
---

# Session snapshot — Jul 8 2026 — LANDING 2-tier rebuild in progress; 21yr tier walk-forward RUNNING

## ✅ SHIPPED/LIVE (earlier): both tier SHADOWS live (record daily), dashboard sell-parity fix, Stripe add-on complete. Journey doc + sales playbook delivered. FE knob-hero committed (57abfe8).

## ✅ 21YR WALK-FORWARD DONE (`scripts/tier_vintages_21y.py` → `scripts/tier_curves_21y.json` has metrics + equity curves). NUMBERS (2007-2026 daily, pre-2016 EXT survivorship-caveat):
- **Preserver: 8.6% CAGR · 0.88 Sharpe · −13.2% MaxDD** (≈ market return at ¼ the drawdown)
- **Maximizer: 14.5% CAGR · 0.95 Sharpe · −20.4% MaxDD** (BEATS S&P 9.8% AND raw-mom 13.2% on return, at ⅓ the market's 55% DD — the headline)
- Benchmarks: S&P 9.8%/−55%; Raw 12mo momentum 13.2%/0.69/−57%. (Core=7.3%/0.76/−18.2% INTERNAL — note: differs from prior 8.3% canon, reconcile internally later; Core stays OUT of public copy.)
- Recent-2yr (dial): Preserver 31%/−13%, Maximizer 49%/−17% — legit walk-forward 2yr, keep as "last 2 years" headline. Curves → Track Record chart.

## ⭐ ERIK DIRECTIVES (Jul 8, load-bearing):
1. **NO public copy may show "Core" by name OR its numbers (8.3%/0.73/19%). t30v = INTERNAL only.** Customer sees ONLY Preserver/Maximizer numbers. Generic "engine/dial" language OK.
2. Everything = "walk-forward tested" not "backtest" (Core IS genuine WF; kept "overfit backtests" for others + legal disclaimer). Tiers labeled honestly.
3. No tildes on numbers (removed all). Confident numbers (31 not ~31).

## ⏭️ AFTER RUN LANDS: (a) swap ALL Core numbers on landing → tier 21yr numbers (Performance table "engine" row, FAQ 8.3/0.73/19 + "why $129", hero grid); (b) VERIFY the "2× recovery" hero stat vs curve; (c) then landing = ONE consistent basis, push-ready. Curves feed Track Record chart.

## ✅ DONE THIS SESSION on landing (LandingPageV2.jsx, uncommitted since 57abfe8, dev localhost:5173):
- Hero: knob + Preserve/Maximize, tier #s at dial ends (labeled "last 2 years"), removed raw 19% from grid (fixed triple-MDD confusion: 19 was Core-21yr, 13/17 were tier-2yr).
- Pricing → 2-tier Option A (Preserver buyable / +Maximizer waitlist "launching this month" / Advisory).
- Performance section reworked: headline "Dial your return. Keep the discipline." (killed "less return, less pain"); callout "why the drawdown is the whole game"; table row t30v REMOVED. Edge section: piece 1 → "regime-adaptive engine", piece 2 dial-aware. FAQ: added Preserver-vs-Maximizer (better/more italic), reconciled returns.

## 🔜 NEXT BIG: Track Record page rebuild w/ ANIMATED CHART (3 curves, same 21yr) → Methodology page. GATE: no tier CHARGES until Maximizer signals live (~1wk shadow). Push landing after Core-number swap.
