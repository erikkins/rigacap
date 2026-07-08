# Performance Numbers — Citations Registry

> **Purpose:** Single source of truth for every place we cite performance numbers (returns, Sharpe, drawdown, win rate, track-record length, benchmark comparisons). When the strategy is re-run or a number changes, this registry tells us **every surface that needs to be updated** so claims stay coherent across product, marketing, investor materials, and social.
>
> **Update protocol:** When the canonical numbers change, walk this registry top-to-bottom and update every Status=`STALE` row. Do not push partial updates — coherent or nothing.

---

## 1 · Canonical numbers (source of truth)

> ⚠️ **SUPERSEDED (Jul 1 2026).** Everything in this section is the RETIRED May-27 T3 t10/s8
> (5y-window) lens. The LIVE canonical is the **21-year continuous canon** — see
> `docs/canonical_numbers.json` → `live_canon`: **8.3% ann / 0.73 Sharpe / 19% MaxDD**
> (2007-2026), plus last-24mo **+32% / 2.20 / 8.5% MaxDD**, vs raw-momentum-net 13.2%/0.69/57%
> and SPY 9.8%/55%. The live `/track-record` page already reflects this; the numbers below do
> **not**, and must not be published. Also: the surface `find`-patterns in
> `scripts/perf_citations_surface_map.json` target retired (+204%/+86%/32%) values and need
> re-pointing before the propagator is run again.

These are the numbers every surface must converge on. Any divergence from this table is a defect.

> ⚠️ **SUPERSEDED (2026-07-08):** The product is now **TWO TIERS** — RigaCap Preserver + RigaCap Maximizer — not the single t30v strategy. Everything below the horizontal rule (the May-2026 52-Monday t30v vintage) is **RETIRED, historical-audit only**. **Core/t30v is INTERNAL-ONLY — never cite its name or numbers in public copy.** Use the 2-tier canonical immediately below.

### CURRENT CANONICAL — 2-tier walk-forward (vintage 2026-07-08)

**Source**: `scripts/tier_vintages_21y.py` → `scripts/tier_curves_21y.json` (21-yr daily, 2007–2026) + `scripts/tier_vintages_daily.py` (recent 2-yr, clean standalone window). Live production config: `pwf.run(trail=0.30, max_pos=20, size=0.045)`, regime-routed sleeves. Pre-2016 = disclosed survivorship caveat; 2016+ = survivorship-free, point-in-time. **Say "walk-forward," never "backtest."**

**21-year (2007–2026) — the honest anchor:**

| Metric | Preserver | Maximizer | S&P 500 (price) | Raw momentum |
|---|---|---|---|---|
| Annualized | **8.6%** | **14.5%** | 9.8% | 13.2% |
| Sharpe | 0.88 | 0.95 | 0.54 | 0.69 |
| Max drawdown | −13% | −20% | −55% | −57% |
| $100k → | $500k | $1.39M | $535k | — |
| Calmar | 0.65 | 0.71 | — | — |

**Last 24 months (held-out, clean) — the recent proof (dial shows +31% / +49%):**

| Metric | Preserver | Maximizer | S&P 500 |
|---|---|---|---|
| Annualized | **31.3%** | **48.9%** | 19.9% |
| Sharpe | 1.75 | 1.94 | 1.18 |
| Calmar | 2.43 | 2.83 | 1.05 |
| Max drawdown | −12.9% | −17.3% | −19.0% |

**Supporting stats (public-safe):**
- 2008: both tiers ~flat (+0.1%) while the S&P fell ~37%.
- Recovery (longest underwater): Preserver 2.0yr, Maximizer 3.4yr, S&P 5.4yr → Preserver recovers ~2× faster (**Preserver-specific** claim; Maximizer is only ~1.4×).
- Rolling win-rate vs S&P: Preserver 37% / 23% / 16% (1/3/5-yr); Maximizer 54% / 51% / 48%.
- Preserver adviser cut: −0.9% avg in the S&P's down months (S&P −3.9%), +1.6% in up months, 0.51 monthly correlation, 5 of the S&P's 6 worst months in cash.
- Sharpe vs Buffett (lifetime 0.79): Preserver 0.88 / Maximizer 0.95 — ABOVE Buffett, so ALWAYS pair with the pre-2016 survivorship caveat.

**INTERNAL ONLY (never public):** Core/t30v 21-yr = 7.3% / 0.76 / −18% (differs from the retired 8.3%/0.73/19% canon — reconcile internally; publish neither).

**Surface rules:** comparison tables use "RigaCap Preserver / RigaCap Maximizer" (house-mark + descriptor, TM). Hero dial leads with recent +31% / +49%; performance tables lead with the 21-yr anchor. No tildes on numbers in customer copy. Survivorship-free language = methodology/diligence context only, never a marketing lead.

---

> **The content below is the RETIRED May-2026 single-strategy (t30v) vintage — historical audit only. Do NOT cite in any surface.**

**Vintage**: `2026-05-27` — T3 t10/s8 on live production pickle (`prices/all_data.pkl.gz`, downloaded May 25 2026), **52 weekly Monday start dates** Jan 4 → Dec 27 2021, 5-year forward window each. **Single source script**: `scripts/wf_dd_tighten_stop.py` with `--dd-threshold 10 --tight-stop 8 --baseline-stop 12`.

**What changed since Apr 28 vintage:**
- **Strategy lever added**: DD-conditional trailing-stop tightening (when portfolio is ≥10% below its high-water mark, trail tightens 12% → 8%). Result: Sharpe lifts above 1.0 at median.
- **Methodology widened**: 52 weekly Mondays instead of 8 biweekly January starts. Exposes more path-fragile dates (especially the March 2021 cohort that struggles in any momentum book starting at a regime peak). Distribution is wider, but trustworthier.
- **Pickle**: live production pickle as of May 25 2026 (vs Apr 27 pickle for prior vintage). More current data, cleaner corp-action handling.
- **Code**: T3 t10/s8 monkey-patch in research scripts; production wiring still TODO.

**Methodology framing:** Drop the "simulation vs. friction-adjusted" two-column framing. We publish the **walk-forward result directly** — no derived haircut. Single canonical column = the walk-forward result on the live production pickle.

| Metric | Apr 28 vintage (RETIRED) | **2026-05-27 canonical (T3 t10/s8, 52-Monday)** | Notes |
|---|---|---|---|
| **Median 5y total return** | +160.22% | **+186.63%** | 52-Monday median |
| **Average 5y total return** | +160.22% | **+182.12%** | 52-Monday mean |
| **Median annualized** | 21.5% | **23.4%** ← *headline annualized* | derived from median return |
| **Median Sharpe ratio** | 0.92 | **1.00** ← *hits the institutional 1.0 threshold* | per-date median |
| **Median MaxDD** | 20.4% | **26.4%** ← *higher than prior; broader date sample exposes path-fragile starts* | per-date median |
| **Median Calmar** | (not cited) | **0.81** | derived per-date |
| **Worst start window (5y total)** | +109% | **+35%** ← *path-fragile March 2021 start* | min across 52 dates |
| **Best start window (5y total)** | +252% | **+319%** | max across 52 dates |
| **Start windows with positive return** | 8/8 (100%) | **52/52 (100%)** ← *no negative paths* | n/a |
| Number of start dates tested | 8 (publicly: "multiple") | 52 (publicly: "across multiple weekly start dates") | per-memory rule: never cite the specific number in external comms |
| **Sharpe ≥ 1.0 hit rate** | n/a | **26/52 (50%)** | distributional |
| **Calmar ≥ 1.0 hit rate** | n/a | **15/52 (29%)** | distributional |
| **MaxDD ≤ 30% hit rate** | n/a | **33/52 (63%)** | distributional |
| Win rate | 48.6% | _to recompute on T3 trade list_ | trade-level analysis pending |
| Win/loss ratio | 1.77x | _to recompute_ | trade-level analysis pending |
| Track length | 5y verified | **5y verified across 52 weekly starts on live pickle** | n/a |

**Per-start-date distribution (still publish 8 specific dates on Track Record for visual continuity):**

| Start date | 5y total return | Sharpe | MaxDD | Calmar |
|---|---|---|---|---|
| 2021-01-04 | +101.77% | 0.67 | 26.68% | 0.56 |
| 2021-01-18 | +123.84% | 0.61 | 32.77% | 0.53 |
| 2021-01-25 | +145.11% | 0.83 | 28.30% | 0.69 |
| 2021-02-01 | +115.81% | 0.70 | 30.80% | 0.54 |
| 2021-02-08 | +115.51% | 0.74 | 28.30% | 0.59 |
| 2021-02-15 | +35.07% ← worst (path-fragile) | 0.37 | 32.73% | 0.19 |
| 2021-03-01 | +172.10% | 0.89 | 20.69% | 1.07 |
| 2021-04-05 | +147.88% | 0.89 | 26.37% | 0.75 |
| **Average (8 dates)** | **+119.64%** | **0.71** | **28.33%** | **0.60** |
| **Median (52 dates, headline)** | **+186.63%** | **1.00** | **26.41%** | **0.81** |

**Surface-level rule:**
- **Hero stats (Landing, Track Record headline):** Lead with the **52-Monday median** numbers (return / annualized / Sharpe / MaxDD). Frame as "tested across multiple weekly start dates over 5 years."
- **Track Record full body:** Keep the 8-date per-start-date table for visual continuity, but make clear the headline numbers come from the 52-Monday distribution.
- **Marketing copy:** Use "multiple" or "across multiple weekly start dates" — never cite "52" or "8" externally (per `feedback_no_7_dates.md`).

**The Apr 28 vintage is RETIRED** because:
1. Material strategy improvement (T3 t10/s8) added since
2. Methodology widened (8 → 52 dates) — better stress test
3. Data updated to live production pickle (vs Apr 27 backup)
4. The Apr 28 numbers are no longer reproducible on the current codebase — and that's fine because we've intentionally moved forward

**Honest reframe for external comms:**
> *"Across 52 weekly five-year walk-forward simulations, the strategy delivered a median 23% annualized return with a Sharpe ratio at the institutional 1.0 threshold. Every tested start window produced a positive five-year result. The strategy is built to compress drawdowns, not eliminate them — typical maximum drawdown sits in the same range as a normal market correction (~26%)."*

**Headline angles to amplify:**
- **Sharpe ratio at the institutional 1.0 threshold.** Median across 52 weekly start dates.
- **Every start window positive.** No path-fragile date produced a five-year loss.
- **52 weekly stress tests, not 8.** More rigorous distribution than typical retail signal services publish.
- **Annualized canonical: 23%.** Median across the 52-Monday distribution; rounds to "above 23%" for hero copy.

**Headline angles to retire:**
- `21.5% annualized` → **REPLACE with 23%** (or "above 23%")
- `20.4% MaxDD` → **REPLACE with ~26%** (or range "24-31%" / "in the same range as a market correction")
- `+109% worst-case` → **REPLACE with "every tested start window positive"** (don't lead with the worst number; the +35% outlier is a path-fragility artifact, not a strategy failure)
- `+160% average` → **REPLACE with "+187% median" or "+182% average"**

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

> **Note (2026-05-27 refresh):** Any row previously marked `OK` that cites Apr 28 canonical numbers (21.5% ann, 20.4% MDD, +160% avg, +109% worst, "8 dates") is **now STALE** relative to the new canonical (23% ann, ~26% MDD, +187% median, "52 weekly start dates" framing). The specific OK rows that flipped are tagged below. Rows that cite stable historical figures (SPY benchmark, legacy DWAP, specific trade examples) stay OK.

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
| Marketing strategy doc §18 | same | 21.5% ann vs SPY ~13% | **STALE** | Update 21.5% → 23% (or "above 23%"). Pricing math redo: 23% on $100K = $9,500/yr vs $1,548/yr sub |
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
| **Landing page V2 — performance table** | `frontend/src/LandingPageV2.jsx` L218-232 | +204% sim, +173% friction-adj, +84% SPY | **STALE** | Drop sim/friction-adj column framing. Replace with single canonical column: +187% median 5y / 23% ann / 1.00 Sharpe / ~26% MDD / +319% best / +35% worst |
| **Landing page V2 — FAQ expected returns** | same L407 | sim ~23% ann, friction-adj 21.5%, SPY ~13% | **STALE** | Drop sim/friction-adj framing. Replace with "above 23% median annualized" + SPY benchmark |
| **Landing page V2 — FAQ pricing justification** | same L409 | 21.5% on $100K = $8,500/yr vs $1,548/yr sub | **STALE** | Update math: 23% on $100K = $9,500/yr (vs $1,548/yr sub) — even better value proposition |
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
| Welcome email (HTML body) | `backend/app/services/email_service.py` L1395-1396 | friction-adj ~21.5% ann over 5y | **STALE** | Replace 21.5% with 23% (or "above 23%"). Drop "friction-adjusted" framing. |
| Welcome email (text fallback) | same L1432 | "+240% over 5 years" | **STALE** | Replace with +160% or +173% friction-adj — must match HTML version |
| Welcome email V2 (HTML) | same L1536-1537 | friction-adj ~21.5%; flat 2022 vs SPY -20% | **STALE** | Replace 21.5% → 23%. Verify 2022 claim against T3 equity curve before reusing. |
| Onboarding step 3 (value prop) | same L1804 | friction-adj ~21.5% vs SPY ~13% | **STALE** | Replace 21.5% → 23%. Drop friction-adj framing. |
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
| 2026-05-27 | "T3 t10/s8 on live prod pickle, 52-Monday" (single-strategy t30v) | `/tmp/sweep_52mon_prod_T3_t10s8/summary.csv` | +186.63% med / 23.4% ann / 1.00 Sharpe / 26.41% MDD / +35% worst / +319% best. Single-strategy t30v vintage. **NOW RETIRED** — product split into two tiers (see below). |
| **2026-07-08** | **"2-tier walk-forward (Preserver + Maximizer)"** ← **CURRENT CANONICAL** | `scripts/tier_vintages_21y.py` → `tier_curves_21y.json` + `scripts/tier_vintages_daily.py` | Product is now TWO tiers on one engine. 21-yr (2007–2026): **Preserver 8.6% / 0.88 / −13%**, **Maximizer 14.5% / 0.95 / −20%** vs S&P 9.8% / −55%, raw-mom 13.2% / −57%. Recent 24mo (clean): **Preserver 31.3% / 1.75 / −12.9%**, **Maximizer 48.9% / 1.94 / −17.3%** (= the 31/49 dial). Core/t30v (7.3% / 0.76 / −18%) retired to INTERNAL-ONLY. All prior t30v/single-strategy vintages RETIRED. Say "walk-forward," never "backtest." |

---

## 6 · Open items

- [ ] Confirm whether `LandingPage.jsx` (V1) is still routed/live; delete if not.
- [ ] Recompute trade-level stats (win rate, win/loss ratio, avg winner/loser) from clean-data trade lists.
- [ ] Verify "2022 flat / -7.3% drawdown" claim against clean-data equity curves before reusing.
- [ ] Re-run 10y walk-forward on clean data (currently no clean 10y number — all "+603%" cites are from over-fit run).
- [ ] Audit drip email steps 6-11 for any stale aggregate numbers slipped into drafts.
- [ ] Grep `frontend/index.html` and `frontend/public/` for og/twitter meta containing perf claims.
- [ ] After ablation completes, populate "no-carry" column in §1 + add Vintage row in §5.
