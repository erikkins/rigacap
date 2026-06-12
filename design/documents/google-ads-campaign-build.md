# Google Ads — Stability Search Campaign (Build Spec)
*Jun 12, 2026. Test A of the blitz. $25/day, 2-week read, kill >$150/trial.*

## Step 0 — Conversions first (Goals → Conversions → New → Import → GA4)
- Import **`purchase`** → set as PRIMARY (this is trial-start; CC-required checkout)
- Import **`begin_checkout`** → set as SECONDARY (observation only)

## Step 1 — Campaign settings (Create → Campaign)
| Setting | Value | Why |
|---|---|---|
| Objective | **Create without goal's guidance** (or Leads) | avoids goal-driven defaults |
| Type | **Search** | |
| Networks | Search Network ONLY — **UNCHECK "Search partners" and "Display Network"** | the classic budget leak |
| Locations | United States | |
| ⚠ Location options | **"Presence: people in or regularly in"** (NOT "presence or interest") | default setting shows ads worldwide to people "interested in" the US |
| Language | English | |
| Budget | **$25/day** | |
| Bidding | **Manual CPC**, max CPC **$4.00** | no conversion history yet; switch to Max Conversions after ~20 conversions |
| Ad rotation | Optimize | |
| Name | `stability-search-test-a` | |
| Everything else (assets, audience, broad-match suggestion, "AI Max" toggles) | **decline/skip all** | |

## Step 2 — Ad group 1: `crash-protection` → lands on rigacap.com/
Keywords (phrase + exact, paste as shown):
```
"protect portfolio from crash"
[protect portfolio from crash]
"protect my portfolio"
"portfolio crash protection"
"how to protect investments from market crash"
"reduce portfolio risk"
"reduce stock market risk"
"stock market too volatile"
"prepare portfolio for recession"
"defensive investing strategy"
```
**RSA (Responsive Search Ad):**
- Final URL: `https://rigacap.com/`
- Headlines (pin nothing, let Google rotate): `Built So You Never Panic-Sell` · `Momentum Signals, Risk-First` · `Designed Around the Drawdown` · `A 21-Year Honest Backtest` · `When Markets Break, Hold Cash` · `Capital Preservation First` · `RigaCap — Signals With Stops` · `7-Day Free Trial` · `From $59/Month (First 100)` · `No Hype. Published Losers.`
- Descriptions (all ≤90 chars, verified): `A momentum strategy built around the drawdown, not the brag. Every number labeled.` · `The system goes to cash when markets turn hostile. See the honest 21-year backtest.` · `Signals only — keep your broker, your custody, your control. 7-day free trial.` · `Honest numbers, published methodology, live record accruing in public.`

## Step 3 — Ad group 2: `panic-discipline` → lands on rigacap.com/track-record
Keywords:
```
"stop panic selling stocks"
"how to stop panic selling"
"sold stocks at the bottom"
"when to go to cash stock market"
"should i sell my stocks now"
[should i sell my stocks]
"alternatives to buy and hold"
"investing discipline system"
"trailing stop strategy"
"drawdown protection strategy"
```
**RSA:**
- Final URL: `https://rigacap.com/track-record`
- Headlines: `The Cost of Panic-Selling` · `Watch 21 Years in 60 Seconds` · `What Investors Actually Collect` · `Three Crashes, One Strategy` · `In Cash for 2008's Worst Months` · `Discipline, Outsourced` · `See the Honest Track Record` · `Backtest That Includes 2008` · `7-Day Free Trial` · `Built for the Long Holder`
- Descriptions (all ≤90 chars, verified): `Watch $100k race through 2008, COVID, and 2022 — then see what panic-selling costs.` · `The index's six worst months: the system sat four out in cash. Backtested, labeled.` · `A strategy is only as good as your ability to hold it. We built for that. Free trial.` · `No predictions, no hype. A published backtest and a live record accruing.`

## Step 4 — Negative keywords (campaign level, paste all)
```
free, jobs, careers, salary, course, courses, certification, pdf, book, books,
crypto, bitcoin, forex, options trading, day trading, penny stocks, futures,
reddit, wallstreetbets, gambling, casino, lawsuit, scam, login, app download,
what is a portfolio, definition, meaning, wiki, calculator template, excel,
401k loan, life insurance, car insurance, home insurance, health insurance
```
(the insurance negatives matter — "behavioral capital insurance" language must not match literal insurance queries)

## Step 5 — After launch
- Day 3: search-terms report — add negatives liberally (expect junk)
- Week 2: if ≥20 conversions total, switch bidding → Maximize Conversions
- Kill threshold: >$150/trial after 2 full weeks
- Promo: $500 spend ⇒ $1,000 credit lands automatically (~3 weeks at this budget)

## Compliance notes
- No performance numbers in ad text beyond "21-year backtest" framing (Google financial-services + exaggerated-claims policy); the landing pages carry the disclosed numbers with backtest labels
- If an ad is disapproved for financial services: appeal with "impersonal financial publication / signals newsletter, not personalized advice, no managed accounts" (publisher's exemption language)
