import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, Zap, TrendingUp, DollarSign, BarChart3, ArrowRight, Target, Activity } from 'lucide-react';
import MarketMeasuredSignup from './components/MarketMeasuredSignup';

export default function BlogWeCalledItTGTXPage() {
  useEffect(() => { document.title = 'We Called It: TGTX +46% | RigaCap';
    const meta = document.querySelector('meta[name="description"]');
    if (meta) meta.setAttribute('content', 'How RigaCap spotted TG Therapeutics +46% breakout in just 14 days. A $22 biotech stock nobody was watching.');

    // OG tags for social sharing
    document.querySelector('meta[property="og:title"]')?.setAttribute('content', 'We Called It: TG Therapeutics +46% in 14 Days | RigaCap');
    document.querySelector('meta[property="og:description"]')?.setAttribute('content', 'How RigaCap spotted TG Therapeutics +46% breakout in just 14 days. A $22 biotech stock nobody was watching.');
    document.querySelector('meta[property="og:url"]')?.setAttribute('content', 'https://rigacap.com/blog/we-called-it-tgtx');
    document.querySelector('meta[name="twitter:title"]')?.setAttribute('content', 'We Called It: TG Therapeutics +46% in 14 Days | RigaCap');
    document.querySelector('meta[name="twitter:description"]')?.setAttribute('content', 'How RigaCap spotted TG Therapeutics +46% breakout in just 14 days. A $22 biotech stock nobody was watching.');
    // JSON-LD Article schema
    const existingSchema = document.querySelector('script[type="application/ld+json"]');
    if (existingSchema) existingSchema.remove();
    const schema = document.createElement('script');
    schema.type = 'application/ld+json';
    schema.text = JSON.stringify({
      "@context": "https://schema.org",
      "@type": "Article",
      "headline": "We Called It: TG Therapeutics +46% in 14 Days",
      "description": "How RigaCap spotted TG Therapeutics +46% breakout in just 14 days. A $22 biotech stock nobody was watching.",
      "author": {"@type": "Organization", "name": "RigaCap"},
      "publisher": {"@type": "Organization", "name": "RigaCap", "url": "https://rigacap.com"},
      "url": "https://rigacap.com/blog/we-called-it-tgtx",
      "articleSection": "Case Study",
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
          <p className="text-sm font-medium uppercase tracking-wider text-claret mb-6">Walk-Forward Trade</p>
          <h1 className="font-display text-3xl sm:text-5xl font-bold text-ink tracking-tight mb-4" style={{ fontVariationSettings: '"opsz" 48' }}>
            We Called It: How Our System Caught TG Therapeutics' +46% Breakout
          </h1>
          <p className="text-lg text-ink-mute max-w-2xl mx-auto">
            A $22 biotech stock. Two weeks. +46.3% return.
            <br className="hidden sm:block" />
            No FDA analysis required — just the math.
          </p>
        </div>
      </section>

      {/* Trade Card */}
      <section className="max-w-3xl mx-auto px-4 sm:px-6 -mt-8 relative z-10">
        <div className="bg-paper-card border border-claret/30 rounded p-6 sm:p-8">
          <div className="flex items-center gap-2 mb-6">
            <DollarSign className="w-5 h-5 text-claret" />
            <span className="text-sm font-semibold text-claret uppercase tracking-wider">TGTX Trade Summary</span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 sm:gap-6">
            <div className="text-center">
              <div className="text-xs text-ink-light uppercase tracking-wider mb-1">Entry</div>
              <div className="text-xl sm:text-2xl font-bold text-ink">$22.63</div>
              <div className="text-xs text-ink-light mt-0.5">Apr 24, 2023</div>
            </div>
            <div className="text-center">
              <div className="text-xs text-ink-light uppercase tracking-wider mb-1">Exit</div>
              <div className="text-xl sm:text-2xl font-bold text-ink">$33.10</div>
              <div className="text-xs text-ink-light mt-0.5">May 8, 2023</div>
            </div>
            <div className="text-center">
              <div className="text-xs text-ink-light uppercase tracking-wider mb-1">Return</div>
              <div className="text-xl sm:text-2xl font-bold text-positive">+46.3%</div>
              <div className="text-xs text-ink-light mt-0.5">14 days</div>
            </div>
            <div className="text-center">
              <div className="text-xs text-ink-light uppercase tracking-wider mb-1">Exit Type</div>
              <div className="text-xl sm:text-2xl font-bold text-claret">Trailing</div>
              <div className="text-xs text-ink-light mt-0.5">Stop triggered</div>
            </div>
          </div>
        </div>
      </section>

      {/* Article Body */}
      <article className="max-w-3xl mx-auto px-4 sm:px-6 py-12 sm:py-16">
        <div className="space-y-4 text-ink-mute text-[1.05rem] leading-[1.75]">

          {/* The Setup */}
          <h2 className="font-display text-2xl font-bold text-ink mt-0 mb-4" style={{ fontVariationSettings: '"opsz" 48' }}>
            The Setup: Spring 2023
          </h2>
          <p className="text-ink-mute leading-relaxed text-base">
            Spring 2023. The biotech sector was crawling out of the wreckage of 2022.
            The XBI biotech index was still down over 50% from its 2021 highs. Most
            investors were still scared of small-cap biotech — burned by the post-COVID
            crash that wiped out speculative names across the sector.
          </p>
          <p className="text-ink-mute leading-relaxed text-base">
            Our system wasn't scared. It doesn't read headlines, follow analyst sentiment,
            or care about what happened last year. It reads data. And the data on TG
            Therapeutics (TGTX) was flashing.
          </p>

          {/* Why TGTX Triggered */}
          <h2 className="font-display text-2xl font-bold text-ink mt-12 mb-4 flex items-center gap-2" style={{ fontVariationSettings: '"opsz" 48' }}>
            <Activity className="w-6 h-6 text-claret flex-shrink-0" />
            Why TGTX Triggered
          </h2>
          <p className="text-ink-mute leading-relaxed text-base">
            TGTX wasn't on CNBC. It wasn't trending on Reddit. It was a $22 stock with
            a $2 billion market cap — a mid-cap biotech that most retail investors had
            never heard of. But three independent signals were converging.
          </p>
        </div>

        {/* The Math Card */}
        <div className="bg-paper-card border border-rule rounded overflow-hidden my-8">
          <div className="px-6 py-4 border-b border-rule flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-claret" />
            <span className="text-sm font-semibold text-ink">The Math: 3 Filters That Triggered</span>
          </div>
          <div className="grid gap-0 divide-y divide-rule">
            <div className="px-6 py-5 flex items-start gap-4">
              <div className="w-10 h-10 rounded-lg bg-claret/10 flex items-center justify-center flex-shrink-0">
                <span className="text-claret font-bold">1</span>
              </div>
              <div>
                <h3 className="text-ink font-semibold mb-1">Breakout Detection Confirmed</h3>
                <p className="text-ink-mute text-sm m-0">
                  Price broke decisively above its long-term support level — our proprietary
                  breakout indicator catches these moves before they become obvious. TGTX
                  was showing sustained strength above its baseline, not a
                  one-day spike.
                </p>
              </div>
            </div>
            <div className="px-6 py-5 flex items-start gap-4">
              <div className="w-10 h-10 rounded-lg bg-claret/10 flex items-center justify-center flex-shrink-0">
                <span className="text-claret font-bold">2</span>
              </div>
              <div>
                <h3 className="text-ink font-semibold mb-1">Top-Tier Momentum Ranking</h3>
                <p className="text-ink-mute text-sm m-0">
                  The composite momentum score — combining short-term (10-day) and
                  long-term (60-day) momentum with volatility adjustment — placed TGTX
                  in the top tier of the entire universe. It wasn't just going up. It
                  was going up with conviction.
                </p>
              </div>
            </div>
            <div className="px-6 py-5 flex items-start gap-4">
              <div className="w-10 h-10 rounded-lg bg-positive/10 flex items-center justify-center flex-shrink-0">
                <span className="text-positive font-bold">3</span>
              </div>
              <div>
                <h3 className="text-ink font-semibold mb-1">Volume Confirmation</h3>
                <p className="text-ink-mute text-sm m-0">
                  Trading volume was spiking well above average — the kind of accumulation
                  pattern that typically signals institutional buying. Smart money was
                  moving in before the crowd arrived.
                </p>
              </div>
            </div>
          </div>
        </div>

        <div className="space-y-4 text-ink-mute text-[1.05rem] leading-[1.75]">

          {/* The Entry */}
          <h2 className="font-display text-2xl font-bold text-ink mt-12 mb-4 flex items-center gap-2" style={{ fontVariationSettings: '"opsz" 48' }}>
            <Target className="w-6 h-6 text-positive flex-shrink-0" />
            The Entry: $22.63
          </h2>
          <p className="text-ink-mute leading-relaxed text-base">
            On April 24, 2023, the system flagged TGTX as a buy. All three ensemble
            filters aligned. A $22 stock that most of the market was ignoring.
            No analyst upgrade drove it. No social media hype. Just the math saying
            this stock was breaking out with genuine institutional backing.
          </p>

          {/* The Ride */}
          <h2 className="font-display text-2xl font-bold text-ink mt-12 mb-4 flex items-center gap-2" style={{ fontVariationSettings: '"opsz" 48' }}>
            <TrendingUp className="w-6 h-6 text-positive flex-shrink-0" />
            The Ride: +46% in Two Weeks
          </h2>
          <p className="text-ink-mute leading-relaxed text-base">
            Over the next two weeks, TGTX surged. The FDA approval momentum for
            Briumvi — TG Therapeutics' treatment for multiple sclerosis — was driving
            institutional interest. Revenue expectations were being revised upward.
            The stock climbed from $22 to over $33.
          </p>

          {/* Highlight Box */}
          <div className="bg-paper-deep border border-rule rounded p-6 my-8">
            <p className="text-ink font-semibold text-lg m-0 mb-2">
              The system didn't know about Briumvi. It didn't know about the FDA.
            </p>
            <p className="text-ink-mute m-0">
              It doesn't read clinical trial results or understand drug pipelines.
              It saw a stock breaking out with momentum, volume, and timing alignment —
              and that was enough. The fundamentals confirmed what the price action
              was already saying.
            </p>
          </div>

          {/* The Exit */}
          <h2 className="font-display text-2xl font-bold text-ink mt-12 mb-4" style={{ fontVariationSettings: '"opsz" 48' }}>
            The Exit: $33.10
          </h2>
          <p className="text-ink-mute leading-relaxed text-base">
            On May 8, after TGTX pulled back from its highs, the trailing stop triggered
            at $33.10. The system locked in +46.3% in 14 days and moved on. No second
            guessing. No "maybe it'll bounce back." No holding through the inevitable
            post-run consolidation hoping for more.
          </p>
          <p className="text-ink-mute leading-relaxed text-base">
            The trailing stop is designed to do exactly this: let winners run while they're
            running, then protect gains the moment momentum fades. It turned a volatile
            biotech trade into a disciplined, profitable exit.
          </p>

          {/* The Lesson */}
          <h2 className="font-display text-2xl font-bold text-ink mt-12 mb-4" style={{ fontVariationSettings: '"opsz" 48' }}>
            The Lesson: Data Over Speculation
          </h2>
          <p className="text-ink-mute leading-relaxed text-base">
            You don't need to follow biotech news to catch biotech breakouts.
            You don't need to understand FDA pipelines, read clinical trial data,
            or guess which drugs will get approved. A systematic momentum approach
            catches these moves based on price action — because by the time a stock
            is breaking out with volume, the people who do understand the fundamentals
            have already placed their bets.
          </p>
          <p className="text-ink-mute leading-relaxed text-base">
            The ensemble doesn't know what TG Therapeutics does. It doesn't know what
            Briumvi treats. It knows the stock was breaking out with conviction across
            multiple independent signals — and that was the only information it needed.
          </p>
          <p className="text-ink-mute leading-relaxed text-base">
            This is the advantage of systematic trading: you capture moves driven by
            catalysts you'd never have known about, in sectors you'd never have researched,
            at entries you'd never have had the confidence to take on your own.
          </p>
        </div>

        {/* CTA */}
        <div className="bg-paper-card border border-rule rounded p-8 sm:p-10 my-12 text-center">
          <h2 className="font-display text-2xl sm:text-3xl font-bold text-ink mb-3" style={{ fontVariationSettings: '"opsz" 48' }}>
            Catch the Next Breakout
          </h2>
          <p className="text-ink-mute mb-6 max-w-lg mx-auto">
            TGTX was one trade out of hundreds the system has flagged.
            The next breakout is already forming — the question is whether
            you'll see the signal.
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
              View Full Track Record
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
            <Link to="/blog/we-called-it-mrna" className="block p-4 bg-paper-card rounded border border-rule hover:border-rule-dark transition-colors">
              <span className="text-ink font-medium">We Called It: Moderna +51%</span>
              <span className="block text-ink-light text-sm mt-1">How our system caught Moderna summer 2021 breakout and locked in gains.</span>
            </Link>
            <Link to="/blog/momentum-trading" className="block p-4 bg-paper-card rounded border border-rule hover:border-rule-dark transition-colors">
              <span className="text-ink font-medium">Momentum Trading Explained</span>
              <span className="block text-ink-light text-sm mt-1">The momentum ranking system behind trades like TGTX and MRNA.</span>
            </Link>
            <Link to="/blog/walk-forward-results" className="block p-4 bg-paper-card rounded border border-rule hover:border-rule-dark transition-colors">
              <span className="text-ink font-medium">Inside Our 5-Year Walk-Forward</span>
              <span className="block text-ink-light text-sm mt-1">The full walk-forward simulation that produced these real trade signals.</span>
            </Link>
          </div>
        </div>

        {/* Disclaimer */}
        <p className="text-xs text-ink-light leading-relaxed">
          All performance figures are from walk-forward simulations using historical market data.
          The TGTX trade described is a real signal generated by the system during walk-forward testing,
          not a cherry-picked example. Past performance does not guarantee future results. RigaCap
          provides trading signals only — execute trades through your own brokerage account. See our{' '}
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
