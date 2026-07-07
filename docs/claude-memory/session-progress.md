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

## ✅ FE HERO BUILT (Jul 7, staged — NOT committed/deployed)
- `frontend/src/LandingPageV2.jsx` (live landing at `/`): added `RiskKnob` React component (SVG, JS geometry — knurled amp knob, gold pointer, umlaut-11, RIGACAP mark) + rebuilt `HeroSection` as 2-col knob hero using Tailwind brand tokens (paper/claret/Fraunces already in tailwind.config.js). Headline now **"One knob. / Preserve to Maximize."** (Maximize capitalized per Erik). VERIFIED rendering live via vite dev + screenshot (`design/documents/fe-hero-render.png`). Compiles clean.
- KEPT below hero: 4-stat grid + $59 founding para. DROPPED: old headline, 2008 −38/−0.5 box (Erik may want re-added), italic line. CTAs: "Join the founding list"→onGetStarted('founding'); "See how it works"→/track-record.
- **UNCOMMITTED** on research branch. Erik reviewing. Suggested mobile check before any deploy.

## 🧭 POSITIONING DEBATE (open, Jul 7) — resolving the stats + umbrella message
- Erik: 8.3%(21yr ann) + 19%(MaxDD) are WORST-CASE numbers — is that what we headline? I flagged 8.3% lags market (~9.8%) + undersells.
- Erik CAUGHT my error: I said "we don't chase return" as thesis → but then what is Maximizer? Correct: that's the PRESERVER line, NOT the product line. **Unifying thesis = "You set the ambition. We keep the discipline."** (managed risk at ANY setting; brand = discipline NOT caution; Maximizer = offense WITH the vol-brake seatbelt). AWAITING Erik's OK on that umbrella phrasing.
- PROPOSED revised stat grid (drop bare 8.3%, reframe 19% vs MARKET ~55% not vs raw-momentum): **2.20 Sharpe** (unifying risk-adj number, great at any setting) · **19% vs market 55%** (drawdown edge) · **+32% last-24mo** (recent, Maximize-side) · **2008·COVID·2022** (durability). Apply once Erik confirms umbrella.
- NEXT after lock: cascade direction to rest of landing + social. Then Signal-Intelligence + investor doc updates.

## 🛠️ PRODUCT NOTE (Erik asked): Maximizer→Preserver fallback WORKS
Add-on = separate Stripe line-item on Preserver base. Cancel just add-on (Portal) → base stays → webhook subscription.updated re-detects → has_maxpp_addon=false → served Preserver. No migration (signals service). TODO at live-serving: (1) configure Stripe Portal to allow removing add-on item; (2) guard orphan case (add-on requires base).

## ⚠️⚠️ RULES REINFORCED (Erik corrected me twice this session)
1. **NEVER "survivorship-free" in OUTWARD/customer copy** (heroes) — it's TABLE STAKES not marketing ([[feedback_survivorship_free_not_marketing]]). FINE in INTERNAL docs (sales playbook keeps it, due-diligence framing). Scrubbed all heroes + journey (journey→plainer lang, better for father anyway).
2. **Hero must say WHAT IT IS to a cold visitor** — not jargon ("regime-adaptive momentum"). Fix: red chip "Buy/Sell Signals · You Execute" + plain subhead ("sends you the buy/sell calls, you execute at your broker"). Signals-only product.
3. Printables = WHITE bg (paper wastes ink), claret OK as light accent.
4. GATE: no live TIER performance claims on public site until shadows validate (~1wk). Proof lines use drawdown/regime/"tiers launching", not live tier numbers.

## NEXT (Erik queue): pick hero → build full hero + cascade landing/social. Then Signal Intelligence + investor doc updates (non-critical). Branch: research/... (merged to main 6×).
