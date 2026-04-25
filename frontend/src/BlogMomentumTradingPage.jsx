import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, ArrowRight, TrendingUp, Filter, Shield, Zap, BarChart3, Activity, AlertTriangle } from 'lucide-react';
import MarketMeasuredSignup from './components/MarketMeasuredSignup';

export default function BlogMomentumTradingPage() {
  useEffect(() => { document.title = 'Momentum Trading Explained | RigaCap';
    const meta = document.querySelector('meta[name="description"]');
    if (meta) meta.setAttribute('content', 'Momentum trading is not day trading. Learn how RigaCap uses breakout timing, momentum ranking, and volume confirmation to catch breakouts.');

    // OG tags for social sharing
    document.querySelector('meta[property="og:title"]')?.setAttribute('content', 'Momentum Trading Explained: How Stock Signals Work | RigaCap');
    document.querySelector('meta[property="og:description"]')?.setAttribute('content', 'Momentum trading is not day trading. Learn how a rules-based ensemble system catches stock breakouts using timing, ranking, and confirmation.');
    document.querySelector('meta[property="og:url"]')?.setAttribute('content', 'https://rigacap.com/blog/momentum-trading');
    document.querySelector('meta[name="twitter:title"]')?.setAttribute('content', 'Momentum Trading Explained: How Stock Signals Work | RigaCap');
    document.querySelector('meta[name="twitter:description"]')?.setAttribute('content', 'Momentum trading is not day trading. Learn how a rules-based ensemble system catches stock breakouts using timing, ranking, and confirmation.');
    // JSON-LD Article schema
    const existingSchema = document.querySelector('script[type="application/ld+json"]');
    if (existingSchema) existingSchema.remove();
    const schema = document.createElement('script');
    schema.type = 'application/ld+json';
    schema.text = JSON.stringify({
      "@context": "https://schema.org",
      "@type": "Article",
      "headline": "Momentum Trading Explained: How Stock Signals Work",
      "description": "Momentum trading is not day trading. Learn how a rules-based ensemble system catches stock breakouts using timing, ranking, and confirmation.",
      "author": {"@type": "Organization", "name": "RigaCap"},
      "publisher": {"@type": "Organization", "name": "RigaCap", "url": "https://rigacap.com"},
      "url": "https://rigacap.com/blog/momentum-trading",
      "articleSection": "Education",
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
          <p className="text-sm font-medium uppercase tracking-wider text-claret mb-6">Strategy Deep Dive</p>
          <h1 className="font-display text-4xl sm:text-5xl font-bold text-ink tracking-tight mb-4" style={{ fontVariationSettings: '"opsz" 48' }}>
            Momentum Trading Explained
          </h1>
          <p className="text-lg text-ink-mute max-w-2xl mx-auto">
            How stock signals actually work — and why three filters
            <br className="hidden sm:block" />
            are better than one.
          </p>
        </div>
      </section>

      {/* Article Body */}
      <article className="max-w-3xl mx-auto px-4 sm:px-6 py-12 sm:py-16">
        <div className="space-y-4 text-ink-mute text-[1.05rem] leading-[1.75]">

          {/* Section 1: What is Momentum Trading */}
          <h2 className="font-display text-2xl font-bold text-ink mt-0 mb-4 flex items-center gap-2" style={{ fontVariationSettings: '"opsz" 48' }}>
            <TrendingUp className="w-6 h-6 text-claret flex-shrink-0" />
            What Is Momentum Trading?
          </h2>
          <p className="text-ink-mute leading-relaxed text-base">
            Momentum trading is built on a simple observation: stocks that have been going up
            tend to keep going up, and stocks that have been going down tend to keep going down.
            This isn't speculation — it's one of the most well-documented phenomena in academic
            finance, studied and confirmed across decades of market data.
          </p>
          <p className="text-ink-mute leading-relaxed text-base">
            But momentum trading is <em>not</em> day trading. It's not staring at charts all day
            or making impulsive decisions. It's a systematic, rules-based approach where every
            buy and sell decision follows predefined criteria. No emotions, no hunches, no overrides.
          </p>
          <p className="text-ink-mute leading-relaxed text-base">
            A momentum system doesn't care about headlines, earnings surprises, or social media
            sentiment. It measures price behavior against objective thresholds and acts only when
            the data says to act.
          </p>

          {/* Highlight Box */}
          <div className="bg-claret/10 border border-claret/30 rounded p-6 my-8">
            <p className="text-ink font-semibold text-lg m-0 mb-2">
              Momentum is not prediction.
            </p>
            <p className="text-ink-mute m-0">
              A momentum system doesn't try to predict what a stock will do. It identifies
              what a stock is <em>already doing</em> — trending — and rides that trend until
              the data says it's over. The edge comes from consistency, not clairvoyance.
            </p>
          </div>

          {/* Section 2: The Three Filters */}
          <h2 className="font-display text-2xl font-bold text-ink mt-12 mb-4 flex items-center gap-2" style={{ fontVariationSettings: '"opsz" 48' }}>
            <Filter className="w-6 h-6 text-claret flex-shrink-0" />
            The Three Filters Behind Every Signal
          </h2>
          <p className="text-ink-mute leading-relaxed text-base">
            RigaCap doesn't use a single indicator to generate signals. Instead, every potential
            trade must pass through three independent filters before it becomes a signal. Each
            filter targets a different dimension of stock behavior.
          </p>

          {/* Filter Cards */}
          <div className="grid gap-4 my-8 not-prose">
            <div className="bg-paper-card border border-rule rounded p-6">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-10 h-10 bg-claret/10 rounded-lg flex items-center justify-center">
                  <Zap className="w-5 h-5 text-claret" />
                </div>
                <div>
                  <h3 className="text-ink font-semibold text-base m-0">Filter 1: Timing</h3>
                  <p className="text-ink-light text-sm m-0">Breakout Detection</p>
                </div>
              </div>
              <p className="text-ink-mute text-sm m-0">
                The stock's price must show a confirmed breakout above a key support level.
                This catches early breakouts — moments when a stock transitions from
                consolidation into a genuine uptrend. Without this filter, you'd be buying stocks
                that are merely drifting sideways.
              </p>
            </div>

            <div className="bg-paper-card border border-rule rounded p-6">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-10 h-10 bg-claret/10 rounded-lg flex items-center justify-center">
                  <BarChart3 className="w-5 h-5 text-claret" />
                </div>
                <div>
                  <h3 className="text-ink font-semibold text-base m-0">Filter 2: Quality</h3>
                  <p className="text-ink-light text-sm m-0">Momentum Ranking</p>
                </div>
              </div>
              <p className="text-ink-mute text-sm m-0">
                Every stock in the universe is scored on a composite momentum metric — a blend of
                short-term momentum, long-term momentum, and a volatility penalty. Only the
                highest-ranked stocks survive. This ensures you're not just buying breakouts,
                but the <em>best</em> breakouts.
              </p>
            </div>

            <div className="bg-paper-card border border-rule rounded p-6">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-10 h-10 bg-positive/10 rounded-lg flex items-center justify-center">
                  <Activity className="w-5 h-5 text-positive" />
                </div>
                <div>
                  <h3 className="text-ink font-semibold text-base m-0">Filter 3: Confirmation</h3>
                  <p className="text-ink-light text-sm m-0">Price + Volume</p>
                </div>
              </div>
              <p className="text-ink-mute text-sm m-0">
                The stock must be trading near its recent highs, with a volume spike confirming
                institutional interest. A breakout without volume is often a fake-out. This filter
                separates real institutional moves from noise.
              </p>
            </div>
          </div>

          {/* Section 3: Why 3 Filters Matter */}
          <h2 className="font-display text-2xl font-bold text-ink mt-12 mb-4 flex items-center gap-2" style={{ fontVariationSettings: '"opsz" 48' }}>
            <Shield className="w-6 h-6 text-positive flex-shrink-0" />
            Why Three Filters, Not One?
          </h2>
          <p className="text-ink-mute leading-relaxed text-base">
            Any single filter catches too many false positives. A stock can break above its
            key level and immediately reverse. A stock can rank high on momentum from
            a one-day spike that doesn't sustain. A stock can be near its recent highs on
            declining volume, suggesting the move is exhausted.
          </p>
          <p className="text-ink-mute leading-relaxed text-base">
            When all three agree simultaneously, something meaningful is happening. The stock
            is breaking out (timing), it's one of the strongest movers in the market (quality),
            and institutions are stepping in with real volume (confirmation). That convergence
            creates a high-conviction signal.
          </p>

          {/* Comparison Table */}
          <div className="my-8 not-prose overflow-x-auto">
            <table className="w-full text-sm border border-rule rounded overflow-hidden">
              <thead>
                <tr className="bg-paper-card">
                  <th className="text-left text-ink-mute font-medium px-4 py-3 border-b border-rule">Scenario</th>
                  <th className="text-center text-ink-mute font-medium px-4 py-3 border-b border-rule">Timing</th>
                  <th className="text-center text-ink-mute font-medium px-4 py-3 border-b border-rule">Quality</th>
                  <th className="text-center text-ink-mute font-medium px-4 py-3 border-b border-rule">Confirm</th>
                  <th className="text-left text-ink-mute font-medium px-4 py-3 border-b border-rule">Outcome</th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-b border-rule/50">
                  <td className="text-ink-mute px-4 py-3">Stock breaks out on low volume</td>
                  <td className="text-center text-positive px-4 py-3">Pass</td>
                  <td className="text-center text-positive px-4 py-3">Pass</td>
                  <td className="text-center text-negative px-4 py-3">Fail</td>
                  <td className="text-ink-light px-4 py-3">No signal — likely fake-out</td>
                </tr>
                <tr className="border-b border-rule/50">
                  <td className="text-ink-mute px-4 py-3">Momentum spike, no breakout</td>
                  <td className="text-center text-negative px-4 py-3">Fail</td>
                  <td className="text-center text-positive px-4 py-3">Pass</td>
                  <td className="text-center text-positive px-4 py-3">Pass</td>
                  <td className="text-ink-light px-4 py-3">No signal — chasing, not leading</td>
                </tr>
                <tr className="border-b border-rule/50">
                  <td className="text-ink-mute px-4 py-3">Near high but weak ranking</td>
                  <td className="text-center text-positive px-4 py-3">Pass</td>
                  <td className="text-center text-negative px-4 py-3">Fail</td>
                  <td className="text-center text-positive px-4 py-3">Pass</td>
                  <td className="text-ink-light px-4 py-3">No signal — mediocre momentum</td>
                </tr>
                <tr>
                  <td className="text-ink font-medium px-4 py-3">All three aligned</td>
                  <td className="text-center text-positive px-4 py-3">Pass</td>
                  <td className="text-center text-positive px-4 py-3">Pass</td>
                  <td className="text-center text-positive px-4 py-3">Pass</td>
                  <td className="text-claret font-medium px-4 py-3">Signal fired</td>
                </tr>
              </tbody>
            </table>
          </div>

          <p className="text-ink-mute leading-relaxed text-base">
            Think of it as triangulation. One reading can be wrong. Three independent readings
            pointing the same direction dramatically reduce false signals and increase the
            probability you're entering a genuine trend.
          </p>

          {/* Section 4: Ensemble Scoring */}
          <h2 className="font-display text-2xl font-bold text-ink mt-12 mb-4 flex items-center gap-2" style={{ fontVariationSettings: '"opsz" 48' }}>
            <BarChart3 className="w-6 h-6 text-claret flex-shrink-0" />
            How Ensemble Scoring Works
          </h2>
          <p className="text-ink-mute leading-relaxed text-base">
            Once a stock passes all three filters, it receives a composite score that ranks
            it against other qualifying stocks. The formula blends three components:
          </p>
          <ul className="text-ink-mute text-base space-y-2">
            <li>
              <strong className="text-ink">Short-term momentum:</strong> Captures
              recent acceleration. A stock surging over the last few weeks gets a higher
              short-term score than one that's been flat.
            </li>
            <li>
              <strong className="text-ink">Long-term momentum:</strong> Confirms the
              trend has staying power. A short-term spike means little if the stock has been
              declining for months.
            </li>
            <li>
              <strong className="text-ink">Volatility penalty:</strong> Subtracts points for
              erratic price action. Two stocks with identical momentum scores aren't equal if
              one got there in a straight line and the other whipsawed. The smoother path
              is more reliable.
            </li>
          </ul>

          {/* Sample Signal Card */}
          <div className="my-8 not-prose">
            <p className="text-ink-light text-xs uppercase tracking-wider mb-3 font-medium">
              Example Signal Breakdown
            </p>
            <div className="bg-paper-card border border-rule rounded p-6">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <span className="text-ink font-bold text-xl">NVDA</span>
                  <span className="ml-3 px-2 py-0.5 bg-positive/10 text-positive text-xs font-medium rounded-full">
                    Fresh Signal
                  </span>
                </div>
                <span className="text-claret font-bold text-lg">Score: 87</span>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div>
                  <p className="text-ink-light text-xs m-0">Breakout Detection</p>
                  <p className="text-positive font-semibold text-sm m-0">+7.2% above</p>
                </div>
                <div>
                  <p className="text-ink-light text-xs m-0">Momentum Rank</p>
                  <p className="text-claret font-semibold text-sm m-0">#3 of 100</p>
                </div>
                <div>
                  <p className="text-ink-light text-xs m-0">Near Recent High</p>
                  <p className="text-positive font-semibold text-sm m-0">Within 2.1%</p>
                </div>
                <div>
                  <p className="text-ink-light text-xs m-0">Volume Spike</p>
                  <p className="text-positive font-semibold text-sm m-0">1.8x average</p>
                </div>
              </div>
            </div>
          </div>

          <p className="text-ink-mute leading-relaxed text-base">
            The composite score ranks every signal by strength. A stock scoring 90 represents
            stronger convergence than one scoring 65. This ranking determines which stocks
            make it into the portfolio when qualifying signals outnumber available positions.
          </p>

          {/* Section 5: Why 6 Positions */}
          <h2 className="font-display text-2xl font-bold text-ink mt-12 mb-4 flex items-center gap-2" style={{ fontVariationSettings: '"opsz" 48' }}>
            <Activity className="w-6 h-6 text-claret flex-shrink-0" />
            Why a Concentrated Portfolio?
          </h2>
          <p className="text-ink-mute leading-relaxed text-base">
            Most momentum strategies spread capital across 20 or 30 positions. More diversification
            sounds safer, but for momentum specifically, that logic backfires. When you dilute across
            30 positions, you inevitably include stocks ranked 15th, 20th, 25th — stocks that barely
            qualified. Those mediocre positions drag down the winners and flatten returns toward
            the market average.
          </p>
          <p className="text-ink-mute leading-relaxed text-base">
            A concentrated portfolio of our highest-conviction picks strikes the balance:
            focused enough to capture meaningful gains from top-ranked stocks, diversified
            enough that one bad trade doesn't derail the portfolio. Trailing stops provide
            the real risk management.
          </p>

          {/* Highlight Box */}
          <div className="bg-paper-deep border border-rule rounded p-6 my-8">
            <p className="text-ink font-semibold text-lg m-0 mb-2">
              Concentration is a feature, not a bug.
            </p>
            <p className="text-ink-mute m-0">
              If your system is good at identifying the best opportunities, putting meaningful
              capital behind them produces better risk-adjusted returns than spreading thin.
              The catch is that your system has to actually be good — which is why the three-filter
              approach matters so much.
            </p>
          </div>

          {/* Section 6: Fresh vs Monitoring */}
          <h2 className="font-display text-2xl font-bold text-ink mt-12 mb-4 flex items-center gap-2" style={{ fontVariationSettings: '"opsz" 48' }}>
            <Zap className="w-6 h-6 text-claret flex-shrink-0" />
            Fresh Signals vs. Monitoring
          </h2>
          <p className="text-ink-mute leading-relaxed text-base">
            When you log into RigaCap, you'll see signals labeled as either "fresh" or
            "monitoring." Understanding the difference is important for timing your entries.
          </p>
          <p className="text-ink-mute leading-relaxed text-base">
            A <strong className="text-positive">fresh signal</strong> means the stock just
            passed all three filters for the first time, or re-qualified after a gap. The
            system is saying "this is actionable right now."
          </p>
          <p className="text-ink-mute leading-relaxed text-base">
            A <strong className="text-claret">monitoring signal</strong> means the stock
            previously fired a signal and still meets the criteria. The trend is intact but
            the initial entry window may have passed — you'd be entering later in the move.
          </p>
          <p className="text-ink-mute leading-relaxed text-base">
            Fresh signals are the highest-conviction entries, representing the earliest
            detection of a new trend. Monitoring signals confirm existing positions remain
            valid, or offer a second chance if you missed the initial signal — but the
            risk/reward profile shifts as the move matures.
          </p>

          {/* Section 7: Market Regime Filter */}
          <h2 className="font-display text-2xl font-bold text-ink mt-12 mb-4 flex items-center gap-2" style={{ fontVariationSettings: '"opsz" 48' }}>
            <AlertTriangle className="w-6 h-6 text-negative flex-shrink-0" />
            The Market Regime Filter
          </h2>
          <p className="text-ink-mute leading-relaxed text-base">
            Everything above — the three filters, the scoring, the concentration — only
            matters when the broader market is cooperating. Momentum strategies are inherently
            long-biased. When the entire market is falling, even the "best" stocks get pulled lower.
          </p>
          <p className="text-ink-mute leading-relaxed text-base">
            RigaCap's regime filter monitors market health using multiple indicators, including
            whether the broad market is trending up or down. When the regime
            shifts bearish, the system stops issuing buy signals and exits positions regardless
            of their individual strength.
          </p>
          <p className="text-ink-mute leading-relaxed text-base">
            This is where most investors go wrong — finding a stock that looks great on its
            own merits while ignoring the broader market falling around it. In a true bear
            market, no stock is an island.
          </p>

          {/* Regime States */}
          <div className="my-8 not-prose grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="bg-positive/10 border border-positive/20 rounded-lg p-4">
              <p className="text-positive font-semibold text-sm m-0 mb-1">Bullish Regime</p>
              <p className="text-ink-mute text-xs m-0">
                Market trend is healthy. All three filters active. New signals issued normally.
                Portfolio fully invested in top-ranked positions.
              </p>
            </div>
            <div className="bg-negative/10 border border-negative/20 rounded-lg p-4">
              <p className="text-negative font-semibold text-sm m-0 mb-1">Bearish Regime</p>
              <p className="text-ink-mute text-xs m-0">
                Market trend is broken. No new buy signals. Existing positions exit via
                trailing stops or regime-forced sells. Capital moves to cash until conditions improve.
              </p>
            </div>
          </div>

          <p className="text-ink-mute leading-relaxed text-base">
            Going to cash during bear markets isn't about timing the bottom — it's about
            capital preservation. Missing the last 10% of a bull run costs far less than
            riding a 30% drawdown. The system re-enters when the regime shifts back to
            bullish, systematically, without guessing when the bottom is in.
          </p>

          {/* Highlight Box */}
          <div className="bg-claret/10 border border-claret/30 rounded p-6 my-8">
            <p className="text-ink font-semibold text-lg m-0 mb-2">
              The best trade is sometimes no trade at all.
            </p>
            <p className="text-ink-mute m-0">
              Sitting in cash while the market drops isn't failure — it's the system working
              exactly as designed. Protecting capital during downturns is what allows aggressive
              re-entry when the trend resumes.
            </p>
          </div>

        </div>

        {/* CTA */}
        <div className="bg-paper-card border border-rule rounded p-8 sm:p-10 my-12 text-center">
          <h2 className="font-display text-2xl sm:text-3xl font-bold text-ink mb-3" style={{ fontVariationSettings: '"opsz" 48' }}>
            See Today's Signals
          </h2>
          <p className="text-ink-mute mb-6 max-w-lg mx-auto">
            Three filters. Ensemble scoring. Market regime awareness.
            See which stocks are passing all three right now.
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
              className="inline-flex items-center justify-center gap-2 bg-paper-deep hover:bg-paper-card text-ink font-medium px-8 py-3 rounded transition-colors text-base"
            >
              View Track Record
            </Link>
          </div>
          <p className="text-xs text-ink-light mt-4">
            7-day free trial. $39/month after. Cancel anytime.
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
            <Link to="/blog/trailing-stops" className="block p-4 bg-paper-card rounded border border-rule hover:border-rule-dark transition-colors">
              <span className="text-ink font-medium">How Trailing Stops Protect Your Portfolio</span>
              <span className="block text-ink-light text-sm mt-1">Why trailing stops let winners run while automatically locking in gains.</span>
            </Link>
            <Link to="/blog/market-regime-guide" className="block p-4 bg-paper-card rounded border border-rule hover:border-rule-dark transition-colors">
              <span className="text-ink font-medium">Market Regime Trading: A Beginner's Guide</span>
              <span className="block text-ink-light text-sm mt-1">Learn what market regimes are and how to adjust your strategy for each one.</span>
            </Link>
            <Link to="/blog/we-called-it-mrna" className="block p-4 bg-paper-card rounded border border-rule hover:border-rule-dark transition-colors">
              <span className="text-ink font-medium">We Called It: Moderna +51%</span>
              <span className="block text-ink-light text-sm mt-1">How our system caught Moderna's breakout and locked in gains before the crash.</span>
            </Link>
          </div>
        </div>

        {/* Disclaimer */}
        <p className="text-xs text-ink-light leading-relaxed">
          All performance references are based on walk-forward simulations using historical market data.
          Past performance does not guarantee future results. Momentum strategies involve risk including
          loss of principal. RigaCap provides trading signals only — execute trades through your own
          brokerage account. This article is for educational purposes and does not constitute investment
          advice. See our{' '}
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
