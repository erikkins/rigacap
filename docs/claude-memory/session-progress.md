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

## 🔜 NEXT: DEPLOY the batch (commit+push main → CI/CD) → then FLIP INSTAGRAM back ON via Social-tab toggle (currently paused). Then: update social PROFILES (bios/pinned still Core), email drip redesign (+31/49 energy, bigger fonts), tier BADGE on dashboard, LinkedIn ad channel, public WF trades on TrackRecord, 10y-vs-21y.

## KEY DECISIONS: verification (not link-removal) fixed Meta ban; links OK on verified acct — only the UTM funnel string was the risk. Toggle live: IG/Threads OFF, X/TikTok ON (S3 social/platform_toggles.json). Meta account VERIFIED as RigaCap LLC.
## ⭐ RULES: no Core/t30v public; walk-forward not backtest; no tildes; claret+paper only; NEVER `aws lambda --environment` partial; commit/push only when Erik asks. Untracked (exclude): scripts/shapes_tpe.db, .claude/.memory_checkpoint_ts.
