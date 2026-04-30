import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, BookOpen, BarChart3, Shield, Brain, TrendingUp, Zap, Target, LineChart } from 'lucide-react';
import MarketMeasuredSignup from './components/MarketMeasuredSignup';
import TopNav from './components/TopNav';

const POSTS = [
  {
    title: 'Inside Our 5-Year Walk-Forward: +160%',
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

const Navbar = () => <TopNav />;

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
          For information purposes only — not a solicitation to invest, purchase, or sell securities in which RigaCap has an interest.
          RigaCap, LLC is not a registered investment advisor. Past performance does not guarantee future results.
          Execute trades through your own brokerage account. See our{' '}
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
