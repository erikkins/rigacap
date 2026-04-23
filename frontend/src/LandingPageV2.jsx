import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import { useAuth } from './contexts/AuthContext';
import LoginModal from './components/LoginModal';
import MarketMeasuredSignup from './components/MarketMeasuredSignup';

const SectionLabel = ({ children }) => (
  <div className="flex items-center gap-3 mb-5">
    <span className="inline-block w-6 h-px bg-claret" />
    <span className="font-body text-[0.78rem] font-medium tracking-[0.18em] uppercase text-ink-mute">
      {children}
    </span>
  </div>
);

const LogoMark = () => (
  <svg className="w-7 h-7 relative top-[5px]" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 1024">
    <g transform="matrix(5.266369152845155 0 0 5.266369152845155 639.7474324688749 511.4611892669334)">
      <g>
        <g transform="matrix(0.447842401165958 0 0 0.447842401165958 -22.37905439059665 -28.76675371508702)"><path fill="#7A2430" transform="translate(-300.0291900499999, -285.76590730000004)" d="M 215.49 348.13 C 215.49 341.43 220.55 335.98 227.05 335.22 L 241.64 278.36 C 238.32 275.99 236.13 272.12 236.13 267.73 C 236.13 260.51 241.98 254.66 249.2 254.66 C 255.89 254.66 261.34 259.71 262.11 266.19 L 309.18 278.16 C 311.55 274.82 315.42 272.63 319.83 272.63 C 324 272.63 327.67 274.62 330.06 277.66 L 391.39 258.85 C 391.87 252.06 397.46 246.69 404.37 246.69 C 405.09 246.69 405.78 246.79 406.47 246.91 L 420.4 223.13 C 395.44 205.2 364.84 194.62 331.76 194.62 C 247.75 194.62 179.66 262.72 179.66 346.72 C 179.66 357.06 180.71 367.15 182.69 376.91 L 216.05 351.72 C 215.72 350.57 215.49 349.38 215.49 348.13 z"/></g>
        <g transform="matrix(0.447842401165958 0 0 0.447842401165958 -11.05489640960161 -8.986830154000359)"><path fill="#7A2430" transform="translate(-325.3152236000001, -329.93305964999996)" d="M 427.89 228.86 L 414.54 251.65 C 416.32 253.88 417.43 256.68 417.43 259.76 C 417.43 266.98 411.58 272.83 404.37 272.83 C 400.19 272.83 396.52 270.84 394.13 267.79 L 332.8 286.61 C 332.33 293.39 326.73 298.76 319.83 298.76 C 313.14 298.76 307.69 293.72 306.92 287.24 L 259.84 275.26 C 257.76 278.21 254.48 280.2 250.71 280.64 L 236.12 337.5 C 239.44 339.87 241.63 343.74 241.63 348.13 C 241.63 355.35 235.78 361.2 228.56 361.2 C 226.02 361.2 223.68 360.45 221.67 359.19 L 185.04 386.86 C 189.39 402.76 196.25 417.63 205.17 431 L 343.51 312.12 L 408.04 312.12 L 465.59 274.41 C 456.09 256.86 443.23 241.4 427.89 228.86 z"/></g>
        <g transform="matrix(0.447842401165958 0 0 0.447842401165958 73.82936460708436 -37.11089695025285)"><polygon fill="#7A2430" points="-45.31,-14.33 45.31,-39.44 -12.75,39.44 -17.06,3.28 "/></g>
        <g transform="matrix(0.447842401165958 0 0 0.447842401165958 -48.16632626991975 25.662112400608095)"><path fill="#141210" transform="translate(-242.44805925, -407.30166625000004)" d="M 297.69 513.38 C 291.85 512.18 286.13 510.68 280.53 508.91 L 280.53 405.3 L 233.16 446.01 L 233.16 485.18 C 189.93 454.31 161.67 403.77 161.67 346.72 C 161.67 321.48 167.23 297.53 177.14 275.97 L 153.41 275.97 C 144.69 297.88 139.84 321.74 139.84 346.72 C 139.84 452.54 225.93 538.63 331.76 538.63 C 336.23 538.63 340.66 538.42 345.06 538.12 L 345.06 349.85 L 297.69 390.55 L 297.69 513.38 z"/></g>
        <g transform="matrix(0.447842401165958 0 0 0.447842401165958 41.62493388227972 31.445543033824293)"><path fill="#141210" transform="translate(-442.94551085, -420.21565254999996)" d="M 523.16 333.38 L 501.27 333.38 C 501.62 337.79 501.85 342.23 501.85 346.72 C 501.85 381 491.63 412.92 474.11 439.65 L 474.11 304.24 L 426.75 335.28 L 426.75 487.65 C 421.24 491.37 415.52 494.78 409.58 497.85 L 409.58 341.74 L 362.22 341.74 L 362.22 536.19 C 453.61 521.55 523.67 442.17 523.67 346.72 C 523.67 342.23 523.46 337.79 523.16 333.38 z"/></g>
        <g transform="matrix(0.447842401165958 0 0 0.447842401165958 -11.758155759779243 -60.819370702594256)"><path fill="#141210" transform="translate(-323.7448958499999, -214.1947097)" d="M 331.75 169.32 C 390.45 169.32 442.58 197.98 474.89 242.04 L 483.06 239.78 C 449.46 192.37 394.16 161.37 331.75 161.37 C 258.06 161.37 194.28 204.6 164.43 267.02 L 173.29 267.02 C 202.53 209.12 262.58 169.32 331.75 169.32 z"/></g>
      </g>
    </g>
  </svg>
);

const Navbar = ({ onGetStarted }) => (
  <nav className="sticky top-0 z-50 bg-paper/95 backdrop-blur-sm border-b border-rule">
    <div className="max-w-[1120px] mx-auto px-4 sm:px-8 py-5 flex items-center justify-between">
      <Link to="/" className="flex items-baseline gap-2.5 no-underline">
        <LogoMark />
        <span className="font-display text-2xl font-semibold text-ink tracking-tight" style={{ fontVariationSettings: '"opsz" 144' }}>
          RigaCap<span className="text-claret">.</span>
        </span>
      </Link>
      <div className="flex items-center gap-9">
        <a href="/about" className="hidden sm:inline text-[0.9rem] text-ink-mute no-underline hover:text-ink transition-colors">About</a>
        <a href="/methodology" className="hidden sm:inline text-[0.9rem] text-ink-mute no-underline hover:text-ink transition-colors">Methodology</a>
        <a href="/track-record" className="hidden sm:inline text-[0.9rem] text-ink-mute no-underline hover:text-ink transition-colors">Track Record</a>
        <a href="#pricing" className="hidden sm:inline text-[0.9rem] text-ink-mute no-underline hover:text-ink transition-colors">Pricing</a>
        <button
          onClick={() => onGetStarted('founding')}
          className="bg-ink text-paper px-4 py-2.5 text-[0.9rem] font-medium rounded-[2px] hover:bg-claret transition-colors"
        >
          Start Trial
        </button>
      </div>
    </div>
  </nav>
);

const HeroSection = ({ onGetStarted }) => (
  <section className="bg-paper pt-16 pb-12 sm:pt-24 sm:pb-16">
    <div className="max-w-[920px] mx-auto px-4 sm:px-8">
      <SectionLabel>The Ensemble Strategy &middot; Est. 2026</SectionLabel>

      <h1
        className="font-display font-normal text-ink mb-8 tracking-[-0.025em] leading-[1.02]"
        style={{ fontSize: 'clamp(2.5rem, 5.5vw, 4.5rem)', fontVariationSettings: '"opsz" 144' }}
      >
        A disciplined momentum strategy that stays in cash when it should &mdash; and{' '}
        <em className="text-claret italic font-normal">exits</em> before major drawdowns.
      </h1>

      <p
        className="font-display italic text-ink-mute text-xl sm:text-[1.2rem] leading-relaxed max-w-[640px] mb-3"
        style={{ fontVariationSettings: '"opsz" 24' }}
      >
        Built for the investor who's tired of fighting their own worst instincts.
      </p>

      <p className="text-[0.95rem] text-ink-mute leading-relaxed max-w-[640px] mb-10">
        Walk-forward validated over 5 years. Built by a former <strong className="text-ink font-medium">Chief Innovation Officer</strong> with 15 years of quantitative research as a parallel practice. <strong className="text-ink font-medium">$129/month.</strong>
      </p>

      <div className="flex flex-wrap gap-4 items-center mb-0">
        <button
          onClick={() => onGetStarted('founding')}
          className="inline-block px-7 py-4 bg-ink text-paper text-[0.95rem] font-medium rounded-[2px] no-underline hover:bg-claret transition-all"
        >
          Claim a Founding Seat &middot; $59/mo
        </button>
        <a
          href="/methodology"
          className="inline-block px-7 py-4 border border-rule-dark text-ink text-[0.95rem] font-medium rounded-[2px] no-underline hover:border-ink transition-all"
        >
          See the methodology
        </a>
      </div>

      <div className="flex flex-wrap gap-12 mt-20 pt-8 border-t border-rule">
        {[
          ['~21.5%', 'Annualized, friction-adjusted'],
          ['Multi-date', 'Robustness tested'],
          ['138', 'Walk-forward periods'],
          ['4,000+', 'Stocks scanned daily'],
        ].map(([value, label]) => (
          <div key={label} className="text-[0.88rem] text-ink-mute leading-snug">
            <strong className="block font-display text-ink text-[1.05rem] font-medium mb-0.5" style={{ fontVariationSettings: '"opsz" 48' }}>
              {value}
            </strong>
            {label}
          </div>
        ))}
      </div>
    </div>
  </section>
);

const ValuePropSection = () => (
  <section className="bg-paper-card py-20 border-t border-rule">
    <div className="max-w-[800px] mx-auto px-4 sm:px-8">
      <SectionLabel>What You're Actually Paying For</SectionLabel>

      <p className="font-display text-[1.5rem] leading-[1.45] text-ink mb-7" style={{ fontVariationSettings: '"opsz" 48' }}>
        You can find signals anywhere. What's harder to find is the{' '}
        <em className="text-claret italic">discipline to follow them.</em>
      </p>

      <div className="space-y-5 text-[1.05rem] leading-[1.75] text-ink max-w-[62ch]">
        <p>
          Most retail investors are reasonably good at finding ideas and reliably bad at three specific things:{' '}
          <strong className="font-medium">sitting in cash when nothing is working, honoring stops without second-guessing,
          and not doubling down on losers.</strong> These are emotional discipline problems, not analytical ones.
          They're also the reason most self-directed trading underperforms the index.
        </p>
        <p>
          RigaCap is an external discipline layer. The system tells you when to enter, when to exit,
          and &mdash; just as importantly &mdash; when to do nothing. When a trailing stop hits,
          the position closes without the usual internal argument about whether it'll bounce back.
          When the seven-regime detector moves to cash, you don't have to summon the willpower to stay out of the market.
          A system you trust is already doing it for you.
        </p>
        <p>
          The hardest work of investing isn't the analysis. It's executing boring rules consistently.{' '}
          <em className="font-display italic text-claret">That's what you're paying for.</em>
        </p>
      </div>
    </div>
  </section>
);

const EdgeSection = () => (
  <section className="py-20 border-t border-rule">
    <div className="max-w-[1120px] mx-auto px-4 sm:px-8">
      <SectionLabel>The Edge</SectionLabel>
      <div className="max-w-[680px] mb-10">
        <h2 className="font-display text-ink mb-4 tracking-[-0.02em]" style={{ fontSize: 'clamp(1.8rem, 3.5vw, 2.75rem)', fontVariationSettings: '"opsz" 96' }}>
          Three pieces of discipline.<br /><em className="text-claret italic">All must align.</em>
        </h2>
      </div>

      <div className="grid md:grid-cols-3 gap-10 mt-12">
        {[
          {
            num: 'Ⅰ / DISCIPLINE',
            title: 'Knows when not to trade.',
            text: <>Seven-regime market detection continuously classifies conditions from Strong Bull to Panic/Crash. When regimes deteriorate, the system reduces exposure or moves to cash &mdash; systematically, without waiting for confirmation. <strong className="font-medium text-ink">Most months, the system generates few or no signals.</strong> That discipline is the product.</>,
          },
          {
            num: 'Ⅱ / ENSEMBLE',
            title: 'Three factors, all must align.',
            text: <>Timing (breakout detection), momentum quality (top-ranked names only), and adaptive risk management (trailing stops, regime-aware position sizing). A signal requires <strong className="font-medium text-ink">all three</strong>. The system stays quiet when they don't &mdash; which is more often than most traders expect.</>,
          },
          {
            num: 'Ⅲ / HONESTY',
            title: 'Published methodology. Disclosed assumptions.',
            text: <>Walk-forward process, optimization parameters, universe filters, and execution assumptions are all public. Where simulation assumptions favor the results &mdash; zero slippage, zero commissions &mdash; that's <strong className="font-medium text-ink">called out explicitly rather than buried.</strong></>,
          },
        ].map(({ num, title, text }) => (
          <div key={num}>
            <span className="block font-mono text-[0.75rem] font-medium tracking-[0.1em] text-claret mb-2">{num}</span>
            <h3 className="font-display text-[1.5rem] font-medium text-ink mb-4 tracking-[-0.015em]" style={{ fontVariationSettings: '"opsz" 72' }}>
              {title}
            </h3>
            <p className="text-ink-mute text-[0.98rem] leading-[1.65]">{text}</p>
          </div>
        ))}
      </div>
    </div>
  </section>
);

const PerformanceSection = () => (
  <section className="py-20 border-t border-rule">
    <div className="max-w-[1120px] mx-auto px-4 sm:px-8">
      <SectionLabel>Performance</SectionLabel>
      <div className="max-w-[680px] mb-6">
        <h2 className="font-display text-ink mb-4 tracking-[-0.02em]" style={{ fontSize: 'clamp(1.8rem, 3.5vw, 2.75rem)', fontVariationSettings: '"opsz" 96' }}>
          Five-year walk-forward results.
        </h2>
        <p className="text-ink-mute text-[1.05rem] leading-[1.65]">
          Tested across multiple start dates in early 2021 to check robustness.
          All three outcomes published &mdash; best, average, and worst.
        </p>
      </div>

      <div className="overflow-x-auto my-10">
        <table className="w-full border-collapse" style={{ fontFeatureSettings: '"tnum"' }}>
          <thead>
            <tr>
              {['Series', '5-Year Return', 'Annualized', 'Sharpe', 'Max Drawdown'].map((h, i) => (
                <th key={h} className={`py-3 ${i === 0 ? 'text-left pr-4' : 'text-right px-5'} font-body font-medium text-[0.75rem] tracking-[0.15em] uppercase text-ink-mute border-b border-rule-dark`}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr className="border-b border-rule">
              <td className="py-4 pr-4 text-[0.95rem]">Simulation (avg. of multiple start dates)</td>
              <td className="py-4 px-5 text-right font-mono text-[0.95rem]">+204%</td>
              <td className="py-4 px-5 text-right font-mono text-[0.95rem]">~23%</td>
              <td className="py-4 px-5 text-right font-mono text-[0.95rem]">0.95</td>
              <td className="py-4 px-5 text-right font-mono text-[0.95rem]">32%</td>
            </tr>
            <tr className="border-b border-rule bg-paper-card">
              <td className="py-4 pr-4 text-[0.95rem] font-semibold text-ink">Friction-adjusted estimate</td>
              <td className="py-4 px-5 text-right font-mono text-[0.95rem] font-medium text-ink">+173%</td>
              <td className="py-4 px-5 text-right font-mono text-[0.95rem] font-medium text-ink">~21.5%</td>
              <td className="py-4 px-5 text-right font-mono text-[0.95rem] text-ink-mute">&mdash;</td>
              <td className="py-4 px-5 text-right font-mono text-[0.95rem] text-ink-mute">&mdash;</td>
            </tr>
            <tr>
              <td className="py-4 pr-4 text-[0.95rem] italic text-ink-mute">S&P 500 (SPY, price only)</td>
              <td className="py-4 px-5 text-right font-mono text-[0.95rem] text-ink-mute">+84%</td>
              <td className="py-4 px-5 text-right font-mono text-[0.95rem] text-ink-mute">~13%</td>
              <td className="py-4 px-5 text-right font-mono text-[0.95rem] text-ink-mute">&mdash;</td>
              <td className="py-4 px-5 text-right font-mono text-[0.95rem] text-ink-mute">&mdash;</td>
            </tr>
          </tbody>
        </table>
      </div>

      <p className="text-[0.85rem] text-ink-mute leading-relaxed">
        Friction-adjusted figures estimate realistic slippage and commissions. Simulation assumes zero of both and uses end-of-day prices &mdash; see{' '}
        <a href="/methodology" className="text-claret underline underline-offset-2 decoration-1">methodology</a> for all assumptions and the best/worst range across start dates.
      </p>

      <div className="bg-paper-card border-l-[3px] border-claret p-8 mt-12 max-w-[62ch]">
        <h3 className="font-display text-[1.15rem] font-semibold text-ink mb-3" style={{ fontVariationSettings: '"opsz" 48' }}>
          The bear-market test.
        </h3>
        <p className="text-ink leading-[1.7]">
          The five-year window included one major bear market. The system ended it flat while the S&P fell 20% &mdash;{' '}
          <strong className="font-medium">not by luck, but by design.</strong> Regime detection triggered de-risking before the drawdown
          and kept the system in cash until conditions improved.{' '}
          <em className="font-display italic text-claret">That behavior, not the headline return, is the reason to subscribe.</em>
        </p>
      </div>

      <div className="mt-10">
        <a href="/track-record" className="font-display italic text-[1.1rem] text-claret no-underline border-b border-claret pb-0.5 hover:text-claret-light hover:border-claret-light transition-colors">
          View full track record →
        </a>
      </div>
    </div>
  </section>
);

const FounderSection = () => (
  <section className="bg-paper-deep py-20 border-t border-rule">
    <div className="max-w-[1120px] mx-auto px-4 sm:px-8">
      <div className="grid md:grid-cols-[1fr_2fr] gap-16 items-start">
        <div className="w-full max-w-[280px] aspect-square border border-rule overflow-hidden">
          <img
            src="/erikheadshot.jpg"
            alt="Erik Kins, founder of RigaCap"
            className="w-full h-full object-cover object-top"
          />
        </div>
        <div>
          <SectionLabel>Who Built This</SectionLabel>
          <h2 className="font-display text-ink font-normal mb-6 tracking-[-0.02em]" style={{ fontSize: 'clamp(1.8rem, 3.5vw, 2.75rem)', fontVariationSettings: '"opsz" 96' }}>
            One <em className="text-claret italic">quant researcher,</em> working solo by choice.
          </h2>
          <div className="space-y-5 text-ink text-[1.05rem] leading-[1.7] max-w-[58ch]">
            <p>
              RigaCap is a solo project. I'm <strong className="font-medium">Erik Kins</strong> &mdash; former Chief Innovation Officer
              at a $1.5B publicly traded healthcare software company, where I led new product development and technology strategy.
              I ran quantitative research as a parallel practice for 15 years before turning it into this product.
            </p>
            <p>
              There's no team, no outside capital, and no marketing department. That's the point.
              The Ensemble strategy is what I'd been running privately. RigaCap is the version I'm willing to put my name on.
            </p>
          </div>
          <a href="/about" className="inline-block mt-8 px-7 py-4 border border-rule-dark text-ink text-[0.95rem] font-medium rounded-[2px] no-underline hover:border-ink transition-all">
            More about me →
          </a>
        </div>
      </div>
    </div>
  </section>
);

const HowItWorksSection = () => (
  <section className="py-20 border-t border-rule">
    <div className="max-w-[1120px] mx-auto px-4 sm:px-8">
      <SectionLabel>How It Works</SectionLabel>
      <h2 className="font-display text-ink mb-4 tracking-[-0.02em]" style={{ fontSize: 'clamp(1.8rem, 3.5vw, 2.75rem)', fontVariationSettings: '"opsz" 96' }}>
        From signal to <em className="text-claret italic">execution.</em>
      </h2>

      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6 mt-12">
        {[
          { title: 'Scan', text: 'Algorithms evaluate ~6,500 US stocks daily, filtered to ~4,000 that meet liquidity and price criteria.' },
          { title: 'Signal', text: 'When timing, momentum, and risk all align, subscribers receive an alert with entry, stop, and target levels.' },
          { title: 'Execute', text: 'You place the trade through your own broker. RigaCap never touches your capital.' },
          { title: 'Exit', text: 'Trailing stops manage risk automatically. Regime changes trigger systematic de-risking.' },
        ].map(({ title, text }, i) => (
          <div key={title} className="border-t border-rule-dark pt-8 relative" style={{ counterIncrement: 'step' }}>
            <span className="block font-mono text-[0.75rem] font-medium tracking-[0.1em] text-claret mb-4">
              {String(i + 1).padStart(2, '0')}
            </span>
            <h3 className="font-display text-[1.4rem] font-medium text-ink mb-2" style={{ fontVariationSettings: '"opsz" 72' }}>
              {title}
            </h3>
            <p className="text-ink-mute text-[0.95rem] leading-relaxed">{text}</p>
          </div>
        ))}
      </div>
    </div>
  </section>
);

const PricingSection = ({ onGetStarted }) => (
  <section id="pricing" className="py-20 border-t border-rule">
    <div className="max-w-[1120px] mx-auto px-4 sm:px-8">
      <SectionLabel>Pricing</SectionLabel>
      <div className="max-w-[680px] mb-4">
        <h2 className="font-display text-ink mb-4 tracking-[-0.02em]" style={{ fontSize: 'clamp(1.8rem, 3.5vw, 2.75rem)', fontVariationSettings: '"opsz" 96' }}>
          Two paths in. <em className="text-claret italic">Cancel anytime.</em>
        </h2>
        <p className="text-ink-mute text-[1.05rem] leading-[1.65]">
          The standard rate reflects the value delivered to a self-directed investor with a meaningful portfolio.
          The founding rate rewards the first 100 subscribers with a locked-in price while the live track record is being built.
        </p>
      </div>

      <div className="grid sm:grid-cols-2 gap-8 mt-12 max-w-[860px]">
        {/* Founding — Featured */}
        <div className="bg-paper-card border-2 border-claret p-10 flex flex-col relative">
          <span className="absolute -top-3 left-8 bg-claret text-paper text-[0.7rem] font-medium tracking-[0.15em] uppercase px-3 py-1">
            Founding &middot; First 100
          </span>
          <h3 className="font-display text-[1.3rem] font-medium text-ink mb-1" style={{ fontVariationSettings: '"opsz" 72' }}>Founding Member</h3>
          <p className="font-display italic text-ink-mute text-[0.92rem] mb-6" style={{ fontVariationSettings: '"opsz" 24' }}>For those who sign up first.</p>
          <div className="mb-1">
            <span className="font-display text-[3.5rem] font-normal text-ink leading-none tracking-tight" style={{ fontVariationSettings: '"opsz" 144' }}>$59</span>
            <span className="text-ink-mute text-[0.95rem] ml-1">/month</span>
          </div>
          <p className="text-ink-mute text-[0.9rem] leading-relaxed mt-3">
            Locked at this rate for <strong className="text-claret font-medium">12 months.</strong> Transitions to $129/month afterward. Only <strong className="text-claret font-medium">100 founding seats</strong> &mdash; then it closes.
          </p>
          <ul className="list-none my-7 pt-6 border-t border-rule flex-1 space-y-1.5">
            {['Everything in the standard plan', 'Direct reply line to Erik', 'Grandfathered access to future features', 'Recognition as a founding subscriber', 'Your feedback shapes the product'].map(item => (
              <li key={item} className="text-ink-mute text-[0.92rem] pl-5 relative before:content-['—'] before:absolute before:left-0 before:text-claret">{item}</li>
            ))}
          </ul>
          <button
            onClick={() => onGetStarted('founding')}
            className="w-full py-4 bg-ink text-paper text-[0.95rem] font-medium rounded-[2px] text-center hover:bg-claret transition-colors"
          >
            Claim a Founding Seat
          </button>
          <p className="text-center font-mono text-[0.72rem] text-claret tracking-[0.1em] uppercase mt-3">~87 of 100 seats remaining</p>
        </div>

        {/* Standard */}
        <div className="bg-paper-card border border-rule p-10 flex flex-col">
          <h3 className="font-display text-[1.3rem] font-medium text-ink mb-1" style={{ fontVariationSettings: '"opsz" 72' }}>Standard</h3>
          <p className="font-display italic text-ink-mute text-[0.92rem] mb-6" style={{ fontVariationSettings: '"opsz" 24' }}>Available once founding seats close.</p>
          <div className="mb-1">
            <span className="font-display text-[3.5rem] font-normal text-ink leading-none tracking-tight" style={{ fontVariationSettings: '"opsz" 144' }}>$129</span>
            <span className="text-ink-mute text-[0.95rem] ml-1">/month</span>
          </div>
          <p className="text-ink-mute text-[0.9rem] leading-relaxed mt-3">
            Or <strong className="text-claret font-medium">$1,099/year</strong> billed annually &mdash; three months free.
          </p>
          <ul className="list-none my-7 pt-6 border-t border-rule flex-1 space-y-1.5">
            {['Unlimited real-time signals', 'Daily email digest', 'Entry, stop, and target levels', 'Seven-regime market context', 'Portfolio tracking dashboard', '4,000+ stocks scanned daily', 'Full methodology access'].map(item => (
              <li key={item} className="text-ink-mute text-[0.92rem] pl-5 relative before:content-['—'] before:absolute before:left-0 before:text-claret">{item}</li>
            ))}
          </ul>
          <button
            onClick={() => onGetStarted('monthly')}
            className="w-full py-4 border border-ink text-ink text-[0.95rem] font-medium rounded-[2px] text-center hover:bg-ink hover:text-paper transition-colors"
          >
            Start 7-Day Free Trial
          </button>
          <p className="text-center text-[0.8rem] text-ink-light mt-3">Credit card required &middot; Cancel anytime</p>
        </div>
      </div>
    </div>
  </section>
);

const faqItems = [
  { q: 'Who is this for?', a: "Self-directed investors with meaningful portfolios who've decided indexing alone is too passive and individual active trading has been too emotional. If you've tried to run your own momentum strategy and found yourself overriding your own rules, this is a system that will do the boring parts consistently whether you feel like it or not." },
  { q: 'What returns should I actually expect?', a: "The simulation average is ~23% annualized. After estimating realistic slippage and commissions, that figure drops to roughly 21.5% — still meaningfully above the S&P's historical average, but lower than the raw simulation. Your actual results will vary based on execution quality, position sizing, and consistency. Past performance does not predict future results. Read the methodology page before subscribing." },
  { q: 'Why publish the lower number?', a: "Because that's the number a subscriber will actually experience. Most signal services publish zero-friction simulation results as their headline figure without disclosing the bias. I'd rather set a realistic expectation and have you stick around than advertise a number you can't reproduce." },
  { q: 'Why $129/month?', a: "Because it reflects the value delivered. On a $100K portfolio targeting 21.5% annualized returns versus SPY's ~13% historical, the potential uplift is around $8,500/year. $1,548/year in subscription cost captures less than 20% of that value — less than what a traditional financial advisor takes in fees." },
  { q: 'How many signals do you generate?', a: "On average, 3–4 high-conviction signals per month from a universe of 4,000+ stocks. When conditions aren't right, the system stays quiet — that discipline is a meaningful part of why it outperforms." },
  { q: 'Has the system ever had a down year?', a: "No losing year over the full 5-year walk-forward. The closest was 2022 at −0.4% (essentially flat) while the S&P fell 20%. In 2024, the system returned +1.2% — positive, but below the S&P. The system is built for broad momentum, not concentrated bets on the Magnificent 7." },
  { q: 'If it works this well, why sell signals instead of running a fund?', a: "Running a fund requires regulatory infrastructure, institutional capital, and a 2+ year live track record — I'm building that now. In the meantime, signals let me prove the system in live markets with real subscribers while bootstrapping. You get access to the same engine I'll eventually deploy with my own capital." },
  { q: 'Can I cancel anytime?', a: 'Yes. No contracts, no commitments. Cancel from your account settings at any time; access continues until the end of your billing period.' },
  { q: 'Do you provide financial advice?', a: 'No. RigaCap provides algorithmic signals and educational information only. RigaCap is not a registered investment advisor. Always do your own research and consider consulting a licensed professional before making investment decisions.' },
];

const FAQSection = () => (
  <section className="py-20 border-t border-rule">
    <div className="max-w-[1120px] mx-auto px-4 sm:px-8">
      <SectionLabel>Frequently Asked</SectionLabel>
      <h2 className="font-display text-ink mb-4 tracking-[-0.02em]" style={{ fontSize: 'clamp(1.8rem, 3.5vw, 2.75rem)', fontVariationSettings: '"opsz" 96' }}>
        Questions, <em className="text-claret italic">honestly answered.</em>
      </h2>
      <div className="mt-12 max-w-[720px]">
        {faqItems.map(({ q, a }) => (
          <details key={q} className="border-t border-rule py-6 group last:border-b">
            <summary className="font-display text-[1.2rem] font-medium text-ink cursor-pointer list-none flex justify-between items-center gap-8 tracking-[-0.01em]" style={{ fontVariationSettings: '"opsz" 72' }}>
              {q}
              <span className="font-mono text-claret text-[1.4rem] font-normal shrink-0 group-open:hidden">+</span>
              <span className="font-mono text-claret text-[1.4rem] font-normal shrink-0 hidden group-open:inline">&minus;</span>
            </summary>
            <p className="mt-4 text-ink-mute leading-[1.7] text-[0.98rem] max-w-[60ch]">{a}</p>
          </details>
        ))}
      </div>
    </div>
  </section>
);

const CTASection = ({ onGetStarted }) => (
  <section className="bg-ink py-20">
    <div className="max-w-3xl mx-auto px-4 sm:px-8 text-center">
      <h2 className="font-display text-paper text-3xl mb-4 tracking-tight" style={{ fontVariationSettings: '"opsz" 96' }}>
        Stop fighting your own worst instincts.
      </h2>
      <p className="font-body text-paper/60 mb-8">
        7-day free trial. Full access. Cancel anytime.
      </p>
      <button
        onClick={() => onGetStarted('founding')}
        className="inline-block px-8 py-4 bg-paper text-ink text-[0.95rem] font-medium rounded-[2px] hover:bg-paper-deep transition-colors"
      >
        Claim a Founding Seat &middot; $59/mo
      </button>
    </div>
  </section>
);

const Footer = () => (
  <footer className="bg-paper-deep border-t border-rule pt-16 pb-8">
    <div className="max-w-[1120px] mx-auto px-4 sm:px-8">
      <div className="grid sm:grid-cols-2 lg:grid-cols-[2fr_1fr_1fr_1fr] gap-12 pb-12 border-b border-rule">
        <div>
          <Link to="/" className="font-display text-[1.4rem] font-semibold text-ink no-underline" style={{ fontVariationSettings: '"opsz" 144' }}>
            RigaCap<span className="text-claret">.</span>
          </Link>
          <p className="mt-4 text-[0.9rem] text-ink-mute leading-relaxed max-w-[32ch]">
            Ensemble trading signals. The market, measured. Built by one quant researcher, shipping honestly.
          </p>
        </div>
        <div>
          <h4 className="font-body text-[0.75rem] font-medium tracking-[0.15em] uppercase text-ink mb-4">Product</h4>
          <ul className="space-y-2">
            {[['Methodology', '/methodology'], ['Track Record', '/track-record'], ['Pricing', '#pricing']].map(([label, href]) => (
              <li key={label}><a href={href} className="text-ink-mute text-[0.92rem] no-underline hover:text-ink transition-colors">{label}</a></li>
            ))}
          </ul>
        </div>
        <div>
          <h4 className="font-body text-[0.75rem] font-medium tracking-[0.15em] uppercase text-ink mb-4">Company</h4>
          <ul className="space-y-2">
            {[['About', '/about'], ['Newsletter', '#newsletter'], ['Blog', '/blog'], ['Contact', '/contact']].map(([label, href]) => (
              <li key={label}><a href={href} className="text-ink-mute text-[0.92rem] no-underline hover:text-ink transition-colors">{label}</a></li>
            ))}
          </ul>
        </div>
        <div>
          <h4 className="font-body text-[0.75rem] font-medium tracking-[0.15em] uppercase text-ink mb-4">Legal</h4>
          <ul className="space-y-2">
            {[['Terms', '/terms'], ['Privacy', '/privacy'], ['Disclaimer', '/disclaimer']].map(([label, href]) => (
              <li key={label}><Link to={href} className="text-ink-mute text-[0.92rem] no-underline hover:text-ink transition-colors">{label}</Link></li>
            ))}
          </ul>
        </div>
      </div>
      <div className="pt-8 flex flex-col sm:flex-row justify-between items-start gap-8">
        <p className="text-[0.78rem] text-ink-light leading-relaxed max-w-[70ch]">
          Trading involves risk. Past performance is not indicative of future results. All performance figures are derived from walk-forward simulations using historical data and do not represent actual trading returns. RigaCap provides algorithmic signals for educational purposes only and is not a registered investment advisor.
        </p>
        <p className="text-[0.78rem] text-ink-light shrink-0">&copy; 2026 RigaCap, LLC</p>
      </div>
    </div>
  </footer>
);

export default function LandingPageV2() {
  const navigate = useNavigate();
  const { isAuthenticated, loading } = useAuth();
  const [showLoginModal, setShowLoginModal] = useState(false);
  const [selectedPlan, setSelectedPlan] = useState('monthly');

  const isReturningVisitor = localStorage.getItem('rigacap_returning') === 'true';
  useEffect(() => { localStorage.setItem('rigacap_returning', 'true'); }, []);
  useEffect(() => {
    if (!loading && isAuthenticated) navigate('/app', { replace: true });
  }, [isAuthenticated, loading, navigate]);

  const handleGetStarted = (plan = 'monthly') => {
    if (isAuthenticated) {
      navigate('/app', { replace: true });
    } else {
      setSelectedPlan(plan);
      setShowLoginModal(true);
    }
  };

  return (
    <div className="min-h-screen bg-paper font-body text-ink text-[17px] leading-[1.65] antialiased">
      <Navbar onGetStarted={handleGetStarted} />
      <HeroSection onGetStarted={handleGetStarted} />
      <ValuePropSection />
      <EdgeSection />
      <PerformanceSection />
      <FounderSection />
      <HowItWorksSection />
      <PricingSection onGetStarted={handleGetStarted} />
      <FAQSection />

      <section id="newsletter" className="bg-paper-card py-16 border-t border-rule">
        <div className="max-w-3xl mx-auto px-4 sm:px-8">
          <MarketMeasuredSignup source="landing_v2" />
        </div>
      </section>

      <CTASection onGetStarted={handleGetStarted} />
      <Footer />

      {showLoginModal && (
        <LoginModal
          onClose={() => setShowLoginModal(false)}
          onSuccess={() => { setShowLoginModal(false); navigate('/app', { replace: true }); }}
          initialMode={isReturningVisitor ? 'login' : 'register'}
          selectedPlan={selectedPlan}
        />
      )}
    </div>
  );
}
