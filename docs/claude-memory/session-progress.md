---
name: session-progress
description: "Live session snapshot (auto-checkpointed ~15min) — what's done, in flight, and next"
metadata:
  node_type: memory
  type: project
  originSessionId: 2dce3134-d861-45c4-a371-80378750f8c0
---

# Session snapshot — Jul 7 2026 (late) — engine work DONE, now deep in MARKETING (hero directions)

Full state: [[project_preserver_2tier_phase2]]. Names LOCKED: Preserver/Core/Maximizer.

## ✅ ENGINE WORK SHIPPED TODAY (deployed+verified)
- **BOTH tier shadows LIVE** (PRESERVER_SHADOW + MAXIMIZER_SHADOW =true). Record at Jul 8 4pm scan → verify `🕯️`+`🚀` logs + rows in preserver_*/maximizer_* tables.
- Maximizer port: breakout detector signal-EXACT, replay PENNY-EXACT, MaximizerBook (vol-brake). Dashboard sell-ribbon parity fix (12%→30%) [[project_sell_alert_parity_bug_jul7]]. Stripe add-on complete+smoke-tested.

## 🖊️ MARKETING DOCS — in progress (design/documents/, house style: Fraunces+Plex)
- ✅ **rigacap-journey.{html,pdf}** DELIVERED — Erik "perfect doc" (father keepsake; 6pg white bg, light claret; myth-busting DWAP→today; ends w/ tier numbers Preserver +31%/-13%, Maximizer +49%/-17%).
- ✅ **rigacap-sales-playbook.{html,pdf}** DELIVERED — internal/confidential; filtration-not-conversion, A/F matrix, 4 personas (Preserver/RIA/Growth-seeker/[Market-Maximizer=release]), objection handbook, qualifying qs, guardrails.
- ✅ **WEBSITE HERO — LOCKED** (`design/documents/hero-knob-final.{html,png}`): **3D KNURLED AMP KNOB w/ GOLD POINTER** (Erik chose this over the glossy Strat-bell version he also tried). Headline **"One knob. Preserve to maximize."** (NOT "these go to 11" — Spinal Tap IP; killed). Claret chip **"Buy/Sell Signals · You Execute"** + kicker **"The Systematic Trading System"** (Erik LOVES these — answer "what IS this" for cold visitor; DO NOT remove). Plain subhead (you execute at your broker). Proof "~⅓ market's worst drawdown · Two decades every regime · Tiers launching this month". Numbers **1=lower-left/Preserve → 11=lower-right/Maximize** (had them backwards, fixed). Preserve(green)/Maximize(claret) labels = 23px uppercase (Erik "make stronger"). **SECRETS: metal umlaut over 11 (Spın̈al Tap nod) + RIGACAP maker's mark on knob face + signature HTML comment** ("sign your work"). ✅ LOCKED — Erik: "yes, this is the one!"
- Explorations archived: hero-directions.{html} (A/B/C dial), hero-knob-directions.{html,png} (D/E/F), Strat-bell in git history. Ref knob img in scratchpad/ref_knob.jpg.

## ✅ FE HERO — COMMITTED Jul 8 (57abfe8, research branch, NOT deployed) + caption = "Walk-forward tested"
- Committed: LandingPageV2 knob hero + rigacap-journey.{html,pdf} + rigacap-sales-playbook.{html,pdf} + hero-knob-final.{html,png}. Dial caption LOCKED to **"Walk-forward tested · both tiers launch this month"** (Erik chose).
- **NEXT MARKETING-DEPLOY STEPS:** (1) Erik mobile-check via Chrome DevTools device mode (headless screenshots unreliable); (2) DECISION PENDING — deploy hero-only NOW vs quick below-the-fold audit first (sections UNDER hero still tell OLD single-product story: old value-prop + pricing w/o Maximizer add-on → risk of disjoint). My lean: quick below-fold audit first. (3) Deploy = merge research→main→CI/CD→live rigacap.com.
- Broader rollout after hero: rest-of-landing 2-tier alignment · pricing section (Preserver + Maximizer add-on, Stripe wired) · social cards claret/paper · ⭐ Track Record page + ANIMATED CHART (big next project).
- ⏰ **TODAY 4pm ET: both shadows first record** (verify 🕯️/🚀 logs + rows) — product gate for serving/charging tiers (~1wk), independent of marketing deploy.

## (superseded) FE HERO — earlier iteration notes
- `frontend/src/LandingPageV2.jsx` (live landing `/`): `RiskKnob` React component (SVG geometry — knurled amp knob, gold pointer, umlaut-11, RIGACAP mark) + rebuilt `HeroSection` 2-col knob hero. Headline **"One knob. / Preserve to Maximize."** Chip "Buy/Sell Signals · You Execute" + kicker "The Systematic Trading System" (Erik LOVES, keep). Desktop render verified good (`design/documents/fe-hero-desktop.png`); compiles clean.
- **⭐ SHOWING TIER NUMBERS AT DIAL ENDS** (Erik: "be honest but bold!", "show them!"): under knob → PRESERVE +31%/−13% · MAXIMIZE +49%/−17% · caption "Backtested · both tiers launch this month". This publishes tier BACKTEST numbers pre-live-launch — Erik OK'd (honest label, not implied-live). Gained back the +49% that was missing.
- Stat grid (credibility, gains-led per Erik): 19% (vs market ~55%) · 21 yrs (2008/COVID/2022) · 2.20 Sharpe · **0 losing 2-year stretches** (swapped from weak "7 regimes"). Dropped 8.3% (Erik: too small). Mobile safeguards added (CTAs stack, grid-cols-1, overflow-clip).
- **⚠️ MOBILE SCREENSHOTS UNRELIABLE** — headless Chrome won't apply phone viewport from CLI (renders ~980 clipped → looks "horrid" but it's an ARTIFACT, CSS is responsive). Verify via Chrome DevTools device mode at localhost:5173.

## 🧭 OPEN DECISIONS (Erik to confirm)
1. **Dial caption label:** verified Core = genuine WALK-FORWARD (pitfwu_wf, survivorship-free, out-of-sample); sleeves = backtest of out-of-sample-validated params. "Backtested" undersells. My lean → **"Walk-forward tested"** (or "Out-of-sample"). AWAITING pick.
2. **Umbrella thesis** = "You set the ambition. We keep the discipline." (Maximizer = offense w/ seatbelt; NOT "we don't chase return" which is the Preserver-only line). Erik agreed-ish.
3. Commit hero to research branch? (still not deployed). 2008 −38/−0.5 box: dropped, Erik may want back.

## ⏳ LANDING BELOW-THE-FOLD — 2-TIER REBUILD IN PROGRESS (Jul 8, staged, UNCOMMITTED since 57abfe8)
- SEQUENCE (Erik): push landing FIRST (new design) → then Track Record (animated chart uplift) → then Methodology.
- Hero polish DONE: proof-line wrap fixed (dropped redundant "Tiers launching this month" from left, it's under the knob); founding para TRIMMED (dropped stat-echo, kept CIO + "$59 not 1%/yr" hook, text-pretty + nowrap for widows).
- **PRICING REBUILT for Option A** (Erik chose A = Preserver buyable + Maximizer waitlist): header "One engine. Your dial."; **Preserver** card ($59 founding→$129/$1,099, "Every buy & sell call the model makes" — fixed the false "unlimited real-time"); **+ Maximizer** card ("Add-on · Launching this month", +$100, "Join the founding list"→onGetStarted('founding'), "first access when signals go live", NO charge yet, dropped "(→$229)"); **Advisory** card ("Preserver + Maximizer, firm-wide"). Dev server localhost:5173 hot-reload; Erik eyeballing.
- **STILL OPEN (small):** (1) add "Preserver vs Maximizer" FAQ? (asked Erik). (2) survivorship-free appears 4× in below-fold (lines 249/275/348/557) — all methodology-transparency/caveat contexts NOT hero-leads → my rec KEEP (Erik's "explaining the concept is fine"); awaiting his call. (3) FAQ still single-strategy framing (acceptable). Then commit + DEPLOY landing (merge research→main→CI/CD).
- ⏰ TODAY 4pm ET: both shadows first record (verify 🕯️/🚀 logs) — product gate, independent of marketing deploy.

## ⚠️⚠️ DATA-ATTRIBUTION CORRECTION (Erik caught, Jul 8) — CRITICAL for honest copy
- **8.3%/0.73/19% (21yr walk-forward) = CORE (t30v), NOT Preserver.** Verified: tier_vintages_daily.py runs ONLY last-2yr + 2021-26 → Preserver 31%/-13% & Maximizer 49%/-17% are RECENT (2yr) clean numbers. Long-history tiers exist (tier_vintages.py 2009-2026) but BIWEEKLY-approx + pre-2016 EXT/survivorship-caveated — NO clean 21yr daily Preserver.
- HONEST STRUCTURE to thread through site: **Core = 21yr walk-forward-proven engine (8.3%/19%); Preserver/Maximizer = tiers ON it, RECENT records (31/49), launching this month.** Page currently BLURS this (Performance table calls 8.3% row "RigaCap—risk-managed" = actually Core; hero mixes Core-21yr risk + tier-2yr returns). FIX labeling as part of Performance rework.

## ⏳ EDGE + PERFORMANCE SECTIONS — REWORK PROPOSED, AWAITING GREEN-LIGHT (Jul 8)
- Erik: "less return, less pain" (Performance headline) is the defensive-only Preserver-trap; must become dial-aware. Performance section literally titled callout "Why the lower number is the point" + table shows RigaCap 8.3% < SPY 9.8% < raw-mom 13.2% → sells AGAINST Maximizer's 49%.
- PROPOSED reframe (Erik to greenlight): Performance headline "Dial your return. Keep the discipline."; lead w/ dial ends (Preserver 31/-13, Maximizer 49/-17 recent); keep 21yr drawdown table as CREDIBILITY relabeled "Core engine"; retire "lower number is the point". Edge: rework 3 pieces → (1) regime-adaptive engine (2) risk discipline (3) dial+seatbelt. + fix Core-vs-tier attribution throughout.
- ALSO PENDING: 4th hero stat ("0 losing 2-year stretches" — Erik: not intuitive + may be FALSE since 2017+2018 both losing years; my rec = swap for recovery-speed "2× faster" AFTER verifying).

## ✅ MANY hero/FAQ polish edits done (Jul 8): pricing→2-tier (A), founding-para trim, ALL tildes removed, "backtest"→"walk-forward tested" throughout (kept "overfit backtests" for others + legal disclaimer), new Preserver-vs-Maximizer FAQ (better/more now italic), reconciled returns FAQ. Dev server localhost:5173 hot-reload.

## 🔜 NEXT BIG PROJECTS: **Track Record page rebuild w/ ANIMATED CHART** (out-of-sample curve; label Core-21yr vs tiers-recent) → Methodology page.

## 🛠️ PRODUCT NOTE (Erik asked): Maximizer→Preserver fallback WORKS
Add-on = separate Stripe line-item on Preserver base. Cancel just add-on (Portal) → base stays → webhook subscription.updated re-detects → has_maxpp_addon=false → served Preserver. No migration (signals service). TODO at live-serving: (1) configure Stripe Portal to allow removing add-on item; (2) guard orphan case (add-on requires base).

## ⚠️⚠️ RULES REINFORCED (Erik corrected me twice this session)
1. **NEVER "survivorship-free" in OUTWARD/customer copy** (heroes) — it's TABLE STAKES not marketing ([[feedback_survivorship_free_not_marketing]]). FINE in INTERNAL docs (sales playbook keeps it, due-diligence framing). Scrubbed all heroes + journey (journey→plainer lang, better for father anyway).
2. **Hero must say WHAT IT IS to a cold visitor** — not jargon ("regime-adaptive momentum"). Fix: red chip "Buy/Sell Signals · You Execute" + plain subhead ("sends you the buy/sell calls, you execute at your broker"). Signals-only product.
3. Printables = WHITE bg (paper wastes ink), claret OK as light accent.
4. GATE: no live TIER performance claims on public site until shadows validate (~1wk). Proof lines use drawdown/regime/"tiers launching", not live tier numbers.

## NEXT (Erik queue): pick hero → build full hero + cascade landing/social. Then Signal Intelligence + investor doc updates (non-critical). Branch: research/... (merged to main 6×).
