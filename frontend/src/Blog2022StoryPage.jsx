import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, Shield, TrendingDown, TrendingUp, Clock, BarChart3, ArrowRight } from 'lucide-react';

export default function Blog2022StoryPage() {
  useEffect(() => { document.title = 'The 2022 Story | RigaCap'; }, []);
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
      <section className="relative overflow-hidden bg-gradient-to-br from-red-900/80 via-gray-900 to-emerald-900/60">
        <div className="absolute inset-0 overflow-hidden">
          <div className="absolute -top-40 -right-40 w-80 h-80 bg-red-500/10 rounded-full blur-3xl"></div>
          <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-emerald-500/10 rounded-full blur-3xl"></div>
        </div>
        <div className="relative max-w-3xl mx-auto px-4 sm:px-6 py-16 sm:py-24 text-center">
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-white/10 backdrop-blur-sm rounded-full text-sm font-medium mb-6">
            <Shield className="w-4 h-4 text-amber-300" />
            <span className="text-white/90">Walk-Forward Validated</span>
          </div>
          <h1 className="text-4xl sm:text-5xl font-bold text-white tracking-tight mb-4">
            The 2022 Story
          </h1>
          <p className="text-lg text-blue-200/80 max-w-2xl mx-auto">
            The S&P 500 fell 20%. Our system gained 6%.
            <br className="hidden sm:block" />
            Here's exactly how — and why it matters.
          </p>
        </div>
      </section>

      {/* Comparison Cards */}
      <section className="max-w-3xl mx-auto px-4 sm:px-6 -mt-8 relative z-10">
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-gray-900 border border-red-500/30 rounded-xl p-6 text-center">
            <TrendingDown className="w-6 h-6 text-red-400 mx-auto mb-2" />
            <div className="text-3xl sm:text-4xl font-bold text-red-400">-20.4%</div>
            <div className="text-xs text-gray-500 uppercase tracking-wider mt-1">S&P 500</div>
            <div className="text-xs text-gray-600 mt-0.5">2022 Calendar Year</div>
          </div>
          <div className="bg-gray-900 border border-emerald-500/30 rounded-xl p-6 text-center">
            <TrendingUp className="w-6 h-6 text-emerald-400 mx-auto mb-2" />
            <div className="text-3xl sm:text-4xl font-bold text-emerald-400">+6.0%</div>
            <div className="text-xs text-gray-500 uppercase tracking-wider mt-1">RigaCap</div>
            <div className="text-xs text-gray-600 mt-0.5">Walk-Forward Validated</div>
          </div>
        </div>
      </section>

      {/* Article Body */}
      <article className="max-w-3xl mx-auto px-4 sm:px-6 py-12 sm:py-16">
        <div className="prose prose-invert prose-gray max-w-none">

          {/* The Setup */}
          <h2 className="text-2xl font-bold text-white mt-0 mb-4 flex items-center gap-2">
            The Year Everyone Lost Money
          </h2>
          <p className="text-gray-300 leading-relaxed text-base">
            2022 was brutal. The Fed hiked rates seven times. Inflation hit 9.1%.
            The S&P 500 dropped 20.4% — its worst year since 2008. The Nasdaq fell 33%.
            Bonds, which were supposed to be safe, dropped 13%. There was nowhere to hide.
          </p>
          <p className="text-gray-300 leading-relaxed text-base">
            Every "buy the dip" call turned into a falling knife.
            Every bounce turned into a lower high.
            Retail investors who tried to time the bottom got destroyed.
          </p>

          {/* What Our System Did */}
          <h2 className="text-2xl font-bold text-white mt-12 mb-4 flex items-center gap-2">
            <Clock className="w-6 h-6 text-amber-400 flex-shrink-0" />
            What Our System Did: Nothing
          </h2>
          <p className="text-gray-300 leading-relaxed text-base">
            For five consecutive months, our system generated zero buy signals. Zero.
          </p>
          <p className="text-gray-300 leading-relaxed text-base">
            It detected that market conditions were unfavorable — the SPY was trading below its
            200-day moving average, our 7-regime model classified conditions as a bear market —
            and it refused to deploy capital. It sat on its hands while everyone else
            was trying to catch a falling knife.
          </p>

          {/* Highlight Box */}
          <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-6 my-8">
            <p className="text-amber-200 font-semibold text-lg m-0 mb-2">
              The hardest thing in trading isn't knowing when to buy.
            </p>
            <p className="text-amber-200/80 m-0">
              It's knowing when to do nothing. Our system doesn't have ego,
              doesn't get bored, and doesn't feel pressure to justify a subscription fee
              by generating activity. When conditions are wrong, it waits.
            </p>
          </div>

          <p className="text-gray-300 leading-relaxed text-base">
            When the regime filter finally cleared — when conditions showed genuine
            recovery, not a dead cat bounce — the system re-entered with precision.
            Concentrated positions in momentum leaders. 12% trailing stops to protect gains.
          </p>
          <p className="text-gray-300 leading-relaxed text-base">
            The result: <span className="text-emerald-400 font-semibold">+6.0% for the year</span>.
            Not spectacular. Not a moonshot. But while the S&P 500 lost a fifth of its value,
            our subscribers would have been up.
          </p>

          {/* The Math */}
          <h2 className="text-2xl font-bold text-white mt-12 mb-4 flex items-center gap-2">
            <BarChart3 className="w-6 h-6 text-blue-400 flex-shrink-0" />
            Why This Matters More Than a 50% Year
          </h2>
          <p className="text-gray-300 leading-relaxed text-base">
            Anyone can make money in a bull market. 2021 and 2025 were easy — stocks
            went up, momentum was everywhere, and even random picks did well.
            The real test of a strategy is what happens when the market turns against you.
          </p>
        </div>

        {/* Comparison Table */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden my-8">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800">
                <th className="text-left px-6 py-3 text-xs uppercase tracking-wider text-gray-500 font-semibold">Scenario</th>
                <th className="text-right px-6 py-3 text-xs uppercase tracking-wider text-gray-500 font-semibold">$10,000 Start</th>
                <th className="text-right px-6 py-3 text-xs uppercase tracking-wider text-gray-500 font-semibold">After 2022</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-gray-800/50">
                <td className="px-6 py-4 text-gray-400">S&P 500 Index Fund</td>
                <td className="px-6 py-4 text-right text-gray-400">$10,000</td>
                <td className="px-6 py-4 text-right text-red-400 font-semibold">$7,960</td>
              </tr>
              <tr className="border-b border-gray-800/50">
                <td className="px-6 py-4 text-gray-400">Average Hedge Fund</td>
                <td className="px-6 py-4 text-right text-gray-400">$10,000</td>
                <td className="px-6 py-4 text-right text-red-400 font-semibold">$9,360</td>
              </tr>
              <tr className="bg-emerald-500/10 border-t border-emerald-500/30">
                <td className="px-6 py-4 text-emerald-400 font-medium">RigaCap</td>
                <td className="px-6 py-4 text-right text-gray-400">$10,000</td>
                <td className="px-6 py-4 text-right text-emerald-400 font-bold">$10,600</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div className="prose prose-invert prose-gray max-w-none">
          <p className="text-gray-300 leading-relaxed text-base">
            The difference between losing 20% and gaining 6% isn't just 26 percentage points.
            It's the compounding effect. Someone who lost 20% in 2022 needed a 25% gain in
            2023 just to get back to even. Our subscribers started 2023 already ahead —
            and compounded from there.
          </p>

          {/* How It Works */}
          <h2 className="text-2xl font-bold text-white mt-12 mb-4">
            The Three Lines of Defense
          </h2>
          <p className="text-gray-300 leading-relaxed text-base">
            Our system didn't predict the 2022 crash. Nobody did. Instead, it has
            three built-in mechanisms that protect capital when conditions deteriorate:
          </p>
        </div>

        {/* Defense Cards */}
        <div className="grid gap-4 my-8">
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 rounded-lg bg-red-500/20 flex items-center justify-center flex-shrink-0">
                <span className="text-red-400 font-bold">1</span>
              </div>
              <div>
                <h3 className="text-white font-semibold mb-1">7-Regime Market Intelligence</h3>
                <p className="text-gray-400 text-sm m-0">
                  Our proprietary model classifies the market into 7 distinct regimes — from
                  strong bull to panic crash. When conditions shift to unfavorable territory,
                  the system stops buying entirely. No new positions. Full cash. This alone
                  avoided the worst of 2022.
                </p>
              </div>
            </div>
          </div>
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 rounded-lg bg-amber-500/20 flex items-center justify-center flex-shrink-0">
                <span className="text-amber-400 font-bold">2</span>
              </div>
              <div>
                <h3 className="text-white font-semibold mb-1">Automatic Downside Protection</h3>
                <p className="text-gray-400 text-sm m-0">
                  Every position has a dynamic trailing stop that locks in gains as a stock rises.
                  If it reverses, we exit automatically — no hesitation, no hoping for a bounce.
                  Losses are capped before they can compound.
                </p>
              </div>
            </div>
          </div>
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 rounded-lg bg-blue-500/20 flex items-center justify-center flex-shrink-0">
                <span className="text-blue-400 font-bold">3</span>
              </div>
              <div>
                <h3 className="text-white font-semibold mb-1">Ensemble Entry Scoring</h3>
                <p className="text-gray-400 text-sm m-0">
                  We don't chase stocks — we wait for multiple independent signals to align.
                  Timing, momentum, and breakout confirmation must all agree before we enter.
                  In a bear market, almost nothing passes this filter — which is exactly the point.
                </p>
              </div>
            </div>
          </div>
        </div>

        <div className="prose prose-invert prose-gray max-w-none">
          {/* The Bigger Picture */}
          <h2 className="text-2xl font-bold text-white mt-12 mb-4">
            The Bigger Picture: 5 Years, Zero Losing Years
          </h2>
          <p className="text-gray-300 leading-relaxed text-base">
            2022 wasn't a fluke. Across 5 years of walk-forward testing — starting from
            multiple start dates to eliminate timing luck — the system has never had a losing year.
          </p>
        </div>

        {/* 5-Year Summary */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden my-8">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800">
                <th className="text-left px-6 py-3 text-xs uppercase tracking-wider text-gray-500 font-semibold">Year</th>
                <th className="text-right px-6 py-3 text-xs uppercase tracking-wider text-gray-500 font-semibold">RigaCap</th>
                <th className="text-right px-6 py-3 text-xs uppercase tracking-wider text-gray-500 font-semibold">S&P 500</th>
                <th className="text-left px-6 py-3 text-xs uppercase tracking-wider text-gray-500 font-semibold hidden sm:table-cell">Note</th>
              </tr>
            </thead>
            <tbody>
              {[
                { year: '2021', rc: '+4.6%', spy: '+21.0%', note: 'Choppy momentum rotations', rcColor: 'text-emerald-400' },
                { year: '2022', rc: '+6.0%', spy: '-20.4%', note: 'Bear market — stayed positive', rcColor: 'text-emerald-400', highlight: true },
                { year: '2023', rc: '+4.5%', spy: '+23.4%', note: 'Cautious recovery positioning', rcColor: 'text-emerald-400' },
                { year: '2024', rc: '+20.3%', spy: '+23.8%', note: 'Near parity with SPY', rcColor: 'text-emerald-400' },
                { year: '2025', rc: '+57.4%', spy: '+18.3%', note: 'Breakout year — 3x SPY', rcColor: 'text-emerald-400' },
              ].map((row) => (
                <tr key={row.year} className={`border-b border-gray-800/50 ${row.highlight ? 'bg-amber-500/10' : ''}`}>
                  <td className={`px-6 py-4 font-medium ${row.highlight ? 'text-amber-400' : 'text-white'}`}>{row.year}</td>
                  <td className={`px-6 py-4 text-right font-semibold ${row.rcColor}`}>{row.rc}</td>
                  <td className={`px-6 py-4 text-right ${row.spy.startsWith('-') ? 'text-red-400' : 'text-gray-400'}`}>{row.spy}</td>
                  <td className="px-6 py-4 text-gray-500 text-xs hidden sm:table-cell">{row.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="prose prose-invert prose-gray max-w-none">
          <p className="text-gray-300 leading-relaxed text-base">
            The system doesn't try to beat the market every year. In bull markets like 2023,
            it may lag the S&P. But it never gives back what it earned. Over 5 years,
            the average total return is +240% vs. the S&P's +84%.
          </p>

          {/* Methodology Note */}
          <h2 className="text-2xl font-bold text-white mt-12 mb-4">
            How We Know This Is Real
          </h2>
          <p className="text-gray-300 leading-relaxed text-base">
            These aren't backtested results — they're walk-forward validated. The difference
            matters.
          </p>
          <p className="text-gray-300 leading-relaxed text-base">
            A backtest looks at historical data and finds parameters that would have worked.
            Walk-forward testing is harder: the system sees only the data that was available
            at each point in time, makes decisions in real-time, and can never peek ahead.
            There's no hindsight bias, no curve-fitting, no cherry-picking.
          </p>
          <p className="text-gray-300 leading-relaxed text-base">
            We run each simulation from multiple start dates to prove the results
            aren't dependent on when you begin. Every single start date produced a positive
            5-year return. Every single one beat the S&P 500.
          </p>
        </div>

        {/* CTA */}
        <div className="bg-gradient-to-br from-indigo-900/50 to-blue-900/50 border border-indigo-500/30 rounded-2xl p-8 sm:p-10 my-12 text-center">
          <h2 className="text-2xl sm:text-3xl font-bold text-white mb-3">
            Stop Trading on Emotions
          </h2>
          <p className="text-blue-200/80 mb-6 max-w-lg mx-auto">
            The next bear market is coming. The question is whether your portfolio
            will be protected by math or exposed by emotion.
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

        {/* Related Reading */}
        <div className="mt-12 pt-8 border-t border-gray-800">
          <h3 className="text-lg font-semibold text-white mb-4">Related Reading</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Link to="/blog/market-regime-guide" className="block p-4 bg-gray-900 rounded-lg border border-gray-800 hover:border-gray-600 transition-colors">
              <span className="text-white font-medium">Market Regime Trading: A Beginner's Guide</span>
              <span className="block text-gray-500 text-sm mt-1">How regime detection helped navigate the 2022 bear market.</span>
            </Link>
            <Link to="/blog/trailing-stops" className="block p-4 bg-gray-900 rounded-lg border border-gray-800 hover:border-gray-600 transition-colors">
              <span className="text-white font-medium">How Trailing Stops Protect Your Portfolio</span>
              <span className="block text-gray-500 text-sm mt-1">The trailing stop mechanism that limited drawdowns during 2022.</span>
            </Link>
            <Link to="/blog/walk-forward-results" className="block p-4 bg-gray-900 rounded-lg border border-gray-800 hover:border-gray-600 transition-colors">
              <span className="text-white font-medium">Inside Our 5-Year Walk-Forward</span>
              <span className="block text-gray-500 text-sm mt-1">Full performance breakdown including the 2022 period.</span>
            </Link>
          </div>
        </div>

        {/* Disclaimer */}
        <p className="text-xs text-gray-600 leading-relaxed">
          All performance figures are from walk-forward simulations using historical market data.
          Past performance does not guarantee future results. RigaCap provides trading signals only —
          execute trades through your own brokerage account. See our{' '}
          <Link to="/terms" className="text-gray-500 underline hover:text-gray-400">Terms of Service</Link>{' '}
          for full disclaimers.
        </p>
      </article>

      {/* Footer */}
      <footer className="border-t border-gray-800 py-8 text-center text-xs text-gray-600">
        <p>&copy; {new Date().getFullYear()} RigaCap, LLC. All rights reserved.</p>
      </footer>
    </div>
  );
}
