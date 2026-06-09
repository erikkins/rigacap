# Email Cadence — 10,000-Foot View

> Source of truth for what arrives in a RigaCap subscriber's inbox over a typical month, and why. Maintained alongside `docs/MarketingNewsletterStrategyCLAUDE.md` (§13–§14). This doc is the operational view; the marketing doc is the strategic principles.

Last updated: 2026-04-28.

---

## TL;DR

A typical active subscriber receives:

- **2 scheduled subscriber emails per week** (Sunday newsletter + Tuesday regime report)
- **Up to 1 lifecycle drip email per week** during the first 90 days, taper to ~0 after
- **0–N event-triggered alerts** (sell alerts, double signals, silent cash) — driven by the strategy, not the calendar
- **Daily digest** if subscribed (Mon–Fri 6 PM ET) — the always-on "what is the system telling you today" email

Total: averages ~3-5 emails/week for an engaged subscriber, mostly weekdays. Per marketing doc §13: *"Email volume is a budget, not a count. If a subscriber consistently receives more than 4-5 emails per week, the cadence is over-saturated — investigate and trim."*

---

## Classification

Every email in the system fits exactly one of these registers. Mixing registers within a single email is the strongest "this feels off" smell.

| Register | Voice | When to use | Examples |
|---|---|---|---|
| **Publication** | Editorial-financial-publication, third person ("the system saw"), measured | Newsletters, regime reports, weekly summaries | `market_measured`, `weekly_regime_report` |
| **Founder** | First person from Erik, conversational, includes "reply to me" affordance | Lifecycle drip, win-back, personal check-ins | `onboarding_drip` (DR-001 through DR-010), win-back |
| **Transactional** | Functional, no editorial voice | Welcome, password reset, receipts | `send_welcome_email`, `send_password_reset_email` |
| **Alert** | Tight, present-tense, action-oriented | Sell alerts, double signals, silent cash | `send_sell_alert`, `send_double_signal_alert` |
| **Admin** | Internal-only, never goes to subscribers | Pipeline health, ticker health, strategy analysis | `send_health_report`, `send_admin_alert` |

---

## Subscriber-Facing Schedule (Recurring)

Times are **ET** (US Eastern, the strategy's native timezone).

| Email | Cron (UTC) | ET | Days | Audience | Register |
|---|---|---|---|---|---|
| **Daily digest** | `0 22 ? * MON-FRI` | 6 PM | Mon–Fri | All daily-digest subscribers | Publication-tinted (signal data) + alert |
| **Regime report** | `0 13 ? * TUE` | 9 AM | Tue | All subscribers | Publication |
| **Market, Measured** (newsletter) | `0 23 ? * SUN` | 7 PM | Sun | All subscribers + free list | Publication |
| **Onboarding drip** | `0 14 * * ?` | 10 AM | Daily check, fires only if subscriber matches a step's trigger | Per-subscriber lifecycle | Founder |

### Daily digest (`0 22 ? * MON-FRI` — 6 PM ET)
- Composed by `scheduler_service.send_daily_emails()` reading dashboard.json
- **Per-subscriber filtered** (as of commit `8fc7835`) — held positions removed from monitoring section
- Freshness gate: HOLDS if dashboard.json `generated_at` doesn't match today

### Regime report (`0 13 ? * TUE` — 9 AM ET)
- Was Monday until commit `545060e` (Apr 27) moved to Tuesday so it doesn't compete with Sunday newsletter
- Tactical/analytical voice, 300-600 words

### Market, Measured (`0 23 ? * SUN` — 7 PM ET)
- Newsletter generation runs Saturday 8 PM ET (locked draft); cron sends Sunday 7 PM ET
- 800-1,500 words, editorial register
- Per memory `feedback_newsletter_no_signals.md`: NEVER includes signals or tickers

### Onboarding drip (`0 14 * * ?` — 10 AM ET)
- Daily *trigger check*, not a daily *send*
- Per-subscriber state machine: Day 0 / 3 / 5 / 7 / 8 (5 steps shipped)
- Marketing doc §14 specs 10 steps: DR-001 through DR-010 — **5 missing event-triggered ones not yet shipped** (see Gaps below)

---

## Subscriber-Facing Schedule (Event-Triggered, Polled)

These run on a clock, but only send if a real event happened. Empty days produce no emails — that's the point.

| Email | Cron (UTC) | ET | Days | Trigger inside cron | Register |
|---|---|---|---|---|---|
| **Double signal alert** | `0 21 ? * MON-FRI` | 5 PM | Mon–Fri | Symbol persisted as ensemble signal for 2nd consecutive day | Alert |
| **Sell alert / Silent Cash** | `0/5 13-19 ? * MON-FRI` | every 5 min, 9 AM–3 PM | Mon–Fri | Position trailing stop hit OR cash-mode regime entered | Alert |

### Why every 5 min for intraday
- Sell alerts must fire same-day to be useful; once-a-day at 6 PM is too late for stop-out actionability
- Per memory `397807b`: Silent Cash alert only fires on fresh signals, not monitoring (avoids alert spam)
- Memory `feedback_signal_consistency.md`: all alerts read from dashboard.json only

---

## Subscriber-Facing Schedule (Event-Triggered, On-Demand)

Fire instantly when the event happens, no cron involved.

| Email | Trigger | Register |
|---|---|---|
| `send_welcome_email` | Account creation (Stripe webhook or signup) | Transactional |
| `send_password_reset_email` | User clicks "forgot password" | Transactional |
| `send_winback_email` | Trial ended without paid conversion | Founder (per marketing doc §14 RE-001/RE-002/RE-003) |
| `send_referral_reward_email` | Referral converts to paid | Transactional |
| `send_post_approval_notification` (T-24h, T-1h) | Social post pending review | Admin (Erik only) — but uses subscriber-facing send infrastructure |

---

## Admin-Only Schedule (Erik's Inbox Only)

Never to subscribers. Different `AdminEmailService` class. Allowlist = `ADMIN_EMAILS` env var.

| Email | Cron (UTC) | ET | Days | What |
|---|---|---|---|---|
| **Pipeline health report** | `30 11 * * ?` | 7:30 AM | Daily | Health monitor's GREEN/YELLOW/RED summary; only sends if Y or R (or `always_send=true`) |
| **Ticker health alert** | `0 11 ? * MON-FRI` | 7 AM | Mon–Fri | Position tickers with stale/missing data |
| **Admin health check** | `0 11 ? * MON-FRI` | 7 AM | Mon–Fri | Separate from pipeline health — broader system check |
| **Strategy analysis** | `30 22 ? * FRI` | 6:30 PM | Fri | Biweekly auto-analysis output |
| **Engagement opportunities** | `0 13 ? * MON-FRI` | 9 AM | Mon–Fri | Reply suggestions across fintwit accounts |
| **Post notifications** | `0 * * * ?` | every hour | Daily | Social post approval reminders (T-24h, T-1h) |
| **Monthly recap** | `0 14 1 * ?` | 10 AM | 1st of month | Self-summary |

Plus admin-only alerts on infra:
- Email-failure report (when daily emails fail >N retries)
- AI generation complete (TPE / WF jobs)
- Switch notification (auto-switch fired)

---

## Internal-Only Schedules (No Email)

These don't email anyone but are part of the cron layout for completeness.

| Cron | UTC | ET | What |
|---|---|---|---|
| `scanner` | 30 20 MON-FRI | 4:30 PM | Daily price scan + dashboard.json export |
| `warmer` | rate(5 min) | always | Lambda keep-warm |
| `nightly_data_hygiene` | 30 22 MON-FRI | 6:30 PM | Corp-actions poll + asset-ID verification (now bulk-fetch) |
| `nightly_wf` | 0 0 TUE-SAT | 8 PM | 90-day walk-forward for missed-opportunities |
| `pickle_rebuild` | 0 0 SUN | 8 PM Sun | Weekly pickle archive |
| `biweekly_tpe` | 0 0 TUE | 8 PM Tue | TPE adaptive-params optimization |
| `generate_social_posts` | 0 1 TUE-SAT | 9 PM | Generate posts from nightly WF trades |
| `intraday_monitor` | 0/5 13-19 MON-FRI | every 5 min | Position monitoring (drives sell alerts above) |
| `publish_posts` | 0/15 always | every 15 min | Auto-publish approved scheduled social posts |
| `new_user_check` | 0 1 * * ? | 9 PM daily | New-user follow-up |

---

## Visual Heatmap — A Typical Week

What lands in an engaged subscriber's inbox each day. Times are ET. Items in `()` are conditional.

```
Sun ─── 7 PM     Newsletter (Market, Measured)
        (anytime)  Onboarding drip if Day-N matches

Mon ─── 6 PM     Daily digest
        9 AM–3 PM (sell alert if stop hit)

Tue ─── 9 AM     Regime report
        6 PM     Daily digest
        9 AM–3 PM (sell alert if stop hit)

Wed ─── 6 PM     Daily digest
        9 AM–3 PM (sell alert if stop hit)

Thu ─── 6 PM     Daily digest
        9 AM–3 PM (sell alert if stop hit)

Fri ─── 5 PM     (Double signal alert if symbol persisted)
        6 PM     Daily digest
        9 AM–3 PM (sell alert if stop hit)

Sat ─── (silent — no scheduled subscriber emails)
```

**Active subscriber baseline:** 5 daily digests + 1 regime report + 1 newsletter = **7 scheduled emails per week**, plus alerts and drip.

That's higher than the marketing doc's "2-3 scheduled per week" guidance — see Gap #2 below.

---

## Conflicts and Gaps Surfaced by This Audit

### 1. Daily digest cadence may be over-saturated vs. doc target

Marketing doc §13: *"2-3 scheduled emails per week (newsletter + regime report + maybe one drip)."*

Reality: subscribed-to-daily-digest subscribers get **5 daily digests + 2 weekly briefings = 7 scheduled emails per week**.

**Decision needed:** Is daily digest truly opt-in (subscribers actively chose it), in which case 7/week is consented and fine? Or is it default-on, making 7/week an over-saturation risk per doc?

Looking at code: `u.get_email_preference('daily_digest')` is checked at scheduler.py:1705. So it IS a preference. Default likely on. Worth confirming + maybe consider making daily digest opt-in (default off, user opts in).

### 2. Drip emails — 5 of 10 specced are missing

Marketing doc §14 specs DR-001 through DR-010. Memory says 5 are shipped. Missing/aspirational:
- **DR-005** (first stop-out) — needs event hook on trailing-stop fire
- **DR-006** (first profitable exit) — needs event hook on profitable close
- **DR-008** (7-day quiet streak) — needs day-counter against last-signal date
- **DR-009** (Day 60 methodology spotlight) — content draft needed
- **DR-010** (Day 90 retention) — content draft needed

DR-005, DR-006, DR-008 are the highest-leverage because they fire at *moments of subscriber doubt* (a stop = "did I just lose money?" / silence = "is this product worth it?") — exactly when reinforcement is most useful.

### 3. Re-engagement sequence (RE-001 through RE-003) — not implemented

Doc §14 specs three re-engagement emails for lapsed trials. Codebase has `send_winback_email` (single email) but not the three-step worked-example sequence.

The most powerful one (RE-001 — fire when a trial-exited prospect's signal fires 24-48h later) requires Marketing Rule attorney sign-off per the doc. Could draft content + infra now, gate on attorney approval.

### 4. Tuesday is heavy (regime report 9 AM + daily digest 6 PM + biweekly_tpe at 8 PM)

For an opted-in subscriber, Tuesday delivers TWO subscriber emails plus an internal optimization that could spawn admin emails. Not over the budget but the busiest day. Sun and Mon are also two-email days (newsletter Sun, digest Mon). 

Doc §13: *"Wednesday-Friday (variable): drip emails / re-engagement. Schedule to avoid Sunday-Tuesday window."* — not currently enforced; onboarding_drip fires daily.

### 5. No subscriber preference UI for cadence

Doc §13: *"Build subscription preference management from day one. Subscribers should be able to choose which email types they want."*

Code has `get_email_preference()` checks for `daily_digest`, `sell_alerts`, `double_signals`, `intraday_signals`, `market_measured`. So preferences exist. Need to check: is there a UI where subscribers manage these? If not, the preferences are effectively defaults-only.

### 6. No silent-cash standalone email — currently bundled into daily digest only

When the system is in cash mode and there are no signals, the daily digest still fires (with a "system is quiet" body). Doc §11 voice line *"When the system stays quiet, that's the discipline working"* is on-brand. But there's no separate `silent_cash_alert` channel — should there be? Probably no; redundant with daily digest's quiet-day rendering.

---

## Suggested Cadence Changes (For Discussion)

In priority order, smallest first:

1. **Confirm daily-digest opt-in default**, surface in user settings UI
2. **Ship DR-005, DR-006, DR-008** (highest-leverage doubt-moment drips) — content drafts + event hooks
3. **Move biweekly_tpe / nightly_wf away from Tuesday** to balance the week
4. **Re-engagement sequence (RE-001 through RE-003)** — design + attorney review
5. **Subscriber preference UI** if not already complete

None of these are urgent; #2 and #4 are the real value-adds.

---

## Operational Notes

- **All subscriber-facing emails read from dashboard.json (or DB)** — never compute on-the-fly. Source of truth = dashboard. (Memory `feedback_signal_consistency.md`)
- **Freshness gate on subscriber emails** — `_validate_data_freshness()` before send (scheduler.py). Stale dashboard → emails HELD + admin alert. (Memory `feedback_never_blast_without_target.md`)
- **`target_emails` admin override** bypasses freshness + subscription checks for testing. Always use this for manual sends.
- **Email failures retry up to 3 times** with exponential backoff (visible in CloudWatch as `Email to X failed (attempt N/3)`)
- **List-Unsubscribe + List-Unsubscribe-Post (RFC 8058)** headers on all subscriber emails — done
- **Per-subscriber filtering** of held positions in monitoring section — done as of commit `8fc7835`
- **No-cache headers on dashboard.json** — done as of commit `3ded73c`
