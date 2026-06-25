---
name: project-admin-mobile-app-jun25
description: "The admin iPhone app build — native Expo, push-first, admin-tab data + Ads API; recovered after a lost session"
metadata: 
  node_type: memory
  type: project
  originSessionId: 2dce3134-d861-45c4-a371-80378750f8c0
---

# Admin iPhone App (started Jun 25 2026, recovered from lost session 701a2e93)

**Goal (Erik, L13808 of the Jun-24 session):** an Admin iPhone app to "pop in and check on everything at a moment's notice." Wants: see what users we have at a glance, **largely the admin-tab data**, plus **Ads API integration** for realtime-ish stats. **Never goes on the App Store** → build format unconstrained (Expo dev build / ad-hoc / internal distribution fine).

**Decisions locked:**
- **Native Expo, push-first** (Erik, L13830). Confirmed again Jun 25.
- Scope = **all four glance priorities** + **most admin-tab data** + **Ads API**: (1) monitor scan/pipeline health, (2) approve/act on alerts, (3) growth metrics, (4) live portfolio.

**Existing `mobile/` app (the fork to resolve):** repo already has a real Expo / React Native app `com.rigacap.app` — a **user-facing** app (auth incl. Google/Apple/Face ID, signals tab, signal detail, price charts, regime badges, push notifications, paper brand). NOT a stub. BUT last commit ~**May 5** (~7 weeks stale vs t30v/pricing/parity changes). `mobile/` is gitignored/untracked. Open fork Erik never resolved: bolt admin onto this app vs **separate code stream**. → Leaning **separate Expo app** (admin-only, never app-store, avoids shipping admin screens to subscribers + no brand/auth collision). CONFIRM with Erik before scaffolding.

**Backend is ready — auth + endpoints already exist:**
- Auth: JWT bearer. `get_current_user` → `get_admin_user` (checks `user.is_admin()`, 403 otherwise) in `backend/app/core/security.py:216`. Login via `/api/auth` router. Token type must be `"access"`.
- Admin API: `backend/app/api/admin.py`, mounted at `/api/admin` (and `/api/admin/social`). ~60+ endpoints already: `/stats` (AdminStatsResponse), `/users` (UserListResponse), `/service-status`, `/pipeline-log`, `/model-portfolio` + `/equity-curve` + `/trades`, `/strategies/*`, `/market-regime/current`, `/newsletter/draft`, etc.
- Web admin today = `frontend/src/components/AdminDashboard.jsx` (2971 lines, 11 tabs: Overview, Portfolio, Strategies, Strategy Lab, Auto-Pilot, Social, Newsletter, Leads, Traffic, Hygiene, Users). Desktop-dense. The mobile app should surface a curated glance subset, not clone all 11.
- Ads API: NOT yet wired anywhere (see [[project_ad_conversion_tracking_jun24]] — currently screenshots only, no Google Ads API). The app's ads stats need a NEW backend endpoint that calls the Google Ads API server-side (don't put Ads creds in the app).

**FORK RESOLVED (Jun 25): separate Expo app** → building at repo `mobile-admin/` (sibling of `mobile/`). Reuses `mobile/`'s proven plumbing verbatim where possible: `services/api.ts` (axios+JWT+refresh, /api/auth/refresh), `services/notifications.ts` (registers Expo token to `/api/push/register`), `constants/theme.ts` (paper brand), Expo Router (SDK 54, expo-router 6, react 19). Auth = email/password (+2FA supported) via `/api/auth/login`; gate on `user.role==='admin'` after login (reject non-admins in the app, not just rely on API 403s). Push to Erik's phone = backend `push_notification_service.send_to_user(db, user_id, title, body, data)` already exists — wire admin email alerts (new-account, 0-signal scan, hygiene) to ALSO call this.

**Backend endpoint map for the glance (all live, admin-gated):**
- Growth/users: `GET /api/admin/stats` → {total_users, active_trials, paid_subscribers, expired_trials, disabled_users, new_users_today, new_users_week, mrr}. `GET /api/admin/users?page=&per_page=` → {users:[{id,email,name,role,is_active,created_at,last_login,subscription_status,trial_days_remaining,is_founding}], total,page,per_page}.
- Pipeline health: `GET /api/admin/service-status` → {overall_status, services{}, metrics{}}. `GET /api/admin/pipeline-log`. `GET /api/admin/aws-health`.
- Live portfolio: `GET /api/admin/model-portfolio`, `/model-portfolio/equity-curve`, `/model-portfolio/trades`. `GET /api/admin/market-regime/current`.
- Founding seats: `GET /api/billing/founding-status` (public).
- ADS: NOT built. Google Ads API needs OAuth + developer token server-side (creds NEVER in app). Plan: new `GET /api/admin/ads/summary` wrapping Google Ads API; app Ads tab reads it. Until then app shows "not configured." This is milestone 2 (a real project — see [[project_ad_conversion_tracking_jun24]]).

**SCAFFOLD BUILT (Jun 25) — `mobile-admin/` (git-tracked, like mobile/). Runnable once `npm install` + `eas init`.** See `mobile-admin/README.md`.
- Files: app.json (bundle `com.rigacap.admin`, scheme `rigacapadmin`, projectId placeholder `REPLACE_WITH_eas_init`), eas.json (internal dist), package.json (lean — dropped google/apple/web-browser/screen-orientation/svg vs mobile/). Reused verbatim: services/api.ts, services/notifications.ts, constants/theme.ts.
- New code: services/auth.ts (email/pw + 2FA, **NotAdminError gate: role!=='admin' → reject + clear tokens, never persist**), services/admin.ts (typed wrappers: getStats/getUsers/getServiceStatus/getModelPortfolio/getCurrentRegime/getFoundingStatus/getAdsSummary→null on 404), hooks/useAuth.tsx (admin-gated), app/_layout.tsx (router + notif-tap deep-link), app/(auth)/login.tsx + verify-2fa.tsx, app/(tabs)/_layout.tsx (4 tabs), index.tsx=Glance (health banner + growth grid + founding seats), users.tsx (list + founder/trial/paid badges + sign-out), portfolio.tsx (regime + value/cash/positions, defensive field reads), ads.tsx (milestone-2 placeholder until backend endpoint). components/StatCard, Section.
- NOTE: `tsc` against mobile/'s toolchain showed only ENVIRONMENTAL errors (no node_modules/jsx/lib in mobile-admin) — not code bugs. Code follows mobile/ patterns exactly.

**ADMIN ALERTS → PUSH: DONE (Jun 25, reuses existing push infra).** The admin app registers its Expo token under the SAME erik@rigacap.com user, so pushing to that user reaches the admin app for free. Added `push_notification_service.send_to_admin_email(to_email,title,body,data)` — self-contained (opens own session), ADMIN_EMAILS-gated (never pushes a normal subscriber), best-effort. Wired in 2 places: (a) `email_service.send_admin_alert()` — pushes to THAT to_email only (it's sometimes called in a `for admin in ADMIN_EMAILS` loop → fan-out would duplicate), covers 0-signal scan alarm + hygiene + canary + missing-positions, data.screen=glance; (b) `auth.py _ping_admin_new_signup` — new-account ping, data.screen=users. All 3 files py_compile OK. CAVEAT: pushes also reach the subscriber `mobile/` app if installed on same phone (PushToken has no per-app column) — harmless (own phone); clean fix = add `app` column to PushToken, defer unless it annoys. NOTE: still needs `eas init` + projectId + a device build before any push actually arrives.

**Next steps (in README "Outstanding work"):**
1. `cd mobile-admin && npm install && npx eas init` → paste real projectId into app.json (needed for push tokens).
3. **Ads milestone 2** — build `GET /api/admin/ads/summary` (Google Ads API, dev token + OAuth refresh in Lambda env/Secrets, NEVER in app) returning {spend,clicks,impressions,conversions,cpc,date_range,campaigns[]}. App already renders it.
4. Verify `model-portfolio` real payload shape → tighten types in services/admin.ts.
5. (optional) Add Strategy/Social/Newsletter/Hygiene glance cards later if Erik wants more of the 11 web tabs.

**Recovery note:** this whole thread was reconstructed from transcript `701a2e93-…jsonl` (47MB) after Erik accidentally closed VS Code Jun 25 and lost the live context. Lesson → [[feedback_checkpoint_memory_during_session]].
