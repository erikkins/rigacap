import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, ArrowRight, TrendingUp, BarChart3, Target, AlertTriangle, Zap, LineChart, ShieldCheck } from 'lucide-react';
import MarketMeasuredSignup from './components/MarketMeasuredSignup';

export default function BlogWalkForwardResultsPage() {
  useEffect(() => { document.title = 'Inside Our 21-Year Walk-Forward | RigaCap';
    const DESC = 'RigaCap 21-year continuous walk-forward simulation (2007–2026): the Preserver at 8.6% / 0.88 Sharpe / −13% worst drawdown, the Maximizer at 14.5% — a fraction of the drawdown of raw momentum or the S&P.';
    const meta = document.querySelector('meta[name="description"]');
    if (meta) meta.setAttribute('content', DESC);
    document.querySelector('meta[property="og:title"]')?.setAttribute('content', 'Inside Our 21-Year Walk-Forward | RigaCap');
    document.querySelector('meta[property="og:description"]')?.setAttribute('content', DESC);
    document.querySelector('meta[property="og:url"]')?.setAttribute('content', 'https://rigacap.com/blog/walk-forward-results');
    document.querySelector('meta[name="twitter:title"]')?.setAttribute('content', 'Inside Our 21-Year Walk-Forward | RigaCap');
    document.querySelector('meta[name="twitter:description"]')?.setAttribute('content', DESC);
    const existingSchema = document.querySelector('script[type="application/ld+json"]');
    if (existingSchema) existingSchema.remove();
    const schema = document.createElement('script');
    schema.type = 'application/ld+json';
    schema.text = JSON.stringify({
      "@context": "https://schema.org",
      "@type": "Article",
      "headline": "Inside Our 21-Year Walk-Forward",
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
            Inside Our 21-Year Walk-Forward
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
            <div className="text-3xl sm:text-4xl font-bold text-positive">-13%</div>
            <div className="text-xs text-ink-light uppercase tracking-wider mt-1">RigaCap Preserver</div>
            <div className="text-xs text-ink-light mt-0.5">Worst drawdown, 21-year</div>
          </div>
          <div className="bg-paper-card border border-rule/50 rounded p-6 text-center">
            <BarChart3 className="w-6 h-6 text-ink-mute mx-auto mb-2" />
            <div className="text-3xl sm:text-4xl font-bold text-ink-mute">-55%</div>
            <div className="text-xs text-ink-light uppercase tracking-wider mt-1">S&P 500</div>
            <div className="text-xs text-ink-light mt-0.5">Same period (2008–09)</div>
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
            decisions. We then run the test <strong className="font-medium">continuously across
            21 years, 2007 through 2026</strong> — through the 2008 financial crisis, the COVID
            crash, and the 2022 bear — with the most recent 24 months held out as a final exam
            the strategy was never tuned on.
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
            { label: 'Time Span', value: '21 Years', detail: '2007 through 2026' },
            { label: 'Data Integrity', value: 'Survivorship-free', detail: 'From 2016 on; pre-2016 caveated in methodology' },
            { label: 'Decisions', value: 'Point-in-time', detail: 'No look-ahead, ever' },
            { label: 'Robustness', value: 'Held-out 24 mo', detail: 'A final window never tuned on' },
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
            This window captures everything: the 2008 financial crisis, the 2018-Q4 correction,
            the COVID crash, the brutal 2022 bear market, and the AI-fueled rally that followed.
            If a strategy can
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
                <th className="text-right px-6 py-3 text-xs uppercase tracking-wider text-ink-light font-semibold">RigaCap Preserver</th>
                <th className="text-right px-6 py-3 text-xs uppercase tracking-wider text-ink-light font-semibold">RigaCap Maximizer</th>
                <th className="text-right px-6 py-3 text-xs uppercase tracking-wider text-ink-light font-semibold">S&P 500</th>
              </tr>
            </thead>
            <tbody>
              {[
                { metric: 'Annualized Return', pres: '8.6%', max: '14.5%', spy: '9.8%' },
                { metric: 'Sharpe Ratio', pres: '0.88', max: '0.95', spy: '0.54', highlight: true },
                { metric: 'Max Drawdown', pres: '−13%', max: '−20%', spy: '−55%', highlight: true },
              ].map((row) => (
                <tr key={row.metric} className={`border-b border-rule/50 ${row.highlight ? 'bg-positive/5' : ''}`}>
                  <td className="px-6 py-4 text-ink-mute font-medium">{row.metric}</td>
                  <td className={`px-6 py-4 text-right font-semibold ${row.highlight ? 'text-positive' : 'text-ink'}`}>{row.pres}</td>
                  <td className={`px-6 py-4 text-right font-semibold ${row.highlight ? 'text-positive' : 'text-ink'}`}>{row.max}</td>
                  <td className="px-6 py-4 text-right text-ink-light">{row.spy}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="space-y-4 text-ink-mute text-[1.05rem] leading-[1.75]">
          <p className="text-ink-mute leading-relaxed text-base">
            Here's the honest tradeoff — and it's exactly why we run the same engine at two
            settings. The <em>raw</em> momentum factor returns 13.2% a year net of trading costs,
            but it does it with a stomach-churning 57% drawdown that almost no real investor
            survives. The <strong className="font-medium">Preserver</strong> dials that risk
            almost all the way down: 8.6% a year — roughly the S&P's own pace — for a worst
            drawdown of just 13%, a quarter of the index's 55%. The{' '}
            <strong className="font-medium">Maximizer</strong> keeps more of the upside: 14.5% a
            year, ahead of both raw momentum and the S&P, while holding its worst drawdown to
            20% — about a third of the raw factor's. Neither chases the biggest number; both chase
            a number you can actually live through.
          </p>

          {/* Equity Curve Description */}
          <h2 className="font-display text-2xl font-bold text-ink mt-12 mb-4 flex items-center gap-2" style={{ fontVariationSettings: '"opsz" 48' }}>
            <LineChart className="w-6 h-6 text-claret flex-shrink-0" />
            The Shape of the Equity Curve
          </h2>
          <p className="text-ink-mute leading-relaxed text-base">
            The equity curve tells the real story. Across 21 years — including 2008, when the
            S&P lost more than half its value — the Preserver's worst peak-to-trough loss was
            just 13%. Through the 2022 bear, when the S&P fell roughly 20%, the Preserver lost
            only 6.5% — not by predicting the crash, but by responding to the data:
            risk-based sizing leaned away from the most volatile names, and disciplined exits
            cut losers before they compounded.
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
            Why a Held-Out Window Matters
          </h2>
          <p className="text-ink-mute leading-relaxed text-base">
            Cherry-picking a favorable start date is the most common backtest distortion in
            retail signal services. A strategy can look incredible from one date and unremarkable
            from another. We addressed this by running one continuous 21-year simulation — no
            chosen start date to flatter the result — and by holding out the most recent 24 months
            (June 2024 through May 2026) as a final exam the strategy was never tuned on.
          </p>
        </div>

        {/* Held-out window result */}
        <div className="grid grid-cols-3 gap-4 my-8">
          <div className="bg-paper-card border border-positive/30 rounded p-6 text-center">
            <TrendingUp className="w-6 h-6 text-positive mx-auto mb-2" />
            <div className="text-3xl sm:text-4xl font-bold text-positive">+31.3%</div>
            <div className="text-xs text-ink-light uppercase tracking-wider mt-1">Preserver Annualized</div>
            <div className="text-xs text-ink-light mt-0.5">Held-out 24 months</div>
          </div>
          <div className="bg-paper-card border border-claret/30 rounded p-6 text-center">
            <BarChart3 className="w-6 h-6 text-claret mx-auto mb-2" />
            <div className="text-3xl sm:text-4xl font-bold text-claret">1.75</div>
            <div className="text-xs text-ink-light uppercase tracking-wider mt-1">Sharpe Ratio</div>
            <div className="text-xs text-ink-light mt-0.5">vs S&P 1.18</div>
          </div>
          <div className="bg-paper-card border border-rule/50 rounded p-6 text-center">
            <ShieldCheck className="w-6 h-6 text-ink-mute mx-auto mb-2" />
            <div className="text-3xl sm:text-4xl font-bold text-ink-mute">-12.9%</div>
            <div className="text-xs text-ink-light uppercase tracking-wider mt-1">Max Drawdown</div>
            <div className="text-xs text-ink-light mt-0.5">vs S&P -19.0%</div>
          </div>
        </div>

        <div className="space-y-4 text-ink-mute text-[1.05rem] leading-[1.75]">
          <p className="text-ink-mute leading-relaxed text-base">
            Over that held-out window the Preserver compounded at 31.3% annualized with a 1.75
            Sharpe and a 12.9% maximum drawdown; dialed up to the Maximizer, 48.9% at a 1.94
            Sharpe — against the S&P's 19.9%, 1.18, and 19.0%. A two-year stretch that strong
            won't repeat on schedule; the 21-year averages — 8.6% for the Preserver, 14.5% for
            the Maximizer — are the numbers to underwrite. But it's the cleanest evidence we have
            that the rules work on data they were never fitted to. We publish all of it.
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
            <span className="text-negative font-semibold">This is a walk-forward simulation — the live record is just beginning.</span>{' '}
            Walk-forward removes hindsight bias and we model trading costs, but the strategy has
            only recently gone live. Even good strategies give a little back once real money is
            involved. Underwrite us conservatively — think high-single-digits for the Preserver,
            low-teens for the Maximizer — until the live record builds.
          </p>
          <p className="text-ink-mute text-sm m-0">
            <span className="text-negative font-semibold">Past performance does not guarantee future results.</span>{' '}
            The next two decades could look nothing like the last two. Regimes shift, correlations
            break, and a true momentum-factor winter would hurt us. We believe a diversified,
            risk-managed implementation handles this better than concentrated bets — but nothing
            is certain.
          </p>
          <p className="text-ink-mute text-sm m-0">
            <span className="text-negative font-semibold">The drawdown is real.</span>{' '}
            At its worst, the Preserver was down about 13% from its peak, the Maximizer about 20%.
            Those are real numbers that test an investor's resolve — they're just far smaller ones
            than the 57% the raw factor demands, or the 55% the S&P itself endured. We don't hide
            them; we lead with them.
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
