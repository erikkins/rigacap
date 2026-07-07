# 2-Tier Launch Plan (Preserver + Maximizer) — WORKING SPEC

*Jul 7 2026. Decisions locked; sequencing + build checklist below. Two parallel tracks with
one hard gate: we build commerce + marketing now, but never charge for a tier or publish its
performance until it produces LIVE signals (Phase 2 done).*

## Decisions (locked)
- **Sequencing: WAITLIST-FIRST.** Market the live t30v's strong recent numbers now +
  "tiers coming" waitlist/founding-cohort; build Stripe + product in parallel; flip tiers
  live once Phase 2 shadow-validates.
- **Pricing:** Base (Preserver) unchanged — $129/mo std, $1,099/yr, founders $59.
  **Maximizer = paid add-on: +$100/mo → $229/mo** (founding add-on +$79/mo;
  annual +$1,000 → ~$2,099/yr). Structured as a Stripe add-on *subscription item*.
- **Audience: SEGMENT BOTH.** Preserver = $250k+ preservers/advisers (flagship, on-brand).
  Maximizer = a NEW aggressive-growth channel (younger, growth-seeking); different messaging.

## Timeline — 2-WEEK SPRINT (4-week hard ceiling)
Launch-gated on shadow validation, NOT calendar. 2 weeks is achievable because the sleeve
paths are ALREADY penny-exact validated offline (10+yr history) — the live shadow only
confirms the PIPELINE runs clean (~1 week), it doesn't wait for rare regimes.

| days | Track A — Product | Track B — Commerce/Marketing |
|---|---|---|
| **0–2** | rule B ✅ → migration (off-hours) → deploy shadow hook | Stripe add-on Prices + code; open waitlist + both channels |
| **3–9** | shadow runs; confirm daily pipeline matches offline replay | build demand; read the tier-split signal; landing/social live |
| **10–12** | pipeline confirmed clean → tiers ready to serve | founding soft-launch (final gut-check; founders convert first) |
| **~14** | **FIRE** — flip entitlement gating + tier serving | public launch, both audiences |

**Floor ≈ 10–14 days** (the shadow needs ~1 clean week; execution must be crisp). If the
shadow surfaces a pipeline issue, use the buffer up to 4 weeks — but don't drag past that
(waitlist demand goes cold). Move fast on the parallel builds to hold the 2-week line.

## The two tracks + the gate
**Track A — Product (rollout).** Finish Phase 2: ✅ book-transition rule B → migration →
shadow hook → 2–4wk shadow validation → tiers live. (Gated on Erik ✅ + off-hours migration.)
**Track B — Commerce + Marketing (buildable NOW, parallel).** Stripe add-on + waitlist +
landing/social. Ready to flip on the moment Track A lands.
**GATE:** no tier performance claims published + no tier charges until that tier is LIVE.
The live t30v Core numbers (last-2yr ~36%/1.87/−15%) ARE honest + marketable today.

## Pricing structure (final)
| | Monthly (std) | Founding | Annual |
|---|---|---|---|
| **Base — Preserver** | $129 | $59 | $1,099 |
| **+ Maximizer add-on** | +$100 (→$229) | +$79 (→$138 founding) | +$1,000 (→~$2,099) |
- Existing t30v subscribers → auto-migrate to Preserver base (free upgrade; Preserver ≥ Core).
- Add-on = separate Stripe subscription item so it toggles on/off the base cleanly.

## Stripe objects (Track B) — CREATED Jul 7 ✅
"Maximizer Add-on" product with 3 Prices (base Preserver reuses existing RigaCap Premium
$129/$59/$1,099 IDs, unchanged):
- **Standard $100/mo** → `price_1Tqf2nCOYW9ZRoIIkfELxlzb` → env `STRIPE_PRICE_ID_MAXPP_STANDARD`
- **Founder $79/mo** → `price_1Tqf2nCOYW9ZRoII6rbnXbhF` → env `STRIPE_PRICE_ID_MAXPP_FOUNDING`
- **Annual $1,000/yr** → `price_1Tqf2nCOYW9ZRoIISghdCu2W` → env `STRIPE_PRICE_ID_MAXPP_ANNUAL`
- Set these in the Lambda env via SAFE read-modify-write; NEVER `update-function-configuration
  --environment` (wipes all env vars → outage). config.py declares the getenv reads.
- **Checkout/portal:** allow adding the add-on item at checkout + toggling via Customer Portal.
- **Gating:** add-on entitlement → serve Maximizer signals (once live) only to add-on holders.

## Waitlist (capture demand NOW)
- Landing: "Maximizer — join the founding waitlist" CTA (aggressive channel) +
  "Preserver early access" (preserver channel). Email capture → tag by tier interest.
- Founding-cohort framing (limited seats) to drive urgency + validate the segment split.
- Metric: waitlist signups by tier = the demand signal that de-risks the build.

## Marketing / social strategy shift (segment both)
- **Preserver channel** (existing $250k+ / adviser / preservation voice): lead with
  drawdown-control + the honest tradeoff; RIA/adviser angle (Paul's feedback).
- **Maximizer channel** (NEW, aggressive-growth): lead with the eye-popping recent numbers
  + "offense with a seatbelt" (the vol-scaling brake is the differentiator vs reckless momo).
  Younger/growth audience, different platforms/voice.
- Rebuild social cards in CLARET+PAPER ([[feedback_brand_claret_paper]]); retire navy/gold.
- CAUTION: market Maximizer on the DURABLE ~+7pp edge + the crash-brake, NOT the 49% peak.

## Sequenced checklist
1. [ ] Trace current Stripe/billing code → plan add-on wiring (in progress).
2. [ ] Create Stripe add-on Product + 3 Prices; add env vars (safe RMW).
3. [ ] Checkout + Customer Portal: add-on toggle.
4. [ ] Waitlist capture (landing CTAs + tier tagging).
5. [ ] Landing/marketing: update to 2-tier (claret/paper); waitlist live.
6. [ ] Social: stand up the two channels; rebuild cards.
7. [ ] (Track A) Phase 2: rule B ✅ → migration → shadow → validate → tiers live.
8. [ ] Flip: entitlement gating + tier serving + charge; announce.
