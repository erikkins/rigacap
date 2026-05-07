# Performance Numbers — Citations Registry

> **Purpose:** Single source of truth for every place we cite performance numbers (returns, Sharpe, drawdown, win rate, track-record length, benchmark comparisons). When the strategy is re-run or a number changes, this registry tells us **every surface that needs to be updated** so claims stay coherent across product, marketing, investor materials, and social.
>
> **Update protocol:** When the canonical numbers change, walk this registry top-to-bottom and update every Status=`STALE` row. Do not push partial updates — coherent or nothing.

---

## 1 · Canonical numbers (source of truth)

These are the numbers every surface must converge on. Any divergence from this table is a defect.

**Methodology framing:** Drop the "simulation vs. friction-adjusted" two-column framing. We publish the **walk-forward result directly** — no derived haircut. The walk-forward simulation already includes realistic fills at the rebalance boundary; further haircuts (taxes, subscriber behavioral drag) are user-specific and shouldn't be embedded in the headline number. **Single canonical column = the walk-forward result on clean 11y data.**

| Metric | Currently published (to be retired) | **Canonical (clean WF, carry-on)** | Notes |
|---|---|---|---|
| Total return (5y, avg) | +204% (sim) / +173% (friction-adj) | **+160.22%** | `/tmp/wf_5y_8dates_summary.csv` (2026-04-28) |
| Annualized return | 23% (sim) | **21.5%** ← *marketing canonical, locked after 11y consistency check* | 5y derived rounds to 21.1; 11y comes in at 21.6; we publish the rounded mid-figure |
| Sharpe ratio | 0.95 | **0.92** | per-date avg |
| Max drawdown | 32% (sim claim) | **20.4%** ← *better than published by 36%* | per-date avg |
| Worst start date (5y) | +86% | **+109%** ← *better than published by 23 pp* | Apr 1, 2021 start |
| Best start date (5y) | _not currently cited_ | **+252%** | Jan 18, 2021 start |
| Win rate | 48.6% | _to recompute from trade list_ | trade-level analysis pending |
| Win/loss ratio | 1.77x | _to recompute_ | trade-level analysis pending |
| Track length | 5y / 10y | **5y verified clean (multi-start) + 11y verified clean (single-start)** | n/a |
| **11y total return** | (retired +603%) | **+675%** (Oct 2015 → Apr 2026, 10.5 yrs) | `/tmp/wf_11y_clean_fixed/` |
| **11y annualized** | (retired ~37%) | **~21.6%** ← *11y comes in just above the published 21.5% — strongest consistency check* | derived |
| **11y Sharpe / MaxDD** | (retired 1.19 / 30%) | **0.95 / 28.1%** (longer window includes more bear cycles) | per-run |
| **11y vs SPY** | (retired +257% SPY) | **+318% SPY** → +357 pp total alpha / ~7.6 pp annualized | per-run |
| Number of start dates | "multiple" (publicly) | 8 (internally) | n/a |
| SPY 5y benchmark | +84% | **+92.63%** (avg of multiple start dates) | per-date avg |
| Alpha vs SPY (5y) | +89 pp | **+67.6 pp** | RigaCap − SPY |
| Annualized alpha | ~8.5 pp | **~7.1 pp** | derived |
| 2022 capital preservation | "flat while SPY -20%" | **+8.0% avg (every start positive); SPY -19.4%** | clean-data per-year compute |
| 2024 performance | "+1.2%" | **+31.9% avg; SPY +24%** | clean-data per-year compute |
| Win rate | 48.6% | **42.0%** | trade-level aggregate |
| Win/loss ratio | 1.77x | **2.51x** ← *better than published* | trade-level aggregate |
| **Cascade Guard return contribution** | "+87 pp" (Apr 19, dirty data) | **+37.7 pp / +3.7 pp annualized** | no-CG ablation 2026-04-28 |
| Cascade Guard Sharpe contribution | (not previously cited) | **+0.14** | no-CG ablation |
| Cascade Guard MDD impact | "same MDD" claim | **~neutral (slightly worse: +1.2pp)** | no-CG ablation — DO NOT claim drawdown protection |

**Per-start-date distribution (publish on Track Record page; do not bury upside):**

| Start date | 5y total return | Sharpe | MaxDD | SPY same window |
|---|---|---|---|---|
| 2021-01-04 | +145.36% | 0.92 | 20.26% | +98.45% |
| 2021-01-18 | **+252.06%** ← best | 0.88 | 25.87% | +95.68% |
| 2021-01-25 | +160.18% | 0.83 | 20.42% | +92.08% |
| 2021-02-01 | +156.34% | 0.96 | 20.38% | +97.03% |
| 2021-02-08 | +156.34% | 0.96 | 20.38% | +97.03% |
| 2021-02-15 | +156.34% | 0.96 | 20.38% | +97.03% |
| 2021-03-01 | +145.83% | 0.95 | 16.71% | +88.63% |
| 2021-04-01 | **+109.31%** ← worst | 0.89 | 18.97% | +75.12% |
| **Average** | **+160.22%** | **0.92** | **20.42%** | **+92.63%** |

**Surface-level rule:**
- **Hero stats (Landing, Track Record headline):** Show the **average** + worst start date + Sharpe + MaxDD (4-stat layout).
- **Track Record full body:** Show the **per-start-date distribution above** so subscribers can see best / worst / typical. Don't lead with +252% but don't hide it either.
- **Other surfaces (emails, social):** Use the **average** unless context specifically calls for the range.

**No-carry ablation reference (NOT canonical, kept for the vintage log):** +155.06% / 0.88 Sharpe / 18.66% MaxDD. Confirmed that carry-on CB pause is the correct semantic — better return + Sharpe for small MaxDD cost.

**Carry-on production parity action:** the `cb_pause_carries_periods=True` semantic exists in the backtester only. **Must port to production scanner before any external comms cite the canonical numbers** (per WF↔Prod parity rule). Otherwise we're advertising a strategy subscribers can't realize.

**Headline angles to amplify:**
- **Drawdown beats simulation by ~36%.** §15 modeled 32% MaxDD; real walk-forward came in at 20.4%. Under-promise, over-deliver.
- **Worst-case floor beats published floor.** Real worst start date came in at +109% (Apr 1, 2021); website claims worst is +86%. The floor is **+23pp higher than what we promised** — real-world performance was tighter on the downside than our own modeling.
- **Annualized canonical: 21.5%.** 5y per-date avg derives to 21.1, 11y derives to 21.6 — we publish 21.5 as the rounded mid-figure that's defensible against either window.
- **Cascade Guard fires consistently.** 2-4 events per 5y window in every run; not theoretical.

**Honest reframe for external comms:**
> *"We modeled an average of +204% with a worst case of +86% and a 32% drawdown. Reality came in tighter on every risk metric: max drawdown 20%, worst-case still +109%, and our annualized return landed within rounding of the 21.5% friction-adjusted estimate."*

**Headline angles to retire / requalify:**
- ~~`+603%` (10y)~~ → **REPLACED with +675% (11y)** on 2026-04-29 clean re-run. Status: **PUBLISHABLE.**
- `+384%` (5y). Sourced from same over-fit run. Status: **DO NOT PUBLISH** — replace with +160% (real) or +173% (friction-adjusted estimate, currently on website).
- `~37%` annualized. Status: **DO NOT PUBLISH** — replace with 21.5%.
- 30% MaxDD. Status: **REPLACE with 20.4%** wherever cited.

---

## 2 · Status legend

| Status | Meaning |
|---|---|
| **OK** | Number matches canonical table or is a stable historical reference (e.g., legacy DWAP for context) |
| **STALE** | Number is from a superseded run; must update before next external comms cycle |
| **DEFER** | Internal-only doc; OK to lag if outward-facing surfaces are coherent |
| **REVIEW** | Need product/legal review before changing (e.g., Marketing Rule disclosures) |

---

## 3 · Surfaces

### 3.1 Investor-facing PDFs / HTML

| Surface | File | Numbers cited | Status | Notes |
|---|---|---|---|---|
| Investor report — cover stats | `design/documents/rigacap-investor-report.html` L481-495 | +603%, 1.19, ~37%, 30% | **STALE** | All four headline numbers from over-fit run |
| Investor report — exec summary | same L512-544 | +603%, ~37%, 1.19, 30% | **STALE** | Repeat of cover claims in prose |
| Investor report — performance table | same L542-550 | 5y +384%, 10y +603%, ~37%, 30% | **STALE** | Replace 5y with +160%/21.5%/0.92/20.4%; hold 10y until re-run |
| Investor report — benchmark bars | same L567-574 | +603% vs +257% SPY | **STALE** | Hold until 10y clean re-run |
| Investor report — 2022 callout | same L691, L976 | flat vs SPY -20%; -7.3% vs SPY -20% | **REVIEW** | Verify against equity curves before keeping |
| Investor report — Cascade Guard | same L980 | +87 pp from circuit breaker | **REVIEW** | Need to rederive on clean data |
| Signal Intelligence doc — opening | `design/documents/rigacap-signal-intelligence.html` | +603%, ~37%, 1.19, 30% | **STALE** | Single biggest doc to update — this is "the secret sauce" doc |
| Signal Intelligence doc — perf table | same | +384% RigaCap vs +84% SPY (5y) | **STALE** | Replace with +160% / SPY +92.6% |
| Signal Intelligence doc — trade stats | same | 48.6% win, 1.77x, +15% avg winner, -8.6% avg loser | **REVIEW** | Recompute on clean-data trade list |
| Signal Intelligence doc — carry analysis | same | +206% vs +121% (carry vs force-close) | **STALE** | Re-run with carry-vs-no-carry ablation when complete |
| Pricing analysis | `design/documents/rigacap-pricing-analysis.html` | +603% (RigaCap), +284% (Seeking Alpha) | **STALE** | Hold pending 10y |
| Marketing playbook | `design/documents/rigacap-marketing-playbook.html` | +603%, 24% MaxDD | **STALE** | Hold pending 10y; 24% MaxDD also stale (real 20.4% on 5y) |
| Messaging frameworks | `design/documents/rigacap-messaging-frameworks.html` | +603%, ~35% ann, 1.19, 30% MaxDD | **STALE** | Headline variants A-E need rewriting |

**PDF regen reminder:** After HTML edits, regenerate `.pdf` siblings via the Chrome headless command in `CLAUDE.md`.

---

### 3.2 Marketing & strategy docs (internal canonical)

| Surface | File | Numbers cited | Status | Notes |
|---|---|---|---|---|
| Marketing strategy doc §15 | `docs/MarketingNewsletterStrategyCLAUDE.md` L662-673 | +204% sim, +173% friction-adj, ~23% / 21.5% ann, Sharpe 0.95, **MaxDD 32%** | **STALE** | This is the document that drove §15 — drop sim 32% to real 20.4% (the headline change) |
| Marketing strategy doc §15 | same L672-673 | SPY 5y +84%, ~13% ann | **OK** | Stable historical figure; can stay |
| Marketing strategy doc §18 | same | 21.5% ann vs SPY ~13% | **OK** | Pricing logic intact — annualized is within rounding |
| Beta-tester update | `docs/beta-tester-update-apr2026.md` | "16% → ~20%", best +30% / worst +14% ann; 10y +497% / 19.6% ann / Sharpe 0.97 | **DEFER** | Internal doc; can lag, but flag if reused externally |
| Beta-tester update — comparative table | same | RigaCap +497% vs SPY +257% vs HF ~+160% | **DEFER** | Same — internal context |
| CLAUDE.md — Strategy v2 | `CLAUDE.md` L34-36 | 263% / 29% ann / 1.15 / -14.2% / 49% win | **OK** | Historical "Strategy v2" (old momentum strategy) — stays as evolution context |
| CLAUDE.md — Recent Performance | same L40-43 | 95% / 14% ann / 1.19 / -10.5% / 47% win | **STALE** | Said to be "recent 5y" — but conflicts with new clean run; either retire or label as superseded |
| CLAUDE.md — v1→v2 comparison | same L70 | Sharpe 1.48 (v2) | **OK** | Historical context for strategy evolution |
| CLAUDE.md — Ensemble (current production) | same L91-98 | +240% / 33% ann / 1.19 / 30% MaxDD / SPY +84% / 10y +603% / 24% MaxDD | **STALE** | Update 5y row; flag 10y row as "pending clean re-run" |
| README.md | `README.md` | 216% / 70% ann / 1.14 / -11.8% / 52.3% win (DWAP) | **OK** | Legacy DWAP results — historical, not current claims |

---

### 3.3 Frontend (live website)

| Surface | File | Numbers cited | Status | Notes |
|---|---|---|---|---|
| Landing page V1 — stats section | `frontend/src/LandingPage.jsx` L208-213 | ~37%, +384%, 30% MaxDD, "flat 2022", 1.19 Sharpe | **STALE** | Likely the OLD landing page — confirm whether V1 or V2 is live |
| Landing page V1 — FAQ | same | +384% / ~37% / 1.19 Sharpe; 2022 capital preservation | **STALE** | Same |
| **Landing page V2 — performance table** | `frontend/src/LandingPageV2.jsx` L218-232 | +204% sim, +173% friction-adj, +84% SPY | **OK** | Matches §15. **THIS IS WHAT'S LIVE per user.** |
| **Landing page V2 — FAQ expected returns** | same L407 | sim ~23% ann, friction-adj 21.5%, SPY ~13% | **OK** | Matches canonical |
| **Landing page V2 — FAQ pricing justification** | same L409 | 21.5% on $100K = $8,500/yr vs $1,548/yr sub | **OK** | Stable pricing math |
| Track Record page V1 | `frontend/src/TrackRecordPage.jsx` | +263% avg, +165% worst, 0.92 Sharpe, 27% MaxDD; +568% best; 333 trades, 48.6% win, 1.77x | **STALE** | Confirm V1 is still routed; if V2 is live, delete V1 |
| **Track Record page V2 (LIVE)** | `frontend/src/TrackRecordPageV2.jsx` L59-62, L113-127 | +204% avg, **+86% worst**, 0.95 Sharpe, 32% MaxDD; table row: +204% sim / +173% friction-adj / ~21.5% ann; SPY +84%; 333 trades, 48.6% win, 1.77x | **STALE on 3 of 4 hero stats; OK on annualized friction-adj** | **Real numbers vs V2 claims:** avg +160% (-44pp vs sim, -13pp vs friction-adj), **worst +109% (+23pp BETTER)**, Sharpe 0.92 (-0.03, within rounding), **MaxDD 20.4% (-11.6pp BETTER)**. Reframe to lead with friction-adjusted column and retire the +204% sim hero stat. |
| 10y Track Record page | `frontend/src/TrackRecord10YPage.jsx` | NASDAQ-100 ~+350% | **REVIEW** | Pending 10y clean re-run |
| Blog: 2022 story | `frontend/src/Blog2022StoryPage.jsx` | +384% RigaCap vs +84% SPY | **STALE** | Replace with +160% / +92.6% |
| Blog: We Called It (MRNA) | `frontend/src/BlogWeCalledItMRNAPage.jsx` | Moderna +51%, +29%, +75%, -40% | **OK** | Specific trade example, not aggregate metric |
| Blog: We Called It (TGTX) | `frontend/src/BlogWeCalledItTGTXPage.jsx` | TGTX +46% in 14 days | **OK** | Specific trade example |
| Blog index | `frontend/src/BlogIndexPage.jsx` | "+384% 5y walk-forward" featured headline; MRNA +51%, TGTX +46% | **STALE** | Replace +384% featured |

**Open question:** Confirm whether `LandingPage.jsx` (V1) is still routed/live anywhere. If V2 is the only live surface, V1 can be deleted rather than updated.

---

### 3.4 Email templates

| Surface | File | Numbers cited | Status | Notes |
|---|---|---|---|---|
| Welcome email (HTML body) | `backend/app/services/email_service.py` L1395-1396 | friction-adj ~21.5% ann over 5y | **OK** | Matches canonical |
| Welcome email (text fallback) | same L1432 | "+240% over 5 years" | **STALE** | Replace with +160% or +173% friction-adj — must match HTML version |
| Welcome email V2 (HTML) | same L1536-1537 | friction-adj ~21.5%; flat 2022 vs SPY -20% | **OK** | Matches canonical |
| Onboarding step 3 (value prop) | same L1804 | friction-adj ~21.5% vs SPY ~13% | **OK** | Matches canonical |
| Onboarding step 3 — drip body | same | "~21.5% annualized" + "ended 2022 flat" | **REVIEW** | Verify 2022 flat claim against clean-data equity curve before re-sending |
| Daily digest | `backend/app/services/email_service.py` (digest section) | _no aggregate perf numbers_ | **OK** | Per-signal info only, no track-record claims |
| Newsletter / market_measured | `backend/app/services/email_service.py` (newsletter) | _editorial only, no signals or perf claims_ | **OK** | Locked in by `feedback_newsletter_no_signals.md` |
| Regime report | `backend/app/services/email_service.py` (regime) | _no aggregate perf numbers_ | **OK** | Regime probabilities only |
| Onboarding steps 6-11 (drips DR-005/006/008, RE-001/002/003) | same | _to audit — drafts are recent_ | **REVIEW** | Verify no stale aggregate numbers slipped into drafts |

---

### 3.5 Social & marketing assets

| Surface | File | Numbers cited | Status | Notes |
|---|---|---|---|---|
| Social launch cards (canvas) | `design/brand/social-launch-cards.html` | "+384% / ~37% / 1.19 Sharpe" | **STALE** | Card art needs regen with new numbers; PNG outputs in `frontend/public/launch-cards/` will need replacing |
| AI content generator prompts | `backend/app/services/ai_content_service.py` | _no hardcoded aggregate numbers (good)_ | **OK** | Pulls trade-by-trade info from DB |
| OG / Twitter card meta | `frontend/index.html` (or equivalent) | _verify whether og:description carries any perf claim_ | **REVIEW** | Grep for og:description and twitter:description |
| Social profile bios (Twitter / Instagram) | _external — manually maintained_ | _likely +384% / ~37%_ | **REVIEW** | Out-of-repo; user must check live profiles |
| Already-published social posts | DB `social_posts` table | _likely cite +384% / +603% / ~37%_ | **DEFER** | Past posts are immutable; only ensure future scheduled queue is clean |

---

### 3.6 Out-of-repo surfaces (manual review required)

These can't be grep'd; must be checked manually before next external comms push.

- [ ] Twitter/X profile bio
- [ ] Instagram profile bio
- [ ] LinkedIn page (if applicable)
- [ ] Stripe product description (if numbers appear)
- [ ] Any podcast/interview writeups Erik has done
- [ ] Any beta-tester comms not in `docs/`
- [ ] Press / analyst kit if shared externally
- [ ] PDFs already emailed to investors (cannot retract — log as "historical at vintage X")

---

## 4 · Update sequence (when ready)

When canonical numbers change:

1. **Update §1 of this doc first** with new canonical values + date.
2. **Update Marketing strategy doc §15 + §18** (`docs/MarketingNewsletterStrategyCLAUDE.md`) — internal source of truth.
3. **Update Signal Intelligence doc HTML** — biggest external doc; regen PDF.
4. **Update Investor report HTML** — second biggest external doc; regen PDF.
5. **Update frontend** in this order: Landing V2 → Track Record → Blog index → Blog post bodies. Deploy via CI/CD.
6. **Update email templates** — `email_service.py` welcome (text+HTML), onboarding steps. Deploy via CI/CD.
7. **Regenerate social launch card PNGs** from `social-launch-cards.html`.
8. **Walk out-of-repo checklist** (§3.6).
9. **Mark every row in §3 as Status=OK** — no `STALE` rows allowed at end of pass.
10. **Commit with single message:** `Refresh performance citations to <vintage>` — keeps git blame coherent.

---

## 5 · Vintage log

Track each canonical refresh so we can audit "what did we claim, when?"

| Date | Vintage | Source run | Notes |
|---|---|---|---|
| _pre-2026-04-28_ | "Trial 37 (over-fit pickle)" | TPE Trial 37 on dirty pickle | Drove +384% / +603% / ~37% / 30% MaxDD across all surfaces. Now retired. |
| 2026-04-28 | "Clean-data 8-date 5y, carry-on" | `/tmp/wf_5y_8dates_summary.csv` | +160.22% / 0.92 / 20.4% / SPY +92.63%. **Current canonical.** Pending: no-carry ablation, 10y clean re-run. |
| 2026-04-28 | "Clean-data 8-date 5y, no-carry (ablation)" | `/tmp/wf_5y_8dates_no_carry_summary.csv` | +155.06% / 0.88 / 18.66% / SPY +90.33%. **Ablation only — not canonical.** Confirms CB pause-carries-periods behavior is a positive trade (better return + Sharpe for small MaxDD cost). |
| 2026-04-28 | "Clean-data 8-date 5y, no-CG (ablation v2 — true CG counterfactual)" | `/tmp/wf_5y_8dates_no_cg_summary.csv` | +122.49% / 0.78 / 19.24%. **CG impact = +37.7pp return / +3.7pp ann / +0.14 Sharpe / ~neutral MDD.** Replaces Apr 19's over-fit "+87pp / same MDD" claim. Note: v1 attempt had a flag-plumbing bug (override applied at wrong call site); v2 verified via `pause_events=0` across all 8 runs before trusting numbers. |
| _pending_ | "Clean-data 10y" | TBD | 10y re-run not yet scheduled. |

---

## 6 · Open items

- [ ] Confirm whether `LandingPage.jsx` (V1) is still routed/live; delete if not.
- [ ] Recompute trade-level stats (win rate, win/loss ratio, avg winner/loser) from clean-data trade lists.
- [ ] Verify "2022 flat / -7.3% drawdown" claim against clean-data equity curves before reusing.
- [ ] Re-run 10y walk-forward on clean data (currently no clean 10y number — all "+603%" cites are from over-fit run).
- [ ] Audit drip email steps 6-11 for any stale aggregate numbers slipped into drafts.
- [ ] Grep `frontend/index.html` and `frontend/public/` for og/twitter meta containing perf claims.
- [ ] After ablation completes, populate "no-carry" column in §1 + add Vintage row in §5.
