import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, TrendingUp, ArrowRight, DollarSign, ShieldCheck, Target, Clock } from 'lucide-react';
import MarketMeasuredSignup from './components/MarketMeasuredSignup';

export default function BlogWeCalledItMRNAPage() {
  useEffect(() => { document.title = 'We Called It: Moderna +51% | RigaCap'; }, []);
    const meta = document.querySelector('meta[name="description"]');
    if (meta) meta.setAttribute('content', 'How RigaCap caught Moderna +51% run in summer 2021 and locked in gains with a trailing stop before the stock crashed 66%.');
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
      <section className="relative overflow-hidden bg-gradient-to-br from-emerald-900/80 via-gray-900 to-green-900/60">
        <div className="absolute inset-0 overflow-hidden">
          <div className="absolute -top-40 -right-40 w-80 h-80 bg-emerald-500/10 rounded-full blur-3xl"></div>
          <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-green-500/10 rounded-full blur-3xl"></div>
        </div>
        <div className="relative max-w-3xl mx-auto px-4 sm:px-6 py-16 sm:py-24 text-center">
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-white/10 backdrop-blur-sm rounded-full text-sm font-medium mb-6">
            <TrendingUp className="w-4 h-4 text-emerald-300" />
            <span className="text-white/90">Walk-Forward Trade</span>
          </div>
          <h1 className="text-4xl sm:text-5xl font-bold text-white tracking-tight mb-4">
            We Called It: Moderna's +51% Run
          </h1>
          <p className="text-lg text-emerald-200/80 max-w-2xl mx-auto">
            How our ensemble system caught MRNA's breakout at $217,
            <br className="hidden sm:block" />
            rode it to $328, and exited before the collapse.
          </p>
        </div>
      </section>

      {/* Trade Card */}
      <section className="max-w-3xl mx-auto px-4 sm:px-6 -mt-8 relative z-10">
        <div className="bg-gray-900 border border-emerald-500/30 rounded-xl p-6 sm:p-8">
          <div className="flex items-center gap-2 mb-4">
            <DollarSign className="w-5 h-5 text-emerald-400" />
            <span className="text-xs uppercase tracking-wider text-gray-500 font-semibold">MRNA Trade Summary</span>
          </div>
          <div className="grid grid-cols-3 gap-4 text-center">
            <div>
              <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">Entry</div>
              <div className="text-2xl sm:text-3xl font-bold text-white">$217</div>
              <div className="text-xs text-gray-500 mt-0.5">Jun 10, 2021</div>
            </div>
            <div>
              <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">Peak</div>
              <div className="text-2xl sm:text-3xl font-bold text-amber-400">$380+</div>
              <div className="text-xs text-gray-500 mt-0.5">Mid-July 2021</div>
            </div>
            <div>
              <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">Exit</div>
              <div className="text-2xl sm:text-3xl font-bold text-emerald-400">$328</div>
              <div className="text-xs text-gray-500 mt-0.5">Jul 27, 2021</div>
            </div>
          </div>
          <div className="mt-4 pt-4 border-t border-gray-800 flex flex-wrap items-center justify-center gap-6 text-sm">
            <div><span className="text-gray-500">Return:</span> <span className="text-emerald-400 font-bold">+51.4%</span></div>
            <div><span className="text-gray-500">Hold time:</span> <span className="text-white">~7 weeks</span></div>
            <div><span className="text-gray-500">Exit reason:</span> <span className="text-amber-400">Trailing stop</span></div>
          </div>
        </div>
      </section>

      {/* Article Body */}
      <article className="max-w-3xl mx-auto px-4 sm:px-6 py-12 sm:py-16">
        <div className="prose prose-invert prose-gray max-w-none">

          {/* The Setup */}
          <h2 className="text-2xl font-bold text-white mt-0 mb-4 flex items-center gap-2">
            <Target className="w-6 h-6 text-emerald-400 flex-shrink-0" />
            The Setup
          </h2>
          <p className="text-gray-300 leading-relaxed text-base">
            Summer 2021. The COVID vaccine rollout was accelerating worldwide, and Moderna
            was at the center of it. After months of sideways consolidation in the $150-$200
            range, MRNA started showing signs of a breakout that most traders were too
            distracted to notice.
          </p>
          <p className="text-gray-300 leading-relaxed text-base">
            Our ensemble system noticed. Three independent signals aligned simultaneously:
            the breakout detection confirmed a shift in the stock's price structure, momentum
            ranking placed MRNA in the top 5 of our entire universe, and a volume spike
            confirmed institutional money was flowing in. When the math lines up like
            that, the system acts.
          </p>

          {/* The Entry */}
          <h2 className="text-2xl font-bold text-white mt-12 mb-4 flex items-center gap-2">
            <DollarSign className="w-6 h-6 text-emerald-400 flex-shrink-0" />
            The Entry: $217 on June 10
          </h2>
          <p className="text-gray-300 leading-relaxed text-base">
            The system doesn't care about news narratives. It doesn't read headlines about
            Delta variants or booster shots. It saw the math line up — breakout confirmed,
            momentum accelerating, volume surging — and generated a buy signal at $217.
          </p>
          <p className="text-gray-300 leading-relaxed text-base">
            This is what separates systematic trading from gut-feel trading. A human might
            have hesitated: "MRNA already doubled from its 2020 lows — am I too late?"
            The system doesn't ask that question. It measures, it scores, it acts.
          </p>

          {/* The Ride */}
          <h2 className="text-2xl font-bold text-white mt-12 mb-4 flex items-center gap-2">
            <TrendingUp className="w-6 h-6 text-emerald-400 flex-shrink-0" />
            The Ride: 7 Weeks of Controlled Momentum
          </h2>
          <p className="text-gray-300 leading-relaxed text-base">
            What happened next was remarkable. MRNA surged through June and into July,
            climbing past $250, then $300, and eventually touching $380 at its peak. The
            stock gained over 75% from our entry price in less than two months.
          </p>
          <p className="text-gray-300 leading-relaxed text-base">
            Throughout the entire run, our 12% trailing stop followed the price upward,
            ratcheting the exit floor higher with every new high. At $300, the floor was
            $264. At $350, the floor was $308. At $380, the floor was $334. The stop
            never moves down — it only moves up, locking in more and more of the gain.
          </p>
        </div>

        {/* Timeline Visual */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 sm:p-8 my-8">
          <h3 className="text-sm uppercase tracking-wider text-gray-500 font-semibold mb-6">Trade Timeline</h3>
          <div className="relative">
            {/* Connecting line */}
            <div className="absolute left-4 top-3 bottom-3 w-0.5 bg-gradient-to-b from-emerald-500 via-amber-500 to-emerald-500"></div>
            <div className="space-y-6">
              <div className="flex items-start gap-4 pl-1">
                <div className="w-7 h-7 rounded-full bg-emerald-500/20 border-2 border-emerald-500 flex items-center justify-center flex-shrink-0 z-10">
                  <div className="w-2 h-2 rounded-full bg-emerald-400"></div>
                </div>
                <div>
                  <div className="text-white font-semibold text-sm">Jun 10 — Entry at $217</div>
                  <div className="text-gray-500 text-xs mt-0.5">Ensemble signal fires: breakout detection + top momentum + volume spike</div>
                </div>
              </div>
              <div className="flex items-start gap-4 pl-1">
                <div className="w-7 h-7 rounded-full bg-emerald-500/20 border-2 border-emerald-500 flex items-center justify-center flex-shrink-0 z-10">
                  <div className="w-2 h-2 rounded-full bg-emerald-400"></div>
                </div>
                <div>
                  <div className="text-white font-semibold text-sm">Late June — Passes $280</div>
                  <div className="text-gray-500 text-xs mt-0.5">Trailing stop ratchets to $246. Already +29% in pocket.</div>
                </div>
              </div>
              <div className="flex items-start gap-4 pl-1">
                <div className="w-7 h-7 rounded-full bg-amber-500/20 border-2 border-amber-500 flex items-center justify-center flex-shrink-0 z-10">
                  <div className="w-2 h-2 rounded-full bg-amber-400"></div>
                </div>
                <div>
                  <div className="text-amber-400 font-semibold text-sm">Mid-July — Peak at $380+</div>
                  <div className="text-gray-500 text-xs mt-0.5">Trailing stop at $334. High water mark set. +75% from entry.</div>
                </div>
              </div>
              <div className="flex items-start gap-4 pl-1">
                <div className="w-7 h-7 rounded-full bg-emerald-500/20 border-2 border-emerald-500 flex items-center justify-center flex-shrink-0 z-10">
                  <div className="w-2 h-2 rounded-full bg-emerald-400"></div>
                </div>
                <div>
                  <div className="text-white font-semibold text-sm">Jul 27 — Trailing stop triggers at $328.50</div>
                  <div className="text-gray-500 text-xs mt-0.5">MRNA pulls back from peak. System exits automatically. +51.4% locked in.</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="prose prose-invert prose-gray max-w-none">
          {/* The Exit */}
          <h2 className="text-2xl font-bold text-white mt-12 mb-4 flex items-center gap-2">
            <ShieldCheck className="w-6 h-6 text-emerald-400 flex-shrink-0" />
            The Exit: Discipline Over Greed
          </h2>
          <p className="text-gray-300 leading-relaxed text-base">
            On July 27, MRNA pulled back from its $380+ peak, and the 12% trailing stop
            triggered at $328.50. The system exited automatically. No second-guessing,
            no "maybe it'll bounce back," no checking Twitter for reassurance. The math
            said exit, so it exited.
          </p>
          <p className="text-gray-300 leading-relaxed text-base">
            The result: <span className="text-emerald-400 font-semibold">+51.4% in 7 weeks</span>.
            We captured $111.50 per share of the $163 peak-to-entry move — that's
            68% of the maximum possible gain. Not bad for a system that has no opinion
            about vaccines, variants, or virology.
          </p>
        </div>

        {/* What If You Held comparison */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden my-8">
          <div className="px-6 py-3 border-b border-gray-800">
            <h3 className="text-sm uppercase tracking-wider text-gray-500 font-semibold m-0">What if you held?</h3>
          </div>
          <div className="grid grid-cols-2 divide-x divide-gray-800">
            <div className="p-6 text-center">
              <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">Our Exit</div>
              <div className="text-3xl sm:text-4xl font-bold text-emerald-400">+51.4%</div>
              <div className="text-sm text-gray-400 mt-1">Sold at $328.50</div>
              <div className="text-xs text-gray-600 mt-0.5">Jul 27, 2021</div>
            </div>
            <div className="p-6 text-center">
              <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">If You Held</div>
              <div className="text-3xl sm:text-4xl font-bold text-red-400">-40%</div>
              <div className="text-sm text-gray-400 mt-1">Fell to ~$130</div>
              <div className="text-xs text-gray-600 mt-0.5">Early 2022</div>
            </div>
          </div>
          <div className="px-6 py-4 bg-emerald-500/5 border-t border-emerald-500/20">
            <p className="text-sm text-emerald-200/80 m-0 text-center">
              The trailing stop turned a potential 40% loss into a 51% gain.
              That's a 91 percentage point swing.
            </p>
          </div>
        </div>

        <div className="prose prose-invert prose-gray max-w-none">
          {/* The Lesson */}
          <h2 className="text-2xl font-bold text-white mt-12 mb-4 flex items-center gap-2">
            <Clock className="w-6 h-6 text-amber-400 flex-shrink-0" />
            The Lesson: Math Beats Narrative
          </h2>
          <p className="text-gray-300 leading-relaxed text-base">
            "Let winners run, cut losers short" isn't a platitude — it's math.
            The 12% trailing stop is what makes this possible. It gives a winning
            trade room to breathe while establishing a non-negotiable floor.
          </p>

          {/* Highlight Box */}
          <div className="bg-emerald-500/10 border border-emerald-500/30 rounded-xl p-6 my-8">
            <p className="text-emerald-200 font-semibold text-lg m-0 mb-2">
              Most traders got the MRNA thesis right.
            </p>
            <p className="text-emerald-200/80 m-0">
              They knew vaccines were a tailwind. They bought in. But without a systematic
              exit plan, they watched their gains evaporate as MRNA fell 66% from its peak.
              The difference between a great entry and a great trade is knowing when to leave.
            </p>
          </div>

          <p className="text-gray-300 leading-relaxed text-base">
            MRNA eventually fell to around $130 by early 2022 — a 66% decline from
            the July peak. Investors who held through the drop didn't just lose their
            gains; they lost 40% of their original investment. Meanwhile, our system
            had already moved on to the next opportunity, compounding from a higher base.
          </p>

          <p className="text-gray-300 leading-relaxed text-base">
            This is the power of the ensemble approach. The entry was good — three
            independent signals all confirming the breakout. But the exit was where
            the real value was created. No human emotion. No attachment to the stock.
            No "it might come back." Just math, executing exactly as designed.
          </p>

          {/* How The System Works */}
          <h2 className="text-2xl font-bold text-white mt-12 mb-4">
            How the Ensemble Caught This Trade
          </h2>
          <p className="text-gray-300 leading-relaxed text-base">
            Our system requires three independent factors to align before entering
            any position. On June 10, MRNA passed all three:
          </p>
        </div>

        {/* Factor Cards */}
        <div className="grid gap-4 my-8">
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 rounded-lg bg-emerald-500/20 flex items-center justify-center flex-shrink-0">
                <span className="text-emerald-400 font-bold">1</span>
              </div>
              <div>
                <h3 className="text-white font-semibold mb-1">Breakout Detection (Timing)</h3>
                <p className="text-gray-400 text-sm m-0">
                  MRNA's price broke decisively above a key long-term support level — a reliable
                  signal that institutional accumulation is shifting the stock's equilibrium
                  higher. Our proprietary breakout indicator catches these moves early.
                </p>
              </div>
            </div>
          </div>
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 rounded-lg bg-blue-500/20 flex items-center justify-center flex-shrink-0">
                <span className="text-blue-400 font-bold">2</span>
              </div>
              <div>
                <h3 className="text-white font-semibold mb-1">Top Momentum Ranking (Quality)</h3>
                <p className="text-gray-400 text-sm m-0">
                  Short-term (10-day) and long-term (60-day) momentum placed MRNA in the
                  top 5 of our entire stock universe. This confirms the breakout has
                  genuine force behind it, not just a single-day pop.
                </p>
              </div>
            </div>
          </div>
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 rounded-lg bg-amber-500/20 flex items-center justify-center flex-shrink-0">
                <span className="text-amber-400 font-bold">3</span>
              </div>
              <div>
                <h3 className="text-white font-semibold mb-1">Volume Spike (Confirmation)</h3>
                <p className="text-gray-400 text-sm m-0">
                  Trading volume surged 1.3x above the average — a sign that smart money
                  was moving in. Without this confirmation, the system stays on the
                  sidelines. Volume validates conviction.
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* CTA */}
        <div className="bg-gradient-to-br from-emerald-900/50 to-green-900/50 border border-emerald-500/30 rounded-2xl p-8 sm:p-10 my-12 text-center">
          <h2 className="text-2xl sm:text-3xl font-bold text-white mb-3">
            Get Signals Like This
          </h2>
          <p className="text-emerald-200/80 mb-6 max-w-lg mx-auto">
            Our system scans the market daily for trades with this kind of
            edge — breakout timing, momentum confirmation, and built-in
            downside protection. Every signal comes with automatic trailing stops.
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
            <Link to="/blog/trailing-stops" className="block p-4 bg-gray-900 rounded-lg border border-gray-800 hover:border-gray-600 transition-colors">
              <span className="text-white font-medium">How Trailing Stops Protect Your Portfolio</span>
              <span className="block text-gray-500 text-sm mt-1">The trailing stop mechanism that locked in Moderna's gains before the crash.</span>
            </Link>
            <Link to="/blog/momentum-trading" className="block p-4 bg-gray-900 rounded-lg border border-gray-800 hover:border-gray-600 transition-colors">
              <span className="text-white font-medium">Momentum Trading Explained</span>
              <span className="block text-gray-500 text-sm mt-1">How momentum ranking identifies breakout candidates like MRNA.</span>
            </Link>
            <Link to="/blog/we-called-it-tgtx" className="block p-4 bg-gray-900 rounded-lg border border-gray-800 hover:border-gray-600 transition-colors">
              <span className="text-white font-medium">We Called It: TGTX +46%</span>
              <span className="block text-gray-500 text-sm mt-1">Another real trade from our walk-forward simulation with a biotech breakout.</span>
            </Link>
          </div>
        </div>

        {/* Disclaimer */}
        <p className="text-xs text-gray-600 leading-relaxed">
          Walk-forward simulation result. Past trades do not guarantee future performance.
          RigaCap provides trading signals only — execute trades through your own brokerage
          account. See our{' '}
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
