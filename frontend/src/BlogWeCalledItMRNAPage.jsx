import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, TrendingUp, ArrowRight, DollarSign, ShieldCheck, Target, Clock } from 'lucide-react';
import MarketMeasuredSignup from './components/MarketMeasuredSignup';

export default function BlogWeCalledItMRNAPage() {
  useEffect(() => { document.title = 'We Called It: Moderna +51% | RigaCap'; }, []);
    const meta = document.querySelector('meta[name="description"]');
    if (meta) meta.setAttribute('content', 'How RigaCap caught Moderna +51% run in summer 2021 and locked in gains with a trailing stop before the stock crashed 66%.');

    // OG tags for social sharing
    document.querySelector('meta[property="og:title"]')?.setAttribute('content', 'We Called It: How Our System Caught Moderna +51% Run | RigaCap');
    document.querySelector('meta[property="og:description"]')?.setAttribute('content', 'How RigaCap caught Moderna +51% run in summer 2021 and locked in gains with a trailing stop before the stock crashed 66%.');
    document.querySelector('meta[property="og:url"]')?.setAttribute('content', 'https://rigacap.com/blog/we-called-it-mrna');
    document.querySelector('meta[name="twitter:title"]')?.setAttribute('content', 'We Called It: How Our System Caught Moderna +51% Run | RigaCap');
    document.querySelector('meta[name="twitter:description"]')?.setAttribute('content', 'How RigaCap caught Moderna +51% run in summer 2021 and locked in gains with a trailing stop before the stock crashed 66%.');
    // JSON-LD Article schema
    const existingSchema = document.querySelector('script[type="application/ld+json"]');
    if (existingSchema) existingSchema.remove();
    const schema = document.createElement('script');
    schema.type = 'application/ld+json';
    schema.text = JSON.stringify({
      "@context": "https://schema.org",
      "@type": "Article",
      "headline": "We Called It: How Our System Caught Moderna +51% Run",
      "description": "How RigaCap caught Moderna +51% run in summer 2021 and locked in gains with a trailing stop before the stock crashed 66%.",
      "author": {"@type": "Organization", "name": "RigaCap"},
      "publisher": {"@type": "Organization", "name": "RigaCap", "url": "https://rigacap.com"},
      "url": "https://rigacap.com/blog/we-called-it-mrna",
      "articleSection": "Case Study",
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
          <p className="text-sm font-medium uppercase tracking-wider text-claret mb-6">Walk-Forward Trade</p>
          <h1 className="font-display text-4xl sm:text-5xl font-bold text-ink tracking-tight mb-4" style={{ fontVariationSettings: '"opsz" 48' }}>
            We Called It: Moderna +51% Run
          </h1>
          <p className="text-lg text-ink-mute max-w-2xl mx-auto">
            How our ensemble system caught MRNA's breakout at $217,
            <br className="hidden sm:block" />
            rode it to $328, and exited before the collapse.
          </p>
        </div>
      </section>

      {/* Trade Card */}
      <section className="max-w-3xl mx-auto px-4 sm:px-6 -mt-8 relative z-10">
        <div className="bg-paper-card border border-positive/30 rounded p-6 sm:p-8">
          <div className="flex items-center gap-2 mb-4">
            <DollarSign className="w-5 h-5 text-positive" />
            <span className="text-xs uppercase tracking-wider text-ink-light font-semibold">MRNA Trade Summary</span>
          </div>
          <div className="grid grid-cols-3 gap-4 text-center">
            <div>
              <div className="text-xs text-ink-light uppercase tracking-wider mb-1">Entry</div>
              <div className="text-2xl sm:text-3xl font-bold text-ink">$217</div>
              <div className="text-xs text-ink-light mt-0.5">Jun 10, 2021</div>
            </div>
            <div>
              <div className="text-xs text-ink-light uppercase tracking-wider mb-1">Peak</div>
              <div className="text-2xl sm:text-3xl font-bold text-claret">$380+</div>
              <div className="text-xs text-ink-light mt-0.5">Mid-July 2021</div>
            </div>
            <div>
              <div className="text-xs text-ink-light uppercase tracking-wider mb-1">Exit</div>
              <div className="text-2xl sm:text-3xl font-bold text-positive">$328</div>
              <div className="text-xs text-ink-light mt-0.5">Jul 27, 2021</div>
            </div>
          </div>
          <div className="mt-4 pt-4 border-t border-rule flex flex-wrap items-center justify-center gap-6 text-sm">
            <div><span className="text-ink-light">Return:</span> <span className="text-positive font-bold">+51.4%</span></div>
            <div><span className="text-ink-light">Hold time:</span> <span className="text-ink">~7 weeks</span></div>
            <div><span className="text-ink-light">Exit reason:</span> <span className="text-claret">Trailing stop</span></div>
          </div>
        </div>
      </section>

      {/* Article Body */}
      <article className="max-w-3xl mx-auto px-4 sm:px-6 py-12 sm:py-16">
        <div className="space-y-4 text-ink-mute text-[1.05rem] leading-[1.75]">

          {/* The Setup */}
          <h2 className="font-display text-2xl font-bold text-ink mt-0 mb-4 flex items-center gap-2" style={{ fontVariationSettings: '"opsz" 48' }}>
            <Target className="w-6 h-6 text-positive flex-shrink-0" />
            The Setup
          </h2>
          <p className="text-ink-mute leading-relaxed text-base">
            Summer 2021. The COVID vaccine rollout was accelerating worldwide, and Moderna
            was at the center of it. After months of sideways consolidation in the $150-$200
            range, MRNA started showing signs of a breakout that most traders were too
            distracted to notice.
          </p>
          <p className="text-ink-mute leading-relaxed text-base">
            Our ensemble system noticed. Three independent signals aligned simultaneously:
            the breakout detection confirmed a shift in the stock's price structure, momentum
            ranking placed MRNA in the top 5 of our entire universe, and a volume spike
            confirmed institutional money was flowing in. When the math lines up like
            that, the system acts.
          </p>

          {/* The Entry */}
          <h2 className="font-display text-2xl font-bold text-ink mt-12 mb-4 flex items-center gap-2" style={{ fontVariationSettings: '"opsz" 48' }}>
            <DollarSign className="w-6 h-6 text-positive flex-shrink-0" />
            The Entry: $217 on June 10
          </h2>
          <p className="text-ink-mute leading-relaxed text-base">
            The system doesn't care about news narratives. It doesn't read headlines about
            Delta variants or booster shots. It saw the math line up — breakout confirmed,
            momentum accelerating, volume surging — and generated a buy signal at $217.
          </p>
          <p className="text-ink-mute leading-relaxed text-base">
            This is what separates systematic trading from gut-feel trading. A human might
            have hesitated: "MRNA already doubled from its 2020 lows — am I too late?"
            The system doesn't ask that question. It measures, it scores, it acts.
          </p>

          {/* The Ride */}
          <h2 className="font-display text-2xl font-bold text-ink mt-12 mb-4 flex items-center gap-2" style={{ fontVariationSettings: '"opsz" 48' }}>
            <TrendingUp className="w-6 h-6 text-positive flex-shrink-0" />
            The Ride: 7 Weeks of Controlled Momentum
          </h2>
          <p className="text-ink-mute leading-relaxed text-base">
            What happened next was remarkable. MRNA surged through June and into July,
            climbing past $250, then $300, and eventually touching $380 at its peak. The
            stock gained over 75% from our entry price in less than two months.
          </p>
          <p className="text-ink-mute leading-relaxed text-base">
            Throughout the entire run, our 12% trailing stop followed the price upward,
            ratcheting the exit floor higher with every new high. At $300, the floor was
            $264. At $350, the floor was $308. At $380, the floor was $334. The stop
            never moves down — it only moves up, locking in more and more of the gain.
          </p>
        </div>

        {/* Timeline Visual */}
        <div className="bg-paper-card border border-rule rounded p-6 sm:p-8 my-8">
          <h3 className="text-sm uppercase tracking-wider text-ink-light font-semibold mb-6">Trade Timeline</h3>
          <div className="relative">
            {/* Connecting line */}
            <div className="absolute left-4 top-3 bottom-3 w-0.5 bg-gradient-to-b from-positive via-claret to-positive"></div>
            <div className="space-y-6">
              <div className="flex items-start gap-4 pl-1">
                <div className="w-7 h-7 rounded-full bg-positive/10 border-2 border-positive flex items-center justify-center flex-shrink-0 z-10">
                  <div className="w-2 h-2 rounded-full bg-positive"></div>
                </div>
                <div>
                  <div className="text-ink font-semibold text-sm">Jun 10 — Entry at $217</div>
                  <div className="text-ink-light text-xs mt-0.5">Ensemble signal fires: breakout detection + top momentum + volume spike</div>
                </div>
              </div>
              <div className="flex items-start gap-4 pl-1">
                <div className="w-7 h-7 rounded-full bg-positive/10 border-2 border-positive flex items-center justify-center flex-shrink-0 z-10">
                  <div className="w-2 h-2 rounded-full bg-positive"></div>
                </div>
                <div>
                  <div className="text-ink font-semibold text-sm">Late June — Passes $280</div>
                  <div className="text-ink-light text-xs mt-0.5">Trailing stop ratchets to $246. Already +29% in pocket.</div>
                </div>
              </div>
              <div className="flex items-start gap-4 pl-1">
                <div className="w-7 h-7 rounded-full bg-claret/10 border-2 border-claret flex items-center justify-center flex-shrink-0 z-10">
                  <div className="w-2 h-2 rounded-full bg-claret"></div>
                </div>
                <div>
                  <div className="text-claret font-semibold text-sm">Mid-July — Peak at $380+</div>
                  <div className="text-ink-light text-xs mt-0.5">Trailing stop at $334. High water mark set. +75% from entry.</div>
                </div>
              </div>
              <div className="flex items-start gap-4 pl-1">
                <div className="w-7 h-7 rounded-full bg-positive/10 border-2 border-positive flex items-center justify-center flex-shrink-0 z-10">
                  <div className="w-2 h-2 rounded-full bg-positive"></div>
                </div>
                <div>
                  <div className="text-ink font-semibold text-sm">Jul 27 — Trailing stop triggers at $328.50</div>
                  <div className="text-ink-light text-xs mt-0.5">MRNA pulls back from peak. System exits automatically. +51.4% locked in.</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="space-y-4 text-ink-mute text-[1.05rem] leading-[1.75]">
          {/* The Exit */}
          <h2 className="font-display text-2xl font-bold text-ink mt-12 mb-4 flex items-center gap-2" style={{ fontVariationSettings: '"opsz" 48' }}>
            <ShieldCheck className="w-6 h-6 text-positive flex-shrink-0" />
            The Exit: Discipline Over Greed
          </h2>
          <p className="text-ink-mute leading-relaxed text-base">
            On July 27, MRNA pulled back from its $380+ peak, and the 12% trailing stop
            triggered at $328.50. The system exited automatically. No second-guessing,
            no "maybe it'll bounce back," no checking Twitter for reassurance. The math
            said exit, so it exited.
          </p>
          <p className="text-ink-mute leading-relaxed text-base">
            The result: <span className="text-positive font-semibold">+51.4% in 7 weeks</span>.
            We captured $111.50 per share of the $163 peak-to-entry move — that's
            68% of the maximum possible gain. Not bad for a system that has no opinion
            about vaccines, variants, or virology.
          </p>
        </div>

        {/* What If You Held comparison */}
        <div className="bg-paper-card border border-rule rounded overflow-hidden my-8">
          <div className="px-6 py-3 border-b border-rule">
            <h3 className="text-sm uppercase tracking-wider text-ink-light font-semibold m-0">What if you held?</h3>
          </div>
          <div className="grid grid-cols-2 divide-x divide-rule">
            <div className="p-6 text-center">
              <div className="text-xs text-ink-light uppercase tracking-wider mb-2">Our Exit</div>
              <div className="text-3xl sm:text-4xl font-bold text-positive">+51.4%</div>
              <div className="text-sm text-ink-mute mt-1">Sold at $328.50</div>
              <div className="text-xs text-ink-light mt-0.5">Jul 27, 2021</div>
            </div>
            <div className="p-6 text-center">
              <div className="text-xs text-ink-light uppercase tracking-wider mb-2">If You Held</div>
              <div className="text-3xl sm:text-4xl font-bold text-negative">-40%</div>
              <div className="text-sm text-ink-mute mt-1">Fell to ~$130</div>
              <div className="text-xs text-ink-light mt-0.5">Early 2022</div>
            </div>
          </div>
          <div className="px-6 py-4 bg-positive/5 border-t border-positive/20">
            <p className="text-sm text-ink-mute m-0 text-center">
              The trailing stop turned a potential 40% loss into a 51% gain.
              That's a 91 percentage point swing.
            </p>
          </div>
        </div>

        <div className="space-y-4 text-ink-mute text-[1.05rem] leading-[1.75]">
          {/* The Lesson */}
          <h2 className="font-display text-2xl font-bold text-ink mt-12 mb-4 flex items-center gap-2" style={{ fontVariationSettings: '"opsz" 48' }}>
            <Clock className="w-6 h-6 text-claret flex-shrink-0" />
            The Lesson: Math Beats Narrative
          </h2>
          <p className="text-ink-mute leading-relaxed text-base">
            "Let winners run, cut losers short" isn't a platitude — it's math.
            The 12% trailing stop is what makes this possible. It gives a winning
            trade room to breathe while establishing a non-negotiable floor.
          </p>

          {/* Highlight Box */}
          <div className="bg-positive/10 border border-positive/30 rounded p-6 my-8">
            <p className="text-ink font-semibold text-lg m-0 mb-2">
              Most traders got the MRNA thesis right.
            </p>
            <p className="text-ink-mute m-0">
              They knew vaccines were a tailwind. They bought in. But without a systematic
              exit plan, they watched their gains evaporate as MRNA fell 66% from its peak.
              The difference between a great entry and a great trade is knowing when to leave.
            </p>
          </div>

          <p className="text-ink-mute leading-relaxed text-base">
            MRNA eventually fell to around $130 by early 2022 — a 66% decline from
            the July peak. Investors who held through the drop didn't just lose their
            gains; they lost 40% of their original investment. Meanwhile, our system
            had already moved on to the next opportunity, compounding from a higher base.
          </p>

          <p className="text-ink-mute leading-relaxed text-base">
            This is the power of the ensemble approach. The entry was good — three
            independent signals all confirming the breakout. But the exit was where
            the real value was created. No human emotion. No attachment to the stock.
            No "it might come back." Just math, executing exactly as designed.
          </p>

          {/* How The System Works */}
          <h2 className="font-display text-2xl font-bold text-ink mt-12 mb-4" style={{ fontVariationSettings: '"opsz" 48' }}>
            How the Ensemble Caught This Trade
          </h2>
          <p className="text-ink-mute leading-relaxed text-base">
            Our system requires three independent factors to align before entering
            any position. On June 10, MRNA passed all three:
          </p>
        </div>

        {/* Factor Cards */}
        <div className="grid gap-4 my-8">
          <div className="bg-paper-card border border-rule rounded p-6">
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 rounded-lg bg-positive/10 flex items-center justify-center flex-shrink-0">
                <span className="text-positive font-bold">1</span>
              </div>
              <div>
                <h3 className="text-ink font-semibold mb-1">Breakout Detection (Timing)</h3>
                <p className="text-ink-mute text-sm m-0">
                  MRNA's price broke decisively above a key long-term support level — a reliable
                  signal that institutional accumulation is shifting the stock's equilibrium
                  higher. Our proprietary breakout indicator catches these moves early.
                </p>
              </div>
            </div>
          </div>
          <div className="bg-paper-card border border-rule rounded p-6">
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 rounded-lg bg-claret/10 flex items-center justify-center flex-shrink-0">
                <span className="text-claret font-bold">2</span>
              </div>
              <div>
                <h3 className="text-ink font-semibold mb-1">Top Momentum Ranking (Quality)</h3>
                <p className="text-ink-mute text-sm m-0">
                  Short-term (10-day) and long-term (60-day) momentum placed MRNA in the
                  top 5 of our entire stock universe. This confirms the breakout has
                  genuine force behind it, not just a single-day pop.
                </p>
              </div>
            </div>
          </div>
          <div className="bg-paper-card border border-rule rounded p-6">
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 rounded-lg bg-claret/10 flex items-center justify-center flex-shrink-0">
                <span className="text-claret font-bold">3</span>
              </div>
              <div>
                <h3 className="text-ink font-semibold mb-1">Volume Spike (Confirmation)</h3>
                <p className="text-ink-mute text-sm m-0">
                  Trading volume surged 1.3x above the average — a sign that smart money
                  was moving in. Without this confirmation, the system stays on the
                  sidelines. Volume validates conviction.
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* CTA */}
        <div className="bg-paper-card border border-rule rounded p-8 sm:p-10 my-12 text-center">
          <h2 className="font-display text-2xl sm:text-3xl font-bold text-ink mb-3" style={{ fontVariationSettings: '"opsz" 48' }}>
            Get Signals Like This
          </h2>
          <p className="text-ink-mute mb-6 max-w-lg mx-auto">
            Our system scans the market daily for trades with this kind of
            edge — breakout timing, momentum confirmation, and built-in
            downside protection. Every signal comes with automatic trailing stops.
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
            <Link to="/blog/trailing-stops" className="block p-4 bg-paper-card rounded border border-rule hover:border-rule-dark transition-colors">
              <span className="text-ink font-medium">How Trailing Stops Protect Your Portfolio</span>
              <span className="block text-ink-light text-sm mt-1">The trailing stop mechanism that locked in Moderna's gains before the crash.</span>
            </Link>
            <Link to="/blog/momentum-trading" className="block p-4 bg-paper-card rounded border border-rule hover:border-rule-dark transition-colors">
              <span className="text-ink font-medium">Momentum Trading Explained</span>
              <span className="block text-ink-light text-sm mt-1">How momentum ranking identifies breakout candidates like MRNA.</span>
            </Link>
            <Link to="/blog/we-called-it-tgtx" className="block p-4 bg-paper-card rounded border border-rule hover:border-rule-dark transition-colors">
              <span className="text-ink font-medium">We Called It: TGTX +46%</span>
              <span className="block text-ink-light text-sm mt-1">Another real trade from our walk-forward simulation with a biotech breakout.</span>
            </Link>
          </div>
        </div>

        {/* Disclaimer */}
        <p className="text-xs text-ink-light leading-relaxed">
          Walk-forward simulation result. Past trades do not guarantee future performance.
          RigaCap provides trading signals only — execute trades through your own brokerage
          account. See our{' '}
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
