---
name: session-progress
description: "Live session snapshot (auto-checkpointed ~15min) — what's done, in flight, and next"
metadata: 
  node_type: memory
  type: project
  originSessionId: 2dce3134-d861-45c4-a371-80378750f8c0
---

# Session snapshot — Jun 25 2026

**Context:** Built + shipped the RigaCap **admin mobile app** (Expo, `mobile-admin/`). Erik is live-testing it on his iPhone (EK17) and filing fixes. Full detail [[project_admin_mobile_app_jun25]]. Checkpoint discipline active [[feedback_checkpoint_memory_during_session]].

**Done + deployed this session:**
- App scaffold (Glance/Users/Portfolio/Ads, email+2FA, role=admin gate) → EAS preview build installed on EK17 (project `@rigacap/rigacap-admin`, projectId `4c1d1b71`).
- Admin alerts → push (backend, prod). 
- **Stats/MRR fix (prod, commit `07c746e`):** `_exclude_test_users` drops +test/@example/admin emails from total/new-today/new-week/trials/paid; MRR off stale $10→$129 est (→$0 now). Erik sees via pull-to-refresh.
- **App fixes (committed, in the building OTA build):** Portfolio now requests `portfolio_type=live` (API returned nested {live,walkforward}) + real fields; Glance health banner taps → `app/services.tsx` per-service detail; **EAS Update/OTA enabled** (updates.url + runtimeVersion).

**In flight:** OTA-capable iOS build `12136de0-ea0f-45fc-9e30-2dcd05058945` (watcher `bra62aokj`). When done → Erik installs it ONCE (new QR); after that all JS changes ship via `eas update --branch preview` (no rebuild). Current on-phone build is NOT OTA-capable.

**Next:** install new build → verify Portfolio + service detail + a real push. Then Ads milestone-2 endpoint still TODO. Dev server `b6cbe2vtu` may still be running on :8081.
