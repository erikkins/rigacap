import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, TrendingUp, TrendingDown, Activity, BarChart3, ArrowRight, Zap, Shield, Sun, Cloud, CloudRain, CloudLightning, Sunrise } from 'lucide-react';
import MarketMeasuredSignup from './components/MarketMeasuredSignup';

const regimes = [
  {
    name: 'Strong Bull',
    icon: Sun,
    iconColor: 'text-positive',
    borderColor: 'border-positive/40',
    bgColor: 'bg-positive/10',
    badgeColor: 'bg-positive/20 text-positive',
    description: 'Broad rally across sectors. Most stocks are rising, volatility is low, and investor confidence is high. This is the environment where momentum strategies thrive.',
    systemAction: 'Fully deployed. Maximum positions, riding the trend with trailing stops to protect gains.',
    example: 'Late 2021 — everything was going up. Tech, energy, financials all rallied together.',
  },
  {
    name: 'Weak Bull',
    icon: TrendingUp,
    iconColor: 'text-positive',
    borderColor: 'border-positive/30',
    bgColor: 'bg-positive/5',
    badgeColor: 'bg-positive/15 text-positive',
    description: 'Market is drifting higher, but leadership is narrow. A handful of mega-caps are carrying the index while most stocks go nowhere. Breadth is deteriorating beneath the surface.',
    systemAction: 'Selective entries only. Tighter quality filters. The system is pickier about which signals to act on.',
    example: 'Mid-2023 — the "Magnificent Seven" rallied while the average stock was flat.',
  },
  {
    name: 'Rotating Bull',
    icon: Activity,
    iconColor: 'text-teal-600',
    borderColor: 'border-teal-500/30',
    bgColor: 'bg-teal-500/5',
    badgeColor: 'bg-teal-500/15 text-teal-600',
    description: 'Sectors taking turns leading. One week it\'s energy, the next it\'s healthcare. The market is positive overall but choppy and unpredictable day-to-day.',
    systemAction: 'Cautious positioning. The system may enter but keeps position sizes moderate and watches for regime deterioration.',
    example: 'Early 2024 — sector rotation accelerated as investors debated rate cut timing.',
  },
  {
    name: 'Range Bound',
    icon: BarChart3,
    iconColor: 'text-ink-mute',
    borderColor: 'border-rule',
    bgColor: 'bg-paper-deep',
    badgeColor: 'bg-paper-deep text-ink-mute',
    description: 'Market going sideways. No clear trend in either direction. Breakouts fail, momentum stalls, and most moves reverse within days.',
    systemAction: 'Patience mode. Very few signals generated. Mostly sitting in cash, waiting for a directional move.',
    example: 'Summer 2022 — the market chopped between support and resistance for weeks before resuming its decline.',
  },
  {
    name: 'Weak Bear',
    icon: CloudRain,
    iconColor: 'text-negative',
    borderColor: 'border-negative/30',
    bgColor: 'bg-negative/5',
    badgeColor: 'bg-negative/15 text-negative',
    description: 'Market trending down slowly. Not a crash, but a persistent grind lower. Each rally fails at a lower high. Optimism is fading.',
    systemAction: 'Reduced exposure with tight stops. The system may hold a position or two but is mostly defensive.',
    example: 'Early 2022 — the Fed started hawkish talk and the market began rolling over before the real crash.',
  },
  {
    name: 'Panic Crash',
    icon: CloudLightning,
    iconColor: 'text-negative',
    borderColor: 'border-negative/40',
    bgColor: 'bg-negative/10',
    badgeColor: 'bg-negative/20 text-negative',
    description: 'Sharp, fast decline. Volatility spikes. Correlations go to 1 — everything drops together. Fear dominates and selling feeds on itself.',
    systemAction: 'Full cash. Zero positions. The system exits everything and waits. This is where capital preservation matters most.',
    example: 'March 2020 — COVID crash. June 2022 — inflation shock. The market dropped 10%+ in days.',
  },
  {
    name: 'Recovery',
    icon: Sunrise,
    iconColor: 'text-claret',
    borderColor: 'border-claret/30',
    bgColor: 'bg-claret/5',
    badgeColor: 'bg-claret/15 text-claret',
    description: 'Market bottoming and turning. Volatility is still elevated but declining. Early leaders are emerging from the wreckage. The crowd is still fearful.',
    systemAction: 'Cautious re-entry. Early signals appear and the system begins deploying capital again — but slowly, with tight risk controls.',
    example: 'October 2022 — the bear market bottom. Stocks started recovering but most investors were still paralyzed by fear.',
  },
];

export default function BlogMarketRegimesPage() {
  useEffect(() => { document.title = 'The 7 Market Regimes | RigaCap'; }, []);
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
          <p className="text-sm font-medium uppercase tracking-widest text-claret mb-6">Proprietary Intelligence</p>
          <h1 className="font-display text-4xl sm:text-5xl font-bold text-ink tracking-tight mb-4" style={{ fontVariationSettings: '"opsz" 48' }}>
            The 7 Market Regimes
          </h1>
          <p className="text-lg text-ink-mute max-w-2xl mx-auto">
            Most strategies have one mode. Ours detects seven.
            <br className="hidden sm:block" />
            Understanding the current regime changes everything.
          </p>
        </div>
      </section>

      {/* Article Body */}
      <article className="max-w-3xl mx-auto px-4 sm:px-6 py-12 sm:py-16">
        <div className="prose prose-gray max-w-none">

          {/* The Problem */}
          <h2 className="font-display text-2xl font-bold text-ink mt-0 mb-4" style={{ fontVariationSettings: '"opsz" 48' }}>
            The Problem With One-Size-Fits-All
          </h2>
          <p className="text-ink-mute leading-relaxed text-base">
            Most trading strategies use the same rules regardless of market conditions.
            A momentum strategy that works beautifully in a bull market gets destroyed in
            a bear. A defensive strategy that protects you in crashes misses the rallies
            entirely. And a "balanced" approach does neither well.
          </p>
          <p className="text-ink-mute leading-relaxed text-base">
            The market isn't one thing. It cycles through distinct phases — each with
            different characteristics, different risks, and different opportunities. A
            strategy that doesn't recognize these phases is flying blind.
          </p>
          <p className="text-ink-mute leading-relaxed text-base">
            RigaCap's ensemble system classifies the market into seven distinct regimes
            and adjusts its behavior accordingly. Not with vague rules of thumb, but with
            a quantitative model that reads the market's vital signs in real time.
          </p>
        </div>

        {/* The 7 Regimes */}
        <h2 className="font-display text-2xl font-bold text-ink mt-12 mb-6 flex items-center gap-2" style={{ fontVariationSettings: '"opsz" 48' }}>
          <Shield className="w-6 h-6 text-claret flex-shrink-0" />
          The Seven Regimes
        </h2>

        <div className="grid gap-4 my-8">
          {regimes.map((regime, index) => {
            const Icon = regime.icon;
            return (
              <div key={regime.name} className={`bg-paper-card border ${regime.borderColor} rounded p-6`}>
                <div className="flex items-start gap-4">
                  <div className={`w-10 h-10 rounded ${regime.bgColor} flex items-center justify-center flex-shrink-0`}>
                    <Icon className={`w-5 h-5 ${regime.iconColor}`} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="text-ink font-semibold m-0">{regime.name}</h3>
                      <span className={`text-[10px] font-medium uppercase tracking-wider px-2 py-0.5 rounded ${regime.badgeColor}`}>
                        Regime {index + 1}
                      </span>
                    </div>
                    <p className="text-ink-mute text-sm m-0 mb-3">
                      {regime.description}
                    </p>
                    <div className="flex flex-col sm:flex-row sm:items-start gap-2 sm:gap-6 text-xs">
                      <div>
                        <span className="text-ink-light uppercase tracking-wider font-medium">System response: </span>
                        <span className="text-ink-mute">{regime.systemAction}</span>
                      </div>
                    </div>
                    <div className="mt-2 text-xs">
                      <span className="text-ink-light uppercase tracking-wider font-medium">Historical example: </span>
                      <span className="text-ink-mute">{regime.example}</span>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        <div className="prose prose-gray max-w-none">

          {/* Why This Matters */}
          <h2 className="font-display text-2xl font-bold text-ink mt-12 mb-4 flex items-center gap-2" style={{ fontVariationSettings: '"opsz" 48' }}>
            <BarChart3 className="w-6 h-6 text-claret flex-shrink-0" />
            Why This Matters
          </h2>
          <p className="text-ink-mute leading-relaxed text-base">
            Regime-aware trading isn't a marginal improvement — it's a fundamentally
            different approach. A static momentum strategy would have been fully invested
            through all of 2022, riding the market down 20%. A regime-aware strategy
            recognized deteriorating conditions and stepped aside.
          </p>
        </div>

        {/* Highlight Box */}
        <div className="bg-claret/10 border border-claret/30 rounded p-6 my-8">
          <p className="text-claret font-semibold text-lg m-0 mb-2">
            In 2022, our regime model detected deteriorating conditions and moved to cash BEFORE the 20% crash.
          </p>
          <p className="text-ink-mute m-0 text-sm">
            While static strategies rode the market down, our system generated zero buy signals for five
            consecutive months. The result: positive returns in a year when the S&P 500 lost a fifth of its value.
            That single regime call — doing nothing when everyone else was buying the dip — was worth more
            than a year's worth of stock picks.
          </p>
        </div>

        <div className="prose prose-gray max-w-none">

          {/* Transitions */}
          <h2 className="font-display text-2xl font-bold text-ink mt-12 mb-4 flex items-center gap-2" style={{ fontVariationSettings: '"opsz" 48' }}>
            <Zap className="w-6 h-6 text-claret flex-shrink-0" />
            Regime Transitions Are Where the Money Is
          </h2>
          <p className="text-ink-mute leading-relaxed text-base">
            Identifying the current regime is valuable. But the real edge is detecting
            transitions early — the shift from Weak Bull to Weak Bear, or from Panic Crash
            to Recovery. These are the moments that make or break a portfolio.
          </p>
          <p className="text-ink-mute leading-relaxed text-base">
            Think about the investors who held through the entire 2022 drawdown and
            sold at the bottom in October — right before the recovery began. They got both
            transitions wrong: they stayed invested as conditions deteriorated, then panicked
            out just as conditions improved.
          </p>
          <p className="text-ink-mute leading-relaxed text-base">
            Our system watches for transition signals continuously. When multiple indicators
            start pointing in a new direction, the regime classification shifts — and the
            system's behavior changes with it. No emotion, no second-guessing, no waiting
            for confirmation from the financial news cycle.
          </p>
        </div>

        {/* Transition visual */}
        <div className="bg-paper-card border border-rule rounded p-6 my-8">
          <p className="text-xs text-ink-light uppercase tracking-wider font-medium mb-4">Example Regime Sequence: 2022-2023</p>
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="px-3 py-1.5 bg-positive/15 text-positive rounded font-medium">Strong Bull</span>
            <ArrowRight className="w-4 h-4 text-ink-light" />
            <span className="px-3 py-1.5 bg-positive/10 text-positive rounded font-medium">Weak Bull</span>
            <ArrowRight className="w-4 h-4 text-ink-light" />
            <span className="px-3 py-1.5 bg-negative/10 text-negative rounded font-medium">Weak Bear</span>
            <ArrowRight className="w-4 h-4 text-ink-light" />
            <span className="px-3 py-1.5 bg-negative/15 text-negative rounded font-medium">Panic Crash</span>
            <ArrowRight className="w-4 h-4 text-ink-light" />
            <span className="px-3 py-1.5 bg-claret/10 text-claret rounded font-medium">Recovery</span>
            <ArrowRight className="w-4 h-4 text-ink-light" />
            <span className="px-3 py-1.5 bg-positive/10 text-positive rounded font-medium">Weak Bull</span>
          </div>
          <p className="text-ink-light text-xs mt-4 m-0">
            Each transition triggered a change in system behavior — from fully deployed, to selective, to cash, and back again.
          </p>
        </div>

        <div className="prose prose-gray max-w-none">

          {/* Where Are We Now */}
          <h2 className="font-display text-2xl font-bold text-ink mt-12 mb-4 flex items-center gap-2" style={{ fontVariationSettings: '"opsz" 48' }}>
            <Activity className="w-6 h-6 text-claret flex-shrink-0" />
            Where Are We Now?
          </h2>
          <p className="text-ink-mute leading-relaxed text-base">
            The current market regime is updated daily on every subscriber's dashboard.
            You can see not just the current classification, but the probability distribution
            across all seven regimes — so you know when a transition might be approaching.
          </p>
          <p className="text-ink-mute leading-relaxed text-base">
            Our{' '}
            <Link to="/market-regime" className="text-claret hover:text-claret/80 underline underline-offset-2 transition-colors">
              Market Regime Dashboard
            </Link>
            {' '}shows the current regime, historical regime timeline, and forward-looking
            probability shifts — all derived from the same quantitative model that drives
            our trading signals.
          </p>
          <p className="text-ink-mute leading-relaxed text-base">
            Subscribers also receive weekly regime briefings and immediate alerts when a
            regime shift is detected. You'll never be caught off guard by a changing market.
          </p>
        </div>

        {/* CTA */}
        <div className="border border-rule rounded p-8 sm:p-10 my-12 text-center">
          <h2 className="font-display text-2xl sm:text-3xl font-bold text-ink mb-3" style={{ fontVariationSettings: '"opsz" 48' }}>
            See the Regime Intelligence in Action
          </h2>
          <p className="text-ink-mute mb-6 max-w-lg mx-auto">
            Stop guessing what the market is doing. Let our 7-regime model tell you —
            and automatically adjust your exposure to match.
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
              <span className="block text-ink-light text-sm mt-1">A practical guide to trading different market regimes as a beginner.</span>
            </Link>
            <Link to="/blog/market-crash" className="block p-4 bg-paper-card rounded border border-rule hover:border-rule-dark transition-colors">
              <span className="text-ink font-medium">What to Do When the Market Crashes</span>
              <span className="block text-ink-light text-sm mt-1">What panic crash and weak bear regimes mean for your portfolio.</span>
            </Link>
          </div>
        </div>

        {/* Disclaimer */}
        <p className="text-xs text-ink-light leading-relaxed">
          All performance figures are from walk-forward simulations using historical market data.
          Market regime classifications are derived from quantitative models and may not predict future market conditions.
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
