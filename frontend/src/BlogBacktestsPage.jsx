import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, AlertTriangle, CheckCircle, XCircle, BarChart3, ArrowRight, Eye, EyeOff } from 'lucide-react';

export default function BlogBacktestsPage() {
  return (
    <div className="min-h-screen bg-gray-950 text-gray-300">
      {/* Nav */}
      <nav className="bg-gray-900 border-b border-gray-800">
        <div className="max-w-3xl mx-auto px-4 py-4 flex items-center gap-4">
          <Link to="/" className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors">
            <ArrowLeft size={18} />
            <span className="text-sm">Back to RigaCap</span>
          </Link>
        </div>
      </nav>

      {/* Hero */}
      <section className="relative overflow-hidden bg-gradient-to-br from-red-900/80 via-gray-900 to-amber-900/60">
        <div className="absolute inset-0 overflow-hidden">
          <div className="absolute -top-40 -right-40 w-80 h-80 bg-red-500/10 rounded-full blur-3xl"></div>
          <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-amber-500/10 rounded-full blur-3xl"></div>
        </div>
        <div className="relative max-w-3xl mx-auto px-4 sm:px-6 py-16 sm:py-24 text-center">
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-white/10 backdrop-blur-sm rounded-full text-sm font-medium mb-6">
            <AlertTriangle className="w-4 h-4 text-amber-300" />
            <span className="text-white/90">Investor Education</span>
          </div>
          <h1 className="text-4xl sm:text-5xl font-bold text-white tracking-tight mb-4">
            Why Most Backtests Are Lies
          </h1>
          <p className="text-lg text-blue-200/80 max-w-2xl mx-auto">
            That strategy with 500% returns? It probably won't work in real life.
            <br className="hidden sm:block" />
            Here's how to tell the difference between proof and marketing.
          </p>
        </div>
      </section>

      {/* Article Body */}
      <article className="max-w-3xl mx-auto px-4 sm:px-6 py-12 sm:py-16">
        <div className="prose prose-invert prose-gray max-w-none">

          {/* The Problem */}
          <h2 className="text-2xl font-bold text-white mt-0 mb-4 flex items-center gap-2">
            <EyeOff className="w-6 h-6 text-red-400 flex-shrink-0" />
            The Dirty Secret of Trading Strategies
          </h2>
          <p className="text-gray-300 leading-relaxed text-base">
            Scroll through any trading forum, fintech landing page, or investment newsletter
            and you'll see the same thing: a chart going up and to the right, a breathless
            headline about triple-digit returns, and the implicit promise that you can have
            them too.
          </p>
          <p className="text-gray-300 leading-relaxed text-base">
            Almost all of these results come from <strong className="text-white">backtesting</strong> — running
            a strategy against historical data to see how it <em>would have</em> performed.
            On the surface, this sounds rigorous. Scientific, even.
          </p>
          <p className="text-gray-300 leading-relaxed text-base">
            It's not. It's more like predicting yesterday's weather and calling yourself
            a meteorologist.
          </p>

          {/* Highlight Box */}
          <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 my-8">
            <p className="text-red-200 font-semibold text-lg m-0 mb-2">
              Here's the uncomfortable truth:
            </p>
            <p className="text-red-200/80 m-0">
              Given enough historical data and enough parameter combinations, you can
              make <em>any</em> strategy look brilliant in hindsight. The hard part isn't
              finding something that worked — it's finding something that <em>will</em> work.
            </p>
          </div>

          <p className="text-gray-300 leading-relaxed text-base">
            The gap between a backtested strategy and a real-world strategy is where most
            investors lose money. Understanding that gap is the single most important thing
            you can learn before trusting any quantitative system — including ours.
          </p>
        </div>

        {/* Common Tricks Section */}
        <div className="prose prose-invert prose-gray max-w-none">
          <h2 className="text-2xl font-bold text-white mt-12 mb-4 flex items-center gap-2">
            <AlertTriangle className="w-6 h-6 text-amber-400 flex-shrink-0" />
            Five Ways Backtests Deceive You
          </h2>
          <p className="text-gray-300 leading-relaxed text-base mb-6">
            These aren't edge cases. They're standard practice across the industry —
            sometimes intentional, sometimes the result of sloppy methodology.
          </p>
        </div>

        <div className="grid gap-4 my-8">
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
            <div className="flex items-start gap-4">
              <XCircle className="w-6 h-6 text-red-400 flex-shrink-0 mt-0.5" />
              <div>
                <h3 className="text-white font-semibold mb-1">Cherry-Picked Date Ranges</h3>
                <p className="text-gray-400 text-sm m-0">
                  Start your backtest right after a market crash and end it before the next one.
                  Instant 300% returns. Shift those dates by six months and the same strategy
                  might lose 40%. The date range is doing the heavy lifting, not the strategy.
                </p>
              </div>
            </div>
          </div>
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
            <div className="flex items-start gap-4">
              <XCircle className="w-6 h-6 text-red-400 flex-shrink-0 mt-0.5" />
              <div>
                <h3 className="text-white font-semibold mb-1">Overfitted Parameters</h3>
                <p className="text-gray-400 text-sm m-0">
                  Test 10,000 parameter combinations, show the best one. The strategy didn't
                  "discover" something — it memorized the training data. This is the most
                  common and most dangerous form of backtest fraud. The more parameters you
                  optimize, the more certain your results are meaningless.
                </p>
              </div>
            </div>
          </div>
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
            <div className="flex items-start gap-4">
              <XCircle className="w-6 h-6 text-red-400 flex-shrink-0 mt-0.5" />
              <div>
                <h3 className="text-white font-semibold mb-1">Survivorship Bias</h3>
                <p className="text-gray-400 text-sm m-0">
                  Only test stocks that exist today. This quietly removes every company that
                  went bankrupt, got delisted, or merged — which are exactly the stocks that
                  would have destroyed the strategy's returns. The losers vanish from history.
                </p>
              </div>
            </div>
          </div>
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
            <div className="flex items-start gap-4">
              <XCircle className="w-6 h-6 text-red-400 flex-shrink-0 mt-0.5" />
              <div>
                <h3 className="text-white font-semibold mb-1">Look-Ahead Bias</h3>
                <p className="text-gray-400 text-sm m-0">
                  Use information that wasn't available at the time of the trade. Earnings
                  reported after market close used for that day's decision. Index membership
                  that changed two years later. It's subtle, hard to detect, and almost
                  always inflates returns.
                </p>
              </div>
            </div>
          </div>
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
            <div className="flex items-start gap-4">
              <XCircle className="w-6 h-6 text-red-400 flex-shrink-0 mt-0.5" />
              <div>
                <h3 className="text-white font-semibold mb-1">Invisible Transaction Costs</h3>
                <p className="text-gray-400 text-sm m-0">
                  No slippage, no commissions, no market impact, no bid-ask spreads. The
                  backtest assumes you can buy and sell instantly at the exact closing price.
                  In real markets, those frictions compound — especially for strategies that
                  trade frequently.
                </p>
              </div>
            </div>
          </div>
        </div>

        <div className="prose prose-invert prose-gray max-w-none">
          <p className="text-gray-300 leading-relaxed text-base">
            Any one of these issues can turn a losing strategy into a winner on paper.
            Combined — which they often are — they can fabricate returns out of thin air.
          </p>

          {/* Walk-Forward Section */}
          <h2 className="text-2xl font-bold text-white mt-12 mb-4 flex items-center gap-2">
            <Eye className="w-6 h-6 text-emerald-400 flex-shrink-0" />
            What Walk-Forward Testing Actually Does
          </h2>
          <p className="text-gray-300 leading-relaxed text-base">
            Walk-forward testing is fundamentally different from backtesting. Instead of
            looking at all the data and finding what worked, it simulates real-time decision
            making — stepping through history one day at a time, seeing only what was
            available at that moment.
          </p>
          <p className="text-gray-300 leading-relaxed text-base">
            Think of it this way: a backtest is an open-book exam where you've already seen
            the answer key. Walk-forward is a pop quiz, every single day, for five years.
          </p>
        </div>

        {/* Walk-Forward Benefits */}
        <div className="grid gap-4 my-8">
          <div className="bg-gray-900 border border-emerald-500/20 rounded-xl p-6">
            <div className="flex items-start gap-4">
              <CheckCircle className="w-6 h-6 text-emerald-400 flex-shrink-0 mt-0.5" />
              <div>
                <h3 className="text-white font-semibold mb-1">No Peeking Ahead</h3>
                <p className="text-gray-400 text-sm m-0">
                  At each decision point, the system only sees data that was actually available
                  at that moment in time. Tomorrow's prices, next week's earnings, next
                  month's Fed decision — all invisible. Exactly like real trading.
                </p>
              </div>
            </div>
          </div>
          <div className="bg-gray-900 border border-emerald-500/20 rounded-xl p-6">
            <div className="flex items-start gap-4">
              <CheckCircle className="w-6 h-6 text-emerald-400 flex-shrink-0 mt-0.5" />
              <div>
                <h3 className="text-white font-semibold mb-1">Fixed Parameters, No Cheating</h3>
                <p className="text-gray-400 text-sm m-0">
                  The strategy's rules are locked before the simulation begins. There's no
                  mid-test optimization, no "well, let's try a different stop loss for this
                  period." The same rules face every market condition — bull, bear, crash,
                  and recovery.
                </p>
              </div>
            </div>
          </div>
          <div className="bg-gray-900 border border-emerald-500/20 rounded-xl p-6">
            <div className="flex items-start gap-4">
              <CheckCircle className="w-6 h-6 text-emerald-400 flex-shrink-0 mt-0.5" />
              <div>
                <h3 className="text-white font-semibold mb-1">Multiple Start Dates</h3>
                <p className="text-gray-400 text-sm m-0">
                  We run the full simulation from 7 different start dates spaced across
                  different market conditions. This eliminates timing luck — you can't
                  accidentally pick a favorable starting point when you test all of them.
                </p>
              </div>
            </div>
          </div>
          <div className="bg-gray-900 border border-emerald-500/20 rounded-xl p-6">
            <div className="flex items-start gap-4">
              <CheckCircle className="w-6 h-6 text-emerald-400 flex-shrink-0 mt-0.5" />
              <div>
                <h3 className="text-white font-semibold mb-1">Survives the Bear Market</h3>
                <p className="text-gray-400 text-sm m-0">
                  Every walk-forward test includes the 2022 bear market — the S&P 500 down
                  20%, the Nasdaq down 33%. The system doesn't get to skip the hard parts.
                  It has to survive them with the same rules it uses in a bull market.
                </p>
              </div>
            </div>
          </div>
          <div className="bg-gray-900 border border-emerald-500/20 rounded-xl p-6">
            <div className="flex items-start gap-4">
              <CheckCircle className="w-6 h-6 text-emerald-400 flex-shrink-0 mt-0.5" />
              <div>
                <h3 className="text-white font-semibold mb-1">Realistic Execution</h3>
                <p className="text-gray-400 text-sm m-0">
                  Trades are executed at next-day prices, not the closing price that triggered
                  the signal. The simulation accounts for the reality that you can't act on
                  information the instant it becomes available.
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Comparison Table */}
        <div className="prose prose-invert prose-gray max-w-none">
          <h2 className="text-2xl font-bold text-white mt-12 mb-4 flex items-center gap-2">
            <BarChart3 className="w-6 h-6 text-blue-400 flex-shrink-0" />
            Backtest vs. Walk-Forward: Side by Side
          </h2>
        </div>

        <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden my-8">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800">
                <th className="text-left px-6 py-3 text-xs uppercase tracking-wider text-gray-500 font-semibold">Dimension</th>
                <th className="text-left px-6 py-3 text-xs uppercase tracking-wider text-red-400/80 font-semibold">Traditional Backtest</th>
                <th className="text-left px-6 py-3 text-xs uppercase tracking-wider text-emerald-400/80 font-semibold">Walk-Forward</th>
              </tr>
            </thead>
            <tbody>
              {[
                { dim: 'Data visibility', bt: 'Sees all history at once', wf: 'Sees only past data at each point' },
                { dim: 'Parameters', bt: 'Optimized after seeing results', wf: 'Fixed before simulation begins' },
                { dim: 'Date range', bt: 'Often cherry-picked', wf: 'Multiple start dates tested' },
                { dim: 'Analogous to', bt: 'Open-book exam with answer key', wf: 'Pop quiz every day for 5 years' },
                { dim: 'Survivorship bias', bt: 'Usually present', wf: 'Tests against actual universe at each date' },
                { dim: 'Transaction costs', bt: 'Often ignored', wf: 'Next-day execution, realistic fills' },
                { dim: 'Bear market test', bt: 'Can be excluded from range', wf: 'Must survive 2022 with same rules' },
                { dim: 'Confidence level', bt: 'Shows what could have worked', wf: 'Shows what would have worked' },
              ].map((row, i) => (
                <tr key={i} className="border-b border-gray-800/50">
                  <td className="px-6 py-4 text-white font-medium text-xs sm:text-sm">{row.dim}</td>
                  <td className="px-6 py-4 text-red-300/80 text-xs sm:text-sm">{row.bt}</td>
                  <td className="px-6 py-4 text-emerald-300/80 text-xs sm:text-sm">{row.wf}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* How to Spot a Fake */}
        <div className="prose prose-invert prose-gray max-w-none">
          <h2 className="text-2xl font-bold text-white mt-12 mb-4 flex items-center gap-2">
            <AlertTriangle className="w-6 h-6 text-amber-400 flex-shrink-0" />
            How to Spot a Fake Backtest
          </h2>
          <p className="text-gray-300 leading-relaxed text-base">
            Next time someone shows you a strategy with impressive returns, ask these
            questions. If they can't answer them — or won't — walk away.
          </p>
        </div>

        <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-6 sm:p-8 my-8">
          <h3 className="text-amber-200 font-semibold text-lg mb-4">The Backtest Smell Test</h3>
          <div className="space-y-4">
            {[
              {
                q: '"What date range did you test?"',
                why: 'If it conveniently starts after a crash and ends before one, the date range is doing the work. Legitimate strategies test across multiple market cycles, including bear markets.'
              },
              {
                q: '"How many parameter combinations did you try?"',
                why: 'If they tested thousands of combinations and showed you the best one, that\'s data mining — not strategy development. The more combinations tested, the less reliable the winner.'
              },
              {
                q: '"Were these results walk-forward or in-sample?"',
                why: 'In-sample means the strategy saw all the data before making "decisions." Walk-forward means it made decisions in real time. Only one of these tells you anything about the future.'
              },
              {
                q: '"Does your stock universe include companies that were delisted?"',
                why: 'If they only tested stocks that exist today, they\'re quietly removing every company that failed — which artificially inflates returns by an estimated 1-2% per year.'
              },
              {
                q: '"What happens if you shift the start date by 3 months?"',
                why: 'Robust strategies produce similar results regardless of when you start. Fragile strategies can swing from +200% to -30% based on a small shift. This is the single best test of whether results are real.'
              },
              {
                q: '"What was your worst year?"',
                why: 'If they only show cumulative returns without the painful stretches, they\'re hiding something. Every strategy has drawdowns. The question is whether those drawdowns are survivable.'
              },
            ].map((item, i) => (
              <div key={i} className="border-l-2 border-amber-500/40 pl-4">
                <p className="text-amber-100 font-medium text-sm m-0">{item.q}</p>
                <p className="text-amber-200/60 text-xs mt-1 m-0">{item.why}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="prose prose-invert prose-gray max-w-none">
          {/* What We Do Differently */}
          <h2 className="text-2xl font-bold text-white mt-12 mb-4 flex items-center gap-2">
            <BarChart3 className="w-6 h-6 text-blue-400 flex-shrink-0" />
            What RigaCap Does Differently
          </h2>
          <p className="text-gray-300 leading-relaxed text-base">
            We publish walk-forward results, not backtests. Every number on our{' '}
            <Link to="/track-record" className="text-blue-400 underline hover:text-blue-300">track record page</Link>{' '}
            comes from a simulation where the system had no knowledge of the future.
          </p>
          <p className="text-gray-300 leading-relaxed text-base">
            We test from 7 different start dates spanning different market conditions.
            We include the full 2022 bear market — no skipping the hard parts.
            Our parameters are fixed before each test begins, not optimized after
            seeing the results.
          </p>
          <p className="text-gray-300 leading-relaxed text-base">
            Are our returns lower than some backtested strategies you'll find online?
            Absolutely. A walk-forward test will always produce more modest numbers than
            a curve-fitted backtest. That's the point. Our numbers are real — and real
            is what matters when it's your money.
          </p>

          {/* Highlight Box */}
          <div className="bg-blue-500/10 border border-blue-500/30 rounded-xl p-6 my-8">
            <p className="text-blue-200 font-semibold text-lg m-0 mb-2">
              The best backtest result you'll ever see is also the least likely to work.
            </p>
            <p className="text-blue-200/80 m-0">
              Returns and realism are inversely correlated. The more a strategy was
              optimized to fit historical data, the worse it will perform going forward.
              Walk-forward testing is the only methodology that forces honesty.
            </p>
          </div>

          <p className="text-gray-300 leading-relaxed text-base">
            We built RigaCap for ourselves first — to find a system we could actually
            trust with our own capital. Walk-forward validation wasn't a marketing decision.
            It was the only methodology we were willing to stake real money on.
          </p>
          <p className="text-gray-300 leading-relaxed text-base">
            Every signal you receive from RigaCap is generated by the same strategy, with
            the same parameters, that survived five years of walk-forward testing across
            bull markets, bear markets, rate hikes, and recovery rallies. No hindsight.
            No cheating. No lies.
          </p>
        </div>

        {/* CTA */}
        <div className="bg-gradient-to-br from-indigo-900/50 to-blue-900/50 border border-indigo-500/30 rounded-2xl p-8 sm:p-10 my-12 text-center">
          <h2 className="text-2xl sm:text-3xl font-bold text-white mb-3">
            See the Results for Yourself
          </h2>
          <p className="text-blue-200/80 mb-6 max-w-lg mx-auto">
            No cherry-picked charts. No hypothetical returns. Just five years of
            walk-forward validated performance — tested from 7 different start dates.
          </p>
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <Link
              to="/app"
              className="inline-flex items-center justify-center gap-2 bg-amber-500 hover:bg-amber-400 text-gray-950 font-semibold px-8 py-3 rounded-xl transition-colors text-base"
            >
              Start Free Trial
              <ArrowRight size={18} />
            </Link>
            <Link
              to="/track-record"
              className="inline-flex items-center justify-center gap-2 bg-white/10 hover:bg-white/20 text-white font-medium px-8 py-3 rounded-xl transition-colors text-base"
            >
              View Full Track Record
            </Link>
          </div>
          <p className="text-xs text-gray-500 mt-4">
            7-day free trial. $39/month after. Cancel anytime.
          </p>
        </div>

        {/* Disclaimer */}
        <p className="text-xs text-gray-600 leading-relaxed">
          All performance figures are from walk-forward simulations using historical market data.
          Walk-forward testing reduces but does not eliminate all sources of bias. Past performance
          does not guarantee future results. RigaCap provides trading signals only —
          execute trades through your own brokerage account. This article is for educational
          purposes and does not constitute investment advice. See our{' '}
          <Link to="/terms" className="text-gray-500 underline hover:text-gray-400">Terms of Service</Link>{' '}
          for full disclaimers.
        </p>
      </article>

      {/* Footer */}
      <footer className="border-t border-gray-800 py-8 text-center text-xs text-gray-600">
        <p>&copy; {new Date().getFullYear()} RigaCap. All rights reserved.</p>
      </footer>
    </div>
  );
}
