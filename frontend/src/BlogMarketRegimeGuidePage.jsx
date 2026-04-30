import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, ArrowRight, BookOpen, Thermometer, Eye, AlertTriangle, CheckCircle, TrendingUp, Shield } from 'lucide-react';
import MarketMeasuredSignup from './components/MarketMeasuredSignup';

const regimeSpectrum = [
  { name: 'Strong Bull', color: 'bg-emerald-500', textColor: 'text-emerald-100', brief: 'Everything rising together' },
  { name: 'Weak Bull', color: 'bg-emerald-400', textColor: 'text-emerald-950', brief: 'Only a few leaders' },
  { name: 'Rotating Bull', color: 'bg-teal-400', textColor: 'text-teal-950', brief: 'Sectors taking turns' },
  { name: 'Range Bound', color: 'bg-gray-400', textColor: 'text-gray-950', brief: 'Going nowhere' },
  { name: 'Weak Bear', color: 'bg-orange-400', textColor: 'text-orange-950', brief: 'Slow grind lower' },
  { name: 'Panic Crash', color: 'bg-red-500', textColor: 'text-red-100', brief: 'Sharp, fast decline' },
  { name: 'Recovery', color: 'bg-blue-400', textColor: 'text-blue-950', brief: 'Market bottoming out' },
];

const actionTable = [
  {
    regime: 'Strong Bull / Weak Bull',
    action: 'Stay invested, let momentum work',
    why: 'The trend is your friend. Fighting it costs more than riding it.',
    color: 'text-positive',
  },
  {
    regime: 'Rotating Bull',
    action: 'Be selective, follow the leaders',
    why: 'Not everything works. Pick the sectors showing strength right now.',
    color: 'text-teal-600',
  },
  {
    regime: 'Range Bound',
    action: 'Reduce position sizes, be patient',
    why: 'Breakouts fail in sideways markets. Smaller bets limit the damage.',
    color: 'text-ink-mute',
  },
  {
    regime: 'Weak Bear / Panic Crash',
    action: 'Go to cash, protect capital',
    why: 'Catching falling knives is expensive. Cash is a position.',
    color: 'text-negative',
  },
  {
    regime: 'Recovery',
    action: 'Start re-entering cautiously',
    why: 'Early leaders emerge, but false bottoms are common. Go slow.',
    color: 'text-claret',
  },
];

export default function BlogMarketRegimeGuidePage() {
  useEffect(() => {
    document.title = "Market Regime Trading: A Beginner's Guide | RigaCap";
    const meta = document.querySelector('meta[name="description"]');
    if (meta) meta.setAttribute('content', 'Most investors think bull or bear. Reality has 7 distinct market regimes. Learn how to read the market mood and trade accordingly.');

    // OG tags for social sharing
    document.querySelector('meta[property="og:title"]')?.setAttribute('content', 'Market Regime Trading: A Beginner\'s Guide | RigaCap');
    document.querySelector('meta[property="og:description"]')?.setAttribute('content', 'Most investors think bull or bear. Reality has 7 distinct market regimes. Learn how to read the market mood and trade accordingly.');
    document.querySelector('meta[property="og:url"]')?.setAttribute('content', 'https://rigacap.com/blog/market-regime-guide');
    document.querySelector('meta[name="twitter:title"]')?.setAttribute('content', 'Market Regime Trading: A Beginner\'s Guide | RigaCap');
    document.querySelector('meta[name="twitter:description"]')?.setAttribute('content', 'Most investors think bull or bear. Reality has 7 distinct market regimes. Learn how to read the market mood and trade accordingly.');
    // JSON-LD Article schema
    const existingSchema = document.querySelector('script[type="application/ld+json"]');
    if (existingSchema) existingSchema.remove();
    const schema = document.createElement('script');
    schema.type = 'application/ld+json';
    schema.text = JSON.stringify({
      "@context": "https://schema.org",
      "@type": "Article",
      "headline": "Market Regime Trading: A Beginner\'s Guide",
      "description": "Most investors think bull or bear. Reality has 7 distinct market regimes. Learn how to read the market mood and trade accordingly.",
      "author": {"@type": "Organization", "name": "RigaCap"},
      "publisher": {"@type": "Organization", "name": "RigaCap", "url": "https://rigacap.com"},
      "url": "https://rigacap.com/blog/market-regime-guide",
      "articleSection": "Education",
    });
    document.head.appendChild(schema);
    return () => { if (schema.parentNode) schema.remove(); };
  }, []);

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
          <p className="text-sm font-medium uppercase tracking-widest text-claret mb-6">Beginner's Guide</p>
          <h1 className="font-display text-3xl sm:text-5xl font-bold text-ink tracking-tight mb-4" style={{ fontVariationSettings: '"opsz" 48' }}>
            Market Regime Trading: A Beginner's Guide to Reading the Market's Mood
          </h1>
          <p className="text-lg text-ink-mute max-w-2xl mx-auto">
            Stop thinking in "bull or bear." The market has seven distinct personalities
            — and knowing which one is active changes everything.
          </p>
        </div>
      </section>

      {/* Article Body */}
      <article className="max-w-3xl mx-auto px-4 sm:px-6 py-12 sm:py-16">
        <div className="prose prose-gray max-w-none">

          {/* Opening */}
          <h2 className="font-display text-2xl font-bold text-ink mt-0 mb-4" style={{ fontVariationSettings: '"opsz" 48' }}>
            Bull or Bear? It's Not That Simple
          </h2>
          <p className="text-ink-mute leading-relaxed text-base">
            Ask most investors what the market is doing and you'll get one of two answers:
            "it's a bull market" or "it's a bear market." That's like describing the
            weather as either "nice" or "bad." Technically not wrong, but not very useful
            when you're deciding whether to pack an umbrella.
          </p>
          <p className="text-ink-mute leading-relaxed text-base">
            In reality, the market moves through at least seven distinct phases — each
            with its own personality, its own risks, and its own playbook. Understanding
            these phases is what separates investors who react from investors who anticipate.
          </p>
        </div>

        {/* What is a Market Regime */}
        <div className="prose prose-gray max-w-none">
          <h2 className="font-display text-2xl font-bold text-ink mt-12 mb-4 flex items-center gap-2" style={{ fontVariationSettings: '"opsz" 48' }}>
            <Thermometer className="w-6 h-6 text-claret flex-shrink-0" />
            What Is a Market Regime?
          </h2>
          <p className="text-ink-mute leading-relaxed text-base">
            A market regime is the market's personality at any given time. Think of it
            as the environment your investments are living in. Just like plants grow
            differently in summer versus winter, stocks behave differently depending
            on the market's current regime.
          </p>
          <p className="text-ink-mute leading-relaxed text-base">
            The regime determines which strategies work and which ones fail. A momentum
            strategy that prints money in a Strong Bull can destroy your portfolio in a
            Panic Crash. A defensive approach that saves you during a bear market will
            leave you sitting on the sidelines during the best rallies.
          </p>
          <p className="text-ink-mute leading-relaxed text-base">
            The key insight: <span className="text-ink font-medium">you don't need to predict the future — you
            just need to correctly identify the present.</span>
          </p>
        </div>

        {/* The 7 Regimes — Visual Spectrum */}
        <h2 className="font-display text-2xl font-bold text-ink mt-12 mb-6 flex items-center gap-2" style={{ fontVariationSettings: '"opsz" 48' }}>
          <Eye className="w-6 h-6 text-claret flex-shrink-0" />
          The 7 Market Regimes at a Glance
        </h2>

        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2 my-8">
          {regimeSpectrum.map((regime) => (
            <div
              key={regime.name}
              className={`${regime.color} rounded p-3 text-center flex flex-col justify-between min-h-[100px]`}
            >
              <p className={`${regime.textColor} font-bold text-xs sm:text-sm m-0 leading-tight`}>
                {regime.name}
              </p>
              <p className={`${regime.textColor} text-[10px] sm:text-xs m-0 mt-1 opacity-80 leading-tight`}>
                {regime.brief}
              </p>
            </div>
          ))}
        </div>

        <p className="text-sm text-ink-light text-center mb-8">
          Green = bullish regimes. Amber/Red = bearish. Blue = transition.{' '}
          <Link to="/blog/market-regimes" className="text-claret hover:text-claret/80 underline underline-offset-2 transition-colors">
            Read the deep-dive on all 7 regimes
          </Link>
        </p>

        {/* Why Regime > Stock Picking */}
        <div className="prose prose-gray max-w-none">
          <h2 className="font-display text-2xl font-bold text-ink mt-12 mb-4 flex items-center gap-2" style={{ fontVariationSettings: '"opsz" 48' }}>
            <TrendingUp className="w-6 h-6 text-claret flex-shrink-0" />
            Why Regime Matters More Than Stock Picking
          </h2>
          <p className="text-ink-mute leading-relaxed text-base">
            Here's a hard truth most investors learn the expensive way: the best stock in
            a Panic Crash still loses money. The worst stock in a Strong Bull often goes up.
          </p>
          <p className="text-ink-mute leading-relaxed text-base">
            Studies consistently show that 60-80% of a stock's movement comes from the
            overall market and its sector — not from anything specific to that company.
            When the tide goes out, nearly every boat drops. When it comes in, most float
            higher.
          </p>
          <p className="text-ink-mute leading-relaxed text-base">
            This means your first question shouldn't be "which stock should I buy?" It
            should be <span className="text-ink font-medium">"should I be buying anything at
            all right now?"</span> The regime answers that question.
          </p>
        </div>

        {/* How to Detect the Regime */}
        <div className="prose prose-gray max-w-none">
          <h2 className="font-display text-2xl font-bold text-ink mt-12 mb-4 flex items-center gap-2" style={{ fontVariationSettings: '"opsz" 48' }}>
            <Eye className="w-6 h-6 text-claret flex-shrink-0" />
            How to Tell Which Regime You're In
          </h2>
          <p className="text-ink-mute leading-relaxed text-base">
            You don't need a PhD to get a rough read on the market's current mood. Here
            are four signals even beginners can track:
          </p>
        </div>

        <div className="grid gap-4 my-8">
          <div className="bg-paper-card border border-rule rounded p-5">
            <h4 className="text-ink font-semibold m-0 mb-2">1. SPY vs. Its 200-Day Moving Average</h4>
            <p className="text-ink-mute text-sm m-0">
              The simplest regime indicator. Pull up a chart of SPY (the S&P 500 ETF) and
              its 200-day moving average. If SPY is above the line, the market is broadly
              bullish. Below it, bearish. It's not perfect, but it keeps you on the right
              side of the major trend about 80% of the time.
            </p>
          </div>
          <div className="bg-paper-card border border-rule rounded p-5">
            <h4 className="text-ink font-semibold m-0 mb-2">2. Market Breadth</h4>
            <p className="text-ink-mute text-sm m-0">
              Are most stocks going up, or just a handful of large ones? When the S&P 500
              rises but fewer than half its stocks are above their own 50-day average, that's
              a Weak Bull — narrow leadership that can crack at any time. Broad participation
              means a healthier, more sustainable move.
            </p>
          </div>
          <div className="bg-paper-card border border-rule rounded p-5">
            <h4 className="text-ink font-semibold m-0 mb-2">3. The VIX (Market Fear Index)</h4>
            <p className="text-ink-mute text-sm m-0">
              The VIX measures how much volatility investors expect over the next 30 days.
              Think of it as the market's anxiety level. Below 15 means calm (bullish regimes).
              Between 20-30 means nervous (range-bound or weak bear). Above 30 means fear
              is running the show (panic crash territory).
            </p>
          </div>
          <div className="bg-paper-card border border-rule rounded p-5">
            <h4 className="text-ink font-semibold m-0 mb-2">4. Sector Rotation Patterns</h4>
            <p className="text-ink-mute text-sm m-0">
              Which sectors are leading? In a Strong Bull, growth sectors like technology
              and consumer discretionary lead. In a defensive regime, utilities and healthcare
              take over. When leadership rotates rapidly from sector to sector with no clear
              winner, you're likely in a Rotating Bull or Range Bound environment.
            </p>
          </div>
        </div>

        {/* What to DO — Action Table */}
        <h2 className="font-display text-2xl font-bold text-ink mt-12 mb-6 flex items-center gap-2" style={{ fontVariationSettings: '"opsz" 48' }}>
          <CheckCircle className="w-6 h-6 text-claret flex-shrink-0" />
          What to Do in Each Regime
        </h2>

        <div className="bg-paper-card border border-rule rounded overflow-hidden my-8">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-rule">
                  <th className="text-left text-ink-light uppercase tracking-wider text-xs font-medium px-5 py-3">Regime</th>
                  <th className="text-left text-ink-light uppercase tracking-wider text-xs font-medium px-5 py-3">Action</th>
                  <th className="text-left text-ink-light uppercase tracking-wider text-xs font-medium px-5 py-3 hidden sm:table-cell">Why</th>
                </tr>
              </thead>
              <tbody>
                {actionTable.map((row, i) => (
                  <tr key={row.regime} className={i < actionTable.length - 1 ? 'border-b border-rule/50' : ''}>
                    <td className={`px-5 py-4 font-medium whitespace-nowrap ${row.color}`}>
                      {row.regime}
                    </td>
                    <td className="px-5 py-4 text-ink-mute">
                      {row.action}
                    </td>
                    <td className="px-5 py-4 text-ink-light hidden sm:table-cell">
                      {row.why}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* The #1 Mistake */}
        <div className="bg-negative/10 border border-negative/30 rounded p-6 my-8">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-negative flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-negative font-semibold text-lg m-0 mb-2">
                The #1 Mistake: Treating a Rotating Bull Like a Strong Bull
              </p>
              <p className="text-ink-mute m-0 text-sm leading-relaxed">
                In a Strong Bull, you can buy almost anything and it goes up. In a Rotating
                Bull, only certain sectors are working at any given time — and they change
                fast. The mistake is chasing everything because the index looks healthy,
                when underneath the surface, what worked last week is already fading. Being
                selective is the entire game in a rotating market.
              </p>
            </div>
          </div>
        </div>

        {/* How RigaCap Automates This */}
        <div className="prose prose-gray max-w-none">
          <h2 className="font-display text-2xl font-bold text-ink mt-12 mb-4 flex items-center gap-2" style={{ fontVariationSettings: '"opsz" 48' }}>
            <Shield className="w-6 h-6 text-claret flex-shrink-0" />
            How RigaCap Automates Regime Detection
          </h2>
          <p className="text-ink-mute leading-relaxed text-base">
            Tracking all four signals above — and correctly interpreting what they mean
            together — is a full-time job. That's exactly why we built a system to do it.
          </p>
          <p className="text-ink-mute leading-relaxed text-base">
            RigaCap's regime filter runs <em>before</em> any individual stock signals fire.
            Think of it as a gatekeeper: the system first decides whether the current
            environment is worth trading in, and only then looks for specific opportunities.
            In a Panic Crash, the gatekeeper says "no" — and no amount of bullish-looking
            chart patterns on individual stocks will override that.
          </p>
          <p className="text-ink-mute leading-relaxed text-base">
            This removes the hardest part of investing from your plate: the judgment call.
            No more agonizing over whether the dip is a buying opportunity or the start of
            something worse. The regime model makes that call quantitatively, using the same
            data every day, without emotion or recency bias.
          </p>
          <p className="text-ink-mute leading-relaxed text-base">
            Want to go deeper? Our{' '}
            <Link to="/blog/market-regimes" className="text-claret hover:text-claret/80 underline underline-offset-2 transition-colors">
              full breakdown of all 7 regimes
            </Link>
            {' '}covers each one in detail with historical examples and system response logic.
          </p>
        </div>

        {/* CTA */}
        <div className="border border-rule rounded p-8 sm:p-10 my-12 text-center">
          <h2 className="font-display text-2xl sm:text-3xl font-bold text-ink mb-3" style={{ fontVariationSettings: '"opsz" 48' }}>
            See the Current Market Regime
          </h2>
          <p className="text-ink-mute mb-6 max-w-lg mx-auto">
            Check what the market is doing right now — no account required. See the
            active regime, probability distribution, and what it means for your portfolio.
          </p>
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <Link
              to="/market-regime"
              className="inline-flex items-center justify-center gap-2 bg-ink text-paper hover:bg-claret font-semibold px-8 py-3 rounded transition-colors text-base"
            >
              View Current Regime
              <ArrowRight size={18} />
            </Link>
            <Link
              to="/app"
              className="inline-flex items-center justify-center gap-2 border border-rule hover:border-ink text-ink font-medium px-8 py-3 rounded transition-colors text-base"
            >
              Start Free Trial
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
            <Link to="/blog/market-regimes" className="block p-4 bg-paper-card rounded border border-rule hover:border-rule-dark transition-colors">
              <span className="text-ink font-medium">The 7 Market Regimes — Deep Dive</span>
              <span className="block text-ink-light text-sm mt-1">A detailed look at each of the seven market regimes and what drives them.</span>
            </Link>
            <Link to="/blog/market-crash" className="block p-4 bg-paper-card rounded border border-rule hover:border-rule-dark transition-colors">
              <span className="text-ink font-medium">What to Do When the Market Crashes</span>
              <span className="block text-ink-light text-sm mt-1">Practical steps for protecting your portfolio during market downturns.</span>
            </Link>
            <Link to="/blog/trailing-stops" className="block p-4 bg-paper-card rounded border border-rule hover:border-rule-dark transition-colors">
              <span className="text-ink font-medium">How Trailing Stops Protect Your Portfolio</span>
              <span className="block text-ink-light text-sm mt-1">Why trailing stops are essential for locking in gains during volatile regimes.</span>
            </Link>
          </div>
        </div>

        {/* Disclaimer */}
        <p className="text-xs text-ink-light leading-relaxed">
          All performance references are from walk-forward simulations using historical market data.
          Market regime classifications are derived from quantitative models and may not
          predict future market conditions.
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
