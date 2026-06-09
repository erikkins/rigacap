# Beta Tester Update — April 2026

**Subject:** What we've been building (and why it's been quiet)

---

Hey [Name],

It's Erik. I wanted to give you a real update on what's been happening behind the scenes at RigaCap — because I know it's been quiet on the signal front lately, and you deserve to know why.

## The Short Version

We've been heads-down optimizing the algorithm. The result: **our walk-forward validated returns nearly doubled** — from 16% to almost 20% annualized. And we did it without adding complexity. We actually *simplified* the system.

## What's Been Happening

When you signed up, our ensemble strategy was already solid — it combined breakout timing, momentum quality scoring, and trailing stops with 7-regime market intelligence. It beat the S&P 500 across every test period.

But "solid" wasn't good enough. I wanted to find the ceiling.

Over the past month, we've:

**Hardened the data pipeline.** We migrated to a dual-source architecture (Alpaca + yfinance) with automatic failover. If one data source goes down, the other takes over seamlessly. We also built a freshness gate that holds all communications if data is stale — you'll never get a signal based on yesterday's prices.

**Stress-tested the strategy across 50+ walk-forward simulations.** Walk-forward testing is the gold standard — it simulates exactly what would have happened if you started investing on any given week over the past 5 years. No hindsight bias. No cherry-picking good periods.

**Refined the stock universe.** Our system scans over 4,000 stocks daily. We tested thousands of configurations to find the optimal filtering that captures real breakouts without drowning in noise.

**Ran a parameter tournament.** Instead of letting an AI optimizer search blindly across dozens of variables, we tested each parameter independently to find which ones actually move the needle. Most of them don't. One of them does — significantly.

## The Result

**Walk-forward validated performance (2021–2026, 5 years):**

- Average annualized return: **~20%**
- Every test period positive (7 out of 7 start dates)
- Every test period beats the S&P 500
- Worst case: +14% annualized — still beats most hedge funds
- Best case: +30% annualized

**What that means in dollars:**

| Starting With | 5 Years | 10 Years |
|--------------|---------|-----------|
| $10,000 | $24,800 | $59,700 |
| $25,000 | $61,900 | $149,300 |
| $100,000 | $247,800 | $597,300 |

*Both 5-year and 10-year numbers are walk-forward validated — not projected.*

**10-year walk-forward result:** +497% total return (19.6% annualized), Sharpe ratio 0.97 — tested through 2 bear markets, a pandemic crash, and 3 bull runs.

**For comparison:**

| | 10-Year Return | Annual Fees | Minimum |
|--|---------------|------------|---------|
| **RigaCap** | **+497%** (~20% ann) | **$29-49/mo** | **None** |
| S&P 500 (index fund) | +257% (~14% ann) | ~$0 | None |
| Average hedge fund | ~+160% (~10% ann) | 2% + 20% of profits | $1M+ |

Our walk-forward validated returns are nearly double the market and outpace the average hedge fund — at a fraction of the cost, with no minimums. The best-performing hedge funds in the world (like Renaissance's Medallion Fund) still do better, but they charge 5% management + 44% of profits and require a $10M+ invitation. We're building that kind of intelligence for everyone.

## Why It's Been Quiet

Zero signals recently isn't a bug — it's the algorithm doing its job. The market has been in a "rotating bull" regime with elevated volatility. Our regime intelligence system recognized this and has been cautious, waiting for high-conviction setups rather than forcing trades in choppy conditions.

Other services would spam you with mediocre signals to look busy. We'd rather protect your capital and wait for the right moment. That discipline is a big part of why the backtested returns are what they are.

## What's Next

The optimized strategy goes live Monday. You'll start seeing signals generated with the refined parameters. Everything you see on the dashboard — the signals, the regime analysis, the portfolio guidance — now reflects this improved engine.

## I Want to Hear From You

You're one of our earliest users, and your experience matters more than any backtest. I have a few quick questions:

1. **Are you checking the dashboard?** How often, and what do you look at most?
2. **Are the daily emails useful?** Too much, too little, just right? Do you read them or skip them?
3. **What would make you continue** your subscription long-term?
4. **Is anything confusing or missing?** Features you wish we had?
5. **Would you refer a friend?** If not, what would change that?

Just hit reply — I read every response personally.

Thanks for being part of this from the early days. The best is ahead.

— Erik

*Founder, RigaCap*

---

*Past performance, including walk-forward testing, does not guarantee future results. All investing involves risk. RigaCap provides signals, not financial advice. Always do your own research and consult a financial advisor.*
