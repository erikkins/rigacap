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

## 🔜 NEXT BIG PROJECT (Erik flagged, excited): **rebuild Track Record page w/ ANIMATED CHART** — the out-of-sample equity curve = the proof behind the "walk-forward tested" label.

## 🛠️ PRODUCT NOTE (Erik asked): Maximizer→Preserver fallback WORKS
Add-on = separate Stripe line-item on Preserver base. Cancel just add-on (Portal) → base stays → webhook subscription.updated re-detects → has_maxpp_addon=false → served Preserver. No migration (signals service). TODO at live-serving: (1) configure Stripe Portal to allow removing add-on item; (2) guard orphan case (add-on requires base).

## ⚠️⚠️ RULES REINFORCED (Erik corrected me twice this session)
1. **NEVER "survivorship-free" in OUTWARD/customer copy** (heroes) — it's TABLE STAKES not marketing ([[feedback_survivorship_free_not_marketing]]). FINE in INTERNAL docs (sales playbook keeps it, due-diligence framing). Scrubbed all heroes + journey (journey→plainer lang, better for father anyway).
2. **Hero must say WHAT IT IS to a cold visitor** — not jargon ("regime-adaptive momentum"). Fix: red chip "Buy/Sell Signals · You Execute" + plain subhead ("sends you the buy/sell calls, you execute at your broker"). Signals-only product.
3. Printables = WHITE bg (paper wastes ink), claret OK as light accent.
4. GATE: no live TIER performance claims on public site until shadows validate (~1wk). Proof lines use drawdown/regime/"tiers launching", not live tier numbers.

## NEXT (Erik queue): pick hero → build full hero + cascade landing/social. Then Signal Intelligence + investor doc updates (non-critical). Branch: research/... (merged to main 6×).
