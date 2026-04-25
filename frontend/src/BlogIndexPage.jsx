import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, BookOpen, BarChart3, Shield, Brain, TrendingUp, Zap, Target, LineChart } from 'lucide-react';
import MarketMeasuredSignup from './components/MarketMeasuredSignup';

const POSTS = [
  {
    title: 'Inside Our 5-Year Walk-Forward: +384%',
    path: '/blog/walk-forward-results',
    description: 'We spent months trying to break our own strategy. It held up.',
    category: 'Results',
    icon: LineChart,
  },
  {
    title: 'We Called It: Moderna +51%',
    path: '/blog/we-called-it-mrna',
    description: 'How the ensemble caught MRNA\'s summer 2021 run — and locked in gains before the crash.',
    category: 'We Called It',
    icon: TrendingUp,
  },
  {
    title: 'We Called It: TGTX +46%',
    path: '/blog/we-called-it-tgtx',
    description: 'A $22 biotech nobody was watching. Our system was.',
    category: 'We Called It',
    icon: Zap,
  },
  {
    title: 'The 2022 Story',
    path: '/blog/2022-story',
    description: "The S&P 500 fell 20%. Our system preserved capital. Here's exactly how.",
    category: 'Case Study',
    icon: BarChart3,
  },
  {
    title: 'Momentum Trading Explained',
    path: '/blog/momentum-trading',
    description: 'Not day trading. Not guessing. A rules-based system that catches breakouts.',
    category: 'Education',
    icon: Target,
  },
  {
    title: 'How Trailing Stops Protect Your Portfolio',
    path: '/blog/trailing-stops',
    description: 'The exit strategy that lets winners run and cuts losers short — automatically.',
    category: 'Education',
    icon: Shield,
  },
  {
    title: 'Market Regime Trading: A Beginner\'s Guide',
    path: '/blog/market-regime-guide',
    description: 'Most investors think bull or bear. Reality has seven moods.',
    category: 'Education',
    icon: BookOpen,
  },
  {
    title: 'Why Most Backtests Are Lies',
    path: '/blog/backtests',
    description: "That strategy with 500% returns? It probably won't work in real life.",
    category: 'Education',
    icon: BookOpen,
  },
  {
    title: 'What to Do When the Market Crashes',
    path: '/blog/market-crash',
    description: 'The playbook most investors wish they had before 2022.',
    category: 'Strategy',
    icon: Shield,
  },
  {
    title: 'The 7 Market Regimes (Deep Dive)',
    path: '/blog/market-regimes',
    description: 'Most strategies have one mode. Ours detects seven.',
    category: 'Intelligence',
    icon: Brain,
  },
];

const SectionLabel = ({ children }) => (
  <div className="flex items-center gap-3 mb-6">
    <span className="inline-block w-6 h-px bg-claret" />
    <span className="font-body text-[0.78rem] font-medium tracking-[0.18em] uppercase text-ink-mute">{children}</span>
  </div>
);

const Navbar = () => (
  <nav className="sticky top-0 z-50 bg-paper/95 backdrop-blur-sm border-b border-rule">
    <div className="max-w-[1120px] mx-auto px-4 sm:px-8 py-5 flex items-center justify-between">
      <Link to="/" className="flex items-center gap-2 no-underline">
        <svg className="w-7 h-7 shrink-0 relative top-[2px]" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 1024"><g transform="matrix(5.27 0 0 5.27 640 511)"><g><g transform="matrix(0.448 0 0 0.448 -22.4 -28.8)"><path fill="#7A2430" transform="translate(-300,-286)" d="M215.49 348.13C215.49 341.43 220.55 335.98 227.05 335.22L241.64 278.36C238.32 275.99 236.13 272.12 236.13 267.73C236.13 260.51 241.98 254.66 249.2 254.66C255.89 254.66 261.34 259.71 262.11 266.19L309.18 278.16C311.55 274.82 315.42 272.63 319.83 272.63C324 272.63 327.67 274.62 330.06 277.66L391.39 258.85C391.87 252.06 397.46 246.69 404.37 246.69C405.09 246.69 405.78 246.79 406.47 246.91L420.4 223.13C395.44 205.2 364.84 194.62 331.76 194.62C247.75 194.62 179.66 262.72 179.66 346.72C179.66 357.06 180.71 367.15 182.69 376.91L216.05 351.72C215.72 350.57 215.49 349.38 215.49 348.13z"/></g><g transform="matrix(0.448 0 0 0.448 -11.1 -9)"><path fill="#7A2430" transform="translate(-325,-330)" d="M427.89 228.86L414.54 251.65C416.32 253.88 417.43 256.68 417.43 259.76C417.43 266.98 411.58 272.83 404.37 272.83C400.19 272.83 396.52 270.84 394.13 267.79L332.8 286.61C332.33 293.39 326.73 298.76 319.83 298.76C313.14 298.76 307.69 293.72 306.92 287.24L259.84 275.26C257.76 278.21 254.48 280.2 250.71 280.64L236.12 337.5C239.44 339.87 241.63 343.74 241.63 348.13C241.63 355.35 235.78 361.2 228.56 361.2C226.02 361.2 223.68 360.45 221.67 359.19L185.04 386.86C189.39 402.76 196.25 417.63 205.17 431L343.51 312.12L408.04 312.12L465.59 274.41C456.09 256.86 443.23 241.4 427.89 228.86z"/></g><g transform="matrix(0.448 0 0 0.448 73.8 -37.1)"><polygon fill="#7A2430" points="-45.31,-14.33 45.31,-39.44 -12.75,39.44 -17.06,3.28"/></g><g transform="matrix(0.448 0 0 0.448 -48.2 25.7)"><path fill="#141210" transform="translate(-242,-407)" d="M297.69 513.38C291.85 512.18 286.13 510.68 280.53 508.91L280.53 405.3L233.16 446.01L233.16 485.18C189.93 454.31 161.67 403.77 161.67 346.72C161.67 321.48 167.23 297.53 177.14 275.97L153.41 275.97C144.69 297.88 139.84 321.74 139.84 346.72C139.84 452.54 225.93 538.63 331.76 538.63C336.23 538.63 340.66 538.42 345.06 538.12L345.06 349.85L297.69 390.55L297.69 513.38z"/></g><g transform="matrix(0.448 0 0 0.448 41.6 31.4)"><path fill="#141210" transform="translate(-443,-420)" d="M523.16 333.38L501.27 333.38C501.62 337.79 501.85 342.23 501.85 346.72C501.85 381 491.63 412.92 474.11 439.65L474.11 304.24L426.75 335.28L426.75 487.65C421.24 491.37 415.52 494.78 409.58 497.85L409.58 341.74L362.22 341.74L362.22 536.19C453.61 521.55 523.67 442.17 523.67 346.72C523.67 342.23 523.46 337.79 523.16 333.38z"/></g><g transform="matrix(0.448 0 0 0.448 -11.8 -60.8)"><path fill="#141210" transform="translate(-324,-214)" d="M331.75 169.32C390.45 169.32 442.58 197.98 474.89 242.04L483.06 239.78C449.46 192.37 394.16 161.37 331.75 161.37C258.06 161.37 194.28 204.6 164.43 267.02L173.29 267.02C202.53 209.12 262.58 169.32 331.75 169.32z"/></g></g></g></svg>
        <span className="font-display text-2xl font-semibold text-ink tracking-tight" style={{ fontVariationSettings: '"opsz" 144' }}>RigaCap<span className="text-claret">.</span></span>
      </Link>
      <div className="flex items-center gap-9">
        <Link to="/methodology" className="text-[0.9rem] text-ink-mute no-underline hover:text-ink transition-colors">Methodology</Link>
        <Link to="/track-record" className="text-[0.9rem] text-ink-mute no-underline hover:text-ink transition-colors">Track Record</Link>
        <Link to="/" className="text-[0.9rem] text-ink-mute no-underline hover:text-ink transition-colors">Home</Link>
      </div>
    </div>
  </nav>
);

export default function BlogIndexPage() {
  useEffect(() => { document.title = 'Blog — RigaCap'; }, []);

  return (
    <div className="min-h-screen bg-paper font-body text-ink text-[17px] leading-[1.65] antialiased">
      <Navbar />

      {/* Header */}
      <header className="pt-16 pb-14 sm:pt-20 sm:pb-16 border-b border-rule">
        <div className="max-w-[720px] mx-auto px-4 sm:px-8">
          <SectionLabel>Blog</SectionLabel>
          <h1
            className="font-display font-normal text-ink mb-5 tracking-[-0.025em] leading-[1.05]"
            style={{ fontSize: 'clamp(2.25rem, 4.5vw, 3.6rem)', fontVariationSettings: '"opsz" 144' }}
          >
            Market intelligence, trading education, and the math behind our signals.
          </h1>
        </div>
      </header>

      {/* Post Grid */}
      <section className="py-16 sm:py-20">
        <div className="max-w-[1120px] mx-auto px-4 sm:px-8">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-px bg-rule">
            {POSTS.map((post) => {
              const Icon = post.icon;
              return (
                <Link
                  key={post.path}
                  to={post.path}
                  className="group bg-paper-card p-8 no-underline block hover:bg-paper transition-colors"
                >
                  <div className="flex items-center gap-3 mb-4">
                    <Icon className="w-4 h-4 text-ink-light" />
                    <span className="text-[0.75rem] font-medium tracking-[0.12em] uppercase text-claret bg-claret/10 px-2.5 py-1 rounded">
                      {post.category}
                    </span>
                  </div>
                  <h3
                    className="font-display text-[1.25rem] font-medium text-ink mb-2 leading-[1.25] tracking-[-0.01em] group-hover:text-claret transition-colors"
                    style={{ fontVariationSettings: '"opsz" 48' }}
                  >
                    {post.title}
                  </h3>
                  <p className="text-[0.92rem] text-ink-mute leading-relaxed mb-4">
                    {post.description}
                  </p>
                  <span className="inline-flex items-center gap-1 text-[0.85rem] text-claret font-medium group-hover:gap-2 transition-all">
                    Read more
                    <ArrowRight size={14} />
                  </span>
                </Link>
              );
            })}
          </div>
        </div>
      </section>

      {/* Signup */}
      <section className="pb-16 sm:pb-20">
        <div className="max-w-[720px] mx-auto px-4 sm:px-8">
          <MarketMeasuredSignup source="blog_index" />
        </div>
      </section>

      {/* Disclaimer */}
      <section className="max-w-[720px] mx-auto px-4 sm:px-8 pb-8">
        <p className="text-[0.78rem] text-ink-light leading-relaxed">
          All performance figures are from walk-forward simulations using historical market data.
          Past performance does not guarantee future results. RigaCap provides trading signals only —
          execute trades through your own brokerage account. See our{' '}
          <Link to="/terms" className="text-ink-mute underline hover:text-ink transition-colors">Terms of Service</Link>{' '}
          for full disclaimers.
        </p>
      </section>

      {/* Footer */}
      <footer className="border-t border-rule py-8 text-center text-[0.78rem] text-ink-light">
        <p>&copy; {new Date().getFullYear()} RigaCap, LLC. All rights reserved.</p>
      </footer>
    </div>
  );
}
