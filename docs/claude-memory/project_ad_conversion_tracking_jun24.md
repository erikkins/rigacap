---
name: project-ad-conversion-tracking-jun24
description: "Google Ads \"0 conversions\" is a GA4→Ads import gap, NOT a dead funnel — GA4 fires 73 key events, Ads sees 0"
metadata: 
  node_type: memory
  type: project
  originSessionId: 701a2e93-33c0-4e85-a7bc-2cb9d9956d94
---

# Ad conversion tracking — the "0 conversions" is a measurement gap (Jun 24 2026)

**Context:** Google Ads `stability-search-test-a` (Jun 12–23): $303.72 spend, 47 clicks (36 mobile / 10 desktop / 1 tablet), 1,866 impr, 2.52% CTR, $6.46 CPC, **0.00 conversions**. Erik asked "is the conversion action firing?"

**Diagnosis (firing works; the IMPORT is broken):**
- GA4 (G-0QKQRXTFSX) Home, last 7 days: 8 active users, 235 events, **73 key events (↑82.5%)**, 5 new users. So **GA4 IS recording conversions** — the firing side works for consenting users.
- Google Ads shows **0** conversions. **73 in GA4 vs 0 in Ads = the GA4→Ads conversion IMPORT is the broken link** (smoking gun). There is NO direct Google Ads tag anywhere (no `AW-…/send_to`), so Ads conversions depend ENTIRELY on GA4 key-event import — which was never completed.

**THE FIX (Ads-UI, not code):** (1) Link GA4↔Ads (Ads→Tools→Linked accounts→Google Analytics); (2) Import key events as conversion actions (Ads→Goals→Conversions→New→Import→GA4). **Import `sign_up` + `purchase` as PRIMARY — NOT `begin_checkout`** (73 key events w/ only 5 new users ⇒ begin_checkout/CTA-clicks are flagged key and inflate; importing it teaches the bidder to chase clicks, not signups). Check GA4→Admin→Key events for what's flagged. A ⚠️ icon sits on the GA4 Home cards — worth hovering.

**Code-side issues found (frontend):**
- gtag is **consent-gated**: `gtag.js` is NOT in index.html — `frontend/src/components/CookieConsent.jsx` `loadGA4()` only runs on consent==accepted. Decline/ignore → `window.gtag` undefined → every `sign_up`/`purchase`/`begin_checkout` silently no-ops. Costs the decline-cookies segment (secondary; Consent Mode v2 would recover modeled conversions). Events are wired in AuthContext.jsx (sign_up email/google/apple), App.jsx:1946 (purchase on checkout return), LandingPageV2/App (begin_checkout).
- STALE bug: `AuthContext.jsx:167` begin_checkout value still uses OLD prices `plan==='annual'?349:39` (should be 1099/129/59 per the Jun-23 pricing fix). Wrong for value-based bidding.

**Search-terms read:** clicks are ON-thesis (capital-preserver: "how to protect investments from stock market crash", "investment strategies for market downturns", "protect my ira from market crash" — 33–100% CTR). Off-persona leak = trade-hunters via "most volatile stocks today"/"volatile stocks today" (top impression eaters, 40+23). **Negatives: add phrase "volatile stocks"/"most volatile" — NOT bare "volatile"** (would kill the on-thesis "is the market volatile right now" anxiety query). Other trade-hunter candidates: "stocks to buy", "best stocks", "day trading", "penny stocks", "stocks to watch".

**No Google Ads API wired** — data via screenshots. For recurring data without API setup (dev-token approval + OAuth): scheduled Ads email report (CSV), Looker Studio connector, or Ads Scripts. Wire the API only if the campaign scales past the test.

**Net:** ads reach the right people at fine CPC; "0 conversions" = un-imported GA4 conversions (fix the link FIRST, before judging negatives — else you can't tell what helped). Related: [[project-pricing-founding-jun23]] (the pre-account land→signup leak).
