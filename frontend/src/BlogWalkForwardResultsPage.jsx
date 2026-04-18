import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, ArrowRight, TrendingUp, TrendingDown, BarChart3, Target, AlertTriangle, Zap, LineChart, ShieldCheck } from 'lucide-react';
import MarketMeasuredSignup from './components/MarketMeasuredSignup';

export default function BlogWalkForwardResultsPage() {
  useEffect(() => { document.title = 'Inside Our 5-Year Walk-Forward | RigaCap'; }, []);
    const meta = document.querySelector('meta[name="description"]');
    if (meta) meta.setAttribute('content', 'Inside RigaCap 5-year walk-forward simulation: +297% total return, 1.10 Sharpe ratio, tested across 138 rebalancing periods.');
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
      <section className="relative overflow-hidden bg-gradient-to-br from-blue-900/80 via-gray-900 to-indigo-900/60">
        <div className="absolute inset-0 overflow-hidden">
          <div className="absolute -top-40 -right-40 w-80 h-80 bg-blue-500/10 rounded-full blur-3xl"></div>
          <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-indigo-500/10 rounded-full blur-3xl"></div>
        </div>
        <div className="relative max-w-3xl mx-auto px-4 sm:px-6 py-16 sm:py-24 text-center">
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-white/10 backdrop-blur-sm rounded-full text-sm font-medium mb-6">
            <LineChart className="w-4 h-4 text-amber-300" />
            <span className="text-white/90">Walk-Forward Validated</span>
          </div>
          <h1 className="text-4xl sm:text-5xl font-bold text-white tracking-tight mb-4">
            Inside Our 5-Year Walk-Forward
          </h1>
          <p className="text-lg text-blue-200/80 max-w-2xl mx-auto">
            Most trading strategies look great on paper. Ours looked great on paper too
            <br className="hidden sm:block" />
            — so we spent months trying to break it.
          </p>
        </div>
      </section>

      {/* Comparison Cards */}
      <section className="max-w-3xl mx-auto px-4 sm:px-6 -mt-8 relative z-10">
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-gray-900 border border-emerald-500/30 rounded-xl p-6 text-center">
            <TrendingUp className="w-6 h-6 text-emerald-400 mx-auto mb-2" />
            <div className="text-3xl sm:text-4xl font-bold text-emerald-400">+297.8%</div>
            <div className="text-xs text-gray-500 uppercase tracking-wider mt-1">Our Strategy</div>
            <div className="text-xs text-gray-600 mt-0.5">5-Year Walk-Forward</div>
          </div>
          <div className="bg-gray-900 border border-gray-700/50 rounded-xl p-6 text-center">
            <BarChart3 className="w-6 h-6 text-gray-400 mx-auto mb-2" />
            <div className="text-3xl sm:text-4xl font-bold text-gray-400">+85.9%</div>
            <div className="text-xs text-gray-500 uppercase tracking-wider mt-1">S&P 500</div>
            <div className="text-xs text-gray-600 mt-0.5">Same Period</div>
          </div>
        </div>
      </section>

      {/* Article Body */}
      <article className="max-w-3xl mx-auto px-4 sm:px-6 py-12 sm:py-16">
        <div className="prose prose-invert prose-lg max-w-none">

          {/* Opening */}
          <h2 className="text-2xl font-bold text-white mt-0 mb-4">
            Trying to Break Our Own Strategy
          </h2>
          <p className="text-gray-300 leading-relaxed text-base">
            It's easy to build a strategy that performs well on historical data. You pick
            the right indicators, tune the parameters until the equity curve looks beautiful,
            and declare victory. The problem? Most of those strategies fall apart the moment
            real money is on the line.
          </p>
          <p className="text-gray-300 leading-relaxed text-base">
            We didn't want to build another one of those. So instead of asking "how good
            can we make this look?", we asked "how hard can we stress-test this before it
            breaks?" The answer: 5.3 years, 138 rebalancing periods, 500 stocks, and zero
            peeking at the future.
          </p>

          {/* What is walk-forward */}
          <h2 className="text-2xl font-bold text-white mt-12 mb-4 flex items-center gap-2">
            <ShieldCheck className="w-6 h-6 text-blue-400 flex-shrink-0" />
            What Walk-Forward Testing Actually Is
          </h2>
          <p className="text-gray-300 leading-relaxed text-base">
            Walk-forward testing is the gold standard for validating trading strategies. Unlike
            a regular backtest — where you optimize on the full dataset and risk curve-fitting —
            walk-forward testing simulates real-world conditions. The system only sees data that
            was available at each point in time. It makes decisions, records results, then moves
            forward. No hindsight. No do-overs.
          </p>
          <p className="text-gray-300 leading-relaxed text-base">
            Every two weeks, the system re-optimizes its parameters using only backward-looking
            data, then trades the next period with those fresh parameters. If the optimization
            was just finding noise, the out-of-sample performance would collapse. Ours didn't.
          </p>
          <p className="text-gray-300 leading-relaxed text-base">
            For a deeper dive into the methodology, see our{' '}
            <Link to="/blog/backtests" className="text-blue-400 hover:text-blue-300 underline">
              complete guide to backtesting vs. walk-forward testing
            </Link>.
          </p>

          {/* Our setup */}
          <h2 className="text-2xl font-bold text-white mt-12 mb-4 flex items-center gap-2">
            <Target className="w-6 h-6 text-amber-400 flex-shrink-0" />
            Our Testing Setup
          </h2>
          <p className="text-gray-300 leading-relaxed text-base">
            The parameters of the test were deliberately punishing:
          </p>
        </div>

        {/* Setup Details */}
        <div className="grid sm:grid-cols-2 gap-4 my-8">
          {[
            { label: 'Time Span', value: '5.3 Years', detail: 'Jan 2021 through early 2026' },
            { label: 'Periods', value: '138', detail: 'Regular rebalancing' },
            { label: 'Stock Universe', value: '500', detail: 'Liquid US equities' },
            { label: 'Re-optimization', value: 'Every 2 Weeks', detail: 'Backward-looking data only' },
          ].map((item) => (
            <div key={item.label} className="bg-gray-900 border border-gray-800 rounded-xl p-5">
              <div className="text-xs text-gray-500 uppercase tracking-wider">{item.label}</div>
              <div className="text-2xl font-bold text-white mt-1">{item.value}</div>
              <div className="text-xs text-gray-500 mt-1">{item.detail}</div>
            </div>
          ))}
        </div>

        <div className="prose prose-invert prose-lg max-w-none">
          <p className="text-gray-300 leading-relaxed text-base">
            This window captures everything: the post-COVID momentum surge of early 2021,
            the brutal 2022 bear market, the cautious 2023 recovery, and the AI-fueled rally
            of 2024-2025. If a strategy can survive all of that without hindsight bias, it's
            worth paying attention to.
          </p>

          {/* Headline Results */}
          <h2 className="text-2xl font-bold text-white mt-12 mb-4 flex items-center gap-2">
            <TrendingUp className="w-6 h-6 text-emerald-400 flex-shrink-0" />
            The Headline Results
          </h2>
        </div>

        {/* Results Table */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden my-8">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800">
                <th className="text-left px-6 py-3 text-xs uppercase tracking-wider text-gray-500 font-semibold">Metric</th>
                <th className="text-right px-6 py-3 text-xs uppercase tracking-wider text-gray-500 font-semibold">Our Strategy</th>
                <th className="text-right px-6 py-3 text-xs uppercase tracking-wider text-gray-500 font-semibold">S&P 500</th>
              </tr>
            </thead>
            <tbody>
              {[
                { metric: 'Total Return', ours: '+297.8%', spy: '+85.9%', highlight: true },
                { metric: 'Sharpe Ratio', ours: '1.10', spy: '0.65' },
                { metric: 'Max Drawdown', ours: '-29.97%', spy: '-25.4%' },
                { metric: 'Annualized Return', ours: '~30%', spy: '~12%' },
                { metric: 'Testing Periods', ours: '138', spy: '—' },
              ].map((row) => (
                <tr key={row.metric} className={`border-b border-gray-800/50 ${row.highlight ? 'bg-emerald-500/5' : ''}`}>
                  <td className="px-6 py-4 text-gray-400 font-medium">{row.metric}</td>
                  <td className={`px-6 py-4 text-right font-semibold ${row.highlight ? 'text-emerald-400' : 'text-white'}`}>{row.ours}</td>
                  <td className="px-6 py-4 text-right text-gray-500">{row.spy}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="prose prose-invert prose-lg max-w-none">
          <p className="text-gray-300 leading-relaxed text-base">
            A 1.10 Sharpe ratio won't make hedge fund managers jealous — but for a fully
            systematic, rules-based strategy with no discretionary overrides, it signals
            genuine risk-adjusted alpha. The S&P 500's Sharpe over the same window was roughly
            0.65. Our strategy delivered nearly triple the total return with a similar drawdown
            profile.
          </p>

          {/* Equity Curve Description */}
          <h2 className="text-2xl font-bold text-white mt-12 mb-4 flex items-center gap-2">
            <LineChart className="w-6 h-6 text-indigo-400 flex-shrink-0" />
            The Shape of the Equity Curve
          </h2>
          <p className="text-gray-300 leading-relaxed text-base">
            The equity curve tells the real story. Early 2021 was strong — momentum was
            everywhere, and the system captured it aggressively. Then came the 2022 bear
            market, and the curve went flat. Not down. Flat. The regime filter moved the
            portfolio to cash, and it stayed there for months while the market shed 20%.
          </p>
          <p className="text-gray-300 leading-relaxed text-base">
            When the recovery began in late 2022 and into 2023, the system re-entered
            cautiously — small gains, measured risk. Then came the acceleration: 2024 and
            2025 saw the curve steepen dramatically as the AI rally created exactly the kind
            of concentrated momentum the system was built to exploit. The best gains came not
            from predicting the rally, but from being positioned when it arrived.
          </p>

          {/* Worst and Best Periods */}
          <h2 className="text-2xl font-bold text-white mt-12 mb-4 flex items-center gap-2">
            <AlertTriangle className="w-6 h-6 text-amber-400 flex-shrink-0" />
            The Best and Worst Periods
          </h2>
          <p className="text-gray-300 leading-relaxed text-base">
            No strategy wins every period. Here are the extremes — and what they reveal
            about how the system handles both euphoria and panic.
          </p>
        </div>

        {/* Best/Worst Table */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden my-8">
          <div className="px-6 py-3 border-b border-gray-800 bg-gray-900/50">
            <span className="text-xs uppercase tracking-wider text-gray-500 font-semibold">Worst Periods</span>
          </div>
          <table className="w-full text-sm">
            <tbody>
              {[
                { period: 'Feb 2021', ret: '-16.6%', context: 'Meme stock squeeze volatility' },
                { period: 'Mar 2021', ret: '-12.5%', context: 'Post-squeeze rotation' },
                { period: 'Sep 2021', ret: '-8.3%', context: 'Sector rotation whipsaw' },
              ].map((row) => (
                <tr key={row.period} className="border-b border-gray-800/50">
                  <td className="px-6 py-3 text-gray-400 font-medium w-28">{row.period}</td>
                  <td className="px-6 py-3 text-right text-red-400 font-semibold w-24">{row.ret}</td>
                  <td className="px-6 py-3 text-gray-500 text-xs">{row.context}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="px-6 py-3 border-b border-t border-gray-800 bg-gray-900/50">
            <span className="text-xs uppercase tracking-wider text-gray-500 font-semibold">Best Periods</span>
          </div>
          <table className="w-full text-sm">
            <tbody>
              {[
                { period: 'Jan 2021', ret: '+24.5%', context: 'Post-COVID momentum surge' },
                { period: 'Sep 2025', ret: '+19.9%', context: 'AI rally breakout' },
                { period: 'Nov 2024', ret: '+16.1%', context: 'Year-end momentum leaders' },
              ].map((row) => (
                <tr key={row.period} className="border-b border-gray-800/50">
                  <td className="px-6 py-3 text-gray-400 font-medium w-28">{row.period}</td>
                  <td className="px-6 py-3 text-right text-emerald-400 font-semibold w-24">{row.ret}</td>
                  <td className="px-6 py-3 text-gray-500 text-xs">{row.context}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="prose prose-invert prose-lg max-w-none">
          <p className="text-gray-300 leading-relaxed text-base">
            The worst drawdowns both came during the meme stock frenzy of early 2021.
            Momentum strategies are vulnerable to sudden reversals, and the GameStop/AMC
            squeeze created exactly that kind of whiplash. But the system recovered within
            two periods each time — the trailing stops limited the damage, and the momentum
            ranking quickly rotated into stronger names.
          </p>

          {/* Adaptive vs Fixed */}
          <h2 className="text-2xl font-bold text-white mt-12 mb-4 flex items-center gap-2">
            <Zap className="w-6 h-6 text-amber-400 flex-shrink-0" />
            Why Adaptive Beats Fixed
          </h2>
          <p className="text-gray-300 leading-relaxed text-base">
            Here's a result that surprised even us. We ran the same strategy with fixed
            parameters — no re-optimization, just locked-in settings from day one — over
            the identical 5-year window.
          </p>
        </div>

        {/* Adaptive vs Fixed comparison */}
        <div className="grid grid-cols-2 gap-4 my-8">
          <div className="bg-gray-900 border border-emerald-500/30 rounded-xl p-6 text-center">
            <Zap className="w-6 h-6 text-emerald-400 mx-auto mb-2" />
            <div className="text-3xl sm:text-4xl font-bold text-emerald-400">+297.8%</div>
            <div className="text-xs text-gray-500 uppercase tracking-wider mt-1">Adaptive</div>
            <div className="text-xs text-gray-600 mt-0.5">Re-optimized biweekly</div>
          </div>
          <div className="bg-gray-900 border border-gray-700/50 rounded-xl p-6 text-center">
            <TrendingDown className="w-6 h-6 text-gray-500 mx-auto mb-2" />
            <div className="text-3xl sm:text-4xl font-bold text-gray-500">+99%</div>
            <div className="text-xs text-gray-500 uppercase tracking-wider mt-1">Fixed Params</div>
            <div className="text-xs text-gray-600 mt-0.5">Same strategy, no adaptation</div>
          </div>
        </div>

        <div className="prose prose-invert prose-lg max-w-none">
          <p className="text-gray-300 leading-relaxed text-base">
            The fixed-parameter version still beat the S&P 500 — which validates the
            underlying strategy logic. But periodic re-optimization tripled the returns.
            Markets change. The momentum characteristics of a post-COVID recovery are
            different from a Fed tightening cycle, which are different from an AI-driven
            tech rally. A strategy that adapts its sensitivity to current conditions
            captures opportunities that a rigid system misses.
          </p>

          {/* What we're NOT claiming */}
          <h2 className="text-2xl font-bold text-white mt-12 mb-4 flex items-center gap-2">
            <AlertTriangle className="w-6 h-6 text-red-400 flex-shrink-0" />
            What We're NOT Claiming
          </h2>
          <p className="text-gray-300 leading-relaxed text-base">
            Transparency matters more than marketing. Here's what you should know:
          </p>
        </div>

        {/* Honesty Box */}
        <div className="bg-red-500/5 border border-red-500/20 rounded-xl p-6 my-8 space-y-3">
          <p className="text-gray-300 text-sm m-0">
            <span className="text-red-400 font-semibold">This is simulation, not live trading.</span>{' '}
            Walk-forward testing removes hindsight bias, but it still assumes perfect execution
            at closing prices. Real-world slippage and commissions would reduce returns modestly.
          </p>
          <p className="text-gray-300 text-sm m-0">
            <span className="text-red-400 font-semibold">Past performance does not guarantee future results.</span>{' '}
            The next 5 years could look nothing like the last 5. Market regimes shift, correlations
            break down, and black swans happen. We believe our adaptive approach handles this better
            than fixed strategies, but nothing is certain.
          </p>
          <p className="text-gray-300 text-sm m-0">
            <span className="text-red-400 font-semibold">The max drawdown was real.</span>{' '}
            At its worst, the strategy was down nearly 30% from its peak. That's a real number
            that would test any investor's resolve. We don't hide it behind averages.
          </p>
        </div>

        <div className="prose prose-invert prose-lg max-w-none">
          <p className="text-gray-300 leading-relaxed text-base">
            We publish these numbers because we believe in the methodology, and because
            we think investors deserve to see exactly what they're getting — the rough
            periods alongside the smooth ones. If a strategy can only be sold by hiding the
            drawdowns, it isn't worth selling.
          </p>
        </div>

        {/* CTA */}
        <div className="bg-gradient-to-br from-indigo-900/50 to-blue-900/50 border border-indigo-500/30 rounded-2xl p-8 sm:p-10 my-12 text-center">
          <h2 className="text-2xl sm:text-3xl font-bold text-white mb-3">
            See the Live Track Record
          </h2>
          <p className="text-blue-200/80 mb-6 max-w-lg mx-auto">
            Our walk-forward results are validated. Our track record is public. See the
            real numbers and decide for yourself.
          </p>
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <Link
              to="/track-record"
              className="inline-flex items-center justify-center gap-2 bg-amber-500 hover:bg-amber-400 text-gray-950 font-semibold px-8 py-3 rounded-xl transition-colors text-base"
            >
              View Track Record
              <ArrowRight size={18} />
            </Link>
            <Link
              to="/blog/backtests"
              className="inline-flex items-center justify-center gap-2 bg-white/10 hover:bg-white/20 text-white font-medium px-8 py-3 rounded-xl transition-colors text-base"
            >
              Read: Backtests Deep-Dive
            </Link>
          </div>
          <p className="text-xs text-gray-500 mt-4">
            7-day free trial. $39/month after. Cancel anytime.
          </p>
        </div>

  
      {/* Weekly newsletter signup */}
      <div className="max-w-3xl mx-auto px-4 sm:px-6 mb-8">
        <MarketMeasuredSignup source="blog_post" variant="dark" />
      </div>

      {/* Related Reading */}
        <div className="mt-12 pt-8 border-t border-gray-800">
          <h3 className="text-lg font-semibold text-white mb-4">Related Reading</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Link to="/blog/backtests" className="block p-4 bg-gray-900 rounded-lg border border-gray-800 hover:border-gray-600 transition-colors">
              <span className="text-white font-medium">Why Most Backtests Are Lies</span>
              <span className="block text-gray-500 text-sm mt-1">The hidden biases that make most backtests worthless and how walk-forward fixes them.</span>
            </Link>
            <Link to="/blog/2022-story" className="block p-4 bg-gray-900 rounded-lg border border-gray-800 hover:border-gray-600 transition-colors">
              <span className="text-white font-medium">The 2022 Story</span>
              <span className="block text-gray-500 text-sm mt-1">How our system navigated the worst bear market in a decade.</span>
            </Link>
            <Link to="/blog/momentum-trading" className="block p-4 bg-gray-900 rounded-lg border border-gray-800 hover:border-gray-600 transition-colors">
              <span className="text-white font-medium">Momentum Trading Explained</span>
              <span className="block text-gray-500 text-sm mt-1">The momentum ranking and breakout timing behind our signals.</span>
            </Link>
          </div>
        </div>

        {/* Disclaimer */}
        <p className="text-xs text-gray-600 leading-relaxed">
          Walk-forward simulation results. Past performance does not guarantee future results.
          Not investment advice. RigaCap provides trading signals only — execute trades through
          your own brokerage account. See our{' '}
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
