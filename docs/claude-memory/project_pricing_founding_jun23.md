---
name: project-pricing-founding-jun23
description: Jun 23 2026 — found checkout was charging WRONG prices ($39/$349 vs advertised $59/$129/$1099). Fixed + built the founding-seat system (server-side $59→$129 switch at 100 seats, counter, founder pill, leads tab, soft-conversion). THE pricing/founding reference.
metadata:
  node_type: memory
  type: project
  originSessionId: 701a2e93-33c0-4e85-a7bc-2cb9d9956d94
---

# Pricing fix + founding-seat system (Jun 23 2026)

## ⚠️ THE BUG: checkout charged the WRONG prices
Surfaced while diagnosing why 44 ad clicks → 0 signups. The Stripe price-ID env vars pointed at a STALE generation:
- `STRIPE_PRICE_ID` = $39/mo, `STRIPE_PRICE_ID_ANNUAL` = $349/yr — **but the site advertises $59 founding / $129 standard / $1099 annual.** Neither matched.
- The CORRECT prices existed in Stripe, just unwired. **Now set (safe full-env-merge, backups /tmp/envbak_price_*):**
  - `STRIPE_PRICE_ID` = `price_1TOqqkCOYW9ZRoIIgPd1BCBC` = **$59/mo (founding)**
  - `STRIPE_PRICE_ID_STANDARD` = `price_1TOqqkCOYW9ZRoIIUryZHBxH` = **$129/mo (standard)** (new var)
  - `STRIPE_PRICE_ID_ANNUAL` = `price_1TOqqkCOYW9ZRoIIYOkp5NmL` = **$1099/yr**
  - (stale/old still in account: $39/mo, $349/yr, $20/mo, $200/yr — ignore)

## Funnel diagnosis (why 0 signups on 44 clicks)
- Checkout requires an account (`Depends(get_current_user)`) → the 44 clickers never reached Stripe (0 new accounts). Leak is **pre-account (land→signup)**, NOT payment/Stripe.
- API Lambda does NOT log request paths greppably (events come as `keys=[...]`) — can't measure the land→signup funnel from CloudWatch; **GA4 is the tool** (page_view → begin_checkout → signup).
- Stripe DOES track abandonment (2 expired/unpaid sessions seen — but those are existing-user/test, not ad-attributable).
- Erik's take: friction is low (SSO = couple clicks). So it's a cold-traffic/trust/big-ask problem → newsletter-first soft conversion is the lever.

## Founding system (built + shipped this session)
**Plan types in checkout: only monthly + annual.** "Founding" was a frontend label that fell through to the monthly price; there was NO founder workflow in code. Now built:
- **billing.py**: `count_founding_seats` + public `GET /api/billing/founding-status` → `{taken,limit,remaining,open}`. Checkout picks the monthly price SERVER-SIDE: founding $59 while `open`, standard $129 once 100 seats taken (can't be spoofed; 'founding'/'monthly' both resolve right). Founder status = DERIVED from `subscription.stripe_price_id == STRIPE_PRICE_ID` in a live status (no schema migration).
- **config.py**: `STRIPE_PRICE_ID_STANDARD`, `FOUNDING_SEAT_LIMIT=100`.
- **App.jsx**: auto-launch Stripe checkout after signup (consume `rigacap_selected_plan`) — SSO→Stripe seamless (was dumping to /app).
- **LandingPageV2**: GATED counter (Erik: never embarrassing) — silent "Limited to first 100" while plenty remain → "Only X of 100 seats left" when `remaining <= FOUNDING_SCARCITY_THRESHOLD` (40) → "Founding Seats Filled" + standard activates when `!open`. Replaced a hardcoded fake "~87 of 100".
- **AdminDashboard**: ★ Founder pill (is_founding) on users; new **Leads tab** (`LeadsTab.jsx`) = newsletter signups / upsell pool (`GET /api/admin/newsletter-signups`, lead-vs-app-user, copy-emails).
- **LoginModal**: register-mode soft-conversion — "Not ready to commit? Follow the free newsletter" → posts email to `/api/public/subscribe-newsletter` (source=signup_modal_soft) so cold visitors don't leak.

## ⚠️ NOT yet enforced / open
- **"Locked 12 months" grandfather is a MARKETING promise, not coded.** Stripe keeps a founder on whatever price they subscribed at, so founders stay $59 indefinitely as long as the $59 price isn't archived (more generous than 12mo). No coded expiry/transition.
- The $129→standard switch is automatic at 100 founding seats (server-side). The "first 100" gate works off live Stripe-subscription count via our DB `stripe_price_id`.
- Founder cohort emails: the pill + leads tab give visibility; no automated cohort-email job built yet.
