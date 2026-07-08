---
name: session-progress
description: "Live session snapshot (auto-checkpointed ~15min) — what's done, in flight, and next"
metadata:
  node_type: memory
  type: project
  originSessionId: 2dce3134-d861-45c4-a371-80378750f8c0
---

# Session snapshot — Jul 8 2026 — 🚀 SHIPPED LIVE. 2-tier rebrand DEPLOYED to main. Tomorrow: email/social design polish.

## ✅ DEPLOYED (pushed to main 19a9eb2, "Deploy RigaCap" run 28967245050 in progress ~4min): full 2-tier rebrand. Merge research/shape-diversifiers→main was CLEAN (main already had Preserver/Maximizer engine+Stripe from earlier; research only added marketing). Frontend prod-built 2×. SSOT double-banner resolved (removed stale Jul-1 Core banner), canonical_numbers.json flagged superseded.

## ✅ CANONICAL (SSOT §1): 21yr **Preserver 8.6%/0.88/−13%** · **Maximizer 14.5%/0.95/−20%** vs S&P 9.8%(price)/−55%, raw 13.2%/−57%. Recent2yr **Pres 31.3%/1.75/−12.9%** · **Max 48.9%/1.94/−17.3%** (=dial 31/49, CLEAN 2016+). $100k→$500k/$1.39M/$535k. 2008 both ~flat vs −37%. Recovery Pres 2.0yr(2×). Preserver adviser: −0.9%/+1.6%/0.51corr/5-of-6-cash. Core/t30v 7.3/0.76/−18 INTERNAL ONLY.

## ✅ WHAT SHIPPED: pages (Landing/TrackRecord+TierRaceChart/ForAdvisers/Methodology), 7 blogs, backend content (ai_content model=claude-sonnet-5, email drips, newsletter, engagement), launch cards (5 PNGs), SSOT. All "walk-forward" not "backtest".

## 🔜 TOMORROW ("fixing our socials"): (1) EMAIL DRIP REDESIGN — Erik: drips are "debbie downer", missing the exciting +31%/+49% recent numbers, fonts too small, uninspired. I started a welcome-hero redesign (bold serif headline + big +31/+49 stat block) then REVERTED to ship clean — REBUILD it + apply hero-stat-block + bigger fonts across welcome + onboarding drips (HTML+text), all 12 emails. (2) SOCIAL ENGINE voice pass + validate Sonnet 5 output (test via test_ai_content Lambda). (3) leftovers: deprecated v1 routes (Core, not nav-linked), investor PDFs, 10y-vs-21y decision (Erik leaning keep-21y+caveat).

## 📌 KEY: welcome email founder-line is CORRECTLY gated (is_founding from Stripe price) — non-founders get clean version, verified. To SEND test emails: pull SMTP creds from Lambda env (aws lambda get-function-configuration rigacap-prod-worker) → local email_service (uses local templates); SES not set up. Samples on Erik's Desktop /rigacap-email-samples/.
## ⭐ RULES: no Core/t30v public; walk-forward not backtest; no tildes on nums; Sharpe>Buffett→survivorship caveat; tables "RigaCap Preserver/Maximizer". GATE no tier CHARGES until Maximizer signals live. Left untracked: scripts/shapes_tpe.db, .claude/.memory_checkpoint_ts.
