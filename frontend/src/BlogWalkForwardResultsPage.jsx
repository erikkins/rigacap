import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, ArrowRight, TrendingUp, TrendingDown, BarChart3, Target, AlertTriangle, Zap, LineChart, ShieldCheck } from 'lucide-react';
import MarketMeasuredSignup from './components/MarketMeasuredSignup';

export default function BlogWalkForwardResultsPage() {
  useEffect(() => { document.title = 'Inside Our 5-Year Walk-Forward | RigaCap';
    const meta = document.querySelector('meta[name="description"]');
    if (meta) meta.setAttribute('content', 'RigaCap 5-year walk-forward simulation across multiple start dates: +160% average return, 0.92 Sharpe, 20.4% max drawdown. Every start date positive, every calendar year positive.');

    // OG tags for social sharing
    document.querySelector('meta[property="og:title"]')?.setAttribute('content', 'Inside Our 5-Year Walk-Forward | RigaCap');
    document.querySelector('meta[property="og:description"]')?.setAttribute('content', 'RigaCap 5-year walk-forward simulation across multiple start dates: +160% average return, 0.92 Sharpe, 20.4% max drawdown. Every start date positive, every calendar year positive.');
    document.querySelector('meta[property="og:url"]')?.setAttribute('content', 'https://rigacap.com/blog/walk-forward-results');
    document.querySelector('meta[name="twitter:title"]')?.setAttribute('content', 'Inside Our 5-Year Walk-Forward | RigaCap');
    document.querySelector('meta[name="twitter:description"]')?.setAttribute('content', 'RigaCap 5-year walk-forward simulation across multiple start dates: +160% average return, 0.92 Sharpe, 20.4% max drawdown.');
    // JSON-LD Article schema
    const existingSchema = document.querySelector('script[type="application/ld+json"]');
    if (existingSchema) existingSchema.remove();
    const schema = document.createElement('script');
    schema.type = 'application/ld+json';
    schema.text = JSON.stringify({
      "@context": "https://schema.org",
      "@type": "Article",
      "headline": "Inside Our 5-Year Walk-Forward",
      "description": "RigaCap 5-year walk-forward simulation across multiple start dates: +160% average return, 0.92 Sharpe, 20.4% max drawdown. Every start date positive, every calendar year positive.",
      "author": {"@type": "Organization", "name": "RigaCap"},
      "publisher": {"@type": "Organization", "name": "RigaCap", "url": "https://rigacap.com"},
      "url": "https://rigacap.com/blog/walk-forward-results",
      "articleSection": "Results",
    });
    document.head.appendChild(schema);
    return () => { if (schema.parentNode) schema.remove(); };
  }, []);  return (
    <div className="min-h-screen bg-paper font-body text-ink">
      {/* Nav */}
      <nav className="sticky top-0 z-50 bg-paper/95 backdrop-blur-sm border-b border-rule">
        <div className="max-w-3xl mx-auto px-4 py-4 flex items-center gap-4">
          <Link to="/blog" className="flex items-center gap-2 text-ink-mute hover:text-ink transition-colors">
            <ArrowLeft size={18} />
            <span className="text-sm">All articles</span>
          </Link>
        </div>
      </nav>

      {/* Hero */}
      <section className="bg-paper border-b border-rule">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 py-16 sm:py-24 text-center">
          <p className="text-sm font-medium uppercase tracking-wider text-claret mb-6">Walk-Forward Validated</p>
          <h1 className="font-display text-4xl sm:text-5xl font-bold text-ink tracking-tight mb-4" style={{ fontVariationSettings: '"opsz" 48' }}>
            Inside Our 5-Year Walk-Forward
          </h1>
          <p className="text-lg text-ink-mute max-w-2xl mx-auto">
            Most trading strategies look great on paper. Ours looked great on paper too
            <br className="hidden sm:block" />
            — so we spent months trying to break it.
          </p>
        </div>
      </section>

      {/* Comparison Cards */}
      <section className="max-w-3xl mx-auto px-4 sm:px-6 -mt-8 relative z-10">
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-paper-card border border-positive/30 rounded p-6 text-center">
            <TrendingUp className="w-6 h-6 text-positive mx-auto mb-2" />
            <div className="text-3xl sm:text-4xl font-bold text-positive">+160%</div>
            <div className="text-xs text-ink-light uppercase tracking-wider mt-1">Our Strategy</div>
            <div className="text-xs text-ink-light mt-0.5">5-Year Walk-Forward, Avg.</div>
          </div>
          <div className="bg-paper-card border border-rule/50 rounded p-6 text-center">
            <BarChart3 className="w-6 h-6 text-ink-mute mx-auto mb-2" />
            <div className="text-3xl sm:text-4xl font-bold text-ink-mute">+93%</div>
            <div className="text-xs text-ink-light uppercase tracking-wider mt-1">S&P 500</div>
            <div className="text-xs text-ink-light mt-0.5">Same Period</div>
          </div>
        </div>
      </section>

      {/* Article Body */}
      <article className="max-w-3xl mx-auto px-4 sm:px-6 py-12 sm:py-16">
        <div className="space-y-4 text-ink-mute text-[1.05rem] leading-[1.75]">

          {/* Opening */}
          <h2 className="font-display text-2xl font-bold text-ink mt-0 mb-4" style={{ fontVariationSettings: '"opsz" 48' }}>
            Trying to Break Our Own Strategy
          </h2>
          <p className="text-ink-mute leading-relaxed text-base">
            It's easy to build a strategy that performs well on historical data. You pick
            the right indicators, tune the parameters until the equity curve looks beautiful,
            and declare victory. The problem? Most of those strategies fall apart the moment
            real money is on the line.
          </p>
          <p className="text-ink-mute leading-relaxed text-base">
            We didn't want to build another one of those. So instead of asking "how good
            can we make this look?", we asked "how hard can we stress-test this before it
            breaks?" The answer: 5 years, biweekly rebalancing, a universe of 4,000+ liquid
            US equities, multiple start dates, and zero peeking at the future.
          </p>

          {/* What is walk-forward */}
          <h2 className="font-display text-2xl font-bold text-ink mt-12 mb-4 flex items-center gap-2" style={{ fontVariationSettings: '"opsz" 48' }}>
            <ShieldCheck className="w-6 h-6 text-claret flex-shrink-0" />
            What Walk-Forward Testing Actually Is
          </h2>
          <p className="text-ink-mute leading-relaxed text-base">
            Walk-forward testing is the gold standard for validating trading strategies. Unlike
            a regular backtest — where you optimize on the full dataset and risk curve-fitting —
            walk-forward testing simulates real-world conditions. The system only sees data that
            was available at each point in time. It makes decisions, records results, then moves
            forward. No hindsight. No do-overs.
          </p>
          <p className="text-ink-mute leading-relaxed text-base">
            Strategy parameters are fixed at the start of the test and applied forward across
            every period — no per-period re-tuning that could quietly leak future information
            into past decisions. Then we run the same test from <strong className="font-medium">multiple
            start dates</strong> across early 2021. If the strategy were just finding noise, the
            outcomes would diverge wildly. Ours stayed consistent.
          </p>
          <p className="text-ink-mute leading-relaxed text-base">
            For a deeper dive into the methodology, see our{' '}
            <Link to="/blog/backtests" className="text-claret hover:text-claret/80 underline">
              complete guide to backtesting vs. walk-forward testing
            </Link>.
          </p>

          {/* Our setup */}
          <h2 className="font-display text-2xl font-bold text-ink mt-12 mb-4 flex items-center gap-2" style={{ fontVariationSettings: '"opsz" 48' }}>
            <Target className="w-6 h-6 text-claret flex-shrink-0" />
            Our Testing Setup
          </h2>
          <p className="text-ink-mute leading-relaxed text-base">
            The parameters of the test were deliberately punishing:
          </p>
        </div>

        {/* Setup Details */}
        <div className="grid sm:grid-cols-2 gap-4 my-8">
          {[
            { label: 'Time Span', value: '5 Years', detail: 'Jan 2021 through early 2026' },
            { label: 'Rebalance Cadence', value: 'Biweekly', detail: 'Same configuration every period' },
            { label: 'Stock Universe', value: '4,000+', detail: 'Liquid US equities' },
            { label: 'Robustness', value: 'Multi-start', detail: 'Same strategy, different start dates' },
          ].map((item) => (
            <div key={item.label} className="bg-paper-card border border-rule rounded p-5">
              <div className="text-xs text-ink-light uppercase tracking-wider">{item.label}</div>
              <div className="text-2xl font-bold text-ink mt-1">{item.value}</div>
              <div className="text-xs text-ink-light mt-1">{item.detail}</div>
            </div>
          ))}
        </div>

        <div className="space-y-4 text-ink-mute text-[1.05rem] leading-[1.75]">
          <p className="text-ink-mute leading-relaxed text-base">
            This window captures everything: the post-COVID momentum surge of early 2021,
            the brutal 2022 bear market, the cautious 2023 recovery, and the AI-fueled rally
            of 2024-2025. If a strategy can survive all of that without hindsight bias, it's
            worth paying attention to.
          </p>

          {/* Headline Results */}
          <h2 className="font-display text-2xl font-bold text-ink mt-12 mb-4 flex items-center gap-2" style={{ fontVariationSettings: '"opsz" 48' }}>
            <TrendingUp className="w-6 h-6 text-positive flex-shrink-0" />
            The Headline Results
          </h2>
        </div>

        {/* Results Table */}
        <div className="bg-paper-card border border-rule rounded overflow-hidden my-8">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-rule">
                <th className="text-left px-6 py-3 text-xs uppercase tracking-wider text-ink-light font-semibold">Metric</th>
                <th className="text-right px-6 py-3 text-xs uppercase tracking-wider text-ink-light font-semibold">Our Strategy</th>
                <th className="text-right px-6 py-3 text-xs uppercase tracking-wider text-ink-light font-semibold">S&P 500</th>
              </tr>
            </thead>
            <tbody>
              {[
                { metric: 'Total Return (avg.)', ours: '+160%', spy: '+93%', highlight: true },
                { metric: 'Worst-case Start', ours: '+109%', spy: '+75%' },
                { metric: 'Best-case Start', ours: '+252%', spy: '+98%' },
                { metric: 'Sharpe Ratio', ours: '0.92', spy: '~0.65' },
                { metric: 'Max Drawdown (avg.)', ours: '-20.4%', spy: '-25%' },
                { metric: 'Annualized Return', ours: '~21%', spy: '~13%' },
              ].map((row) => (
                <tr key={row.metric} className={`border-b border-rule/50 ${row.highlight ? 'bg-positive/5' : ''}`}>
                  <td className="px-6 py-4 text-ink-mute font-medium">{row.metric}</td>
                  <td className={`px-6 py-4 text-right font-semibold ${row.highlight ? 'text-positive' : 'text-ink'}`}>{row.ours}</td>
                  <td className="px-6 py-4 text-right text-ink-light">{row.spy}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="space-y-4 text-ink-mute text-[1.05rem] leading-[1.75]">
          <p className="text-ink-mute leading-relaxed text-base">
            A 0.92 Sharpe won't make hedge fund managers jealous — but for a fully
            systematic, rules-based strategy with no discretionary overrides, it signals
            genuine risk-adjusted alpha. The S&P 500's Sharpe over the same window was roughly
            0.65. The strategy delivered nearly double the total return with a tighter drawdown
            profile than the index. And every start date in the test ended in positive territory
            &mdash; the worst-case still nearly doubled capital.
          </p>

          {/* Equity Curve Description */}
          <h2 className="font-display text-2xl font-bold text-ink mt-12 mb-4 flex items-center gap-2" style={{ fontVariationSettings: '"opsz" 48' }}>
            <LineChart className="w-6 h-6 text-claret flex-shrink-0" />
            The Shape of the Equity Curve
          </h2>
          <p className="text-ink-mute leading-relaxed text-base">
            The equity curve tells the real story. Early 2021 was strong — momentum was
            everywhere, and the system captured it aggressively. Then came the 2022 bear
            market. The S&P 500 fell roughly 20%; the strategy ended the year up about
            +8% on average across start dates. Not by predicting the crash &mdash; by
            responding to the data. Regime-aware position sizing tightened, trailing stops
            did their job, and Cascade Guard paused new entries during the worst of the
            cascade selloffs.
          </p>
          <p className="text-ink-mute leading-relaxed text-base">
            When the recovery accelerated in 2023 and beyond, the system caught the
            move. 2024 produced an average +32% across start dates (versus the index's
            +25%); 2025 has so far averaged about +50%. The best gains came not from
            predicting the rally, but from being positioned when it arrived.
          </p>

          {/* Worst and Best Periods */}
          <h2 className="font-display text-2xl font-bold text-ink mt-12 mb-4 flex items-center gap-2" style={{ fontVariationSettings: '"opsz" 48' }}>
            <AlertTriangle className="w-6 h-6 text-claret flex-shrink-0" />
            The Best and Worst Periods
          </h2>
          <p className="text-ink-mute leading-relaxed text-base">
            No strategy wins every period. Here are the extremes — and what they reveal
            about how the system handles both euphoria and panic.
          </p>
        </div>

        {/* Best/Worst Table */}
        <div className="bg-paper-card border border-rule rounded overflow-hidden my-8">
          <div className="px-6 py-3 border-b border-rule bg-paper-card/50">
            <span className="text-xs uppercase tracking-wider text-ink-light font-semibold">Worst Periods</span>
          </div>
          <table className="w-full text-sm">
            <tbody>
              {[
                { period: 'Mar 2021', ret: '-12.2%', context: 'Post-squeeze rotation, breadth collapse' },
                { period: 'Jul 2023', ret: '-10.4%', context: 'Mid-summer breadth thrust reversal' },
                { period: 'Dec 2024', ret: '-8.6%', context: 'Year-end momentum unwind' },
              ].map((row) => (
                <tr key={row.period} className="border-b border-rule/50">
                  <td className="px-6 py-3 text-ink-mute font-medium w-28">{row.period}</td>
                  <td className="px-6 py-3 text-right text-negative font-semibold w-24">{row.ret}</td>
                  <td className="px-6 py-3 text-ink-light text-xs">{row.context}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="px-6 py-3 border-b border-t border-rule bg-paper-card/50">
            <span className="text-xs uppercase tracking-wider text-ink-light font-semibold">Best Periods</span>
          </div>
          <table className="w-full text-sm">
            <tbody>
              {[
                { period: 'Aug 2024', ret: '+16.4%', context: 'Post-yen-unwind recovery (Cascade Guard fired the prior week)' },
                { period: 'Sep 2025', ret: '+12.6%', context: 'AI rally breadth expansion' },
                { period: 'Nov 2024', ret: '+11.0%', context: 'Year-end momentum leaders' },
              ].map((row) => (
                <tr key={row.period} className="border-b border-rule/50">
                  <td className="px-6 py-3 text-ink-mute font-medium w-28">{row.period}</td>
                  <td className="px-6 py-3 text-right text-positive font-semibold w-24">{row.ret}</td>
                  <td className="px-6 py-3 text-ink-light text-xs">{row.context}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="space-y-4 text-ink-mute text-[1.05rem] leading-[1.75]">
          <p className="text-ink-mute leading-relaxed text-base">
            The worst stretch — March 2021 — came during the meme stock aftermath. Momentum
            strategies are vulnerable to sudden reversals when leadership rotates fast, and
            the GameStop/AMC unwind produced exactly that kind of whiplash. But the system
            recovered within two periods. Trailing stops limited the damage; the momentum
            ranking rotated into stronger names; Cascade Guard prevented forced re-entries
            during the worst of it.
          </p>
          <p className="text-ink-mute leading-relaxed text-base">
            The single best period — August 2024 — is more telling than it looks. Cascade
            Guard had fired the previous week during the yen-carry-unwind selloff, sidelining
            new entries. When the recovery snapped back, the strategy was positioned for it
            rather than chasing late.
          </p>

          {/* Multi-Start-Date Robustness */}
          <h2 className="font-display text-2xl font-bold text-ink mt-12 mb-4 flex items-center gap-2" style={{ fontVariationSettings: '"opsz" 48' }}>
            <Zap className="w-6 h-6 text-claret flex-shrink-0" />
            Why Multi-Start-Date Testing Matters
          </h2>
          <p className="text-ink-mute leading-relaxed text-base">
            Cherry-picking a favorable start date is the most common backtest distortion in
            retail signal services. A strategy can look incredible when run from one specific
            date and unremarkable from another. We addressed this by running the same 5-year
            window from multiple different start dates and publishing the full distribution.
          </p>
        </div>

        {/* Multi-start-date result range */}
        <div className="grid grid-cols-3 gap-4 my-8">
          <div className="bg-paper-card border border-positive/30 rounded p-6 text-center">
            <TrendingUp className="w-6 h-6 text-positive mx-auto mb-2" />
            <div className="text-3xl sm:text-4xl font-bold text-positive">+252%</div>
            <div className="text-xs text-ink-light uppercase tracking-wider mt-1">Best Start</div>
            <div className="text-xs text-ink-light mt-0.5">Top of distribution</div>
          </div>
          <div className="bg-paper-card border border-claret/30 rounded p-6 text-center">
            <BarChart3 className="w-6 h-6 text-claret mx-auto mb-2" />
            <div className="text-3xl sm:text-4xl font-bold text-claret">+160%</div>
            <div className="text-xs text-ink-light uppercase tracking-wider mt-1">Average</div>
            <div className="text-xs text-ink-light mt-0.5">Across all start dates</div>
          </div>
          <div className="bg-paper-card border border-rule/50 rounded p-6 text-center">
            <ShieldCheck className="w-6 h-6 text-ink-mute mx-auto mb-2" />
            <div className="text-3xl sm:text-4xl font-bold text-ink-mute">+109%</div>
            <div className="text-xs text-ink-light uppercase tracking-wider mt-1">Worst Start</div>
            <div className="text-xs text-ink-light mt-0.5">Still nearly doubled</div>
          </div>
        </div>

        <div className="space-y-4 text-ink-mute text-[1.05rem] leading-[1.75]">
          <p className="text-ink-mute leading-relaxed text-base">
            Every start date in the test ended in positive territory. Every calendar year —
            including the 2022 bear market — averaged positive across start dates. The spread
            from worst to best is real path-dependency, not strategy fragility: the same rules
            run from a different entry date land in a different part of the distribution. We
            publish all of it. The headline +160% is the average a typical subscriber experiences
            across the full window.
          </p>

          {/* What we're NOT claiming */}
          <h2 className="font-display text-2xl font-bold text-ink mt-12 mb-4 flex items-center gap-2" style={{ fontVariationSettings: '"opsz" 48' }}>
            <AlertTriangle className="w-6 h-6 text-negative flex-shrink-0" />
            What We're NOT Claiming
          </h2>
          <p className="text-ink-mute leading-relaxed text-base">
            Transparency matters more than marketing. Here's what you should know:
          </p>
        </div>

        {/* Honesty Box */}
        <div className="bg-negative/10 border border-negative/20 rounded p-6 my-8 space-y-3">
          <p className="text-ink-mute text-sm m-0">
            <span className="text-negative font-semibold">This is simulation, not live trading.</span>{' '}
            Walk-forward testing removes hindsight bias, but it still assumes perfect execution
            at closing prices. Real-world slippage and commissions would reduce returns modestly.
          </p>
          <p className="text-ink-mute text-sm m-0">
            <span className="text-negative font-semibold">Past performance does not guarantee future results.</span>{' '}
            The next 5 years could look nothing like the last 5. Market regimes shift, correlations
            break down, and black swans happen. We believe a regime-aware, discipline-driven strategy
            handles this better than discretionary trading, but nothing is certain.
          </p>
          <p className="text-ink-mute text-sm m-0">
            <span className="text-negative font-semibold">The max drawdown was real.</span>{' '}
            At its worst, the strategy was down about 20% from its peak (averaged across start
            dates; the worst single start touched 26%). That's a real number that would test any
            investor's resolve. We don't hide it behind averages — we publish the worst, the best,
            and the typical.
          </p>
        </div>

        <div className="space-y-4 text-ink-mute text-[1.05rem] leading-[1.75]">
          <p className="text-ink-mute leading-relaxed text-base">
            We publish these numbers because we believe in the methodology, and because
            we think investors deserve to see exactly what they're getting — the rough
            periods alongside the smooth ones. If a strategy can only be sold by hiding the
            drawdowns, it isn't worth selling.
          </p>
        </div>

        {/* CTA */}
        <div className="bg-paper-card border border-rule rounded p-8 sm:p-10 my-12 text-center">
          <h2 className="font-display text-2xl sm:text-3xl font-bold text-ink mb-3" style={{ fontVariationSettings: '"opsz" 48' }}>
            See the Live Track Record
          </h2>
          <p className="text-ink-mute mb-6 max-w-lg mx-auto">
            Our walk-forward results are validated. Our track record is public. See the
            real numbers and decide for yourself.
          </p>
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <Link
              to="/track-record"
              className="inline-flex items-center justify-center gap-2 bg-ink text-paper hover:bg-claret font-semibold px-8 py-3 rounded transition-colors text-base"
            >
              View Track Record
              <ArrowRight size={18} />
            </Link>
            <Link
              to="/blog/backtests"
              className="inline-flex items-center justify-center gap-2 bg-paper-deep hover:bg-paper-card text-ink font-medium px-8 py-3 rounded transition-colors text-base"
            >
              Read: Backtests Deep-Dive
            </Link>
          </div>
          <p className="text-xs text-ink-light mt-4">
            7-day free trial. $129/month after. Cancel anytime.
          </p>
        </div>


      {/* Weekly newsletter signup */}
      <div className="max-w-3xl mx-auto px-4 sm:px-6 mb-8">
        <MarketMeasuredSignup source="blog_post" variant="dark" />
      </div>

      {/* Related Reading */}
        <div className="mt-12 pt-8 border-t border-rule">
          <h3 className="font-display text-lg font-semibold text-ink mb-4">Related Reading</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Link to="/blog/backtests" className="block p-4 bg-paper-card rounded border border-rule hover:border-rule-dark transition-colors">
              <span className="text-ink font-medium">Why Most Backtests Are Lies</span>
              <span className="block text-ink-light text-sm mt-1">The hidden biases that make most backtests worthless and how walk-forward fixes them.</span>
            </Link>
            <Link to="/blog/2022-story" className="block p-4 bg-paper-card rounded border border-rule hover:border-rule-dark transition-colors">
              <span className="text-ink font-medium">The 2022 Story</span>
              <span className="block text-ink-light text-sm mt-1">How our system navigated the worst bear market in a decade.</span>
            </Link>
            <Link to="/blog/momentum-trading" className="block p-4 bg-paper-card rounded border border-rule hover:border-rule-dark transition-colors">
              <span className="text-ink font-medium">Momentum Trading Explained</span>
              <span className="block text-ink-light text-sm mt-1">The momentum ranking and breakout timing behind our signals.</span>
            </Link>
          </div>
        </div>

        {/* Disclaimer */}
        <p className="text-xs text-ink-light leading-relaxed">
          Walk-forward simulation results.
          For information purposes only — not a solicitation to invest, purchase, or sell securities in which RigaCap has an interest.
          RigaCap, LLC is not a registered investment advisor. Past performance does not guarantee future results.
          Execute trades through your own brokerage account. See our{' '}
          <Link to="/terms" className="text-ink-light underline hover:text-ink-mute">Terms of Service</Link>{' '}
          for full disclaimers.
        </p>
      </article>

      {/* Footer */}
      <footer className="border-t border-rule py-8 text-center text-xs text-ink-light">
        <p>&copy; {new Date().getFullYear()} RigaCap, LLC. All rights reserved.</p>
      </footer>
    </div>
  );
}
