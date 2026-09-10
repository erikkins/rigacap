---
name: session-progress
description: "Rolling snapshot of the current working session — accomplishments, in-flight work, key context for a fresh session"
metadata: 
  node_type: memory
  type: project
  originSessionId: b87c584c-343d-4a11-aca7-a450196570be
---

# Session progress — updated 2026-09-10

## ✅ SEP 10 — SnapTrade prod key + bogus-signup / email-verify / tracking (advisory, in flight)
- **SnapTrade prod key (advisory only, no code):** "Describe your application" → gave READ-ONLY Mirror framing (read holdings/positions → alignment vs model book; NO trades/no fund movement). "Controls" form: recommended Q1 = commentary + suggested SECURITIES-to-buy/sell (ADD, product literally publishes named signals) + suggested portfolios; OFF = personalized (one model for all, keeps clear of advice + Mirror counsel gate) + AI-generated (signals are rules-based). Q2 = "info only" + "may manually place trades"; OFF = converted-to-orders + automated (no order routing).
- **Bogus signup (wonderboy461@yahoo.com, prob a gawker):** 552 mail errors on every send. Erik wants (a) real email enforced — cut off free access after 5-7 days if unverified; (b) can we track a repeat gawker who wipes cookies / never accepts consent? IN FLIGHT: launched Explore agent (a7f9a84afbfb83330) to map signup/verification flow, User model cols (email_verified? ip? ), IP/device logging, CookieConsent GA4 gating, email bounce handling (552/550 suppression), free/trial state machine + existing time-cutoff hooks. Awaiting agent → then give grounded recs. Prelim tracking view: cookies wiped + consent declined kills GA4/first-party; only server-side levers survive (signup IP logged regardless of consent — imperfect: VPN/mobile-rotate/shared; Stripe payment method only if they pay = moot). Email-verify cutoff piggybacks naturally on free-first spec (email = primary entitlement contact there).

## ✅ SEP 5 — Newsletter Maximizer time-stops + D7 ribbon offset
- **Newsletter logic (SHIPPED bcfbd6f, deploying):** weekly "Market, Measured." only counted PRESERVER stops (model_positions portfolio_type='live', reasons trailing_stop/stop_loss/regime_exit) → "0 stops" true for Preserver but blind to Maximizer. Maximizer breakout book's 29-day time-stops live in `tier_fills` (tier='maximizer', side='sell', reason='hold_exit'). Added a tier_fills count (additive, try/except), surfaced as a DISTINCT data-block fact ("scheduled clock exit, NOT loss-cut"), updated §01 + §03 prompts to keep the two exit types distinct. Erik: DON'T regen — this week's letter is LOCKED; fix is for NEXT week's generation (also fixes the §03 "0 stops" bullet auto). newsletter_generator_service.py.
- **D7 "first week graded" regime ribbon offset (FIXED in scratchpad build_drip.py):** year labels were left-anchored at each year's START boundary (text-anchor default=start, x=i*w) → sat at far-left of each block = looked offset. Fixed to CENTER each label under its year's SPAN midpoint (text-anchor=middle, x=(i0+i1)/2*w) + partial-year min-gap guard (skip if span*w<24). Mirrors frontend BlogSectorObservatoryPage.jsx year-axis convention. Regenerated ribbon_fixed.png, Erik approved. NOTE: drip still NOT productionized (build_drip.py is a scratchpad sample; carry this fix into email_service.send_onboarding_email when porting). Fixed build_drip.py saved to session scratchpad.
- **Newsletter design (dawn header):** Erik floated adding sun/moon+dawn image like the digest; my rec = KEEP text-forward (essay genre ≠ product-email genre; restraint = premium signal). Erik agreed ("looks like a high end newsletter"). Offered 2 optional light-touch family cues if ever wanted: (1) thin dawn-gradient hairline under masthead replacing the 2px solid rule, (2) small spire/eclipse logomark above kicker. NOT built.

## ✅ SEP 4 (44dcba8) — FreeProofView table alignment (Erik's morning bug)
- Both the "21-year walk-forward record" table AND "Recent catches" in components/FreeProofView.jsx used `flex justify-between` → middle value floated by left label/ticker width ("Raw momentum (no floor)" shoved its 13.2%/yr right; days-held wobbled by ticker length). Fixed BOTH to `grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)]` (label left / value centered / DD-or-return right), tabular-nums + whitespace-nowrap. Build green, pushed, deploying.

## ✅ ANSWERED — preview expired/noaccount view (Erik's ask)
- Already exists (admin-only): `?preview_state=free|active|trial|expired|past_due|canceled` (backend signals.py:2129; anything ≠ active → FreeProofView teaser). Use `/app?preview_state=expired` (+ optional `&preview_tier=maximizer`). True logged-out "no account" chrome = same FreeProofView body; log out / incognito to see the "Sign in" CTA variant. Offered to add a distinct `noaccount` state if he wants it while logged in.

## ⚠️ VIX BACKFILL — fork DIED mid-run (prev process exited), NOTHING landed
- Safety-checked: all_data.parquet INTACT (5018 symbols; ^VIX & ^GSPC still frozen at 2026-06-15; no partial write, no .bak). git clean (fork committed nothing).
- STILL TODO (awaiting Erik go): backfill ^VIX/^GSPC 2026-06-15→today into all_data.parquet + ongoing persistence (targeted index-row merge each scan, NOT full 600-sym rewrite=OOM). Root cause: PRICE_SOURCE=parquet skips export_parquet (main.py:1652); indices can't go in PITFWU (Alpaca) so they live only in frozen all_data. Live regime VIX is FINE (re-fetched to data_cache each scan). Only research/WF reading ^VIX from parquet is affected. Re-run INCREMENTALLY this time (keep Erik in loop), safety rails: backup→merge-preserve→verify. Tool: {"parquet_query":{"sql":"...FROM prices..."}} (DuckDB).

## ✅ EARLIER (live in prod)
- Morning Health "DWAP 590/591" squashed (^VIX excluded, 51086e1). Mirror tour → real portal + "Your move" de-buy-pushed (bd45dc8). Mirror go-live (first+default tab). Daily digest v3 both tiers live.

## ⏳ OPEN / QUEUE
- VIX backfill (above) — awaiting go.
- **Tour firing scope** A/B/C: current A=localStorage per-browser (fires for anyone unseen). B=per-account server flag. C=B+new-signups-only. Awaiting Erik.
- **Landing "The Mirror" section** (LandingPageV2.jsx ACTIVE at /) — prime new signups for eclipse default tab; extract AlignmentEclipse (App.jsx:1069, not exported+circular) → components/AlignmentEclipse.jsx OR static PNG.
- **Drips** — productionize redesigned 6-step onboarding into email_service.send_onboarding_email (D1/D3/D7/D12/D15/D22); samples scratchpad build_drip*.py; pattern=backend/app/services/digest_v3.py.
- Password reset + win-back surfaces.

## KEY FACTS / TOOLS
- Email tests → erik@rigacap.com (NOT ekins@cookma.com=this window's Claude login). AWS_PROFILE=rigacap. Deploys ~4min via push to main.
- Worker diag: {"parquet_query":{"sql":...}} (DuckDB all_data ≤200 rows), {"parquet_diagnose":true}, run_migration {"sql":[...]} (Postgres), maximizer_preview, {"daily_emails":{"target_emails":[...],"force_tier":...}}.
- Single source=today's dashboard; email GENERATES NOTHING; NEVER truncate lists; each tier own read. Brand claret/paper; NEVER navy/gold/olive; no DWAP/tape/PITFWU to CUSTOMERS (admin/internal OK).
- FORKS have been unreliable here (rate-limits, one died mid-run). Prefer incremental/direct for sensitive prod-data ops.
