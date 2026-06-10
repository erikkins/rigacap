import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, ArrowRight, AlertTriangle, Eye, Scissors, ShieldCheck, TrendingDown } from 'lucide-react';
import MarketMeasuredSignup from './components/MarketMeasuredSignup';

export default function BlogHonestBacktestPage() {
  useEffect(() => { document.title = 'We Found Our Own Backtest Was Lying | RigaCap'; }, []);
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
          <p className="text-sm font-medium uppercase tracking-widest text-claret mb-6">A Reckoning</p>
          <h1 className="font-display text-4xl sm:text-5xl font-normal text-ink tracking-tight mb-5" style={{ fontVariationSettings: '"opsz" 96' }}>
            We found our own backtest<br /><em className="text-claret italic">was lying to us.</em>
          </h1>
          <p className="text-lg text-ink-mute max-w-2xl mx-auto leading-relaxed">
            Survivorship bias and stock splits had quietly inflated every number we published. So we tore the whole thing down, rebuilt it honestly, and revised our returns <em>down</em>. Here's what that looks like — and why it should make you trust us more, not less.
          </p>
        </div>
      </section>

      {/* Article Body */}
      <article className="max-w-3xl mx-auto px-4 sm:px-6 py-12 sm:py-16">
        <div className="prose prose-gray max-w-none text-[1.075rem] leading-[1.75] text-ink">

          <p className="text-[1.2rem] leading-[1.7] text-ink mb-8">
            Most strategies you'll find online are sold to you with their best face forward. This is the opposite of that. It's the story of how we caught our own research lying — and what we did about it.
          </p>

          <p>For a while, RigaCap published some genuinely impressive backtest numbers. We believed them. We'd built the strategy carefully, tested it across years of data, and the results looked strong. Then one afternoon, running a routine check, something felt slightly too good. So we did the thing most people never do with a number that flatters them: <strong className="font-medium">we tried to prove it wrong.</strong></p>

          <p>We found two bugs. Either one, on its own, is enough to turn a mediocre strategy into a spectacular-looking one. We had both.</p>

          {/* Bug 1 */}
          <div className="my-10 border border-rule bg-paper-card p-7 sm:p-8" style={{ borderLeft: '3px solid #7A2430' }}>
            <div className="flex items-center gap-3 mb-3">
              <Eye className="w-5 h-5 text-claret" />
              <span className="font-mono text-[0.72rem] tracking-[0.12em] uppercase text-claret font-semibold">Bug one</span>
            </div>
            <h3 className="font-display text-[1.5rem] font-medium text-ink mb-3" style={{ fontVariationSettings: '"opsz" 48' }}>Survivorship bias: we were only testing the winners.</h3>
            <p className="text-ink-mute text-[1.02rem] leading-[1.7] mb-0">
              Our backtest drew its stock universe from the companies that exist <em>today</em>. Sounds reasonable — until you realize that every company that went bankrupt, got delisted, or was acquired after falling apart had quietly vanished from the test. We were only ever trading the survivors. It's like judging a parachute design by interviewing the people who landed safely. The strategy never had to navigate the disasters, because the disasters had been deleted from history.
            </p>
          </div>

          {/* Bug 2 */}
          <div className="my-10 border border-rule bg-paper-card p-7 sm:p-8" style={{ borderLeft: '3px solid #7A2430' }}>
            <div className="flex items-center gap-3 mb-3">
              <Scissors className="w-5 h-5 text-claret" />
              <span className="font-mono text-[0.72rem] tracking-[0.12em] uppercase text-claret font-semibold">Bug two</span>
            </div>
            <h3 className="font-display text-[1.5rem] font-medium text-ink mb-3" style={{ fontVariationSettings: '"opsz" 48' }}>Stock splits: phantom gains and phantom losses.</h3>
            <p className="text-ink-mute text-[1.02rem] leading-[1.7] mb-0">
              When a stock splits — say, 10-for-1 — its price drops to a tenth overnight, but nothing of value has changed. If your price history isn't carefully adjusted for that, the math goes haywire: a held position can book a fake 90% loss, or an entry can look like a miraculous gain. Our data had raw, unadjusted splits scattered through it. Each one was a small lie the backtest told itself, and they compounded.
            </p>
          </div>

          <h2 className="font-display text-[1.9rem] font-medium text-ink mt-12 mb-4 tracking-[-0.01em]" style={{ fontVariationSettings: '"opsz" 72' }}>
            So we rebuilt the foundation.
          </h2>
          <p>We could have patched the numbers and moved on. Instead we rebuilt our entire research data layer from scratch, around two non-negotiable principles:</p>

          <ul className="space-y-4 my-6">
            <li className="flex gap-3">
              <ShieldCheck className="w-5 h-5 text-claret flex-shrink-0 mt-1" />
              <span><strong className="font-medium">Survivorship-free.</strong> We reconstructed the companies that died — the delistings, the bankruptcies, the failed mergers — from regulatory filings, and put them back into the test. Now the strategy is judged against the full graveyard, not just the survivors.</span>
            </li>
            <li className="flex gap-3">
              <Eye className="w-5 h-5 text-claret flex-shrink-0 mt-1" />
              <span><strong className="font-medium">Point-in-time.</strong> Every decision in the backtest now uses <em>only</em> the information that existed on that exact date — prices, the eligible universe, and corporate actions all adjusted as-of, never with hindsight. No peeking at the future, not even by accident.</span>
            </li>
          </ul>

          <p>It took weeks. It was not fun. And when we re-ran the strategy on honest data, the numbers came down.</p>

          {/* The reckoning */}
          <div className="my-10 bg-ink text-paper p-8 sm:p-10 rounded-[2px]">
            <div className="flex items-center gap-3 mb-4">
              <TrendingDown className="w-5 h-5 text-paper/70" />
              <span className="font-mono text-[0.72rem] tracking-[0.12em] uppercase text-paper/70 font-semibold">The honest number</span>
            </div>
            <p className="text-paper/90 text-[1.05rem] leading-[1.7] mb-5">
              Stripped of the inflation, our strategy compounds at <strong className="text-paper font-semibold">8.3% a year</strong> across <strong className="text-paper font-semibold">21 years (2007–2026)</strong>, with a worst drawdown of <strong className="text-paper font-semibold">19%</strong> and a Sharpe ratio of <strong className="text-paper font-semibold">0.73</strong> — tested through the 2008 financial crisis, the COVID crash, and the 2022 bear.
            </p>
            <p className="text-paper/70 text-[0.95rem] leading-[1.65] mb-0">
              Lower than what we used to show. More conservative than we'd hoped. And — as far as we can make it — true. (Our data from 2016 onward is survivorship-free and point-in-time; the pre-2016 extension carries a survivorship caveat, disclosed in our methodology.)
            </p>
          </div>

          <h2 className="font-display text-[1.9rem] font-medium text-ink mt-12 mb-4 tracking-[-0.01em]" style={{ fontVariationSettings: '"opsz" 72' }}>
            Why we're telling you this.
          </h2>
          <p>The obvious move is to never mention any of it. Quietly fix the numbers, update the website, hope nobody noticed. Plenty of shops do exactly that.</p>
          <p>We're telling you because <strong className="font-medium">the honesty is the product.</strong> Anyone can publish a flattering backtest; almost no one publishes the one that survived their own attempt to destroy it. When you can't see how a number was made, you're trusting the marketing. When the person behind it has shown you the bodies — the bugs they found, the numbers they walked back — you're trusting the method.</p>
          <p>An 8% strategy you can actually believe is worth more than a 30% strategy you can't.</p>

          <div className="my-10 border-l-[3px] border-claret pl-6 py-1">
            <p className="font-display text-[1.4rem] leading-[1.4] italic text-ink mb-0" style={{ fontVariationSettings: '"opsz" 36' }}>
              The number we publish is the one that's left after we've done everything we can to disprove it.
            </p>
          </div>

          <p>That's the whole philosophy, in one sentence. These results are still backtested — the strategy now runs live, but its real-time record is just beginning, and even good strategies give a little back once real money is involved. So underwrite us conservatively until that live record builds. We'll publish it as it does. Good or bad.</p>

          <p className="text-ink-mute">That's the deal. It's a less exciting pitch than the one we used to make. It's a much more honest one.</p>

        </div>

        {/* Signup */}
        <div className="mt-16 pt-12 border-t border-rule">
          <MarketMeasuredSignup source="blog_honest_backtest" />
        </div>
      </article>

      {/* CTA */}
      <section className="bg-paper-card border-t border-rule py-16">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 text-center">
          <h2 className="font-display text-[1.8rem] font-medium text-ink mb-3" style={{ fontVariationSettings: '"opsz" 72' }}>
            See the honest numbers in full.
          </h2>
          <p className="text-ink-mute mb-7 max-w-xl mx-auto">The complete track record — every regime, every drawdown, nothing hidden.</p>
          <Link to="/track-record" className="inline-flex items-center gap-2 px-7 py-4 bg-ink text-paper text-[0.95rem] font-medium rounded-[2px] no-underline hover:bg-claret transition-colors">
            View the track record
            <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </section>
    </div>
  );
}
