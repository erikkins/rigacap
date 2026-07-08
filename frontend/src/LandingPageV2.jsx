import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import { useAuth } from './contexts/AuthContext';
import LoginModal from './components/LoginModal';
import MarketMeasuredSignup from './components/MarketMeasuredSignup';
import TopNav from './components/TopNav';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';
// Show the live seat counter only once it's genuinely scarce — below this many
// remaining. Above it we keep the honest "First 100" framing with NO raw number,
// so we never show "100 seats available" for weeks (Erik Jun 23). Tunable.
const FOUNDING_SCARCITY_THRESHOLD = 40;

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

// The Risk Knob — a knurled amp/guitar volume knob with a gold pointer, numbers 1→11
// (1 = lower-left/Preserve, 11 = lower-right/Maximize). Secret nods: a metal umlaut over
// the 11 (Spın̈al Tap — never stated in copy) and a "RIGACAP" maker's mark on the face.
const RiskKnob = ({ size = 340, pointer = 0.62 }) => {
  const cx = size / 2, cy = size / 2;
  const Rnum = size * 0.45, Rto = size * 0.378, Rti = size * 0.338, Rbody = size * 0.255, Rcollar = Rbody * 1.18;
  const pos = (f, r) => { const a = (-135 + f * 270) * Math.PI / 180; return [cx + r * Math.sin(a), cy - r * Math.cos(a)]; };
  const face = [];
  for (let i = 0; i < 11; i++) {
    const f = i / 10, is11 = i === 10;
    const [x1, y1] = pos(f, Rti), [x2, y2] = pos(f, Rto), [nx, ny] = pos(f, Rnum);
    const fs = is11 ? 19 : 15, col = is11 ? '#7A2430' : '#141210';
    face.push(<line key={`t${i}`} x1={x1} y1={y1} x2={x2} y2={y2} stroke={col} strokeWidth={is11 ? 3.6 : 2.4} strokeLinecap="round" />);
    face.push(<text key={`n${i}`} x={nx} y={ny + fs * 0.35} textAnchor="middle" fontFamily="Fraunces,Georgia,serif" fontSize={fs} fontWeight={is11 ? 700 : 600} fill={col}>{i + 1}</text>);
    if (is11) {
      const uy = ny - fs * 0.66;
      face.push(<circle key="u1" cx={nx - 3.6} cy={uy} r={1.8} fill="#7A2430" />);
      face.push(<circle key="u2" cx={nx + 3.6} cy={uy} r={1.8} fill="#7A2430" />);
    }
  }
  const knurl = [];
  for (let k = 0; k < 52; k++) {
    const a = (k * 360 / 52) * Math.PI / 180, r1 = Rbody, r2 = Rcollar * 0.985;
    knurl.push(<line key={`k${k}`} x1={cx + r1 * Math.cos(a)} y1={cy + r1 * Math.sin(a)} x2={cx + r2 * Math.cos(a)} y2={cy + r2 * Math.sin(a)} stroke="#000" strokeOpacity={0.38} strokeWidth={1.4} />);
  }
  const [ix, iy] = pos(pointer, Rbody * 0.9), [mx, my] = pos(pointer, Rbody * 0.16);
  return (
    <svg viewBox={`0 0 ${size} ${size}`} className="w-full h-auto" xmlns="http://www.w3.org/2000/svg" aria-label="Risk dial from Preserve to Maximize">
      <defs>
        <filter id="knobSh" x="-50%" y="-50%" width="200%" height="200%"><feDropShadow dx="0" dy="8" stdDeviation="10" floodColor="#000" floodOpacity="0.35" /></filter>
        <radialGradient id="knobDome" cx="38%" cy="28%" r="82%"><stop offset="0%" stopColor="#43392f" /><stop offset="42%" stopColor="#241e18" /><stop offset="100%" stopColor="#0a0806" /></radialGradient>
        <radialGradient id="knobCollar" cx="40%" cy="28%" r="85%"><stop offset="0%" stopColor="#9a9082" /><stop offset="48%" stopColor="#5c554b" /><stop offset="100%" stopColor="#241f1a" /></radialGradient>
        <radialGradient id="knobSpec" cx="50%" cy="50%" r="50%"><stop offset="0%" stopColor="#ffffff" stopOpacity="0.55" /><stop offset="100%" stopColor="#ffffff" stopOpacity="0" /></radialGradient>
      </defs>
      {face}
      <circle cx={cx} cy={cy} r={Rcollar} fill="url(#knobCollar)" filter="url(#knobSh)" />
      {knurl}
      <circle cx={cx} cy={cy} r={Rcollar} fill="none" stroke="#ffffff" strokeOpacity={0.14} strokeWidth={1} />
      <circle cx={cx} cy={cy} r={Rbody} fill="url(#knobDome)" stroke="#000000" strokeOpacity={0.45} strokeWidth={1} />
      <circle cx={cx} cy={cy} r={Rbody - 1.5} fill="none" stroke="#ffffff" strokeOpacity={0.1} strokeWidth={2} />
      <ellipse cx={cx - Rbody * 0.3} cy={cy - Rbody * 0.34} rx={Rbody * 0.52} ry={Rbody * 0.34} fill="url(#knobSpec)" />
      <line x1={mx} y1={my} x2={ix} y2={iy} stroke="#EFD177" strokeWidth={5.5} strokeLinecap="round" />
      <line x1={mx} y1={my} x2={ix} y2={iy} stroke="#ffffff" strokeOpacity={0.45} strokeWidth={1.7} strokeLinecap="round" />
      <circle cx={cx} cy={cy} r={6.5} fill="#141210" />
      <circle cx={cx} cy={cy} r={6.5} fill="none" stroke="#6f6555" strokeWidth={1} />
      <text x={cx} y={cy + Rbody * 0.6} textAnchor="middle" fontFamily="IBM Plex Sans,sans-serif" fontSize={8.5} letterSpacing={2.5} fill="#a49a8c" opacity={0.7}>RIGACAP</text>
    </svg>
  );
};

const Navbar = ({ onGetStarted }) => <TopNav onGetStarted={onGetStarted} />;

const HeroSection = ({ onGetStarted }) => (
  <section className="bg-paper pt-14 pb-12 sm:pt-20 sm:pb-16 overflow-x-clip">
    <div className="max-w-[1120px] mx-auto px-4 sm:px-8">
      <div className="grid grid-cols-1 lg:grid-cols-[1.12fr_0.88fr] gap-10 lg:gap-10 items-center">
        {/* left — the copy: WHAT IT IS first, then the hook */}
        <div>
          <span className="inline-block font-body text-[0.7rem] font-bold tracking-[0.14em] uppercase text-paper bg-claret px-3 py-1.5 rounded-[2px]">
            Buy/Sell Signals &middot; You Execute
          </span>
          <div className="font-body text-[0.78rem] font-semibold tracking-[0.2em] uppercase text-ink-mute mt-4">
            The Systematic Trading System
          </div>
          <h1
            className="font-display font-normal text-ink mt-3 mb-5 tracking-[-0.025em] leading-[1.02]"
            style={{ fontSize: 'clamp(2.6rem, 5.2vw, 4rem)', fontVariationSettings: '"opsz" 144' }}
          >
            One knob.<br />
            <em className="text-claret not-italic">Preserve to Maximize.</em>
          </h1>
          <p className="text-ink-mute text-[1.12rem] sm:text-[1.18rem] leading-[1.5] max-w-[540px] mb-7">
            RigaCap sends you the <strong className="text-ink font-medium">buy and sell calls</strong> from one engine that reads the market and adapts. Turn it down to guard what you&rsquo;ve built, up to add offense &mdash; <strong className="text-ink font-medium">you set the level, you execute at your broker.</strong>
          </p>
          <div className="flex flex-col sm:flex-row sm:flex-wrap gap-3 sm:gap-4 sm:items-center mb-7">
            <button
              onClick={() => onGetStarted('founding')}
              className="w-full sm:w-auto text-center px-7 py-4 bg-claret text-paper text-[1.02rem] font-medium rounded-[2px] no-underline hover:bg-claret-light transition-all"
            >
              Join the founding list
            </button>
            <a
              href="/track-record"
              className="w-full sm:w-auto text-center px-7 py-4 border border-rule-dark text-ink text-[1.02rem] font-medium rounded-[2px] no-underline hover:border-ink transition-all"
            >
              See how it works
            </a>
          </div>
          <div className="text-[0.86rem] text-ink-light leading-relaxed">
            <strong className="inline-block whitespace-nowrap text-ink-mute font-medium">&#8531; the market&rsquo;s worst drawdown</strong>
            <span className="text-rule-dark mx-2">&middot;</span><span className="inline-block whitespace-nowrap">Two decades, every regime</span>
          </div>
        </div>

        {/* right — the risk dial, each end showing its backtested profile */}
        <div className="flex justify-center lg:justify-end">
          <div className="w-full max-w-[380px] bg-paper-deep rounded-lg border border-rule px-7 py-8 flex flex-col items-center">
            <div className="w-full max-w-[300px]">
              <RiskKnob size={340} pointer={0.62} />
            </div>
            <div className="flex justify-between items-start w-full max-w-[330px] mt-5">
              <div className="text-center flex-1">
                <div className="font-display font-semibold uppercase tracking-[0.03em] text-[0.95rem] text-positive">Preserve</div>
                <div className="font-display text-ink text-[1.55rem] font-medium leading-none mt-1.5" style={{ fontVariationSettings: '"opsz" 48' }}>
                  +31%<span className="text-ink-light text-[0.8rem] font-normal">/yr</span>
                </div>
                <div className="text-ink-light text-[0.78rem] mt-1">&minus;13% worst</div>
              </div>
              <div className="w-px self-stretch bg-rule-dark mx-2" />
              <div className="text-center flex-1">
                <div className="font-display font-semibold uppercase tracking-[0.03em] text-[0.95rem] text-claret">Maximize</div>
                <div className="font-display text-ink text-[1.55rem] font-medium leading-none mt-1.5" style={{ fontVariationSettings: '"opsz" 48' }}>
                  +49%<span className="text-ink-light text-[0.8rem] font-normal">/yr</span>
                </div>
                <div className="text-ink-light text-[0.78rem] mt-1">&minus;17% worst</div>
              </div>
            </div>
            <div className="text-ink-light text-[0.72rem] text-center mt-4 leading-snug">
              Last 2 years, walk-forward &middot; both tiers launch this month
            </div>
          </div>
        </div>
      </div>

      {/* SURFACE-MARKER:landing-hero-stats-START */}
      {/* Honest proof retained beneath the hero (backtest-labeled). */}
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-x-8 gap-y-7 pt-10 mt-12 border-t border-rule">
        {[
          ['21 yrs', 'Walk-forward tested — through 2008, COVID & 2022'],
          ['2×', 'Preserver recovered its worst drawdown twice as fast as the market'],
          ['14.5%', 'Maximizer’s 21-year return — the S&P did 9.8%'],
        ].map(([value, label]) => (
          <div key={label} className="text-[0.98rem] text-ink-mute leading-snug">
            <strong className="block font-display text-ink text-[1.3rem] font-medium mb-1" style={{ fontVariationSettings: '"opsz" 48' }}>
              {value}
            </strong>
            {label}
          </div>
        ))}
      </div>
      {/* SURFACE-MARKER:landing-hero-stats-END */}

      <p className="text-[1.05rem] text-ink-mute leading-relaxed max-w-[600px] lg:max-w-none mt-12 text-balance lg:whitespace-nowrap">
        Built by a former <strong className="text-ink font-medium whitespace-nowrap">Chief Innovation Officer</strong>, priced like software &mdash; not 1% of your money every year.
      </p>
    </div>
  </section>
);

const ValuePropSection = () => (
  <section className="bg-paper-card py-20 border-t border-rule">
    <div className="max-w-[800px] mx-auto px-4 sm:px-8">
      <SectionLabel>What You're Actually Paying For</SectionLabel>

      <p className="font-display text-[1.5rem] leading-[1.45] text-ink mb-7" style={{ fontVariationSettings: '"opsz" 48' }}>
        You can find signals anywhere.<br />
        What's harder to find is the <em className="text-claret italic">discipline to follow them.</em>
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
          When the strategy turns defensive and steps back from new entries, you don't have to summon the willpower to wait it out.
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
          Three pieces of discipline.<br /><em className="text-claret italic">Where the edge lives.</em>
        </h2>
      </div>

      <div className="grid md:grid-cols-3 gap-10 mt-12">
        {[
          {
            num: 'Ⅰ / THE ENGINE',
            title: 'Regime-adaptive, not static.',
            text: <>RigaCap reads the market's mood &mdash; seven distinct regimes &mdash; and switches tactics: patient dip-buys in calm trends, deep-rebound buys after panics, aggressive breakouts when momentum pays. <strong className="font-medium text-ink">One engine, a different playbook for each regime.</strong></>,
          },
          {
            num: 'Ⅱ / THE DISCIPLINE',
            title: 'Sized by risk, not conviction.',
            text: <>Spread across a diversified basket, each position sized by the risk it carries &mdash; not by how much we like the story. It's the one piece of engineering that <strong className="font-medium text-ink">cuts the drawdown by two-thirds versus raw momentum</strong> &mdash; and what makes every setting on the dial survivable.</>,
          },
          {
            num: 'Ⅲ / HONESTY',
            title: 'Published method. Disclosed assumptions.',
            text: <>How we test is transparent &mdash; survivorship-free, point-in-time, walk-forward, costs modeled &mdash; and where an assumption favors the results, we say so. <strong className="font-medium text-ink">The exact parameters stay proprietary; the rigor behind them doesn't.</strong></>,
          },
        ].map(({ num, title, text }) => (
          <div key={num}>
            <span className="block font-mono text-[0.8rem] font-medium tracking-[0.1em] text-claret mb-2">{num}</span>
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
          Dial your return. <em className="text-claret italic">Keep the discipline.</em>
        </h2>
        <p className="text-ink-mute text-[1.05rem] leading-[1.65]">
          One proven engine, two settings. <strong className="text-ink font-medium">Preserver</strong> protects, <strong className="text-ink font-medium">Maximizer</strong> pushes &mdash; both run the same disciplined momentum core. The last two years walk-forward tested at <strong className="text-ink font-medium">Preserver 31%</strong> and <strong className="text-ink font-medium">Maximizer 49%</strong>. Below is the honest anchor &mdash; the full 21-year record through three downturns, both products on the same basis.
        </p>
      </div>

      {/* SURFACE-MARKER:perf-comparison-table-START */}
      {/* Mobile: stacked cards so the Max Drawdown column (the whole point) isn't
          scrolled off-screen. Desktop: the table. */}
      <div className="sm:hidden space-y-4 my-8">
        {[
          { strat: 'Raw 12-month momentum, net of costs', ann: '13.2%', sharpe: '0.69', dd: '57%', ddColor: '#8F2D3D', hi: false },
          { strat: 'S&P 500 (price)', ann: '9.8%', sharpe: '—', dd: '55%', ddColor: '#8F2D3D', hi: false },
          { strat: 'RigaCap Preserver', ann: '8.6%', sharpe: '0.88', dd: '13%', ddColor: '#2D5F3F', hi: true },
          { strat: 'RigaCap Maximizer', ann: '14.5%', sharpe: '0.95', dd: '20%', ddColor: '#2D5F3F', hi: true },
        ].map((r) => (
          <div
            key={r.strat}
            className={`border border-rule rounded-[2px] p-4 ${r.hi ? 'bg-paper-card' : 'bg-paper'}`}
            style={r.hi ? { boxShadow: 'inset 3px 0 0 #7A2430' } : {}}
          >
            <div className={`text-[1.05rem] mb-3 ${r.hi ? 'font-semibold text-ink' : 'text-ink-mute'}`}>{r.strat}</div>
            <div className="grid grid-cols-3 gap-2 text-center" style={{ fontFeatureSettings: '"tnum"' }}>
              <div>
                <div className="font-body text-[0.74rem] tracking-[0.1em] uppercase text-ink-mute mb-1">Annual</div>
                <div className={`font-mono text-[1rem] ${r.hi ? 'font-medium text-ink' : 'text-ink-mute'}`}>{r.ann}</div>
              </div>
              <div>
                <div className="font-body text-[0.74rem] tracking-[0.1em] uppercase text-ink-mute mb-1">Sharpe</div>
                <div className={`font-mono text-[1rem] ${r.hi ? 'font-medium text-ink' : 'text-ink-mute'}`}>{r.sharpe}</div>
              </div>
              <div>
                <div className="font-body text-[0.74rem] tracking-[0.1em] uppercase text-ink-mute mb-1">Max DD</div>
                <div className="font-mono text-[1rem] font-semibold" style={{ color: r.ddColor }}>{r.dd}</div>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="hidden sm:block my-10">
        <table className="w-full border-collapse" style={{ fontFeatureSettings: '"tnum"' }}>
          <thead>
            <tr>
              {['Strategy', 'Annualized', 'Sharpe', 'Max Drawdown'].map((h, i) => (
                <th key={h} className={`py-3 ${i === 0 ? 'text-left pl-5 pr-4' : 'text-right px-5'} font-body font-medium text-[0.8rem] tracking-[0.15em] uppercase text-ink-mute border-b border-rule-dark`}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr className="border-b border-rule">
              <td className="py-4 pl-5 pr-4 text-[1.05rem] text-ink-mute">Raw 12-month momentum, net of costs</td>
              <td className="py-4 px-5 text-right font-mono text-[1.05rem] text-ink-mute">13.2%</td>
              <td className="py-4 px-5 text-right font-mono text-[1.05rem] text-ink-mute">0.69</td>
              <td className="py-4 px-5 text-right font-mono text-[1.05rem] font-medium" style={{ color: '#8F2D3D' }}>57%</td>
            </tr>
            <tr className="border-b border-rule">
              <td className="py-4 pl-5 pr-4 text-[1.05rem] text-ink-mute">S&amp;P 500 (price)</td>
              <td className="py-4 px-5 text-right font-mono text-[1.05rem] text-ink-mute">9.8%</td>
              <td className="py-4 px-5 text-right font-mono text-[1.05rem] text-ink-mute">&mdash;</td>
              <td className="py-4 px-5 text-right font-mono text-[1.05rem] font-medium" style={{ color: '#8F2D3D' }}>55%</td>
            </tr>
            <tr className="border-b border-rule bg-paper-card">
              <td className="py-4 pl-5 pr-4 text-[1.05rem] font-semibold text-ink" style={{ boxShadow: 'inset 3px 0 0 #2D5F3F' }}>RigaCap Preserver</td>
              <td className="py-4 px-5 text-right font-mono text-[1.05rem] font-medium text-ink">8.6%</td>
              <td className="py-4 px-5 text-right font-mono text-[1.05rem] font-medium text-ink">0.88</td>
              <td className="py-4 px-5 text-right font-mono text-[1.05rem] font-semibold" style={{ color: '#2D5F3F' }}>13%</td>
            </tr>
            <tr className="border-b border-rule bg-paper-card">
              <td className="py-4 pl-5 pr-4 text-[1.05rem] font-semibold text-ink" style={{ boxShadow: 'inset 3px 0 0 #7A2430' }}>RigaCap Maximizer</td>
              <td className="py-4 px-5 text-right font-mono text-[1.05rem] font-medium text-ink">14.5%</td>
              <td className="py-4 px-5 text-right font-mono text-[1.05rem] font-medium text-ink">0.95</td>
              <td className="py-4 px-5 text-right font-mono text-[1.05rem] font-semibold" style={{ color: '#2D5F3F' }}>20%</td>
            </tr>
          </tbody>
        </table>
      </div>
      {/* SURFACE-MARKER:perf-comparison-table-END */}

      <p className="text-[0.93rem] text-ink-mute leading-relaxed">
        Same momentum factor, same universe. <strong className="text-ink font-medium">We cut the maximum drawdown by two-thirds</strong> through diversification, risk-based sizing, disciplined exits, and a market-regime filter that has now been tested through the 2008 financial crisis, the COVID crash, and the 2022 bear. Walk-forward test, 2007&ndash;2026; 2016+ data is survivorship-free and point-in-time, pre-2016 carries a survivorship caveat (disclosed in full); price returns, net of modeled costs where shown.<br />
        <strong className="text-ink font-medium">Live track record now accruing.</strong> See <a href="/methodology" className="text-claret underline underline-offset-2 decoration-1">methodology</a> for all assumptions.
      </p>

      <div className="bg-paper-card border-l-[3px] border-claret p-8 mt-12 max-w-[62ch]">
        <h3 className="font-display text-[1.15rem] font-semibold text-ink mb-3" style={{ fontVariationSettings: '"opsz" 48' }}>
          Why the drawdown is the whole game.
        </h3>
        <p className="text-ink leading-[1.7]">
          Raw momentum returns 13.2% a year on paper &mdash; but <strong className="font-medium">almost no one survives a 57% drawdown to collect it.</strong> In 2008 it lost nearly half its value in a single year; the index did the same twice in two decades. Investors abandon strategies at the bottom. Maximizer doesn't just cut that loss to a third &mdash; it <strong className="font-medium">out-earns raw momentum outright</strong> (14.5% vs 13.2%). Trimming the worst drawdown to a level you can actually hold is what makes the return reachable at all &mdash; and it's what lets you safely dial the risk <strong className="font-medium">up</strong> to Maximizer instead of blowing up.<br />
          <em className="font-display italic text-claret">The discipline is the product. The setting is your choice.</em>
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
              The engine behind both tiers is what I'd been running privately. RigaCap is the version I'm willing to put my name on.
            </p>
          </div>
          <a href="/about" className="inline-block mt-8 px-7 py-4 border border-rule-dark text-ink text-[1.05rem] font-medium rounded-[2px] no-underline hover:border-ink transition-all">
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
          { title: 'Scan', text: 'Algorithms evaluate 6,500 US stocks daily, filtered to 4,000 that meet liquidity and price criteria.' },
          { title: 'Signal', text: 'When timing, momentum, and risk all align, subscribers receive an alert with entry, stop, and target levels.' },
          { title: 'Execute', text: 'You place the trade through your own broker. RigaCap never touches your capital.' },
          { title: 'Exit', text: 'Trailing stops manage risk automatically. Regime changes trigger systematic de-risking.' },
        ].map(({ title, text }, i) => (
          <div key={title} className="border-t border-rule-dark pt-8 relative" style={{ counterIncrement: 'step' }}>
            <span className="block font-mono text-[0.8rem] font-medium tracking-[0.1em] text-claret mb-4">
              {String(i + 1).padStart(2, '0')}
            </span>
            <h3 className="font-display text-[1.4rem] font-medium text-ink mb-2" style={{ fontVariationSettings: '"opsz" 72' }}>
              {title}
            </h3>
            <p className="text-ink-mute text-[1.05rem] leading-relaxed">{text}</p>
          </div>
        ))}
      </div>
    </div>
  </section>
);

const PricingSection = ({ onGetStarted, founding }) => {
  const open = !founding || founding.open;   // default open until we know otherwise
  const scarce = founding && founding.open && founding.remaining <= FOUNDING_SCARCITY_THRESHOLD;
  return (
  <section id="pricing" className="py-20 border-t border-rule">
    <div className="max-w-[1120px] mx-auto px-4 sm:px-8">
      <SectionLabel>Pricing</SectionLabel>
      <div className="max-w-[680px] mb-4">
        <h2 className="font-display text-ink mb-4 tracking-[-0.02em]" style={{ fontSize: 'clamp(1.8rem, 3.5vw, 2.75rem)', fontVariationSettings: '"opsz" 96' }}>
          One engine. <em className="text-claret italic">Your dial.</em>
        </h2>
        <p className="text-ink-mute text-[1.05rem] leading-[1.65]">
          Start with <strong className="text-ink font-medium">Preserver</strong>, the capital-preservation base &mdash; founding members lock the rate while the live record builds.
          Add <strong className="text-ink font-medium">Maximizer</strong> when you want more offense (launching this month, seatbelt included).
          Advisory firms license the engine at the firm level. Cancel anytime.
        </p>
      </div>

      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-8 mt-12 max-w-[1120px]">
        {/* Founding — Featured */}
        <div className="bg-paper-card border-2 border-claret p-10 flex flex-col relative">
          <span className="absolute -top-3 left-8 bg-claret text-paper text-[0.78rem] font-medium tracking-[0.15em] uppercase px-3 py-1">
            Founding &middot; First 100
          </span>
          <h3 className="font-display text-[1.3rem] font-medium text-ink mb-1" style={{ fontVariationSettings: '"opsz" 72' }}>Preserver</h3>
          <p className="font-display italic text-ink-mute text-[1rem] mb-6" style={{ fontVariationSettings: '"opsz" 24' }}>The capital-preservation dial.</p>
          <div className="mb-1">
            <span className="font-display text-[3.5rem] font-normal text-ink leading-none tracking-tight" style={{ fontVariationSettings: '"opsz" 144' }}>$59</span>
            <span className="text-ink-mute text-[1.05rem] ml-1">/month</span>
          </div>
          <p className="text-ink-mute text-[1rem] leading-relaxed mt-3">
            Founding rate, locked <strong className="text-claret font-medium">12 months</strong> &mdash; then $129/month, or <strong className="text-claret font-medium">$1,099/year</strong>. Only <strong className="text-claret font-medium">100 founding seats</strong>, then it closes.
          </p>
          <ul className="list-none my-7 pt-6 border-t border-rule flex-1 space-y-1.5">
            {['Every buy & sell call the model makes', 'Daily email digest', 'Entry, stop & exit levels', 'Regime-adaptive risk engine', 'Portfolio tracking dashboard', 'Direct reply line to Erik', 'Grandfathered on future features'].map(item => (
              <li key={item} className="text-ink-mute text-[1rem] pl-5 relative before:content-['—'] before:absolute before:left-0 before:text-claret">{item}</li>
            ))}
          </ul>
          <button
            onClick={() => open && onGetStarted('founding')}
            disabled={!open}
            className={`w-full py-4 text-[1.05rem] font-medium rounded-[2px] text-center transition-colors ${open ? 'bg-ink text-paper hover:bg-claret' : 'bg-rule text-ink-light cursor-not-allowed'}`}
          >
            {open ? 'Claim a Founding Seat' : 'Founding Seats Filled'}
          </button>
          {/* Gated counter: silent until scarce (no embarrassing "100 left"),
              real urgency once it's running low, "filled" when closed. */}
          {!open ? (
            <p className="text-center font-mono text-[0.78rem] text-ink-light tracking-[0.1em] uppercase mt-3">All 100 founding seats claimed</p>
          ) : scarce ? (
            <p className="text-center font-mono text-[0.78rem] text-claret tracking-[0.1em] uppercase mt-3">Only {founding.remaining} of 100 seats left</p>
          ) : (
            <p className="text-center font-mono text-[0.78rem] text-claret tracking-[0.1em] uppercase mt-3">Limited to the first 100 subscribers</p>
          )}
        </div>

        {/* Maximizer — add-on, launching this month (waitlist; not charged until signals live) */}
        <div className="bg-paper-card border border-rule p-10 flex flex-col relative">
          <span className="absolute -top-3 left-8 bg-ink text-paper text-[0.78rem] font-medium tracking-[0.15em] uppercase px-3 py-1">
            Add-on &middot; Launching this month
          </span>
          <h3 className="font-display text-[1.3rem] font-medium text-ink mb-1" style={{ fontVariationSettings: '"opsz" 72' }}>+ Maximizer</h3>
          <p className="font-display italic text-ink-mute text-[1rem] mb-6" style={{ fontVariationSettings: '"opsz" 24' }}>Aggressive growth, seatbelt on.</p>
          <div className="mb-1">
            <span className="font-display text-[3.5rem] font-normal text-ink leading-none tracking-tight" style={{ fontVariationSettings: '"opsz" 144' }}>+$100</span>
            <span className="text-ink-mute text-[1.05rem] ml-1">/month</span>
          </div>
          <p className="text-ink-mute text-[1rem] leading-relaxed mt-3">
            Layers onto Preserver &mdash; the aggressive breakout engine with a momentum-crash brake. <strong className="text-claret font-medium">Founding members get first access</strong> at launch.
          </p>
          <ul className="list-none my-7 pt-6 border-t border-rule flex-1 space-y-1.5">
            {['Everything in Preserver', 'Aggressive breakout engine in trending markets', 'Volatility seatbelt on the crash tail', 'Higher-return profile for growth-seekers', 'Toggle on or off anytime'].map(item => (
              <li key={item} className="text-ink-mute text-[1rem] pl-5 relative before:content-['—'] before:absolute before:left-0 before:text-claret">{item}</li>
            ))}
          </ul>
          <button
            onClick={() => onGetStarted('founding')}
            className="w-full py-4 border border-ink text-ink text-[1.05rem] font-medium rounded-[2px] text-center hover:bg-ink hover:text-paper transition-colors"
          >
            Join the founding list
          </button>
          <p className="text-center text-[0.88rem] text-ink-light mt-3">First access when signals go live</p>
        </div>

        {/* Advisory firms */}
        <div className="bg-paper-card border border-rule p-10 flex flex-col">
          <h3 className="font-display text-[1.3rem] font-medium text-ink mb-1" style={{ fontVariationSettings: '"opsz" 72' }}>Advisory Firms</h3>
          <p className="font-display italic text-ink-mute text-[1rem] mb-6" style={{ fontVariationSettings: '"opsz" 24' }}>For RIAs &amp; registered advisers.</p>
          <div className="mb-1">
            <span className="font-display text-[3.5rem] font-normal text-ink leading-none tracking-tight" style={{ fontVariationSettings: '"opsz" 144' }}>Firm</span>
            <span className="text-ink-mute text-[1.05rem] ml-1">license</span>
          </div>
          <p className="text-ink-mute text-[1rem] leading-relaxed mt-3">
            Internal-use license for applying the strategy across client accounts.<br />
            <strong className="text-claret font-medium">You remain the fiduciary.</strong>
          </p>
          <ul className="list-none my-7 pt-6 border-t border-rule flex-1 space-y-1.5">
            {['Preserver + Maximizer, firm-wide', 'Multiple adviser seats', 'Internal use across client books', 'Client-presentable methodology & track record', 'Drawdowns clients can sit through — 13% to 20%, not 55%', 'Direct line to the founder'].map(item => (
              <li key={item} className="text-ink-mute text-[1rem] pl-5 relative before:content-['—'] before:absolute before:left-0 before:text-claret">{item}</li>
            ))}
          </ul>
          <a
            href="/for-advisers"
            className="w-full py-4 border border-ink text-ink text-[1.05rem] font-medium rounded-[2px] text-center hover:bg-ink hover:text-paper transition-colors no-underline"
          >
            See the adviser page
          </a>
          <p className="text-center text-[0.88rem] text-ink-light mt-3">Signals only &middot; no custody, no discretion</p>
        </div>
      </div>
    </div>
  </section>
  );
};

const faqItems = [
  { q: 'Who is this for?', a: <>Two kinds of people. Self-directed investors with meaningful portfolios who've decided indexing alone is too passive and individual active trading has been too emotional — if you've tried to run your own momentum strategy and found yourself overriding your own rules, this is a system that will do the boring parts consistently whether you feel like it or not. And registered investment advisers, who license it at the firm level as a disciplined momentum sleeve their clients can actually hold through a full cycle — see the <a href="/for-advisers" className="text-claret underline underline-offset-2 decoration-1">For Advisers page</a>.</> },
  { q: 'Who is this NOT for?', a: "Anyone who'll bail the moment they trail the market. Both tiers are built to keep you invested through a full cycle, not to win every quarter — even Maximizer, the aggressive setting, is designed to survive the drawdowns that make people capitulate. If watching the index run while your account grinds along for a stretch would make you quit, you'd be paying insurance premiums and cancelling right before the fire. We'd rather tell you that on the front page than learn it from your cancellation survey." },
  { q: "What's the difference between Preserver and Maximizer?", a: <>Same engine, one knob &mdash; you choose how hard to push. Preserver is the capital-preservation setting: strong momentum returns with a tight drawdown (walk-forward tested at 31% a year over the last two years, 13% worst loss). Maximizer dials up the offense &mdash; an aggressive breakout strategy in trending markets, with a volatility &ldquo;seatbelt&rdquo; that automatically eases exposure when its own turbulence spikes (walk-forward tested at 49% a year, 17% worst loss). Maximizer isn&rsquo;t <em className="italic">better</em>, it&rsquo;s <em className="italic">more</em> &mdash; more return and more drawdown, in roughly equal measure &mdash; so pick the setting that matches how much volatility you can actually sit through. Preserver is the flagship and buyable today; Maximizer is a +$100/month add-on launching this month, with founding members getting first access. Both are walk-forward tested; the live record is just beginning.</> },
  { q: 'Is your Sharpe ratio actually good?', a: 'Read it honestly. Long-horizon Sharpe ratios live on a compressed scale. Numbers above 1 come from short windows and overfit backtests; over decades the air gets thin. The S&P 500 scored 0.54 across our same 21-year window; Preserver walk-forward tested at 0.88 and Maximizer at 0.95. The highest lifetime figure ever measured for any fund with 30+ years of real history is Warren Buffett\u2019s 0.79 (\u201cBuffett\u2019s Alpha,\u201d Frazzini, Kabiller & Pedersen, 2018). Ours is walk-forward tested and his is real — that distinction matters — and our pre-2016 data carries a survivorship caveat that flatters the early years, so we hold these as strong-but-honest, not a claim to have out-Sharped Buffett.' },
  { q: 'What returns should I actually expect?', a: "Depends on your setting. Over a 21-year walk-forward (2007–2026, through the 2008 crisis, the COVID crash, and the 2022 bear) Preserver compounds at 8.6% a year with a 13% maximum drawdown; Maximizer at 14.5% with a 20% drawdown — versus the S&P's 9.8% at a 55% drawdown, and raw momentum's 13.2% at 57%. The last two years were far stronger (Preserver 31%, Maximizer 49%), but a two-year window is a tailwind, not a promise — the 21-year figures are the honest anchor because they include every crash. Underwrite to those. Past performance, including walk-forward and simulated results, does not predict future results." },
  { q: "Why don't you publish flashier numbers like other services?", a: "Because we anchor on what survives scrutiny. We rebuilt our research data to be survivorship-free and strictly point-in-time, then extended it back through 2008 — and each time the honest numbers came in more conservative than our earlier figures, we revised them down and said so. Most services lead with cherry-picked windows or zero-friction simulations no subscriber reproduces. We'd rather publish honest walk-forward figures — Preserver's 8.6% at a 13% worst drawdown, Maximizer's 14.5% at 20% — than a flattering number we can't defend." },
  { q: 'Why $129/month?', a: "You're not paying for a return forecast — you're paying for disciplined risk management: a momentum implementation with roughly a third of the raw factor's drawdown across twenty-one years, and the discipline to keep you invested through a cycle instead of bailing at the bottom. On a meaningful portfolio, the value of not abandoning a strategy in a drawdown dwarfs the $1,548/year — and it's less than a traditional advisor's fee." },
  { q: 'How many signals do you generate?', a: "RigaCap holds a diversified basket of positions, refreshed as fresh signals appear — typically several new entries in a normal month, fewer when the market turns hostile. It's selective, not silent: turnover stays low by design, but the strategy is invested whenever conditions support it." },
  { q: 'Has the system ever had a down year?', a: "Yes — and we'd rather tell you than hide it. Across twenty-one years of walk-forward testing both tiers had losing years (2017 and 2018 among them), but the worst peak-to-trough loss across the entire span — including the 2008 financial crisis, the COVID crash, and the 2022 bear — stayed at 13% for Preserver and 20% for Maximizer, while the market lost 55%. The design is built for participation in trends and protection in stress, not to win every quarter. (Walk-forward tested; the live record is accruing now.)" },
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
        className="inline-block px-8 py-4 bg-paper text-ink text-[1.05rem] font-medium rounded-[2px] hover:bg-paper-deep transition-colors"
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
          <p className="mt-4 text-[1rem] text-ink-mute leading-relaxed max-w-[32ch]">
            Regime-adaptive trading signals. The market, measured. Built by one quant researcher, shipping honestly.
          </p>
        </div>
        <div>
          <h4 className="font-body text-[0.8rem] font-medium tracking-[0.15em] uppercase text-ink mb-4">Product</h4>
          <ul className="space-y-2">
            {[['Methodology', '/methodology'], ['Track Record', '/track-record'], ['For Advisers', '/for-advisers'], ['Pricing', '#pricing']].map(([label, href]) => (
              <li key={label}><a href={href} className="text-ink-mute text-[1rem] no-underline hover:text-ink transition-colors">{label}</a></li>
            ))}
          </ul>
        </div>
        <div>
          <h4 className="font-body text-[0.8rem] font-medium tracking-[0.15em] uppercase text-ink mb-4">Company</h4>
          <ul className="space-y-2">
            {[['About', '/about'], ['Newsletter', '/newsletter'], ['Blog', '/blog'], ['Contact', '/contact']].map(([label, href]) => (
              <li key={label}><a href={href} className="text-ink-mute text-[1rem] no-underline hover:text-ink transition-colors">{label}</a></li>
            ))}
          </ul>
        </div>
        <div>
          <h4 className="font-body text-[0.8rem] font-medium tracking-[0.15em] uppercase text-ink mb-4">Legal</h4>
          <ul className="space-y-2">
            {[['Terms', '/terms'], ['Privacy', '/privacy'], ['Disclaimer', '/disclaimer']].map(([label, href]) => (
              <li key={label}><Link to={href} className="text-ink-mute text-[1rem] no-underline hover:text-ink transition-colors">{label}</Link></li>
            ))}
          </ul>
        </div>
      </div>
      <div className="pt-8 flex flex-col sm:flex-row justify-between items-start gap-8">
        <p className="text-[0.78rem] text-ink-light leading-relaxed max-w-[70ch]">
          For information purposes only. Not a solicitation to invest, purchase, or sell securities in which RigaCap has an interest. RigaCap, LLC is not a registered investment advisor. All performance figures are derived from walk-forward simulations using historical data and do not represent actual trading returns. Past performance does not guarantee future results. Trading involves substantial risk.
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

  // Founding-seat status (drives the gated counter + gray-out when full).
  const [founding, setFounding] = useState(null);
  useEffect(() => {
    fetch(`${API_BASE}/api/billing/founding-status`)
      .then(r => r.ok ? r.json() : null)
      .then(setFounding)
      .catch(() => {});  // non-fatal: card just shows the static "First 100" framing
  }, []);
  useEffect(() => {
    if (!loading && isAuthenticated) navigate('/app', { replace: true });
  }, [isAuthenticated, loading, navigate]);

  // Scroll-to-hash on mount: when arriving with /#pricing (or any anchor) from
  // another page, the browser's native anchor scroll fires before React renders
  // the target section, so it lands at the top instead. This finds the target
  // post-render and scrolls smoothly. Re-runs if the hash changes.
  useEffect(() => {
    const scrollToHash = () => {
      if (!window.location.hash) return;
      const id = window.location.hash.slice(1);
      const el = document.getElementById(id);
      if (el) {
        setTimeout(() => el.scrollIntoView({ behavior: 'smooth', block: 'start' }), 80);
      }
    };
    scrollToHash();
    window.addEventListener('hashchange', scrollToHash);
    return () => window.removeEventListener('hashchange', scrollToHash);
  }, []);

  const handleGetStarted = (plan = 'monthly') => {
    // Checkout-intent signal for ads/GA4 (landing CTA click = begin_checkout;
    // the in-app billing buttons fire the same event with value)
    if (window.gtag) window.gtag('event', 'begin_checkout', { currency: 'USD', item_variant: plan });
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
      <PricingSection onGetStarted={handleGetStarted} founding={founding} />
      <FAQSection />

      <section id="newsletter" className="bg-paper-card py-16 border-t border-rule">
        <div className="max-w-3xl mx-auto px-4 sm:px-8">
          <MarketMeasuredSignup source="landing_v2" />
          <Link to="/newsletter" className="inline-block mt-4 text-[0.93rem] text-ink-mute hover:text-claret no-underline transition-colors">
            Read past issues &rarr;
          </Link>
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
