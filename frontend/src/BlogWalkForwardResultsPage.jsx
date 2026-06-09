import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, ArrowRight, TrendingUp, BarChart3, Target, AlertTriangle, Zap, LineChart, ShieldCheck } from 'lucide-react';
import MarketMeasuredSignup from './components/MarketMeasuredSignup';

export default function BlogWalkForwardResultsPage() {
  useEffect(() => { document.title = 'Inside Our 9-Year Walk-Forward | RigaCap';
    const DESC = 'RigaCap 9-year, survivorship-free walk-forward simulation across 16 overlapping windows: ~14% annualized, 0.92 Sharpe, 17% max drawdown — half the drawdown of raw momentum.';
    const meta = document.querySelector('meta[name="description"]');
    if (meta) meta.setAttribute('content', DESC);
    document.querySelector('meta[property="og:title"]')?.setAttribute('content', 'Inside Our 9-Year Walk-Forward | RigaCap');
    document.querySelector('meta[property="og:description"]')?.setAttribute('content', DESC);
    document.querySelector('meta[property="og:url"]')?.setAttribute('content', 'https://rigacap.com/blog/walk-forward-results');
    document.querySelector('meta[name="twitter:title"]')?.setAttribute('content', 'Inside Our 9-Year Walk-Forward | RigaCap');
    document.querySelector('meta[name="twitter:description"]')?.setAttribute('content', DESC);
    const existingSchema = document.querySelector('script[type="application/ld+json"]');
    if (existingSchema) existingSchema.remove();
    const schema = document.createElement('script');
    schema.type = 'application/ld+json';
    schema.text = JSON.stringify({
      "@context": "https://schema.org",
      "@type": "Article",
      "headline": "Inside Our 9-Year Walk-Forward",
      "description": DESC,
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
            Inside Our 9-Year Walk-Forward
          </h1>
          <p className="text-lg text-ink-mute max-w-2xl mx-auto">
            Most trading strategies look great on paper. Ours did too
            <br className="hidden sm:block" />
            — so we spent months trying to break it. Then we found it <em>was</em> lying, and rebuilt it.
          </p>
        </div>
      </section>

      {/* Comparison Cards — the honest headline is risk, not return */}
      <section className="max-w-3xl mx-auto px-4 sm:px-6 -mt-8 relative z-10">
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-paper-card border border-positive/30 rounded p-6 text-center">
            <ShieldCheck className="w-6 h-6 text-positive mx-auto mb-2" />
            <div className="text-3xl sm:text-4xl font-bold text-positive">-17%</div>
            <div className="text-xs text-ink-light uppercase tracking-wider mt-1">Our Strategy</div>
            <div className="text-xs text-ink-light mt-0.5">Worst drawdown, 9-year</div>
          </div>
          <div className="bg-paper-card border border-rule/50 rounded p-6 text-center">
            <BarChart3 className="w-6 h-6 text-ink-mute mx-auto mb-2" />
            <div className="text-3xl sm:text-4xl font-bold text-ink-mute">-34%</div>
            <div className="text-xs text-ink-light uppercase tracking-wider mt-1">S&P 500</div>
            <div className="text-xs text-ink-light mt-0.5">Same period (COVID)</div>
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
            and declare victory. Most of those strategies fall apart the moment real money
            is on the line.
          </p>
          <p className="text-ink-mute leading-relaxed text-base">
            We didn't want to build another one. So instead of asking "how good can we make
            this look?", we asked "how hard can we stress-test this before it breaks?" And when
            we found that our own data was flattering us &mdash; survivorship bias and stock
            splits inflating the numbers &mdash; we rebuilt the entire thing and{' '}
            <Link to="/blog/honest-backtest" className="text-claret hover:text-claret/80 underline">revised our returns down</Link>.
            What follows are the honest results.
          </p>

          {/* What is walk-forward */}
          <h2 className="font-display text-2xl font-bold text-ink mt-12 mb-4 flex items-center gap-2" style={{ fontVariationSettings: '"opsz" 48' }}>
            <ShieldCheck className="w-6 h-6 text-claret flex-shrink-0" />
            What Walk-Forward Testing Actually Is
          </h2>
          <p className="text-ink-mute leading-relaxed text-base">
            Walk-forward testing is the gold standard for validating trading strategies. Unlike
            a regular backtest — where you optimize on the full dataset and risk curve-fitting —
            walk-forward simulates real-world conditions. The system only sees data that was
            available at each point in time. It makes decisions, records results, then moves
            forward. No hindsight. No do-overs.
          </p>
          <p className="text-ink-mute leading-relaxed text-base">
            Strategy parameters are fixed at the start and applied forward across every period —
            no per-period re-tuning that could quietly leak future information into past
            decisions. We then run the same test from <strong className="font-medium">16 overlapping
            start dates</strong> across 2017–2026. If the strategy were just finding noise, the
            outcomes would diverge wildly. Ours stayed consistent: 15 of the 16 windows finished
            positive.
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
            { label: 'Time Span', value: '9 Years', detail: '2017 through 2026' },
            { label: 'Data Integrity', value: 'Survivorship-free', detail: 'Includes companies that died' },
            { label: 'Decisions', value: 'Point-in-time', detail: 'No look-ahead, ever' },
            { label: 'Robustness', value: '16 windows', detail: 'Same rules, different start dates' },
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
            This window captures everything: the 2018-Q4 correction, the COVID crash, the
            brutal 2022 bear market, and the AI-fueled rally that followed. If a strategy can
            survive all of that — on data that includes the companies that went bankrupt — it's
            worth paying attention to.
          </p>

          {/* Headline Results */}
          <h2 className="font-display text-2xl font-bold text-ink mt-12 mb-4 flex items-center gap-2" style={{ fontVariationSettings: '"opsz" 48' }}>
            <TrendingUp className="w-6 h-6 text-positive flex-shrink-0" />
            The Headline Results
          </h2>
        </div>

        {/* Results Table — honest, three-way */}
        <div className="bg-paper-card border border-rule rounded overflow-hidden my-8">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-rule">
                <th className="text-left px-6 py-3 text-xs uppercase tracking-wider text-ink-light font-semibold">Metric</th>
                <th className="text-right px-6 py-3 text-xs uppercase tracking-wider text-ink-light font-semibold">RigaCap</th>
                <th className="text-right px-6 py-3 text-xs uppercase tracking-wider text-ink-light font-semibold">Raw Momentum</th>
                <th className="text-right px-6 py-3 text-xs uppercase tracking-wider text-ink-light font-semibold">S&P 500</th>
              </tr>
            </thead>
            <tbody>
              {[
                { metric: 'Annualized Return', ours: '~14%', raw: '22.2%', spy: '~13%' },
                { metric: 'Sharpe Ratio', ours: '0.92', raw: '0.67', spy: '~0.6', highlight: true },
                { metric: 'Max Drawdown', ours: '17%', raw: '35%', spy: '~34%', highlight: true },
                { metric: 'Windows Positive', ours: '15 / 16', raw: '—', spy: '—' },
              ].map((row) => (
                <tr key={row.metric} className={`border-b border-rule/50 ${row.highlight ? 'bg-positive/5' : ''}`}>
                  <td className="px-6 py-4 text-ink-mute font-medium">{row.metric}</td>
                  <td className={`px-6 py-4 text-right font-semibold ${row.highlight ? 'text-positive' : 'text-ink'}`}>{row.ours}</td>
                  <td className="px-6 py-4 text-right text-ink-light">{row.raw}</td>
                  <td className="px-6 py-4 text-right text-ink-light">{row.spy}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="space-y-4 text-ink-mute text-[1.05rem] leading-[1.75]">
          <p className="text-ink-mute leading-relaxed text-base">
            Here's the honest tradeoff. The <em>raw</em> momentum factor actually returns more —
            about 22% a year — but it does it with a stomach-churning 35% drawdown that almost no
            real investor survives. RigaCap gives back some of that raw return in exchange for
            <strong className="font-medium"> roughly half the drawdown and a meaningfully better
            Sharpe</strong>. Versus the S&P, it earns a similar return with far less pain. The
            point was never the biggest number — it was a number you can actually live through.
          </p>

          {/* Equity Curve Description */}
          <h2 className="font-display text-2xl font-bold text-ink mt-12 mb-4 flex items-center gap-2" style={{ fontVariationSettings: '"opsz" 48' }}>
            <LineChart className="w-6 h-6 text-claret flex-shrink-0" />
            The Shape of the Equity Curve
          </h2>
          <p className="text-ink-mute leading-relaxed text-base">
            The equity curve tells the real story. Through the COVID crash, the strategy's
            two-year windows held their drawdown near 9–10% while staying positioned for the
            recovery. Through the 2022 bear, when the S&P fell roughly 20%, RigaCap's 2022
            windows finished positive — not by predicting the crash, but by responding to the
            data: risk-based sizing leaned away from the most volatile names, and disciplined
            exits cut losers before they compounded.
          </p>
          <p className="text-ink-mute leading-relaxed text-base">
            The pattern repeats across regimes. The strategy doesn't try to call tops and
            bottoms. It stays diversified, sizes by risk, lets winners run on a wide leash, and
            steps back when conditions turn hostile. Boring, repeated consistently, is the
            entire edge.
          </p>

          {/* Multi-Start-Date Robustness */}
          <h2 className="font-display text-2xl font-bold text-ink mt-12 mb-4 flex items-center gap-2" style={{ fontVariationSettings: '"opsz" 48' }}>
            <Zap className="w-6 h-6 text-claret flex-shrink-0" />
            Why Multi-Window Testing Matters
          </h2>
          <p className="text-ink-mute leading-relaxed text-base">
            Cherry-picking a favorable start date is the most common backtest distortion in
            retail signal services. A strategy can look incredible from one date and unremarkable
            from another. We addressed this by running the same rules from 16 overlapping start
            dates across the full nine years and publishing the entire distribution.
          </p>
        </div>

        {/* Multi-window result range */}
        <div className="grid grid-cols-3 gap-4 my-8">
          <div className="bg-paper-card border border-positive/30 rounded p-6 text-center">
            <TrendingUp className="w-6 h-6 text-positive mx-auto mb-2" />
            <div className="text-3xl sm:text-4xl font-bold text-positive">+29%</div>
            <div className="text-xs text-ink-light uppercase tracking-wider mt-1">Best Window</div>
            <div className="text-xs text-ink-light mt-0.5">Annualized</div>
          </div>
          <div className="bg-paper-card border border-claret/30 rounded p-6 text-center">
            <BarChart3 className="w-6 h-6 text-claret mx-auto mb-2" />
            <div className="text-3xl sm:text-4xl font-bold text-claret">~14%</div>
            <div className="text-xs text-ink-light uppercase tracking-wider mt-1">Average</div>
            <div className="text-xs text-ink-light mt-0.5">Across all windows</div>
          </div>
          <div className="bg-paper-card border border-rule/50 rounded p-6 text-center">
            <ShieldCheck className="w-6 h-6 text-ink-mute mx-auto mb-2" />
            <div className="text-3xl sm:text-4xl font-bold text-ink-mute">-5%</div>
            <div className="text-xs text-ink-light uppercase tracking-wider mt-1">Worst Window</div>
            <div className="text-xs text-ink-light mt-0.5">The lone negative</div>
          </div>
        </div>

        <div className="space-y-4 text-ink-mute text-[1.05rem] leading-[1.75]">
          <p className="text-ink-mute leading-relaxed text-base">
            Fifteen of the sixteen windows finished positive. The one exception was roughly flat —
            a soft −5% through the choppy 2017–18 stretch. The spread from worst to best is real
            path-dependency, not strategy fragility: the same rules from a different entry date
            land in a different part of the distribution. We publish all of it.
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
            <span className="text-negative font-semibold">This is a backtest — the live record is just beginning.</span>{' '}
            Walk-forward removes hindsight bias and we model trading costs, but the strategy has
            only recently gone live. Even good strategies give a little back once real money is
            involved. Underwrite us conservatively — think high-single-digits to low-teens — until
            the live record builds.
          </p>
          <p className="text-ink-mute text-sm m-0">
            <span className="text-negative font-semibold">Past performance does not guarantee future results.</span>{' '}
            The next nine years could look nothing like the last. Regimes shift, correlations
            break, and a true momentum-factor winter would hurt us. We believe a diversified,
            risk-managed implementation handles this better than concentrated bets — but nothing
            is certain.
          </p>
          <p className="text-ink-mute text-sm m-0">
            <span className="text-negative font-semibold">The drawdown is real.</span>{' '}
            At its worst the strategy was down about 17% from its peak. That's a real number that
            tests an investor's resolve — it's just a far smaller one than the 35% the raw factor
            demands. We don't hide it; we lead with it.
          </p>
        </div>

        <div className="space-y-4 text-ink-mute text-[1.05rem] leading-[1.75]">
          <p className="text-ink-mute leading-relaxed text-base">
            We publish these numbers because the honesty <em>is</em> the product. If a strategy can
            only be sold by hiding the drawdowns — or by quietly leaving survivorship bias in the
            data — it isn't worth selling.
          </p>
        </div>

        {/* CTA */}
        <div className="bg-paper-card border border-rule rounded p-8 sm:p-10 my-12 text-center">
          <h2 className="font-display text-2xl sm:text-3xl font-bold text-ink mb-3" style={{ fontVariationSettings: '"opsz" 48' }}>
            See the Full Track Record
          </h2>
          <p className="text-ink-mute mb-6 max-w-lg mx-auto">
            Every regime, every drawdown, nothing hidden. See the real numbers and decide for
            yourself.
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
              to="/blog/honest-backtest"
              className="inline-flex items-center justify-center gap-2 bg-paper-deep hover:bg-paper-card text-ink font-medium px-8 py-3 rounded transition-colors text-base"
            >
              Read: How We Found Our Backtest Was Lying
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
            <Link to="/blog/honest-backtest" className="block p-4 bg-paper-card rounded border border-rule hover:border-rule-dark transition-colors">
              <span className="text-ink font-medium">We Found Our Own Backtest Was Lying</span>
              <span className="block text-ink-light text-sm mt-1">Survivorship bias and stock splits inflated our numbers. Here's how we caught it and fixed it.</span>
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
