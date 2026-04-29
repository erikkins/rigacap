---
name: Numbers citations registry — single source of truth for performance claims
description: Registry doc enumerating every surface where performance numbers (returns/Sharpe/drawdown/win rate) are cited; walk it whenever canonical numbers change.
type: project
originSessionId: 1081317d-f863-470f-ab07-65ddc614e856
---
## What it is

`docs/numbers-citations-registry.md` is the single source of truth for **every place** RigaCap cites performance numbers across investor materials, marketing, frontend, emails, and social.

**Why:** Numbers were drifting. The over-fit Trial 37 run produced +384%/+603%/~37%/30% MaxDD that propagated to ~15+ surfaces. When the clean-data re-run on 2026-04-28 showed +160%/21.1%/0.92/20.4% MaxDD, we needed a registry to update everything coherently in one pass instead of leaving inconsistent claims across surfaces.

**How to apply:**
- When canonical numbers change (new run, validation, refresh), open the registry and walk every `STALE` row before any partial update goes out.
- Section 1 holds canonical numbers; sections 3.1-3.6 enumerate surfaces.
- Section 4 is the deploy sequence (internal docs first, then external HTML, then frontend, then email, then social).
- Section 5 is the vintage log — track which run produced which set of numbers + when retired.

**Critical principle:** No partial updates. If you can't update all surfaces in one pass, don't update any. Inconsistent claims across surfaces are worse than uniformly stale claims.

**Out-of-repo surfaces** (Twitter/Instagram bios, Stripe product descriptions, podcast writeups) can't be grep'd — checklist in §3.6 must be walked manually.
