# RigaCap Admin (mobile)

A **private, admin-only** native app (Expo / React Native) to check on RigaCap
from your phone — pipeline health, growth, users, the live portfolio, and ad
stats. **Never goes on the App Store** — distributed to your own devices via EAS
internal/dev builds.

Separate from `../mobile/` (the subscriber app) on purpose: no risk of shipping
admin screens to subscribers, no auth/brand collision. It reuses that app's
proven plumbing (`services/api.ts`, `services/notifications.ts`,
`constants/theme.ts`).

## Stack
- Expo SDK 54, Expo Router (file-based), React 19, TypeScript
- Auth: email/password + 2FA against `https://api.rigacap.com`, **gated on
  `user.role === 'admin'`** (non-admins are rejected at login)
- Push: Expo push, registered via the existing `POST /api/push/register`

## Screens (`app/(tabs)/`)
- **Glance** (`index.tsx`) — pipeline-health banner (`/api/admin/service-status`),
  growth metrics (`/api/admin/stats`), founding-seat counter
  (`/api/billing/founding-status`). Pull to refresh.
- **Users** (`users.tsx`) — accounts newest-first (`/api/admin/users`) with
  founder / trial / paid / disabled badges. Sign-out lives here.
- **Portfolio** (`portfolio.tsx`) — live model portfolio + regime
  (`/api/admin/model-portfolio`, `/api/admin/market-regime/current`).
- **Ads** (`ads.tsx`) — Google Ads spend/clicks/conversions. **Milestone 2:**
  shows "not configured" until the backend `/api/admin/ads/summary` endpoint
  exists (see below).

## First-time setup
```bash
cd mobile-admin
npm install
npx eas init          # creates the EAS project → paste its projectId into app.json
                      # (extra.eas.projectId, currently "REPLACE_WITH_eas_init")
npx expo start        # dev (Expo Go won't include native push; use a dev build)
# Device build (push works on a physical device only):
npx eas build --profile development --platform ios
```

## Outstanding work
1. **`extra.eas.projectId`** in `app.json` — set after `eas init` (required for
   push tokens).
2. **Route admin alerts to push.** The backend already has
   `push_notification_service.send_to_user(db, user_id, title, body, data)`.
   Wire the existing admin email alerts (new-account ping, 0-signal scan alarm,
   hygiene) to also call it with Erik's user_id and a `data.screen` hint
   (`users` / `portfolio`) so taps deep-link.
3. **Ads API (milestone 2).** Build `GET /api/admin/ads/summary` server-side:
   Google Ads API with a developer token + OAuth refresh token (credentials live
   in Lambda env / Secrets Manager — **never** in the app). Return
   `{spend, clicks, impressions, conversions, cpc, date_range, campaigns[]}`.
   The Ads tab renders it with zero further UI work.
4. **Verify shapes.** `model-portfolio` fields are read defensively (multiple
   key-name fallbacks); confirm against the real payload and tighten the types
   in `services/admin.ts`.
