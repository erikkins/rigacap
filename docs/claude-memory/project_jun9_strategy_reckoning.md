---
name: jun9-strategy-reckoning-and-launch
description: "Jun 9 2026 — Marketing LAUNCHED (honest site live). But the portfolio-race continuous analysis found t30v is DEFENSE not offense: continuous hold-CAGR ~10% (not the marketed 14% window-mean), lags SPY (13.6%) AND raw momentum (28.8%) on return — only edge is drawdown (17.9% vs 30%+). Live copy OVERSTATES return. Big open decision. Plus: t30v go-live + clean reset + chart/animation + social all pending."
metadata:
  node_type: memory
  originSessionId: daad830f-fb74-43b7-b3d5-fc34eed698de
---

# Jun 9 2026 — Launch day + the strategy reckoning. READ THIS FIRST.

## ⚠️⚠️ THE CRITICAL FINDING — t30v is DEFENSE, not offense (the live copy overstates it)
The **portfolio-race / continuous-hold analysis** (a single $100k held 2017→2026, vs SPY, vs naïve momentum) blew up the comfortable story. Verified from `scripts/pitfwu_wf_periods.py race` (output → `frontend/public/portfolio-race.json`):

| (continuous $100k, 2017→2026) | CAGR | Worst DD | end value |
|---|---|---|---|
| **RigaCap (t30v)** | **9.8%** | **−17.9%** | $241,801 |
| **S&P 500** | 13.6% | −32.0% | $332,884 |
| **Naïve momentum (250d/12-mo)** | **28.8%** | −29.9% | $1,076,997 |

**Three hard truths:**
1. **t30v's real hold-CAGR is ~9.8%, NOT the 14% we marketed.** The "14%" was the MEAN of 16 rolling 2-year windows. An investor who actually held from 2017 got 9.8% — t30v LOST in 2017 (−4.7%) and 2018 (−5.8%), and that early hole drags the compound. Window-mean overstates the hold-return because t30v's returns are uneven (weak early, strong late).
2. **The "raw momentum 22%/35%" in our copy is WRONG.** Real 12-month (250-day) naïve momentum, held continuously, did **28.8% CAGR / 29.9% DD** — it crushed everything riding 2020 (+85%), 2024 (+45%), 2025 (+53%). (Caveat: naïve has NO trading costs modeled — monthly churn of volatile names would shave it meaningfully. But direction is unambiguous.)
3. **t30v is a DEFENSIVE strategy.** Year-by-year: it BEAT the S&P in every rough year (2022: −6.8% vs −19.5%; 2020: +27.7% vs +14.3%; 2026: +19.2% vs +9.6%) but LAGGED badly in every strong year (2017/2019/2024/2025). Over a mostly-up decade, defense lost. The risk controls (DWAP/near-high entry filters + inverse-vol sizing + 30% trail) systematically sand off the explosive winners that drive momentum's 28.8% → leaving 9.8%. **On a continuous hold, t30v lags SPY AND momentum on return; its ONLY edge is drawdown.**

**=> THE LIVE MARKETING OVERSTATES IT.** "~14%, half the drawdown of raw momentum (22%→14%)" is not honest on a continuous basis. The honest pitch is narrower: *"RigaCap won't beat a raging bull. It's built to lose less when things break — ~10%/yr vs the S&P's ~14% over a bull-heavy decade, but it nearly halved your worst drawdown and beat the S&P clean through 2022. Defense, not offense."* Different (preservation-minded) buyer, much more modest claim.

**OPEN DECISION (the pivot point — unresolved):**
- (A) Which lens is honest to lead with: continuous CAGR (~10%, what one investor gets) or window-mean (14%, "robust across start dates" — the analyst liked multi-start-date)? Must use the SAME lens for t30v AND the comparisons. The table currently uses window-mean (t30v 14% vs naïve 22% — internally consistent); the animation naturally shows continuous (t30v 9.8% vs naïve 28.8% — t30v looks bad). Different lenses → opposite stories.
- (B) Is t30v's return give-up justified, or did the controls OVER-SAND the upside? Consider a less-restrictive variant that captures more momentum while keeping reasonable drawdown. The whole validation used window-mean, which MASKED this.
- (C) **Does the live copy need correcting NOW?** It's live with the overstated return story.
- Behavioral angle (panic-sell at ~25% DD → naïve/SPY bail, t30v holds) helps t30v vs SPY but may NOT save it vs naïve (naïve's 28.8% is too far ahead; its 29.9% DD only just trips the threshold). So behavior doesn't fully rescue the return gap.

## ✅ WHAT LAUNCHED TODAY (live + verified, ~55 commits pushed to main, CI/CD deployed)
Honest marketing site is LIVE (Erik verified): landing hero = B ("Institutional discipline. Individual price."), track-record (equity chart REMOVED — see below), Methodology (de-mirage + de-recipe, EOD-execution parity), ALL blogs swept (PITFWU flagship `/blog/honest-backtest` added; #1 WalkForward full rewrite; #4/#9 fixed; #7 dead-links; #8 PITFWU tie-in; #10 "7 Regimes" REMOVED), `/for-advisers` React route wired + footer link, launch social posts de-mirage'd, We-Called-It engine pivoted to discipline-led. t30v port + vol_weight plumbing + CB-aware silent-cash detector all DEPLOYED but DORMANT (strategy 6 NOT flipped → live portfolio still runs OLD 6×15/12% config). Beta-tester launch email ready (`design/beta-tester-changes-email.html`) — the human "drawdown-over-returns" voice; **DO NOT SEND until the strategy-reckoning above is resolved** (it leans on the overstated story).

## CHART / ANIMATION STATE
- Equity-curve chart **REMOVED** from `TrackRecordPageV2.jsx` (placeholder comment marks the spot, `TrackRecordChart` import removed). It showed return-only where t30v ≈/below SPY → argued against the product. Endpoint `get_public_track_record` (signals.py:2891) reads `TRACK_RECORD_SIM_IDS` (config.py — set to bad 1519-1523; REVERT to 922-930 or it 500s/empties). Hardened it null-safe.
- The equity-band approach is DEAD for t30v (staggered-start sims misalign; null SPY pre-2019.5; prod pickle only 2019-2026; original `launch-5y-8dates.sh` used 8 CLOSE early-2021 starts × 5yr = aligned + in-range).
- **Animation vision (Erik's, great):** $100k in t30v vs SPY vs naïve racing forward; drawdown badges flash red on crashes (SPY −32, naïve −30, t30v −18 calm); end with "worst drop survived" tally. PLUS a **behavioral overlay** (panic-sell at ~25% DD → "what you'd actually do") as the killer flip. Data pipeline DONE (`portfolio-race.json`). Component NOT built. **PAUSED pending the strategy decision** — don't animate a story we're not sure is true.

## DATA-SOURCE FINDING
Prod WF Lambda = **7-year pickle (2019-06 → 2026)**. The 9-year validation used **PITFWU parquet (2016+, research only)**. Prod can't reproduce 9-year. Erik: extend parquet back **before 2016** (yfinance) for 2008 GFC + 2009 momentum-crash test (analyst's targeted ask) — and it'd make the animation far more dramatic. Then move race data from frontend/public → S3 (same migration unlocks both).

## STILL PENDING (gated on the strategy decision above)
1. **t30v GO-LIVE** = flip strategy 6 params (20/4.5/trail30/vol_weight=1.0/**CB ON** — crash-breaker under wide trail) + **CLEAN RESET of the live portfolio** (Erik confirmed "start fresh"): close the 2 old positions, fresh capital, clear the CB pause (it's an old tight-trail artifact), t30v live clock starts day 1. The old "+2.7% / 2 positions / 10 sells" is the OLD strategy — archive or supersede, not on the t30v clock. Parity is by-construction (helpers match backtester; the race WF executed). **BUT gated: don't go live on a strategy we're re-evaluating.**
2. **SOCIAL workstream** (Erik dislikes the voice — felt "smarter than the author"): reply-engagement STAYS (only discovery engine at 3 followers) but fix `engagement_service.py` prompt → humble/first-person/vulnerable (the rebuild-story hook), DROP "must cite a number" rule, re-ground in new positioning, pull recipe/regime leaks. Plus rewrite all profiles/bios, redo 5 launch graphics, `social_content_service` FOMO templates. Beta email = voice north star.
3. Signup Individual/Adviser field (migration-first schema change).
4. Underwater/animation chart (above).

## TOOLING: Fable 5
Claude's new Code model. Benchmarks (Erik showed): agentic coding 80.3% vs Opus 4.8's 69.2% (SWE-Bench Pro), 88% vs 82.7% (Terminal-Bench), reasoning HLE 64.5 vs 57.9; **memory + long-context built for exactly this kind of marathon-with-file-memory session ("stays focused across millions of tokens, improves using its own notes, 3× Opus 4.8 with file-based memory").** Erik likely switching to Fable 5 for the work ahead — this memory IS the handoff.
