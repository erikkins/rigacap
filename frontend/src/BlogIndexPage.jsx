import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, ArrowRight, BookOpen, BarChart3, Shield, Brain } from 'lucide-react';

const POSTS = [
  {
    title: 'The 2022 Story',
    path: '/blog/2022-story',
    description: "The S&P 500 fell 20%. Our system gained 6%. Here's exactly how.",
    category: 'Case Study',
    icon: BarChart3,
    badgeColor: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
  },
  {
    title: 'Why Most Backtests Are Lies',
    path: '/blog/backtests',
    description: "That strategy with 500% returns? It probably won't work in real life.",
    category: 'Education',
    icon: BookOpen,
    badgeColor: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
  },
  {
    title: 'What to Do When the Market Crashes',
    path: '/blog/market-crash',
    description: 'The playbook most investors wish they had before 2022.',
    category: 'Strategy',
    icon: Shield,
    badgeColor: 'bg-blue-500/20 text-blue-300 border-blue-500/30',
  },
  {
    title: 'The 7 Market Regimes',
    path: '/blog/market-regimes',
    description: 'Most strategies have one mode. Ours detects seven.',
    category: 'Intelligence',
    icon: Brain,
    badgeColor: 'bg-purple-500/20 text-purple-300 border-purple-500/30',
  },
];

export default function BlogIndexPage() {
  useEffect(() => { document.title = 'Blog | RigaCap'; }, []);
  return (
    <div className="min-h-screen bg-gray-950 text-gray-300">
      {/* Nav */}
      <nav className="bg-gray-900 border-b border-gray-800">
        <div className="max-w-4xl mx-auto px-4 py-4 flex items-center gap-4">
          <Link to="/" className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors">
            <ArrowLeft size={18} />
            <span className="text-sm">Back to RigaCap</span>
          </Link>
        </div>
      </nav>

      {/* Hero */}
      <section className="relative overflow-hidden bg-gradient-to-br from-blue-600/80 via-indigo-900 to-gray-950">
        <div className="absolute inset-0 overflow-hidden">
          <div className="absolute -top-40 -right-40 w-80 h-80 bg-blue-500/10 rounded-full blur-3xl"></div>
          <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-indigo-500/10 rounded-full blur-3xl"></div>
        </div>
        <div className="relative max-w-4xl mx-auto px-4 sm:px-6 py-16 sm:py-24 text-center">
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-white/10 backdrop-blur-sm rounded-full text-sm font-medium mb-6">
            <BookOpen className="w-4 h-4 text-amber-300" />
            <span className="text-white/90">Market Intelligence</span>
          </div>
          <h1 className="text-4xl sm:text-5xl font-bold text-white tracking-tight mb-4">
            RigaCap Blog
          </h1>
          <p className="text-lg text-blue-200/80 max-w-2xl mx-auto">
            Market intelligence, trading education, and the math behind our signals.
          </p>
        </div>
      </section>

      {/* Post Grid */}
      <section className="max-w-4xl mx-auto px-4 sm:px-6 py-12 sm:py-16">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {POSTS.map((post) => {
            const Icon = post.icon;
            return (
              <Link
                key={post.path}
                to={post.path}
                className="group bg-gray-900 border border-gray-800 rounded-xl p-6 hover:border-gray-700 transition-colors block"
              >
                <div className="flex items-center gap-3 mb-4">
                  <div className="p-2 bg-gray-800 rounded-lg group-hover:bg-gray-700 transition-colors">
                    <Icon className="w-5 h-5 text-gray-400" />
                  </div>
                  <span className={`text-xs font-medium px-2.5 py-1 rounded-full border ${post.badgeColor}`}>
                    {post.category}
                  </span>
                </div>
                <h3 className="text-lg font-semibold text-white mb-2 group-hover:text-blue-300 transition-colors">
                  {post.title}
                </h3>
                <p className="text-sm text-gray-400 leading-relaxed mb-4">
                  {post.description}
                </p>
                <span className="inline-flex items-center gap-1 text-sm text-blue-400 group-hover:text-blue-300 transition-colors">
                  Read more
                  <ArrowRight size={14} className="group-hover:translate-x-1 transition-transform" />
                </span>
              </Link>
            );
          })}
        </div>
      </section>

      {/* CTA */}
      <section className="max-w-4xl mx-auto px-4 sm:px-6 pb-16">
        <div className="bg-gradient-to-br from-indigo-900/50 to-blue-900/50 border border-indigo-500/30 rounded-2xl p-8 sm:p-10 text-center">
          <h2 className="text-2xl sm:text-3xl font-bold text-white mb-3">
            Stop Trading on Emotions
          </h2>
          <p className="text-blue-200/80 mb-6 max-w-lg mx-auto">
            Our system scans 4,000 stocks daily and only speaks up when the math says go.
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
              View Track Record
            </Link>
          </div>
          <p className="text-xs text-gray-500 mt-4">
            7-day free trial. $39/month after. Cancel anytime.
          </p>
        </div>
      </section>

      {/* Disclaimer */}
      <section className="max-w-4xl mx-auto px-4 sm:px-6 pb-8">
        <p className="text-xs text-gray-600 leading-relaxed">
          All performance figures are from walk-forward simulations using historical market data.
          Past performance does not guarantee future results. RigaCap provides trading signals only —
          execute trades through your own brokerage account. See our{' '}
          <Link to="/terms" className="text-gray-500 underline hover:text-gray-400">Terms of Service</Link>{' '}
          for full disclaimers.
        </p>
      </section>

      {/* Footer */}
      <footer className="border-t border-gray-800 py-8 text-center text-xs text-gray-600">
        <p>&copy; {new Date().getFullYear()} RigaCap. All rights reserved.</p>
      </footer>
    </div>
  );
}
