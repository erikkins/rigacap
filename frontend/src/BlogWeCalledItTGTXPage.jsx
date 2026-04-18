import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, Zap, TrendingUp, DollarSign, BarChart3, ArrowRight, Target, Activity } from 'lucide-react';
import MarketMeasuredSignup from './components/MarketMeasuredSignup';

export default function BlogWeCalledItTGTXPage() {
  useEffect(() => { document.title = 'We Called It: TGTX +46% | RigaCap'; }, []);
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
      <section className="relative overflow-hidden bg-gradient-to-br from-purple-900/80 via-gray-900 to-violet-900/60">
        <div className="absolute inset-0 overflow-hidden">
          <div className="absolute -top-40 -right-40 w-80 h-80 bg-purple-500/10 rounded-full blur-3xl"></div>
          <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-violet-500/10 rounded-full blur-3xl"></div>
        </div>
        <div className="relative max-w-3xl mx-auto px-4 sm:px-6 py-16 sm:py-24 text-center">
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-white/10 backdrop-blur-sm rounded-full text-sm font-medium mb-6">
            <Zap className="w-4 h-4 text-amber-300" />
            <span className="text-white/90">Walk-Forward Trade</span>
          </div>
          <h1 className="text-3xl sm:text-5xl font-bold text-white tracking-tight mb-4">
            We Called It: How Our System Caught TG Therapeutics' +46% Breakout
          </h1>
          <p className="text-lg text-purple-200/80 max-w-2xl mx-auto">
            A $22 biotech stock. Two weeks. +46.3% return.
            <br className="hidden sm:block" />
            No FDA analysis required — just the math.
          </p>
        </div>
      </section>

      {/* Trade Card */}
      <section className="max-w-3xl mx-auto px-4 sm:px-6 -mt-8 relative z-10">
        <div className="bg-gray-900 border border-purple-500/30 rounded-xl p-6 sm:p-8">
          <div className="flex items-center gap-2 mb-6">
            <DollarSign className="w-5 h-5 text-amber-400" />
            <span className="text-sm font-semibold text-amber-400 uppercase tracking-wider">TGTX Trade Summary</span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 sm:gap-6">
            <div className="text-center">
              <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">Entry</div>
              <div className="text-xl sm:text-2xl font-bold text-white">$22.63</div>
              <div className="text-xs text-gray-500 mt-0.5">Apr 24, 2023</div>
            </div>
            <div className="text-center">
              <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">Exit</div>
              <div className="text-xl sm:text-2xl font-bold text-white">$33.10</div>
              <div className="text-xs text-gray-500 mt-0.5">May 8, 2023</div>
            </div>
            <div className="text-center">
              <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">Return</div>
              <div className="text-xl sm:text-2xl font-bold text-emerald-400">+46.3%</div>
              <div className="text-xs text-gray-500 mt-0.5">14 days</div>
            </div>
            <div className="text-center">
              <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">Exit Type</div>
              <div className="text-xl sm:text-2xl font-bold text-amber-400">Trailing</div>
              <div className="text-xs text-gray-500 mt-0.5">Stop triggered</div>
            </div>
          </div>
        </div>
      </section>

      {/* Article Body */}
      <article className="max-w-3xl mx-auto px-4 sm:px-6 py-12 sm:py-16">
        <div className="prose prose-invert prose-gray max-w-none">

          {/* The Setup */}
          <h2 className="text-2xl font-bold text-white mt-0 mb-4">
            The Setup: Spring 2023
          </h2>
          <p className="text-gray-300 leading-relaxed text-base">
            Spring 2023. The biotech sector was crawling out of the wreckage of 2022.
            The XBI biotech index was still down over 50% from its 2021 highs. Most
            investors were still scared of small-cap biotech — burned by the post-COVID
            crash that wiped out speculative names across the sector.
          </p>
          <p className="text-gray-300 leading-relaxed text-base">
            Our system wasn't scared. It doesn't read headlines, follow analyst sentiment,
            or care about what happened last year. It reads data. And the data on TG
            Therapeutics (TGTX) was flashing.
          </p>

          {/* Why TGTX Triggered */}
          <h2 className="text-2xl font-bold text-white mt-12 mb-4 flex items-center gap-2">
            <Activity className="w-6 h-6 text-purple-400 flex-shrink-0" />
            Why TGTX Triggered
          </h2>
          <p className="text-gray-300 leading-relaxed text-base">
            TGTX wasn't on CNBC. It wasn't trending on Reddit. It was a $22 stock with
            a $2 billion market cap — a mid-cap biotech that most retail investors had
            never heard of. But three independent signals were converging.
          </p>
        </div>

        {/* The Math Card */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden my-8">
          <div className="px-6 py-4 border-b border-gray-800 flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-blue-400" />
            <span className="text-sm font-semibold text-white">The Math: 3 Filters That Triggered</span>
          </div>
          <div className="grid gap-0 divide-y divide-gray-800">
            <div className="px-6 py-5 flex items-start gap-4">
              <div className="w-10 h-10 rounded-lg bg-purple-500/20 flex items-center justify-center flex-shrink-0">
                <span className="text-purple-400 font-bold">1</span>
              </div>
              <div>
                <h3 className="text-white font-semibold mb-1">Breakout Detection Confirmed</h3>
                <p className="text-gray-400 text-sm m-0">
                  Price broke decisively above its long-term support level — our proprietary
                  breakout indicator catches these moves before they become obvious. TGTX
                  was showing sustained strength above its baseline, not a
                  one-day spike.
                </p>
              </div>
            </div>
            <div className="px-6 py-5 flex items-start gap-4">
              <div className="w-10 h-10 rounded-lg bg-amber-500/20 flex items-center justify-center flex-shrink-0">
                <span className="text-amber-400 font-bold">2</span>
              </div>
              <div>
                <h3 className="text-white font-semibold mb-1">Top-Tier Momentum Ranking</h3>
                <p className="text-gray-400 text-sm m-0">
                  The composite momentum score — combining short-term (10-day) and
                  long-term (60-day) momentum with volatility adjustment — placed TGTX
                  in the top tier of the entire universe. It wasn't just going up. It
                  was going up with conviction.
                </p>
              </div>
            </div>
            <div className="px-6 py-5 flex items-start gap-4">
              <div className="w-10 h-10 rounded-lg bg-emerald-500/20 flex items-center justify-center flex-shrink-0">
                <span className="text-emerald-400 font-bold">3</span>
              </div>
              <div>
                <h3 className="text-white font-semibold mb-1">Volume Confirmation</h3>
                <p className="text-gray-400 text-sm m-0">
                  Trading volume was spiking well above average — the kind of accumulation
                  pattern that typically signals institutional buying. Smart money was
                  moving in before the crowd arrived.
                </p>
              </div>
            </div>
          </div>
        </div>

        <div className="prose prose-invert prose-gray max-w-none">

          {/* The Entry */}
          <h2 className="text-2xl font-bold text-white mt-12 mb-4 flex items-center gap-2">
            <Target className="w-6 h-6 text-emerald-400 flex-shrink-0" />
            The Entry: $22.63
          </h2>
          <p className="text-gray-300 leading-relaxed text-base">
            On April 24, 2023, the system flagged TGTX as a buy. All three ensemble
            filters aligned. A $22 stock that most of the market was ignoring.
            No analyst upgrade drove it. No social media hype. Just the math saying
            this stock was breaking out with genuine institutional backing.
          </p>

          {/* The Ride */}
          <h2 className="text-2xl font-bold text-white mt-12 mb-4 flex items-center gap-2">
            <TrendingUp className="w-6 h-6 text-emerald-400 flex-shrink-0" />
            The Ride: +46% in Two Weeks
          </h2>
          <p className="text-gray-300 leading-relaxed text-base">
            Over the next two weeks, TGTX surged. The FDA approval momentum for
            Briumvi — TG Therapeutics' treatment for multiple sclerosis — was driving
            institutional interest. Revenue expectations were being revised upward.
            The stock climbed from $22 to over $33.
          </p>

          {/* Highlight Box */}
          <div className="bg-purple-500/10 border border-purple-500/30 rounded-xl p-6 my-8">
            <p className="text-purple-200 font-semibold text-lg m-0 mb-2">
              The system didn't know about Briumvi. It didn't know about the FDA.
            </p>
            <p className="text-purple-200/80 m-0">
              It doesn't read clinical trial results or understand drug pipelines.
              It saw a stock breaking out with momentum, volume, and timing alignment —
              and that was enough. The fundamentals confirmed what the price action
              was already saying.
            </p>
          </div>

          {/* The Exit */}
          <h2 className="text-2xl font-bold text-white mt-12 mb-4">
            The Exit: $33.10
          </h2>
          <p className="text-gray-300 leading-relaxed text-base">
            On May 8, after TGTX pulled back from its highs, the trailing stop triggered
            at $33.10. The system locked in +46.3% in 14 days and moved on. No second
            guessing. No "maybe it'll bounce back." No holding through the inevitable
            post-run consolidation hoping for more.
          </p>
          <p className="text-gray-300 leading-relaxed text-base">
            The trailing stop is designed to do exactly this: let winners run while they're
            running, then protect gains the moment momentum fades. It turned a volatile
            biotech trade into a disciplined, profitable exit.
          </p>

          {/* The Lesson */}
          <h2 className="text-2xl font-bold text-white mt-12 mb-4">
            The Lesson: Data Over Speculation
          </h2>
          <p className="text-gray-300 leading-relaxed text-base">
            You don't need to follow biotech news to catch biotech breakouts.
            You don't need to understand FDA pipelines, read clinical trial data,
            or guess which drugs will get approved. A systematic momentum approach
            catches these moves based on price action — because by the time a stock
            is breaking out with volume, the people who do understand the fundamentals
            have already placed their bets.
          </p>
          <p className="text-gray-300 leading-relaxed text-base">
            The ensemble doesn't know what TG Therapeutics does. It doesn't know what
            Briumvi treats. It knows the stock was breaking out with conviction across
            multiple independent signals — and that was the only information it needed.
          </p>
          <p className="text-gray-300 leading-relaxed text-base">
            This is the advantage of systematic trading: you capture moves driven by
            catalysts you'd never have known about, in sectors you'd never have researched,
            at entries you'd never have had the confidence to take on your own.
          </p>
        </div>

        {/* CTA */}
        <div className="bg-gradient-to-br from-purple-900/50 to-violet-900/50 border border-purple-500/30 rounded-2xl p-8 sm:p-10 my-12 text-center">
          <h2 className="text-2xl sm:text-3xl font-bold text-white mb-3">
            Catch the Next Breakout
          </h2>
          <p className="text-purple-200/80 mb-6 max-w-lg mx-auto">
            TGTX was one trade out of hundreds the system has flagged.
            The next breakout is already forming — the question is whether
            you'll see the signal.
          </p>
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <Link
              to="/app"
              className="inline-flex items-center justify-center gap-2 bg-amber-500 hover:bg-amber-400 text-gray-950 font-semibold px-8 py-3 rounded-xl transition-colors text-base"
            >
              Start Free Trial
              <ArrowRight size={18} />
            </Link>
            <Link
              to="/track-record"
              className="inline-flex items-center justify-center gap-2 bg-white/10 hover:bg-white/20 text-white font-medium px-8 py-3 rounded-xl transition-colors text-base"
            >
              View Full Track Record
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
            <Link to="/blog/we-called-it-mrna" className="block p-4 bg-gray-900 rounded-lg border border-gray-800 hover:border-gray-600 transition-colors">
              <span className="text-white font-medium">We Called It: Moderna +51%</span>
              <span className="block text-gray-500 text-sm mt-1">How our system caught Moderna summer 2021 breakout and locked in gains.</span>
            </Link>
            <Link to="/blog/momentum-trading" className="block p-4 bg-gray-900 rounded-lg border border-gray-800 hover:border-gray-600 transition-colors">
              <span className="text-white font-medium">Momentum Trading Explained</span>
              <span className="block text-gray-500 text-sm mt-1">The momentum ranking system behind trades like TGTX and MRNA.</span>
            </Link>
            <Link to="/blog/walk-forward-results" className="block p-4 bg-gray-900 rounded-lg border border-gray-800 hover:border-gray-600 transition-colors">
              <span className="text-white font-medium">Inside Our 5-Year Walk-Forward</span>
              <span className="block text-gray-500 text-sm mt-1">The full walk-forward simulation that produced these real trade signals.</span>
            </Link>
          </div>
        </div>

        {/* Disclaimer */}
        <p className="text-xs text-gray-600 leading-relaxed">
          All performance figures are from walk-forward simulations using historical market data.
          The TGTX trade described is a real signal generated by the system during walk-forward testing,
          not a cherry-picked example. Past performance does not guarantee future results. RigaCap
          provides trading signals only — execute trades through your own brokerage account. See our{' '}
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
