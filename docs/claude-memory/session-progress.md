---
name: session-progress
description: "Live session snapshot (auto-checkpointed ~15min) — what's done, in flight, and next"
metadata:
  node_type: memory
  type: project
  originSessionId: 2dce3134-d861-45c4-a371-80378750f8c0
---

# Session snapshot — Jul 10 2026 (Fri) — 🚨 META ACCOUNT RESTRICTED (fraud/scam flag). 2-tier rebrand LIVE+healthy 2 days. Erik back from COVID.

## 🚨🚨 URGENT (Jul 10) — INSTAGRAM/META RESTRICTION: "rigacapital" (RigaCap IG/FB) got restricted Jul 2 for "fraud, scams and deceptive practices" → **can't share links until Aug 1**, 21 days to appeal ("Request review"). CAUSE = account PATTERN not one post: perf/"signals" claims + external link in EVERY post + #TradingResults/#AlgoTrading hashtags = Meta's investment-scam classifier. Trigger example = the June "Monthly Recap" IG post (DARK off-brand card, link, scammy hashtags — it's a TEMPLATE post from social_content_service.py monthly-recap, ai_generated=False). RISK: continued auto-posting same pattern → escalation to PERMANENT ban.
## PLAN (proposed, awaiting Erik go): (1) PAUSE IG/FB auto-posting NOW (stop the bleeding) — check if simple flag flip; (2) DRAFT the appeal (I draft, Erik submits) — lean on legitimacy: RigaCap LLC registered/D&B-verified, signals-only (no custody/not broker/RIA), on-site disclaimers+ToS, walk-forward transparency, past-perf≠future; (3) REWORK content so it can't re-trigger: KILL external links in IG/FB posts→"link in bio", soften results/signals framing→lead with education/insight, drop #TradingResults/#AlgoTrading/#TradingSignals, on-brand claret/paper cards (dark card is off-brand+scam-adjacent). Erik agreed socials>badge bc profiles/posts still show Core+scammy. Social publishers: social_posting_service.py (post_to_twitter/instagram/threads/tiktok), post_scheduler_service, social_content_service (templates incl monthly recap), scheduler.py _publish_scheduled_posts. NO bio/profile-update API found (bios are manual).

## ⏸️ DEFERRED by this: badge (found it — entitlement via AuthContext→/api/auth/me→subscription.has_maxpp_addon; Maximizer if addon ELSE Preserver — NEVER both, Erik confirmed; ~15min), email drip redesign, dashboard-book-swap-to-Preserver (needs shadow promotion), public walk-forward trades on TrackRecord, 10y-vs-21y.

## OG snapshot header (still true):

## ✅ DEPLOYED & CONFIRMED GREEN (main 19a9eb2, "Deploy RigaCap" run 28967245050 = success 4m, Jul 8). Site healthy Jul 10: rigacap.com HTTP 200, track-record-curves.json serving. 2 days of live daily-scans/emails/social on new tier numbers + Sonnet 5. Merge research→main was CLEAN. SSOT double-banner resolved; canonical_numbers.json flagged superseded.

## ✅ CANONICAL (SSOT §1): 21yr **Preserver 8.6%/0.88/−13%** · **Maximizer 14.5%/0.95/−20%** vs S&P 9.8%(price)/−55%, raw 13.2%/−57%. Recent2yr **Pres 31.3%/1.75/−12.9%** · **Max 48.9%/1.94/−17.3%** (=dial 31/49, CLEAN 2016+). $100k→$500k/$1.39M/$535k. 2008 both ~flat vs −37%. Recovery Pres 2.0yr(2×). Preserver adviser: −0.9%/+1.6%/0.51corr/5-of-6-cash. Core/t30v 7.3/0.76/−18 INTERNAL ONLY.

## ✅ WHAT SHIPPED: pages (Landing/TrackRecord+TierRaceChart/ForAdvisers/Methodology), 7 blogs, backend content (ai_content model=claude-sonnet-5, email drips, newsletter, engagement), launch cards (5 PNGs), SSOT. All "walk-forward" not "backtest".

## 🔜 TOMORROW ("fixing our socials"): (1) EMAIL DRIP REDESIGN — Erik: drips are "debbie downer", missing the exciting +31%/+49% recent numbers, fonts too small, uninspired. I started a welcome-hero redesign (bold serif headline + big +31/+49 stat block) then REVERTED to ship clean — REBUILD it + apply hero-stat-block + bigger fonts across welcome + onboarding drips (HTML+text), all 12 emails. (2) SOCIAL ENGINE voice pass + validate Sonnet 5 output (test via test_ai_content Lambda). (3) **UPDATE ALL SOCIAL SITES (out-of-repo, MANUAL/API)** — Erik added: X/Twitter, Instagram, Threads, LinkedIn profiles → bios, pinned posts, header/profile images to 2-tier positioning (currently likely single-product / old +384%/~37% numbers per SSOT §3.5-3.6). Draft new bio copy for Erik; use Twitter API v2 / IG Graph API where profile edits are possible; post the fresh launch-card PNGs. Also Stripe product description. (4) leftovers: deprecated v1 routes (Core, not nav-linked), investor PDFs, 10y-vs-21y decision (Erik leaning keep-21y+caveat).

## 📌 KEY: welcome email founder-line is CORRECTLY gated (is_founding from Stripe price) — non-founders get clean version, verified. To SEND test emails: pull SMTP creds from Lambda env (aws lambda get-function-configuration rigacap-prod-worker) → local email_service (uses local templates); SES not set up. Samples on Erik's Desktop /rigacap-email-samples/.
## ⭐ RULES: no Core/t30v public; walk-forward not backtest; no tildes on nums; Sharpe>Buffett→survivorship caveat; tables "RigaCap Preserver/Maximizer". GATE no tier CHARGES until Maximizer signals live. Left untracked: scripts/shapes_tpe.db, .claude/.memory_checkpoint_ts.
