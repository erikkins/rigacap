import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, ArrowRight, Shield, TrendingUp, Target, Brain, AlertTriangle, CheckCircle, XCircle } from 'lucide-react';
import MarketMeasuredSignup from './components/MarketMeasuredSignup';

export default function BlogTrailingStopsPage() {
  useEffect(() => { document.title = 'How Trailing Stops Protect Your Portfolio | RigaCap'; }, []);
    const meta = document.querySelector('meta[name="description"]');
    if (meta) meta.setAttribute('content', 'Learn how trailing stop losses let your winners run while automatically protecting gains. See how to find the right trailing stop percentage.');

    // OG tags for social sharing
    document.querySelector('meta[property="og:title"]')?.setAttribute('content', 'How Trailing Stops Protect Your Portfolio | RigaCap');
    document.querySelector('meta[property="og:description"]')?.setAttribute('content', 'Learn how trailing stop losses let your winners run while automatically protecting gains. See how to find the right trailing stop percentage.');
    document.querySelector('meta[property="og:url"]')?.setAttribute('content', 'https://rigacap.com/blog/trailing-stops');
    document.querySelector('meta[name="twitter:title"]')?.setAttribute('content', 'How Trailing Stops Protect Your Portfolio | RigaCap');
    document.querySelector('meta[name="twitter:description"]')?.setAttribute('content', 'Learn how trailing stop losses let your winners run while automatically protecting gains. See how to find the right trailing stop percentage.');
    // JSON-LD Article schema
    const existingSchema = document.querySelector('script[type="application/ld+json"]');
    if (existingSchema) existingSchema.remove();
    const schema = document.createElement('script');
    schema.type = 'application/ld+json';
    schema.text = JSON.stringify({
      "@context": "https://schema.org",
      "@type": "Article",
      "headline": "How Trailing Stops Protect Your Portfolio",
      "description": "Learn how trailing stop losses let your winners run while automatically protecting gains. See how to find the right trailing stop percentage.",
      "author": {"@type": "Organization", "name": "RigaCap"},
      "publisher": {"@type": "Organization", "name": "RigaCap", "url": "https://rigacap.com"},
      "url": "https://rigacap.com/blog/trailing-stops",
      "articleSection": "Education",
    });
    document.head.appendChild(schema);
    return () => { if (schema.parentNode) schema.remove(); };

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
          <p className="text-sm font-medium uppercase tracking-wider text-claret mb-6">Risk Management</p>
          <h1 className="font-display text-4xl sm:text-5xl font-bold text-ink tracking-tight mb-4" style={{ fontVariationSettings: '"opsz" 48' }}>
            How Trailing Stops Protect Your Portfolio
          </h1>
          <p className="text-lg text-ink-mute max-w-2xl mx-auto">
            Without limiting your upside.
            <br className="hidden sm:block" />
            The one rule that lets you ride winners and cut losers automatically.
          </p>
        </div>
      </section>

      {/* Article Body */}
      <article className="max-w-3xl mx-auto px-4 sm:px-6 py-12 sm:py-16">
        <div className="prose prose-lg max-w-none">

          {/* Section 1: What is a trailing stop */}
          <h2 className="font-display text-2xl font-bold text-ink mt-0 mb-4 flex items-center gap-2" style={{ fontVariationSettings: '"opsz" 48' }}>
            <Target className="w-6 h-6 text-positive flex-shrink-0" />
            What Is a Trailing Stop?
          </h2>
          <p className="text-ink-mute leading-relaxed text-base">
            A trailing stop is an automatic sell rule that follows a stock upward but never
            follows it back down. Think of it as a safety net that rises with the stock price.
            If you buy a stock at $100 and set a trailing stop, you'll sell if the stock
            drops below your threshold. Simple enough.
          </p>
          <p className="text-ink-mute leading-relaxed text-base">
            But here's where it gets interesting. If that stock climbs to $150, your trailing
            stop climbs with it. If the stock then pulls back far enough to hit your stop,
            you sell automatically. You locked in a significant gain instead of
            watching it evaporate.
          </p>
          <p className="text-ink-mute leading-relaxed text-base">
            The key concept is the <strong className="text-ink">high water mark</strong> — the
            highest price the stock has reached since you bought it. Your trailing stop is
            always calculated as a percentage below that peak. The stop only moves up, never
            down.
          </p>
        </div>

        {/* Section 2: Fixed vs Trailing */}
        <div className="prose prose-lg max-w-none">
          <h2 className="font-display text-2xl font-bold text-ink mt-12 mb-4 flex items-center gap-2" style={{ fontVariationSettings: '"opsz" 48' }}>
            <TrendingUp className="w-6 h-6 text-claret flex-shrink-0" />
            Fixed Stop Loss vs. Trailing Stop
          </h2>
          <p className="text-ink-mute leading-relaxed text-base">
            Traditional stop losses are fixed at a price below your entry. Buy at $100, set a
            stop at $92, and you'll sell if it drops 8%. That protects your downside — but it
            also caps your thinking. Once the stock reaches $150, your stop is still sitting
            at $92. If the stock reverses and falls back to $95, you'll ride through the entire
            decline and sell near the bottom.
          </p>
          <p className="text-ink-mute leading-relaxed text-base">
            The trailing stop solves this by moving the floor upward as the stock gains.
            It's the difference between protecting your initial capital and protecting
            your profits.
          </p>
        </div>

        {/* Comparison table */}
        <div className="bg-paper-card border border-rule rounded p-6 my-8 overflow-x-auto">
          <p className="text-xs text-ink-light uppercase tracking-wider font-medium mb-4">Comparison</p>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left border-b border-rule">
                <th className="pb-3 text-ink-mute font-medium">Feature</th>
                <th className="pb-3 text-ink-mute font-medium">Fixed Stop Loss</th>
                <th className="pb-3 text-ink-mute font-medium">Trailing Stop</th>
              </tr>
            </thead>
            <tbody className="text-ink-mute">
              <tr className="border-b border-rule/50">
                <td className="py-3 text-ink-mute">Protects against</td>
                <td className="py-3">Initial loss</td>
                <td className="py-3 text-positive">Initial loss + profit giveback</td>
              </tr>
              <tr className="border-b border-rule/50">
                <td className="py-3 text-ink-mute">Moves with price?</td>
                <td className="py-3">
                  <XCircle className="w-4 h-4 text-negative inline" /> No
                </td>
                <td className="py-3">
                  <CheckCircle className="w-4 h-4 text-positive inline" /> Yes, upward only
                </td>
              </tr>
              <tr className="border-b border-rule/50">
                <td className="py-3 text-ink-mute">Lets winners run?</td>
                <td className="py-3">
                  <XCircle className="w-4 h-4 text-negative inline" /> Needs manual target
                </td>
                <td className="py-3">
                  <CheckCircle className="w-4 h-4 text-positive inline" /> Unlimited upside
                </td>
              </tr>
              <tr>
                <td className="py-3 text-ink-mute">Locks in gains?</td>
                <td className="py-3">
                  <XCircle className="w-4 h-4 text-negative inline" /> Never
                </td>
                <td className="py-3">
                  <CheckCircle className="w-4 h-4 text-positive inline" /> Automatically
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* Section 3: How RigaCap uses 12% */}
        <div className="prose prose-lg max-w-none">
          <h2 className="font-display text-2xl font-bold text-ink mt-12 mb-4 flex items-center gap-2" style={{ fontVariationSettings: '"opsz" 48' }}>
            <Shield className="w-6 h-6 text-positive flex-shrink-0" />
            How RigaCap Uses Trailing Stops
          </h2>
          <p className="text-ink-mute leading-relaxed text-base">
            Every position in our portfolio is protected by a carefully tested trailing stop
            calculated from the high water mark. This isn't a number we picked out of thin
            air — it's the result of extensive backtesting across thousands of trades and
            multiple market conditions.
          </p>
          <p className="text-ink-mute leading-relaxed text-base">
            When our system enters a position, it immediately begins tracking the stock's
            highest closing price. Each day, it recalculates the stop level as a fixed
            percentage below that peak. If the stock closes below the stop level, the position is flagged
            for exit. No debates, no hoping it will bounce back, no checking the news to
            see if the drop is "justified." The rule is the rule.
          </p>
        </div>

        {/* Section 4: Real Example */}
        <div className="prose prose-lg max-w-none">
          <h2 className="font-display text-2xl font-bold text-ink mt-12 mb-4" style={{ fontVariationSettings: '"opsz" 48' }}>
            A Real-World Example
          </h2>
          <p className="text-ink-mute leading-relaxed text-base">
            Imagine our system buys a stock at $100. Here's how the trailing stop protects
            the position as the stock moves:
          </p>
        </div>

        {/* Example walkthrough card */}
        <div className="bg-paper-card border border-rule rounded p-6 my-8">
          <p className="text-xs text-ink-light uppercase tracking-wider font-medium mb-5">Trailing Stop in Action</p>
          <div className="space-y-4">
            <div className="flex items-start gap-4">
              <div className="w-8 h-8 rounded-full bg-claret/10 flex items-center justify-center flex-shrink-0 text-claret text-sm font-bold">1</div>
              <div>
                <p className="text-ink font-medium m-0">Entry at $100</p>
                <p className="text-ink-mute text-sm m-0">Stop level set at our trailing stop percentage below entry price.</p>
              </div>
            </div>
            <div className="flex items-start gap-4">
              <div className="w-8 h-8 rounded-full bg-claret/10 flex items-center justify-center flex-shrink-0 text-claret text-sm font-bold">2</div>
              <div>
                <p className="text-ink font-medium m-0">Stock climbs to $120</p>
                <p className="text-ink-mute text-sm m-0">New high water mark. Stop rises with it. You're now guaranteed a profit if the stop triggers.</p>
              </div>
            </div>
            <div className="flex items-start gap-4">
              <div className="w-8 h-8 rounded-full bg-positive/10 flex items-center justify-center flex-shrink-0 text-positive text-sm font-bold">3</div>
              <div>
                <p className="text-ink font-medium m-0">Stock reaches $150</p>
                <p className="text-ink-mute text-sm m-0">New peak. Stop climbs with it. You've locked in a significant portion of the upside.</p>
              </div>
            </div>
            <div className="flex items-start gap-4">
              <div className="w-8 h-8 rounded-full bg-claret/10 flex items-center justify-center flex-shrink-0 text-claret text-sm font-bold">4</div>
              <div>
                <p className="text-ink font-medium m-0">Stock pulls back to $140</p>
                <p className="text-ink-mute text-sm m-0">Stop stays where it is (high water mark is still $150). No action taken — normal volatility.</p>
              </div>
            </div>
            <div className="flex items-start gap-4">
              <div className="w-8 h-8 rounded-full bg-negative/10 flex items-center justify-center flex-shrink-0 text-negative text-sm font-bold">5</div>
              <div>
                <p className="text-ink font-medium m-0">Stock drops to the stop level — stop triggers</p>
                <p className="text-ink-mute text-sm m-0">Exit signal fires. You captured a significant gain instead of riding it back down to $100 or lower.</p>
              </div>
            </div>
          </div>
          <div className="mt-6 pt-4 border-t border-rule">
            <p className="text-positive text-sm font-medium m-0">
              Result: a meaningful gain captured. Without the trailing stop, a round-trip back to $100 means +$0.
            </p>
          </div>
        </div>

        {/* Section 5: Why percentage matters */}
        <div className="prose prose-lg max-w-none">
          <h2 className="font-display text-2xl font-bold text-ink mt-12 mb-4 flex items-center gap-2" style={{ fontVariationSettings: '"opsz" 48' }}>
            <AlertTriangle className="w-6 h-6 text-claret flex-shrink-0" />
            Why the Percentage Matters
          </h2>
          <p className="text-ink-mute leading-relaxed text-base">
            Setting the right trailing stop percentage is a balancing act. Too tight, and
            normal day-to-day price swings will knock you out of perfectly good positions.
            Too loose, and you'll give back too much profit before the exit triggers. Both
            extremes cost you money.
          </p>
          <p className="text-ink-mute leading-relaxed text-base">
            We tested a wide range of trailing stop percentages across thousands of trades
            and multiple market environments. Here's what we found:
          </p>
        </div>

        {/* Percentage comparison card */}
        <div className="bg-paper-card border border-rule rounded p-6 my-8">
          <p className="text-xs text-ink-light uppercase tracking-wider font-medium mb-4">Trailing Stop Percentage Trade-Offs</p>
          <div className="space-y-4">
            <div className="flex items-start gap-4 p-4 bg-negative/10 border border-negative/20 rounded-lg">
              <div className="flex-shrink-0">
                <span className="text-negative font-bold text-lg">Too Tight</span>
              </div>
              <div>
                <p className="text-ink font-medium m-0">Under 10%</p>
                <p className="text-ink-mute text-sm m-0">
                  Stopped out by normal volatility. Many winning trades get cut short — a stock
                  drops on a bad day, you sell, and it recovers the next week without you.
                  High trade frequency, high friction, lower returns.
                </p>
              </div>
            </div>
            <div className="flex items-start gap-4 p-4 bg-positive/10 border border-positive/20 rounded-lg">
              <div className="flex-shrink-0">
                <span className="text-positive font-bold text-lg">Our Setting</span>
              </div>
              <div>
                <p className="text-ink font-medium m-0">The Sweet Spot</p>
                <p className="text-ink-mute text-sm m-0">
                  Wide enough to absorb routine pullbacks without triggering. Tight enough to
                  protect meaningful gains. Tested best across bull markets, corrections, and
                  volatile recovery periods. This is what RigaCap uses.
                </p>
              </div>
            </div>
            <div className="flex items-start gap-4 p-4 bg-claret/10 border border-claret/20 rounded-lg">
              <div className="flex-shrink-0">
                <span className="text-claret font-bold text-lg">Too Loose</span>
              </div>
              <div>
                <p className="text-ink font-medium m-0">Over 15%</p>
                <p className="text-ink-mute text-sm m-0">
                  You keep positions through deeper pullbacks — which sounds good until a
                  pullback turns into a real decline. You give back too much from every peak before
                  the stop kicks in, eating into hard-won profits.
                </p>
              </div>
            </div>
          </div>
        </div>

        <div className="prose prose-lg max-w-none">
          <p className="text-ink-mute leading-relaxed text-base">
            At our chosen percentage, the trailing stop is loose enough that a stock's normal
            daily fluctuations won't trigger it. Most healthy stocks pull back several percent
            regularly during uptrends. Our threshold lets those moves happen naturally while
            still catching genuine reversals before they become devastating losses.
          </p>
        </div>

        {/* Section 6: Psychological benefit */}
        <div className="prose prose-lg max-w-none">
          <h2 className="font-display text-2xl font-bold text-ink mt-12 mb-4 flex items-center gap-2" style={{ fontVariationSettings: '"opsz" 48' }}>
            <Brain className="w-6 h-6 text-claret flex-shrink-0" />
            The Psychological Edge
          </h2>
          <p className="text-ink-mute leading-relaxed text-base">
            The hardest decision in trading isn't when to buy — it's when to sell. Every
            investor has been there: a stock is falling, and you're paralyzed. Sell now and
            lock in a loss? Hold on and hope it recovers? The emotional weight of that
            decision leads to terrible outcomes. People hold losers too long (hoping for a
            comeback) and sell winners too early (afraid of giving back gains).
          </p>
          <p className="text-ink-mute leading-relaxed text-base">
            A trailing stop removes that emotional burden entirely. The sell decision is made
            in advance, governed by a rule you set when you were thinking clearly — not in
            the heat of a market selloff. You don't have to watch the screen, check the news,
            or ask yourself whether this dip is "the one." The system handles it.
          </p>
          <p className="text-ink-mute leading-relaxed text-base">
            This isn't just a convenience — it's a performance advantage. Research consistently
            shows that emotional decision-making is the single biggest drag on individual
            investor returns. By automating the sell decision, you remove the most dangerous
            variable: yourself.
          </p>
        </div>

        {/* Highlight box */}
        <div className="bg-paper-deep border border-rule rounded p-6 my-8">
          <p className="text-ink font-semibold text-lg m-0 mb-2">
            The best traders aren't fearless. They've just removed emotion from the equation.
          </p>
          <p className="text-ink-mute m-0 text-sm">
            A trailing stop means you'll never lie awake wondering whether to sell. The plan
            is already in place. If the stock keeps rising, you keep holding. If it reverses,
            you exit with a defined portion of your gains intact. Either outcome is acceptable
            because you decided the rules in advance.
          </p>
        </div>

        {/* CTA */}
        <div className="bg-paper-card border border-rule rounded p-8 sm:p-10 my-12 text-center">
          <h2 className="font-display text-2xl sm:text-3xl font-bold text-ink mb-3" style={{ fontVariationSettings: '"opsz" 48' }}>
            See Our Trailing Stops in Action
          </h2>
          <p className="text-ink-mute mb-6 max-w-lg mx-auto">
            Every trade in our walk-forward track record was protected by a trailing stop.
            See the entries, exits, and exact returns — no hypotheticals.
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
              to="/app"
              className="inline-flex items-center justify-center gap-2 bg-paper-deep hover:bg-paper-card text-ink font-medium px-8 py-3 rounded transition-colors text-base"
            >
              Start Free Trial
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
            <Link to="/blog/momentum-trading" className="block p-4 bg-paper-card rounded border border-rule hover:border-rule-dark transition-colors">
              <span className="text-ink font-medium">Momentum Trading Explained</span>
              <span className="block text-ink-light text-sm mt-1">How momentum ranking and breakout timing work together to find winning trades.</span>
            </Link>
            <Link to="/blog/market-crash" className="block p-4 bg-paper-card rounded border border-rule hover:border-rule-dark transition-colors">
              <span className="text-ink font-medium">What to Do When the Market Crashes</span>
              <span className="block text-ink-light text-sm mt-1">How regime detection and automatic exits protect your portfolio during downturns.</span>
            </Link>
            <Link to="/blog/walk-forward-results" className="block p-4 bg-paper-card rounded border border-rule hover:border-rule-dark transition-colors">
              <span className="text-ink font-medium">Inside Our 5-Year Walk-Forward</span>
              <span className="block text-ink-light text-sm mt-1">The full breakdown of our walk-forward simulation across 138 rebalancing periods.</span>
            </Link>
          </div>
        </div>

        {/* Disclaimer */}
        <p className="text-xs text-ink-light leading-relaxed">
          This is educational content, not investment advice. All performance figures are
          from walk-forward simulations using historical market data. Past performance does
          not guarantee future results. Trailing stops do not guarantee execution at the
          exact stop price — in fast-moving markets, actual exit prices may differ.
          RigaCap provides trading signals only —
          execute trades through your own brokerage account. See our{' '}
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
