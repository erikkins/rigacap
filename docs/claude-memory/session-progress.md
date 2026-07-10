---
name: session-progress
description: "Live session snapshot (auto-checkpointed ~15min) — what's done, in flight, and next"
metadata:
  node_type: memory
  type: project
  originSessionId: 2dce3134-d861-45c4-a371-80378750f8c0
---

# Session snapshot — Jul 10 2026 (Fri) — 2-tier rebrand LIVE. Meta restriction RESOLVED. Built per-platform posting toggle (READY TO DEPLOY).

## ✅ META RESTRICTION RESOLVED: IG/FB "rigacapital" was restricted Jul 2 (fraud/scam, no-links). Erik did Meta's identity/business VERIFICATION (email→code) → "You can post links now" = LIFTED. Appeal draft NOT needed (moot). BUT the re-trigger risk = the content PATTERN (perf claims + in-post link + #TradingResults/#AlgoTrading + dark off-brand card). De-risk still TODO before resuming IG posting.

## 🔨 BUILT THIS TURN — per-platform posting toggle (Erik wanted softer pause than blanking creds). NOT committed/deployed yet (on main working tree, awaiting Erik's push go):
- NEW backend/app/services/social_platform_toggles.py (S3 social/platform_toggles.json, get/set/is_platform_enabled, cached 30s, fail-open all-on)
- GUARD in post_scheduler_service.check_and_publish (skips paused platform like a cooldown, post stays pending). Only 1 publish path (scheduler._publish_scheduled_posts→check_and_publish).
- API in app/api/social.py: GET/POST /api/admin/social/platform-toggles (get_admin_user auth)
- UI in SocialTab.jsx: "Platform posting" panel, 4 switches (twitter/instagram/threads/tiktok), fetchWithAuth. Frontend builds clean, backend compiles.
- PRE-STAGED S3 state: {twitter:on, instagram:OFF, threads:OFF, tiktok:on}.

## ⏸️ CURRENT PAUSE STATE (temp hack): IG+Threads posting paused by BLANKING INSTAGRAM_BUSINESS_ACCOUNT_ID + THREADS_USER_ID on rigacap-prod-worker env (safe-RMW, full backup at scratchpad/worker-env-backup-META-PAUSE.json). FINISH: (1) deploy toggle, (2) RESTORE those 2 env IDs from backup → toggle governs cleanly.

## 🔜 QUEUE: deploy+finish toggle → DE-RISK CONTENT (in-post links→link-in-bio, drop scammy hashtags, soften framing, on-brand claret cards vs dark) → then resume IG. Also: email drip redesign (+31/+49 energy, bigger fonts), social engine voice pass, UPDATE ALL SOCIAL PROFILES (bios/pinned, still Core), tier BADGE on dashboard (entitlement via /api/auth/me subscription.has_maxpp_addon → Maximizer else Preserver, NEVER both), dashboard portfolio→Preserver book (needs shadow promotion), public WF trades on TrackRecord, LinkedIn as NEW AD channel (Erik flagged, $250k+ audience), 10y-vs-21y.
## ⭐ RULES: no Core/t30v public; walk-forward not backtest; NEVER `aws lambda ... --environment` partial (use safe-RMW full read→modify→write); commit/push only when Erik asks.
