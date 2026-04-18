import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, AlertTriangle, Shield, TrendingDown, TrendingUp, Clock, ArrowRight, Brain } from 'lucide-react';
import MarketMeasuredSignup from './components/MarketMeasuredSignup';

export default function BlogMarketCrashPage() {
  useEffect(() => { document.title = 'What to Do When the Market Crashes | RigaCap'; }, []);
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
      <section className="relative overflow-hidden bg-gradient-to-br from-red-900/80 via-gray-900 to-amber-900/40">
        <div className="absolute inset-0 overflow-hidden">
          <div className="absolute -top-40 -right-40 w-80 h-80 bg-red-500/15 rounded-full blur-3xl"></div>
          <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-amber-500/10 rounded-full blur-3xl"></div>
        </div>
        <div className="relative max-w-3xl mx-auto px-4 sm:px-6 py-16 sm:py-24 text-center">
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-white/10 backdrop-blur-sm rounded-full text-sm font-medium mb-6">
            <AlertTriangle className="w-4 h-4 text-amber-300" />
            <span className="text-white/90">Evergreen Investor Playbook</span>
          </div>
          <h1 className="text-4xl sm:text-5xl font-bold text-white tracking-tight mb-4">
            What to Do When<br /> the Market Crashes
          </h1>
          <p className="text-lg text-amber-200/70 max-w-2xl mx-auto">
            The playbook most investors wish they had before 2022.
            <br className="hidden sm:block" />
            Practical rules that protect your capital when panic sets in.
          </p>
        </div>
      </section>

      {/* Article Body */}
      <article className="max-w-3xl mx-auto px-4 sm:px-6 py-12 sm:py-16">
        <div className="prose prose-invert prose-gray max-w-none">

          {/* The Emotional Spiral */}
          <h2 className="text-2xl font-bold text-white mt-0 mb-4 flex items-center gap-2">
            <Brain className="w-6 h-6 text-red-400 flex-shrink-0" />
            The Emotional Spiral Nobody Escapes
          </h2>
          <p className="text-gray-300 leading-relaxed text-base">
            You already know you shouldn't panic sell. Every investing article you've ever read
            says the same thing. And yet, when the market drops 5% in a day and your portfolio
            is bleeding red, something primal kicks in.
          </p>
          <p className="text-gray-300 leading-relaxed text-base">
            It starts with denial. "This is just a pullback." Then the drop continues. Anxiety
            builds. You start checking your portfolio every hour, doing mental math on how much
            you've lost. The financial news turns apocalyptic. Twitter is full of people calling
            for a 50% crash.
          </p>
          <p className="text-gray-300 leading-relaxed text-base">
            Then comes the capitulation. You sell everything at a loss because the pain of watching
            it fall further feels worse than locking in the loss. You tell yourself you'll buy back
            in "when things settle down."
          </p>
          <p className="text-gray-300 leading-relaxed text-base">
            But things never settle down in a way that feels safe. By the time the news is optimistic
            again, the market has already recovered 20% from its bottom — without you. You missed
            the bounce because you were waiting for permission to feel confident again.
          </p>
          <p className="text-gray-300 leading-relaxed text-base">
            This isn't a character flaw. It's human biology. Our brains evolved to run from danger,
            not to sit calmly while our net worth drops. The investors who survive crashes aren't
            braver — they have better systems.
          </p>

          {/* What NOT To Do */}
          <h2 className="text-2xl font-bold text-white mt-12 mb-4 flex items-center gap-2">
            <AlertTriangle className="w-6 h-6 text-red-400 flex-shrink-0" />
            What NOT to Do
          </h2>
          <p className="text-gray-300 leading-relaxed text-base">
            Before we talk about what works, let's name the mistakes that cost people the most money
            during downturns.
          </p>
        </div>

        {/* What NOT To Do Cards */}
        <div className="grid gap-4 my-8">
          <div className="bg-gray-900 border border-red-500/20 rounded-xl p-6">
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 rounded-lg bg-red-500/20 flex items-center justify-center flex-shrink-0">
                <span className="text-red-400 font-bold">1</span>
              </div>
              <div>
                <h3 className="text-white font-semibold mb-1">Don't Panic Sell at the Bottom</h3>
                <p className="text-gray-400 text-sm m-0">
                  The day you feel the most urgency to sell is almost always the worst day to do it.
                  Capitulation selling — dumping everything because you can't take the pain — is the
                  single most expensive mistake individual investors make. It turns a temporary drawdown
                  into a permanent loss.
                </p>
              </div>
            </div>
          </div>
          <div className="bg-gray-900 border border-red-500/20 rounded-xl p-6">
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 rounded-lg bg-red-500/20 flex items-center justify-center flex-shrink-0">
                <span className="text-red-400 font-bold">2</span>
              </div>
              <div>
                <h3 className="text-white font-semibold mb-1">Don't "Buy the Dip" Blindly</h3>
                <p className="text-gray-400 text-sm m-0">
                  Buying every dip sounds brave until the dip turns into a 40% bear market. In 2022,
                  every "this is the bottom" call was followed by another leg down. A 10% correction and
                  a structural bear market look identical at the beginning. Without a framework to tell
                  them apart, you're just guessing.
                </p>
              </div>
            </div>
          </div>
          <div className="bg-gray-900 border border-red-500/20 rounded-xl p-6">
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 rounded-lg bg-red-500/20 flex items-center justify-center flex-shrink-0">
                <span className="text-red-400 font-bold">3</span>
              </div>
              <div>
                <h3 className="text-white font-semibold mb-1">Don't Check Your Portfolio Every Hour</h3>
                <p className="text-gray-400 text-sm m-0">
                  Every time you check, you trigger another micro-hit of cortisol. Research shows
                  that investors who check daily make worse decisions than those who check weekly or
                  monthly. Watching the number go down doesn't change the number — it just erodes
                  your ability to think clearly.
                </p>
              </div>
            </div>
          </div>
          <div className="bg-gray-900 border border-red-500/20 rounded-xl p-6">
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 rounded-lg bg-red-500/20 flex items-center justify-center flex-shrink-0">
                <span className="text-red-400 font-bold">4</span>
              </div>
              <div>
                <h3 className="text-white font-semibold mb-1">Don't Listen to Bottom-Callers</h3>
                <p className="text-gray-400 text-sm m-0">
                  For every pundit who correctly called the 2022 bottom, a hundred called it wrong —
                  five times. The ones who got it right were lucky, not skilled. Nobody consistently
                  predicts market bottoms. If they could, they wouldn't be on TV.
                </p>
              </div>
            </div>
          </div>
        </div>

        <div className="prose prose-invert prose-gray max-w-none">
          {/* What TO Do */}
          <h2 className="text-2xl font-bold text-white mt-12 mb-4 flex items-center gap-2">
            <Shield className="w-6 h-6 text-emerald-400 flex-shrink-0" />
            What TO Do Instead
          </h2>
          <p className="text-gray-300 leading-relaxed text-base">
            The common thread in every crash survival story isn't bravery or genius. It's having
            a plan that was written before the crash started.
          </p>
        </div>

        {/* What TO Do Cards */}
        <div className="grid gap-4 my-8">
          <div className="bg-gray-900 border border-emerald-500/20 rounded-xl p-6">
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 rounded-lg bg-emerald-500/20 flex items-center justify-center flex-shrink-0">
                <span className="text-emerald-400 font-bold">1</span>
              </div>
              <div>
                <h3 className="text-white font-semibold mb-1">Have Rules BEFORE the Crash Happens</h3>
                <p className="text-gray-400 text-sm m-0">
                  Decide now — while you're calm — what you'll do when the market drops 10%, 20%, 30%.
                  Write it down. The worst time to build a fire escape is when the building is already
                  burning. A predefined system removes emotion from the equation entirely.
                </p>
              </div>
            </div>
          </div>
          <div className="bg-gray-900 border border-emerald-500/20 rounded-xl p-6">
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 rounded-lg bg-emerald-500/20 flex items-center justify-center flex-shrink-0">
                <span className="text-emerald-400 font-bold">2</span>
              </div>
              <div>
                <h3 className="text-white font-semibold mb-1">Use Trailing Stops That Execute Automatically</h3>
                <p className="text-gray-400 text-sm m-0">
                  A trailing stop follows a stock up and triggers a sell if it reverses by a set
                  percentage. You lock in gains as the stock rises, and exit automatically if the
                  trend breaks — no decision-making required in the moment. The key word is
                  "automatically." If you have to decide to sell, you probably won't.
                </p>
              </div>
            </div>
          </div>
          <div className="bg-gray-900 border border-emerald-500/20 rounded-xl p-6">
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 rounded-lg bg-emerald-500/20 flex items-center justify-center flex-shrink-0">
                <span className="text-emerald-400 font-bold">3</span>
              </div>
              <div>
                <h3 className="text-white font-semibold mb-1">Let Market Conditions Tell You When It's Safe</h3>
                <p className="text-gray-400 text-sm m-0">
                  Instead of guessing when the crash is over, use objective measures of market health.
                  A regime filter — based on actual market data, not opinions — can tell you whether
                  conditions favor being invested or sitting in cash. Re-enter when the data says so,
                  not when it "feels" right.
                </p>
              </div>
            </div>
          </div>
          <div className="bg-gray-900 border border-emerald-500/20 rounded-xl p-6">
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 rounded-lg bg-emerald-500/20 flex items-center justify-center flex-shrink-0">
                <span className="text-emerald-400 font-bold">4</span>
              </div>
              <div>
                <h3 className="text-white font-semibold mb-1">Doing Nothing IS a Strategy</h3>
                <p className="text-gray-400 text-sm m-0">
                  Staying in cash during a downturn isn't cowardice — it's capital preservation.
                  You don't earn style points for being fully invested during a crash. The investor
                  who sat in cash through 2022 and re-entered in early 2023 dramatically outperformed
                  the one who held through the entire drawdown.
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* 2022 Proof Highlight Box */}
        <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-6 my-8">
          <p className="text-amber-200 font-semibold text-lg m-0 mb-2">
            In 2022, the S&P 500 fell 20%. Our system gained 6%.
          </p>
          <p className="text-amber-200/80 m-0">
            Not because it predicted the crash — nobody did. But because it had rules
            in place before the crash happened. When market conditions deteriorated, the
            system moved to cash automatically. When conditions improved, it re-entered
            with discipline. No panic. No guessing. Just math.
          </p>
        </div>

        <div className="prose prose-invert prose-gray max-w-none">
          {/* The Math of Not Losing */}
          <h2 className="text-2xl font-bold text-white mt-12 mb-4 flex items-center gap-2">
            <TrendingDown className="w-6 h-6 text-red-400 flex-shrink-0" />
            The Math of Not Losing
          </h2>
          <p className="text-gray-300 leading-relaxed text-base">
            Here's something most investors don't think about until it's too late:
            losses are asymmetric. A 20% loss doesn't require a 20% gain to recover.
            It requires 25%. The deeper the hole, the harder it is to climb out.
          </p>
        </div>

        {/* Loss/Recovery Table */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden my-8">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800">
                <th className="text-left px-6 py-3 text-xs uppercase tracking-wider text-gray-500 font-semibold">Portfolio Loss</th>
                <th className="text-right px-6 py-3 text-xs uppercase tracking-wider text-gray-500 font-semibold">Gain Needed to Break Even</th>
                <th className="text-right px-6 py-3 text-xs uppercase tracking-wider text-gray-500 font-semibold hidden sm:table-cell">$10,000 Becomes</th>
              </tr>
            </thead>
            <tbody>
              {[
                { loss: '-10%', gain: '+11.1%', becomes: '$9,000' },
                { loss: '-20%', gain: '+25.0%', becomes: '$8,000' },
                { loss: '-30%', gain: '+42.9%', becomes: '$7,000' },
                { loss: '-40%', gain: '+66.7%', becomes: '$6,000' },
                { loss: '-50%', gain: '+100.0%', becomes: '$5,000', highlight: true },
              ].map((row) => (
                <tr key={row.loss} className={`border-b border-gray-800/50 ${row.highlight ? 'bg-red-500/10' : ''}`}>
                  <td className={`px-6 py-4 font-semibold ${row.highlight ? 'text-red-400' : 'text-red-400/80'}`}>{row.loss}</td>
                  <td className={`px-6 py-4 text-right font-semibold ${row.highlight ? 'text-amber-400' : 'text-amber-400/80'}`}>{row.gain}</td>
                  <td className="px-6 py-4 text-right text-gray-500 hidden sm:table-cell">{row.becomes}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="prose prose-invert prose-gray max-w-none">
          <p className="text-gray-300 leading-relaxed text-base">
            Lose 50% and you need to double your money just to get back to where you started.
            That could take years. Meanwhile, an investor who limited their drawdown to 10%
            only needs an 11% bounce — something the market delivers routinely in a single quarter.
          </p>

          {/* Highlight Box */}
          <div className="bg-blue-500/10 border border-blue-500/30 rounded-xl p-6 my-8">
            <p className="text-blue-200 font-semibold text-lg m-0 mb-2">
              The best offense in investing is not losing.
            </p>
            <p className="text-blue-200/80 m-0">
              Flashy returns in bull markets get the headlines. But over a full market cycle,
              the investor who avoids the big drawdowns almost always comes out ahead — even if
              their winning years are modest. Compounding doesn't work when you spend half the
              time digging out of a hole.
            </p>
          </div>

          {/* The Recovery Problem */}
          <h2 className="text-2xl font-bold text-white mt-12 mb-4 flex items-center gap-2">
            <Clock className="w-6 h-6 text-amber-400 flex-shrink-0" />
            The Recovery Problem: Missing the Best Days
          </h2>
          <p className="text-gray-300 leading-relaxed text-base">
            There's a cruel irony built into market crashes. The biggest single-day gains in
            market history happen during bear markets — often within days of the biggest drops.
            They're concentrated into a handful of explosive days that nobody can predict.
          </p>
          <p className="text-gray-300 leading-relaxed text-base">
            Studies of the S&P 500 over the last 20 years show that if you missed just the 10
            best trading days, your total return would be cut roughly in half. Miss the 20 best
            days and you'd barely break even. Miss 30, and you'd have lost money over two
            decades of market growth.
          </p>
          <p className="text-gray-300 leading-relaxed text-base">
            The problem? Those best days almost always come right after the worst days — during
            the exact moments when most investors have already sold. The investor who panic-sold
            in March 2020 missed the fastest recovery in market history. The investor who panicked
            out of 2022 missed the 2023 rally.
          </p>
          <p className="text-gray-300 leading-relaxed text-base">
            This is why "sell now and buy back later" sounds logical but almost never works in
            practice. You need a system that keeps you positioned correctly — out during genuine
            regime deterioration, back in when conditions genuinely improve — rather than one
            that relies on you making good decisions while terrified.
          </p>

          {/* The Real Lesson */}
          <h2 className="text-2xl font-bold text-white mt-12 mb-4 flex items-center gap-2">
            <TrendingUp className="w-6 h-6 text-emerald-400 flex-shrink-0" />
            The Real Lesson from Every Market Crash
          </h2>
          <p className="text-gray-300 leading-relaxed text-base">
            Every crash in history has eventually recovered. 1987, 2000, 2008, 2020, 2022 — every
            single one. The market always comes back. The question isn't whether it will recover.
            It's whether you'll still be invested when it does.
          </p>
          <p className="text-gray-300 leading-relaxed text-base">
            The investors who come out ahead aren't the ones who predicted the crash. They're the
            ones who had a system — rules that reduced exposure before the worst of the damage,
            and rules that guided them back in during the recovery. No emotion. No guessing.
            No watching CNBC at 2 AM trying to figure out what to do.
          </p>
          <p className="text-gray-300 leading-relaxed text-base">
            That's exactly what we built RigaCap to do. Our system uses a 7-regime market model
            that classifies conditions in real time. When conditions deteriorate, it reduces
            exposure automatically. When conditions improve, it re-enters with conviction. In 2022,
            while the S&P 500 lost 20%, our walk-forward validated system finished the year up 6%.
          </p>
          <p className="text-gray-300 leading-relaxed text-base">
            The next crash is coming. It always is. The only question is whether you'll face it
            with a plan or with a prayer.
          </p>
        </div>

        {/* CTA */}
        <div className="bg-gradient-to-br from-indigo-900/50 to-blue-900/50 border border-indigo-500/30 rounded-2xl p-8 sm:p-10 my-12 text-center">
          <h2 className="text-2xl sm:text-3xl font-bold text-white mb-3">
            Stop Trading on Emotions.<br />Start Trading on Math.
          </h2>
          <p className="text-blue-200/80 mb-6 max-w-lg mx-auto">
            RigaCap's system protected capital through 2022 — and has never had a losing year
            in 5 years of walk-forward validated testing. See the full results for yourself.
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
              <span className="block text-gray-500 text-sm mt-1">How trailing stops automatically protect gains when markets turn volatile.</span>
            </Link>
            <Link to="/blog/market-regime-guide" className="block p-4 bg-gray-900 rounded-lg border border-gray-800 hover:border-gray-600 transition-colors">
              <span className="text-white font-medium">Market Regime Trading: A Beginner's Guide</span>
              <span className="block text-gray-500 text-sm mt-1">Understanding market regimes helps you prepare before a crash hits.</span>
            </Link>
          </div>
        </div>

        {/* Disclaimer */}
        <p className="text-xs text-gray-600 leading-relaxed">
          All performance figures are from walk-forward simulations using historical market data.
          Past performance does not guarantee future results. RigaCap provides trading signals only —
          execute trades through your own brokerage account. This article is for educational purposes
          and does not constitute financial advice. See our{' '}
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
