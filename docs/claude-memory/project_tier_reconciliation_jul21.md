---
name: project-tier-reconciliation-jul21
description: "CRITICAL — production tier books (rule B single-pool) do NOT reproduce the marketed research tier edges; Preserver loses its DD protection, Maximizer loses its return edge"
metadata: 
  node_type: memory
  type: project
  originSessionId: 264056a8-f1e5-489c-9140-1fb57bda9825
---

# Tier reconciliation: MARKETED (research) vs SERVED (production port) — Jul 21 2026

## The finding (regime-routed, using regime_series; scripts/tier_compare_production.py vs tier_vintages_daily.py)
Research = return-stream allocator (instant costless regime switching, always-warm sleeves) = the MARKETED numbers. Production = real PreserverBook/MaximizerBook (single capital pool, rule-B hold-to-exit, costs, warm-started) = what would actually be SERVED.

| | Research (marketed) | Production (served) |
|---|---|---|
| **LAST 2YR** Core | 35.7/1.87/−14.7 | 37.5/2.08/−12.0 |
| Preserver | 31.3/1.75/−12.9 | 38.8/2.08/−12.3 |
| Maximizer | 48.9/1.94/−17.3 | 34.4/1.59/−20.1 |
| **2021-26** Core | 17.5/1.10/−23.7 | 14.3/0.96/−23.1 |
| Preserver | 19.4/1.33/**−13.5** | 14.3/0.97/**−22.5** |
| Maximizer | **36.2**/1.61/−19.9 | **11.7**/0.79/−21.3 |

## What it means
- **Core reconciles** (framework sound).
- **Preserver LOSES its preservation edge**: marketed −13.5% MaxDD → production −22.5% ≈ Core (−23.1%). "Half the drawdown" NOT deliverable as ported. In production Preserver ≈ Core (answers Erik's "where does Preserver preserve?" — it doesn't).
- **Maximizer LOSES its return edge**: marketed 36.2%/yr → production 11.7%, BELOW Core; Sharpe 1.61→0.79. "Aggressive outperformance" = construction artifact.
- Recent-2yr Preserver production (38.8%) BEAT research (31.3%) — because mirroring Core's hot run beat the sleeve-switching; confirms production Preserver = Core-like (great in bulls, no DD protection).

## ROOT CAUSE = rule B (hold-to-exit), the structural choice we locked
Research books each regime's sleeve RETURN instantly on the flip. Rule B holds falling t30v names through a capitulation until they exit → eats the DD before rotating → never gets the timing benefit. Same dilutes Maximizer's breakout capture. NOT a bug — it's the realistic single-pool construction vs the idealized return-stream.

## IMPLICATION (strategic fork — Erik's call)
Marketed tier advantages are real in the idealized construction but NOT deliverable as currently ported. Integrity issue: current materials cite research numbers we can't serve. Options: (1) test Option A (hard-rotate on regime flip) — recovers sleeve timing at turnover/tax cost; (2) accept production tiers ≈ Core, rethink 2-tier product + re-baseline marketed numbers to deliverable figures; (3) middle-ground partial/accelerated rotation. RECO: backtest Option A next to see how much edge it recovers before any product/marketing decision. This reopens the Option A vs B decision (design doc §1, B was chosen for realism/low-turnover — but B is what erases the edge).

## OPTION A TESTED (Jul 21) — RECOVERS the edge, but at 8 full-book rotations/yr
Option A = hard-rotate full book on each regime flip = research return-stream MINUS round-trip cost on flip days (scripts/tier_vintages_daily.py, COST_RT=0.30%). 2021-26:
| | Research | **Option A** | Production(ruleB) |
|---|---|---|---|
| Preserver | 19.4/1.33/−13.5 | 17.1/1.19/**−18.7** | 14.3/0.97/−22.5 |
| Maximizer | 36.2/1.61/−19.9 | **33.0**/1.49/−20.3 | 11.7/0.79/−21.3 |
=> Maximizer edge is REAL but ONLY with hard-rotate (33% vs ruleB 11.7%). Preserver DD partially recovers (−18.7 vs ruleB −22.5, toward marketed −13.5); rest lost to regime-detection lag + rotation cost. Gap Option-A vs research (~3pp/yr) = turnover cost.

## WHIPSAW / TURNOVER (Erik's question) — regime_series 2021-26, routed-source spells
- ~8 full-book rotates/yr (Max 7.9, Preserver 6.7). Median routed-source spell = 9 DAYS. **ZERO single-day whipsaws** (detector has hysteresis). BUT ~25% of spells ≤5 days (9-11 of ~40 flips) = fast oscillation, "rotate out & back within a week."
- REAL-WORLD: 8 rotates/yr = brutal in TAXABLE (8 short-term tax events/yr + manual exec burden for signals product); VIABLE in tax-advantaged (IRA/401k, no tax drag) → segmentation angle. Behavioral: full-liquidate-on-signal cuts against "anti-capitulation" brand.

## CONFIRMATION FILTER TESTED (Jul 21) — ❌ NOT a clean win; fragile dead-end
N=3/5/8d persistence before rotating (scripts/tier_vintages_daily.py confirm()). 2021-26 crisis window:
Preserver: OptionA(N0) −18.7 / c3d −23.1 / c5d **−26.4** / c8d −21.7 (return 14-17%). Maximizer: OptionA 33.0/−20.3 / c3d 30.1/−23.4 / c5d 28.2/**−30.7** / c8d 33.4/−20.4/3.7fpy.
- **NON-MONOTONIC + FRAGILE:** c5d WORSE than both c3d and c8d (DD −26/−30, worse than NO filter) — lag delayed a defensive rotation at a crisis transition. Picking c8d "because best" = OVERFIT trap.
- **Preserver: confirmation is COUNTERPRODUCTIVE** — its value IS fast defensive rotation; any lag pushes DD −18.7→−22/−26. Preserver wants N=0 (fast), eats turnover.
- Maximizer c8d (33.4/−20.4/3.7fpy) = lone bright spot but 5d fragility = don't trust w/o multi-window robustness.

## THE REAL CONCLUSION: fundamental tension, not a tuning problem
Tier edge REQUIRES fast rotation. EVERY turnover-reduction (rule B, confirmation lag) erodes it, worst in crises. Can't get low-turnover AND preservation from a rotation filter — direct conflict. Marketed edges ≈ require ~8 full rotates/yr = the taxable-account tax/exec problem, unchanged.

## NEXT DIRECTION (recommended, offered): OVERLAY/HEDGE, not rotation
Get fast DD protection WITHOUT full liquidation: on a capitulation flip raise cash partially / add hedge / lean on the existing volatility basket instead of selling the whole book → fast DD cut, far less turnover/tax. + Account-type SEGMENTATION: Option A (fast rotate) for tax-advantaged (turnover free); hedged/gentle for taxable. Rotation-filter tuning = abandoned (fragile). Prototype overlay/hedge next.

## ✅ OVERLAY/HEDGE PROTOTYPE (Jul 21) = THE DELIVERABLE CONSTRUCTION (best so far)
Preserver overlay = keep t30v book (NO liquidation), RAISE CASH in capitulation only (exposure→E); return=exp×t30v_ret; turnover=partial trim on cap enter/exit only. scripts/tier_vintages_daily.py.
2021-26: Core 17.5/1.10/−23.7 | OptionA 17.1/1.19/−18.7 (6.7 full rotates/yr) | **overlay E=0.25 17.9/1.23/−18.8 (4.4 PARTIAL cash-raises/yr)** | E=0.5 17.8/1.20/−20.4 | E=0.75 17.6/1.15/−22.0. LAST-2YR overlay E=0.25 = 32.9/1.87/−12.9 (3/yr).
- **overlay E=0.25 MATCHES Option A's DD with BETTER return+Sharpe & HALF the turnover, as partial trims not full rotations = tax/exec-friendly = DELIVERABLE in taxable.** vs Core: −18.8 vs −23.7 (~5pp less DD) at higher return+Sharpe → Preserver FINALLY preserves better than Core. Answers "where does Preserver preserve": raises cash fast in capitulation.
- HONEST: does NOT reach marketed −13.5% (idealized return-stream captured oversold-BOUNCE upside; pure cash doesn't). Realistic floor ~−19%. Deliverable claim = "~5pp less DD than Core, tax-efficiently," NOT "half the drawdown."
- Robust: flat+monotonic across E (no −30% surprises), intuitive mechanism → less overfit-prone than confirmation filter.

## ✅ RESOLVED (Jul 21) — robustness + tilt + Maximizer overlay (scripts/overlay_robustness.py, 28 monthly 3y starts)
| variant | ann med | ann min | Sh | mdd med | mdd WORST |
|---|---|---|---|---|---|
| Core | 7.9 | 1.0 | 0.56 | −18.8 | −23.7 |
| **P tilt E.25** | **10.2** | **3.0** | **0.77** | **−13.9** | **−18.8** |
| Max research | 17.0 | 6.8 | 1.02 | −19.9 | −19.9 |
| Max tilt E.25 | 15.4 | 5.1 | 0.92 | −19.9 | −19.9 |

### PRESERVER = SOLVED. Ship: t30v + capitulation TILT-overlay E=0.25 (keep book, in capitulation reduce t30v exposure to 25% + put freed 75% in oversold-bounce; ~4 partial trims/yr). DOMINATES Core on every metric incl TAIL: worst-case DD −18.8% (< Core median!) vs Core worst −23.7%; higher median+min return; Sharpe 0.77 vs 0.56. tilt>cash (bounce recapture). E=.25>.5. Robust, low overfit. Re-baseline Preserver marketing to deliverable ~10%/0.77/−14% median (−18.8 worst), NOT research figures.

### MAXIMIZER = overlay is the WRONG TOOL. DD unchanged (−19.9 median==worst, identical all variants) + overlay COSTS return (17.0→15.4). Because Maximizer's dominant DD = the 2022 momentum crash which happens in ROTATING_BULL (breakout leg crashing), NOT capitulation → capitulation overlay never engages. Maximizer's correct defense = the VOL-BRAKE on breakout entries (must WARM-START, see [[project_maximizer_coldstart_jul21]]). ALSO: production single-pool only captured 11.7% vs 17% return-stream — breakout edge is LOSSY to implement. Maximizer = separate open workstream (warm vol-brake + breakout-capture gap) OR launch Preserver-only first, hold Maximizer.

## ✅✅ PRESERVER LOCKED + VALIDATED IN PRODUCTION (Jul 21, commit a12e0e1)
Re-implemented PreserverBook as EXPOSURE-SCALED mirror (return = exposure × core_ret; exposure=0.25 in capitulation else 1.0; one-time trim cost on flip). NOT cash-moving (that was buggy: thrashed → prod ≈ Core −24%). VALIDATED prod single-pool: 2021-26 Preserver 14.5%/1.06/−19.1% BEATS Core 14.3%/0.96/−23.1%; LAST-2YR 35.3%/2.16/−10.5% vs Core 37.5%/2.08/−12.0%. Maps penny-to-penny w/ research return-stream. Dropped oversold-tilt (sleeve-capture, doesn't port). Committed+pushed (shadow-only). TODO: final numbers on FULL-history warm canonical curve for marketing; wire WS2/3/4/5.

## MAXIMIZER = REFRAME NEEDED (task #6, in progress). Per [[feedback_research_maps_to_prod]]: breakout is a SLEEVE-CAPTURE → does NOT port (prod 11.7% vs research 17%). So the breakout OFFENSE itself is the problem, not just the crash defense. An aggressive tier that PORTS must be EXPOSURE-SCALING. Candidate: Maximizer = Core book with EXPOSURE>1 (leverage) in favorable rotating_bull + vol-target de-risk when book vol spikes (Barroso, warm-started) — ports penny-to-penny unlike breakout. BIG: redefines Maximizer (leveraged-Core-vol-targeted, not breakout) — needs Erik buy-in before building.
