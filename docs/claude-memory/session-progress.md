---
name: session-progress
description: "Live session snapshot (auto-checkpointed ~15min) — what's done, in flight, and next"
metadata:
  node_type: memory
  type: project
  originSessionId: 2dce3134-d861-45c4-a371-80378750f8c0
---

# Session snapshot — Jul 10 2026 (Fri) — 2-tier LIVE. Meta resolved. Platform-toggle deployed. Content DE-RISK done (uncommitted) — READY TO DEPLOY BATCH + flip IG on.

## ✅ CONTENT DE-RISK COMPLETE (uncommitted on main working tree, needs deploy):
- **Vanity links**: _inject_utm (social_posting_service.py) rewrites rigacap.com URLs → clean per-platform vanity (rigacap.com/ig/track-record, /x/, /t/); tiktok untouched; emails/already-vanity safe. App.jsx: added VanityRedirect component + routes /x/:dest /ig/:dest /t/:dest → Navigate to /<dest>?utm_source=...&campaign=post (attribution on redirect, no UTM funnel string in caption). Unit-tested ✓, frontend builds ✓.
- **Hashtags DROPPED entirely** (Erik hates them + junk reach + spam-adjacent): ai_content_service (trade map + 2 insight lines) + social_content_service (5 templates) all "". publish guard `if post.hashtags` handles empty.
- **Cards → paper/claret** (were ooogly DARK): chart_card_generator.py generate_text_card + generate_trade_card + _draw_price_chart flipped (bg BRAND_LIGHT, text/symbol BRAND_DARK, price line BRAND_ACCENT claret, hairline grid, light label boxes, ink badges). Text card RENDERED+VERIFIED on-brand (scratchpad/card_text_sample.png). Trade card = same flips, not locally renderable (needs live price data). track_record_chart already paper. FONT note: matplotlib default DejaVu sans, not Fraunces/IBM Plex (optional future polish).

## ✅ CONTENT DE-RISK DEPLOYED (commit 38b0bb9, deploy GREEN Jul 10). Erik flipped INSTAGRAM back ON via toggle himself (toggle works E2E). Live now: clean vanity links, no hashtags, paper/claret cards.

## 📊 TIER WF COMPARISON (from tier_curves_21y.json, INTERNAL — Core is internal-only): 21yr Core 7.3%/0.76/−18%($393k) < Preserver 8.7%/0.88/−13%($500k) < Maximizer 14.5%/0.95/−20%($1.39M). Preserver BEATS Core on all 3 (sleeves add value). LAST-12mo (May25-May26): Core +34.9%/−4%, Preserver +34.6%/−4% (≈IDENTICAL to Core — regime was rotating-bull whole time → Preserver routes to t30v=Core; only diverges in calm_bull + capitulation), Maximizer +104.8%/−8%($205k, breakout sleeve, HOT stretch not a promise). Chart PNGs in scratchpad (last12mo_tiers.png). Rendered brand-styled.

## 🔜 NEXT (Erik's asks, in order): (1) RUN tier sim Jul-10-2025→TODAY (fresh WF, ~2min, rejected twice — re-fire when Erik says go; script ready: START 2024-06-01/END 2026-07-10, EXT=False, slice trailing-12mo). (2) BUILD: /app Simulated-Portfolio widget (bottom of portal) → TIER-AWARE: Preserver users see Preserver+Maximizer (Maximizer=upsell nudge), Maximizer users see Maximizer; NEVER Core. (3) BUILD: public Track-Record sim portfolio → end at PREVIOUS MONTH-END (don't expose current holdings/live signals). (4) GOOGLE ADS rework (Erik excited "babbabinga" — Maximizer-beats-market opens aggressive-growth keywords vs old defensive "barely reach SPY"; need Ads data from Erik). (5) live-book Core→Preserver promotion after ~Jul-14 shadow. Plus parked: social profiles, email drip redesign, tier badge, LinkedIn ads, 10y-vs-21y.
## KEY: live admin/model book = CORE (t30v), NOT Preserver ruleset (Erik confirmed); Preserver==Core in rotating_bull + range_bound. Shadow (~Jul7 start, ~Jul14 = 1wk) validates divergent-regime sleeve behavior.

## ⚠️⚠️ CANONICAL-NUMBERS RULE (Erik frustrated by whiplash — DO NOT REPEAT): RECENT-window tier numbers come ONLY from the STANDALONE run (scripts/recent_tier_curves.json = 2024-06→2026-07-09 EXT=False, OR tier_vintages_daily.py methodology). The 21-YEAR file (tier_curves_21y.json, EXT=True) is ONLY for the 21-YEAR headline — slicing a recent window out of it DRIFTS HIGH (sleeve/vol-brake rolling state differs). This caused the $205k(21yr-slice) vs $163k(clean) double-take AND the earlier 26.5 vs 31.3 one. NEVER slice recent from the 21yr file.

## 📇 CLEAN RECENT NUMBERS (from recent_tier_curves.json, data through Jul 9 2026): trailing-12mo (Jul9'25→Jul9'26, $100k): Preserver +25.8%/$126k, Maximizer +63.5%/$163k, S&P +20.7%/$121k. Maximizer best 12mo window = +85%/$185k (yr ending May'26); does NOT cleanly hit 100% in clean run. Jul1→Jul1: Pres +31%/Max +68%/$168k.

## 🎁 DAD CARD (private, not public — lighter framing OK): /Users/erikkins/Desktop/rigacap-maximizer-card.png ($163,000, Georgia serif brand-fallback since no Fraunces TTF local) + rigacap-year-table.html (Preserver/Maximizer/S&P table). Both consistent on $163k.

## ✅ LAUNCH SEQUENCE SHIPPED: Card #1 POSTED to X(x.com/rigacap/status/2075632566514667745)+Threads+IG. Cards 2-5 SCHEDULED Mon-Thu Jul13-16 @9amET(13:00 UTC) on X/IG/Threads (12 SocialPosts status=scheduled in prod DB; scheduler fires them; editable in Social tab). Threads FLIPPED BACK ON (toggle now X/IG/Threads ON, tiktok off). Posting mechanism: create SocialPost(platform, text_content, hashtags="", image_s3_key=https://rigacap.com/launch-cards/launch-N.png, status) → social_posting_service.publish_post (local, Lambda-env creds). Plain links in caption → _inject_utm vanitizes per-platform at publish. WIDGET (tier-aware /app) PARKED.

## 🎨 PROFILE ASSETS IN FLIGHT: (1) X BANNER rebuilt sharp 1500x500 paper/claret, tagline "Built so you never get a reason to panic-sell" + "One engine two settings—Preserve to Maximize", NO stale numbers → /Users/erikkins/Desktop/rigacap-x-banner.png (source design/brand/profiles/x-banner.png is PNG-only, no HTML). NEEDS TWEAK: avatar overlaps bottom-left (hides sub-line) + mobile crops top/bottom → pull block to vertical center, shift sub up-right. Offered to fix, awaiting. (2) PROFILE BIOS drafted (X≤160/IG≤150/Threads/LinkedIn) — Erik pastes (no bio API). (3) LinkedIn ABOUT rewrite OWED: Erik pasted old one (single-product, "six positions" STALE→now ~20 pos, "friction-adjusted"→walk-forward, add 2-tier Preserver/Maximizer, keep discipline/do-nothing + founder line). Structure: intro/approach/audience/how-it-works/founded.

## 📣 GOOGLE ADS (Erik excited, 2 asks): (1) modify current campaigns/groups for 2-tier story (Maximizer-beats-market opens aggressive-growth keywords vs old defensive "barely reach SPY"); (2) wants Google Ads API access to write directly. REALITY told Erik: I can't self-grant — needs Erik's Google mgr acct + Google approval: developer token (apply, days-wks review), OAuth client+refresh token, creds→env, then build google-ads integration. No existing Ads API in app. INTERIM: rework from Erik's export (campaigns/keywords/search-terms CSV/screenshots). Offered: (a) send card#1, (b) dev-token walkthrough, (c) both — awaiting.

## KEY DECISIONS: verification (not link-removal) fixed Meta ban; links OK on verified acct — only the UTM funnel string was the risk. Toggle live: IG/Threads OFF, X/TikTok ON (S3 social/platform_toggles.json). Meta account VERIFIED as RigaCap LLC.
## ⭐ RULES: no Core/t30v public; walk-forward not backtest; no tildes; claret+paper only; NEVER `aws lambda --environment` partial; commit/push only when Erik asks. Untracked (exclude): scripts/shapes_tpe.db, .claude/.memory_checkpoint_ts.
