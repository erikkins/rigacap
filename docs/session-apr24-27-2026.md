# Session Notes: April 24-27, 2026

## What Shipped

### Editorial Redesign (Pervasive)
- **Tour panels** — Fraunces titles, rule-border illustrations, ink/paper email cards
- **Blog pages (all 11)** — full conversion from dark theme to editorial palette
- **Blog index** — editorial grid with claret badges, Fraunces headings
- **Login/signup modal** — claret CTA, paper header, outlined Apple button
- **Newsletter archive page** (`/newsletter`) — masthead, archive list, signup at bottom
- **Newsletter issue viewer** (`/newsletter/:date`) — 4-section editorial layout with section numbers, breaks, signoff
- **Brand kit** (`design/brand/brand-kit.html`) — full rewrite: bitone mark, paper/ink/claret, Fraunces/IBM Plex, voice guidelines
- **Social avatars** — paper + ink versions, properly centered using icon-halo approach, 400px + 1024px PNGs
- **Market regime page** — converted to editorial
- **Cookie consent, 404, unsubscribe pages** — editorial palette
- **Chart card generator** — BRAND_LIGHT replaces white, gold→claret, navy→ink, "AI-Powered"→"Walk-Forward Verified"
- **Regime report email** — full redesign: paper bg, Georgia serif, claret accent, warm regime colors
- **Login modal** — claret CTA button (not ink — "too goth")

### Navigation Standardization
- All public pages now have consistent nav: Home, About, Methodology, Track Record, Newsletter, Pricing, Start Trial
- Pricing links use `<a>` tags for anchor scroll
- Newsletter added to landing page nav

### Newsletter System (New)
- **Generator service** (`newsletter_generator_service.py`) — Claude-powered 4-section draft:
  - §01 The Week in Focus — market regime read
  - §02 One Idea, Explained — rotating educational topics (8 topics, cycles by week)
  - §03 What the System is Not Doing — anti-pitch (3 items, em-dash bullets)
  - §04 A Note From Erik — personal signoff
- **Admin editor** — Newsletter tab in admin dashboard with per-section text editing, live preview, save/lock/unlock/send workflow
- **Send Test to Me** button — sends to admin email only
- **Send to All** — requires lock + confirmation dialog
- **Auto-save on lock** — editor content saved to S3 before locking
- **Unlock button** — re-edit a locked draft
- **S3 archiving** — locked drafts publish to `newsletter/issues/` for web archive
- **Previous week continuity** — generator references last week's draft for regime change context
- **Cron integration** — Sunday cron uses locked draft ONLY, never auto-generates (killed legacy fallback)
- **Admin notification** — if no locked draft on Sunday, skips send + emails admin warning
- **Recipient list** — free newsletter subscribers + paid users who haven't opted out
- **Email preferences** — `market_measured` toggle added to user preferences modal
- **Unsubscribe** — handles both free subscribers (newsletter_preferences table) and paid users (email_preferences.market_measured)

### Newsletter Voice Rules
- No tickers in free newsletter — ever (S&P 500 index name is the only exception)
- No predictions ("we think the market will...")
- No doom-and-gloom or hype
- No "tape" — banned word
- Pitch in footer only, never in body
- §02 is purely educational — no references to this week's trades
- §03 intro: "Right now, the system is:" (not "is not:" — avoids double negative)
- Every number must come from provided data — hallucination banned
- Previous week's draft loaded for continuity

### Data & Pipeline Fixes
- **Monitoring count fix** — email now shows real count with "and X more on your dashboard"
- **Duplicate market context** — removed third duplicate on dashboard
- **Silent Cash alert** — now only fires on fresh signals, not monitoring
- **Regime report** — `target_emails` support added to prevent accidental blast
- **double_signal_alert** — `text_lines` undefined error (found, needs fix)

### 10-Year Walk-Forward
- **11y pickle validated** — 4,422 symbols, June 2015 → April 2026
- **SPY backfilled** — was only from Jan 2016 due to ETF exclusion, fixed to Jan 2015
- **Run 1 (no cooldown)**: +433%, 0.92 Sharpe, 26.7% MDD, 18.4% annualized
  - 176 regime exits, 175 trailing stops, 6 rebalance exits
  - 2018: -9.5% (whipsaw), 2020: +133%, 2022: +3.4%, 2025: +57%
  - Holding period: median 17d, avg 48d, 18% held 3+ months
  - 20/30 CB events had buys within 10 days (whipsaw problem)
- **Regime cooldown** — new param `regime_cooldown_days` added to backtester
  - After CB fires, system stays in cash for N trading days regardless of regime
  - Wired through StrategyParams, backtester, WF service, local runner
- **Run 3 (in progress)**: 10y with 13-period warmup + 10-day cooldown
- **save_wf_from_s3** Lambda handler — pushes local results to prod DB
- **Track record endpoint** — widened query to match June 2016 start date

### Stripe
- Branding updated in Stripe Dashboard (ink/claret)

### Cron Changes
- Regime report moved from Monday to Tuesday 9 AM ET

## Bugs Fixed
- Blog pages white — broken useEffect in 5 pages (agent collapsed callback)
- Blog pages white — prose classes without typography plugin installed
- Newsletter test 500 — `logger` not defined
- Newsletter generate error — `json.dumps` without import
- Newsletter wrong content sent — cron used `send_market_measured` instead of locked draft
- Newsletter editor didn't save on lock — edits lost
- Newsletter API calls hit CloudFront — missing `API_URL` prefix
- Regime report blasted all 7 subscribers — handler didn't support `target_emails`
- Chart card duplicate BRAND_ACCENT — old gold overwrote claret
- Lambda worker errors — various deploy/indentation issues

## Key Decisions
- Newsletter is purely editorial — same for free and paid, no tickers
- Self-hosted newsletter (not Substack/Beehiiv/Ghost) — own the list
- Saturday 8 PM ET generate, Sunday 10 AM ET auto-send if locked
- No weekend news refresh — "written from Friday's close" is honest
- No auto-generation fallback — locked draft or nothing
- Regime cooldown transcends regime changes — a rule's a rule
- "Tape" banned from all content
- Claret CTA buttons (not ink — "too goth")

## Still Running
- 10y WF run3 with warmup + cooldown (~4h remaining)

## Known Issues / Future
- Newsletter editor needs auto-save on keystroke (fragile save workflow)
- Newsletter editor needs conflict detection (async regen can overwrite)
- Version history for drafts
- Blog pages may need further editorial polish
- `double_signal_alert` email template has `text_lines` undefined error
- Terraform apply needed for regime report cron change
- RDS/S3 backup strategy is thin — worth adding versioning
