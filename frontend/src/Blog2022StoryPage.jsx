import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, Shield, TrendingDown, Clock, BarChart3, ArrowRight } from 'lucide-react';
import MarketMeasuredSignup from './components/MarketMeasuredSignup';

export default function Blog2022StoryPage() {
  useEffect(() => { document.title = 'The 2022 Story | RigaCap'; }, []);
  return (
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
          <p className="text-sm font-medium uppercase tracking-widest text-claret mb-6">Walk-Forward Validated</p>
          <h1 className="font-display text-4xl sm:text-5xl font-bold text-ink tracking-tight mb-4" style={{ fontVariationSettings: '"opsz" 48' }}>
            The 2022 Story
          </h1>
          <p className="text-lg text-ink-mute max-w-2xl mx-auto">
            The S&P 500 fell 20%. Our Preserver lost 6.5%.
            <br className="hidden sm:block" />
            That difference is the whole product — here's why.
          </p>
        </div>
      </section>

      {/* Comparison Cards */}
      <section className="max-w-3xl mx-auto px-4 sm:px-6 -mt-8 relative z-10">
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-paper-card border border-negative/30 rounded p-6 text-center">
            <TrendingDown className="w-6 h-6 text-negative mx-auto mb-2" />
            <div className="text-3xl sm:text-4xl font-bold text-negative">-19.9%</div>
            <div className="text-xs text-ink-light uppercase tracking-wider mt-1">S&P 500</div>
            <div className="text-xs text-ink-light mt-0.5">2022 Calendar Year</div>
          </div>
          <div className="bg-paper-card border border-claret/30 rounded p-6 text-center">
            <Shield className="w-6 h-6 text-claret mx-auto mb-2" />
            <div className="text-3xl sm:text-4xl font-bold text-ink">-6.5%</div>
            <div className="text-xs text-ink-light uppercase tracking-wider mt-1">RigaCap Preserver</div>
            <div className="text-xs text-ink-light mt-0.5">Continuous Walk-Forward</div>
          </div>
        </div>
      </section>

      {/* Article Body */}
      <article className="max-w-3xl mx-auto px-4 sm:px-6 py-12 sm:py-16">
        <div className="prose prose-gray max-w-none">

          {/* The Setup */}
          <h2 className="font-display text-2xl font-bold text-ink mt-0 mb-4 flex items-center gap-2" style={{ fontVariationSettings: '"opsz" 48' }}>
            The Year Everyone Lost Money
          </h2>
          <p className="text-ink-mute leading-relaxed text-base">
            2022 was brutal. The Fed hiked rates relentlessly. Inflation hit a forty-year high.
            The S&P 500 dropped 19.9% — its worst year since 2008. The Nasdaq fell harder.
            Bonds, which were supposed to be safe, lost money too. There was nowhere to hide.
          </p>
          <p className="text-ink-mute leading-relaxed text-base">
            And it was worst of all for momentum investors. The 2021–23 unwind was gutting
            raw 12-month momentum strategies: the very stocks that had led the way up were
            the ones falling hardest, month after month. Every "buy the dip" call turned into
            a falling knife. Every bounce turned into a lower high.
          </p>

          {/* What Our System Did */}
          <h2 className="font-display text-2xl font-bold text-ink mt-12 mb-4 flex items-center gap-2" style={{ fontVariationSettings: '"opsz" 48' }}>
            <Clock className="w-6 h-6 text-claret flex-shrink-0" />
            What Our System Did: Step Back
          </h2>
          <p className="text-ink-mute leading-relaxed text-base">
            For long stretches of 2022, our system generated few or no buy signals.
          </p>
          <p className="text-ink-mute leading-relaxed text-base">
            It detected that market conditions were unfavorable — the SPY was trading below its
            200-day moving average, our 7-regime model classified conditions as a bear market —
            and it stopped deploying fresh capital while trailing stops took risk off the table.
            It sat on its hands while everyone else was trying to catch a falling knife.
          </p>

          {/* Highlight Box */}
          <div className="bg-claret/10 border border-claret/30 rounded p-6 my-8">
            <p className="text-claret font-semibold text-lg m-0 mb-2">
              The hardest thing in trading isn't knowing when to buy.
            </p>
            <p className="text-ink-mute m-0">
              It's knowing when to do nothing. Our system doesn't have ego,
              doesn't get bored, and doesn't feel pressure to justify a subscription fee
              by generating activity. When conditions are wrong, it waits.
            </p>
          </div>

          <p className="text-ink-mute leading-relaxed text-base">
            The result: <span className="text-ink font-semibold">−6.5% for the year</span> in the Preserver.
            Yes — a loss. We're not going to dress that up. But it came in a year when the
            index lost 19.9% and the multi-year momentum unwind was destroying momentum
            investors. Cutting the damage to about a third of the index's loss — in the
            single worst environment for our style of investing — is the system doing
            exactly what it was built to do.
          </p>

          {/* The Math */}
          <h2 className="font-display text-2xl font-bold text-ink mt-12 mb-4 flex items-center gap-2" style={{ fontVariationSettings: '"opsz" 48' }}>
            <BarChart3 className="w-6 h-6 text-claret flex-shrink-0" />
            Why a Small Loss Matters More Than a Big Year
          </h2>
          <p className="text-ink-mute leading-relaxed text-base">
            Anyone can make money in a bull market. Stocks go up, momentum is everywhere,
            and even random picks do well. The real test of a strategy is what happens
            when the market turns against you — because losses compound against you
            in a way gains never do.
          </p>
        </div>

        {/* Comparison Table */}
        <div className="bg-paper-card border border-rule rounded overflow-hidden my-8">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-rule">
                <th className="text-left px-6 py-3 text-xs uppercase tracking-wider text-ink-light font-semibold">Scenario</th>
                <th className="text-right px-6 py-3 text-xs uppercase tracking-wider text-ink-light font-semibold">$10,000 Start</th>
                <th className="text-right px-6 py-3 text-xs uppercase tracking-wider text-ink-light font-semibold">After 2022</th>
                <th className="text-right px-6 py-3 text-xs uppercase tracking-wider text-ink-light font-semibold hidden sm:table-cell">Gain Needed to Recover</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-rule/50">
                <td className="px-6 py-4 text-ink-mute">S&P 500 Index Fund (−19.9%)</td>
                <td className="px-6 py-4 text-right text-ink-mute">$10,000</td>
                <td className="px-6 py-4 text-right text-negative font-semibold">$8,010</td>
                <td className="px-6 py-4 text-right text-negative font-semibold hidden sm:table-cell">+25%</td>
              </tr>
              <tr className="bg-claret/10 border-t border-claret/30">
                <td className="px-6 py-4 text-claret font-medium">RigaCap Preserver (−6.5%)</td>
                <td className="px-6 py-4 text-right text-ink-mute">$10,000</td>
                <td className="px-6 py-4 text-right text-ink font-bold">$9,350</td>
                <td className="px-6 py-4 text-right text-ink font-bold hidden sm:table-cell">+7%</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div className="prose prose-gray max-w-none">
          <p className="text-ink-mute leading-relaxed text-base">
            The difference between losing 20% and losing 6.5% isn't just 13 percentage points.
            It's the compounding math of recovery. Someone who lost 20% in 2022 needed a 25% gain
            just to get back to even — for many index investors, that took years. A 6.5% loss
            is recoverable in months. That's the asymmetry the system is built around: you can't
            avoid every loss, but you can keep every loss small enough that the next leg up
            makes you whole quickly.
          </p>

          {/* How It Works */}
          <h2 className="font-display text-2xl font-bold text-ink mt-12 mb-4" style={{ fontVariationSettings: '"opsz" 48' }}>
            The Three Lines of Defense
          </h2>
          <p className="text-ink-mute leading-relaxed text-base">
            Our system didn't predict the 2022 crash. Nobody did. Instead, it has
            three built-in mechanisms that protect capital when conditions deteriorate:
          </p>
        </div>

        {/* Defense Cards */}
        <div className="grid gap-4 my-8">
          <div className="bg-paper-card border border-rule rounded p-6">
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 rounded bg-negative/10 flex items-center justify-center flex-shrink-0">
                <span className="text-negative font-bold">1</span>
              </div>
              <div>
                <h3 className="text-ink font-semibold mb-1">7-Regime Market Intelligence</h3>
                <p className="text-ink-mute text-sm m-0">
                  Our proprietary model classifies the market into 7 distinct regimes — from
                  strong bull to panic crash. When conditions shift to unfavorable territory,
                  the system stops buying entirely. No new positions. This is what cut the
                  2022 loss to a fraction of the index's — and in 2008 it kept the system
                  in cash almost the entire year.
                </p>
              </div>
            </div>
          </div>
          <div className="bg-paper-card border border-rule rounded p-6">
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 rounded bg-claret/10 flex items-center justify-center flex-shrink-0">
                <span className="text-claret font-bold">2</span>
              </div>
              <div>
                <h3 className="text-ink font-semibold mb-1">Automatic Downside Protection</h3>
                <p className="text-ink-mute text-sm m-0">
                  Every position has a dynamic trailing stop that locks in gains as a stock rises.
                  If it reverses, we exit automatically — no hesitation, no hoping for a bounce.
                  Losses are capped before they can compound.
                </p>
              </div>
            </div>
          </div>
          <div className="bg-paper-card border border-rule rounded p-6">
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 rounded bg-claret/10 flex items-center justify-center flex-shrink-0">
                <span className="text-claret font-bold">3</span>
              </div>
              <div>
                <h3 className="text-ink font-semibold mb-1">Ensemble Entry Scoring</h3>
                <p className="text-ink-mute text-sm m-0">
                  We don't chase stocks — we wait for multiple independent signals to align.
                  Timing, momentum, and breakout confirmation must all agree before we enter.
                  In a bear market, almost nothing passes this filter — which is exactly the point.
                </p>
              </div>
            </div>
          </div>
        </div>

        <div className="prose prose-gray max-w-none">
          {/* The Bigger Picture */}
          <h2 className="font-display text-2xl font-bold text-ink mt-12 mb-4" style={{ fontVariationSettings: '"opsz" 48' }}>
            The Bigger Picture: Losing Less When It Matters
          </h2>
          <p className="text-ink-mute leading-relaxed text-base">
            2022 wasn't a fluke — and we won't pretend the record is spotless. Over the full
            21-year continuous walk-forward (2007–2026), the Preserver has had down years too:
            2015, 2018, and 2022. But look at how small they were — 2015 and 2018 each cost
            barely more than a percent, and the worst of them was 2022 at −6.5%: the very year
            we're proud of, because the S&P lost 19.9% in it. We'd rather show you those warts
            than hide them.
          </p>
          <p className="text-ink-mute leading-relaxed text-base">
            But look at what happens in the years that actually destroy portfolios.
            In 2008, while the S&P 500 fell about 37%, the regime filter held the system in cash
            by design — both tiers finished the year essentially flat, at +0.1%. In 2020, it
            captured the recovery: the Preserver returned +13.0% and the aggressive Maximizer
            setting +41.7%, against the S&P's +15.2%. And in 2022, the Preserver cut a 19.9%
            index loss down to 6.5%. The pattern is consistent: in the worst years, the system
            loses far less — and small losses are the ones you recover from.
          </p>
        </div>

        {/* Recent Years Summary */}
        <div className="bg-paper-card border border-rule rounded overflow-hidden my-8">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-rule">
                <th className="text-left px-6 py-3 text-xs uppercase tracking-wider text-ink-light font-semibold">Year</th>
                <th className="text-right px-6 py-3 text-xs uppercase tracking-wider text-ink-light font-semibold">RigaCap Preserver</th>
                <th className="text-left px-6 py-3 text-xs uppercase tracking-wider text-ink-light font-semibold hidden sm:table-cell">Note</th>
              </tr>
            </thead>
            <tbody>
              {[
                { year: '2021', rc: '+15.9%', note: 'Momentum bull market', rcColor: 'text-positive' },
                { year: '2022', rc: '-6.5%', note: 'S&P 500: −19.9%. Loss cut to about a third of the index', rcColor: 'text-negative', highlight: true },
                { year: '2023', rc: '+8.0%', note: "Recovered 2022's loss", rcColor: 'text-positive' },
                { year: '2024', rc: '+14.3%', note: 'Steady year', rcColor: 'text-positive' },
                { year: '2025', rc: '+29.7%', note: '', rcColor: 'text-positive' },
                { year: '2026 YTD', rc: '+14.9%', note: 'Year to date', rcColor: 'text-positive' },
              ].map((row) => (
                <tr key={row.year} className={`border-b border-rule/50 ${row.highlight ? 'bg-claret/10' : ''}`}>
                  <td className={`px-6 py-4 font-medium ${row.highlight ? 'text-claret' : 'text-ink'}`}>{row.year}</td>
                  <td className={`px-6 py-4 text-right font-semibold ${row.rcColor}`}>{row.rc}</td>
                  <td className="px-6 py-4 text-ink-light text-xs hidden sm:table-cell">{row.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="prose prose-gray max-w-none">
          <p className="text-ink-mute leading-relaxed text-base">
            The system doesn't try to beat the market every year — in strong bull years the
            Preserver often lags. Over the 21-year continuous walk-forward (2007–2026), the
            Preserver compounded at 8.6% a year with a 0.88 Sharpe ratio, roughly matching the
            index's pace in exchange for a worst drawdown of just 13% — against the S&P's 55%
            and raw 12-month momentum's 57%. You accept that tighter drawdown profile in some
            bull-year returns. 2022 is what you get back.
          </p>

          {/* Methodology Note */}
          <h2 className="font-display text-2xl font-bold text-ink mt-12 mb-4" style={{ fontVariationSettings: '"opsz" 48' }}>
            How We Know This Is Real
          </h2>
          <p className="text-ink-mute leading-relaxed text-base">
            These are walk-forward results — not a curve-fit backtest, and now survivorship-free.
            The difference matters.
          </p>
          <p className="text-ink-mute leading-relaxed text-base">
            A backtest looks at historical data and finds parameters that would have worked.
            Walk-forward testing is harder: the system sees only the data that was available
            at each point in time, makes decisions in real-time, and can never peek ahead.
            There's no hindsight bias, no curve-fitting, no cherry-picking.
          </p>
          <p className="text-ink-mute leading-relaxed text-base">
            And we report the continuous path — one portfolio, held through everything from
            2007 to 2026 — not the friendliest start date. That's why this post shows a loss
            for 2022 rather than a flattering window. A strategy that only looks good from
            hand-picked starting points isn't a strategy; it's a story. We'd rather show you
            the loss and let the size of it speak.
          </p>
        </div>

        {/* CTA */}
        <div className="border border-rule rounded p-8 sm:p-10 my-12 text-center">
          <h2 className="font-display text-2xl sm:text-3xl font-bold text-ink mb-3" style={{ fontVariationSettings: '"opsz" 48' }}>
            Stop Trading on Emotions
          </h2>
          <p className="text-ink-mute mb-6 max-w-lg mx-auto">
            The next bear market is coming. The question is whether your portfolio
            will be protected by math or exposed by emotion.
          </p>
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <Link
              to="/app"
              className="inline-flex items-center justify-center gap-2 bg-ink text-paper hover:bg-claret font-semibold px-8 py-3 rounded transition-colors text-base"
            >
              Start Free Trial
              <ArrowRight size={18} />
            </Link>
            <Link
              to="/track-record"
              className="inline-flex items-center justify-center gap-2 border border-rule hover:border-ink text-ink font-medium px-8 py-3 rounded transition-colors text-base"
            >
              View Full Track Record
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
          <h3 className="text-lg font-semibold text-ink mb-4">Related Reading</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Link to="/blog/market-regime-guide" className="block p-4 bg-paper-card rounded border border-rule hover:border-rule-dark transition-colors">
              <span className="text-ink font-medium">Market Regime Trading: A Beginner's Guide</span>
              <span className="block text-ink-light text-sm mt-1">How regime detection helped navigate the 2022 bear market.</span>
            </Link>
            <Link to="/blog/trailing-stops" className="block p-4 bg-paper-card rounded border border-rule hover:border-rule-dark transition-colors">
              <span className="text-ink font-medium">How Trailing Stops Protect Your Portfolio</span>
              <span className="block text-ink-light text-sm mt-1">The trailing stop mechanism that limited drawdowns during 2022.</span>
            </Link>
            <Link to="/blog/walk-forward-results" className="block p-4 bg-paper-card rounded border border-rule hover:border-rule-dark transition-colors">
              <span className="text-ink font-medium">Inside Our 21-Year Walk-Forward</span>
              <span className="block text-ink-light text-sm mt-1">Full performance breakdown including the 2022 period.</span>
            </Link>
          </div>
        </div>

        {/* Disclaimer */}
        <p className="text-xs text-ink-light leading-relaxed">
          All performance figures are from walk-forward simulations using historical market data.
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
