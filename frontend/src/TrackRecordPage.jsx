import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, TrendingUp, BarChart3, Shield, Activity, ArrowRight } from 'lucide-react';
import TrackRecordChart from './components/TrackRecordChart';
import MarketMeasuredSignup from './components/MarketMeasuredSignup';

const HEADLINE_METRICS = [
  { value: '+240%', label: '5-Year Return', subtitle: 'Walk-forward validated', color: 'text-emerald-400' },
  { value: '~28%', label: 'Annualized Return', subtitle: 'Across multiple start dates', color: 'text-emerald-400' },
  { value: '0.89', label: 'Sharpe Ratio', subtitle: 'Risk-adjusted performance', color: 'text-amber-400' },
  { value: '24%', label: 'Max Drawdown', subtitle: 'Peak to trough', color: 'text-amber-400' },
];

const BENCHMARKS = [
  { name: 'RigaCap Ensemble', value: 240, label: '+240%', color: 'from-amber-400 to-amber-500' },
  { name: 'S&P 500', value: 84, label: '+84%', color: 'from-gray-400 to-gray-500' },
];

export default function TrackRecordPage() {
  useEffect(() => { document.title = 'Track Record | RigaCap'; }, []);
  return (
    <div className="min-h-screen bg-gray-950 text-gray-300">
      {/* Nav */}
      <nav className="bg-gray-900 border-b border-gray-800">
        <div className="max-w-5xl mx-auto px-4 py-4 flex items-center gap-4">
          <Link to="/" className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors">
            <ArrowLeft size={18} />
            <span className="text-sm">Back to RigaCap</span>
          </Link>
        </div>
      </nav>

      {/* Hero */}
      <section className="relative overflow-hidden bg-gradient-to-br from-indigo-900 via-blue-900 to-purple-900">
        <div className="absolute inset-0 overflow-hidden">
          <div className="absolute -top-40 -right-40 w-80 h-80 bg-amber-500/10 rounded-full blur-3xl"></div>
          <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-blue-500/10 rounded-full blur-3xl"></div>
        </div>
        <div className="relative max-w-5xl mx-auto px-4 sm:px-6 py-16 sm:py-20 text-center">
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-white/10 backdrop-blur-sm rounded-full text-sm font-medium mb-6">
            <BarChart3 className="w-4 h-4 text-amber-300" />
            <span className="text-white/90">Walk-Forward Validated</span>
          </div>
          <h1 className="text-4xl sm:text-5xl font-bold text-white tracking-tight mb-4">
            Track Record
          </h1>
          <p className="text-lg text-blue-200/80 max-w-2xl mx-auto">
            Year-by-year performance validated through walk-forward simulation — no hindsight bias, no curve-fitting.
          </p>
        </div>
      </section>

      {/* Headline Metrics */}
      <section className="max-w-5xl mx-auto px-4 sm:px-6 -mt-8 relative z-10">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {HEADLINE_METRICS.map((m) => (
            <div key={m.label} className="bg-gray-900 border border-gray-800 rounded-xl p-5 text-center">
              <div className={`text-2xl sm:text-3xl font-bold ${m.color}`}>{m.value}</div>
              <div className="text-xs text-gray-500 uppercase tracking-wider mt-1">{m.label}</div>
              {m.subtitle && <div className="text-xs text-gray-600 mt-0.5">{m.subtitle}</div>}
            </div>
          ))}
        </div>
      </section>

      {/* Equity Curve Chart */}
      <section className="max-w-5xl mx-auto px-4 sm:px-6 pt-10">
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 sm:p-6">
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <Activity className="w-5 h-5 text-blue-400" />
            5-Year Equity Curve — RigaCap vs S&P 500
          </h2>
          <TrackRecordChart />
          <p className="text-xs text-gray-600 mt-3 text-center">
            Shown: best-case start date (+490%). Average across all start dates: +240%. Worst case: +83%.
          </p>
        </div>
      </section>

      {/* Key Highlights */}
      <section className="max-w-5xl mx-auto px-4 sm:px-6 py-12">
        <h2 className="text-2xl font-bold text-white mb-6 flex items-center gap-2">
          <TrendingUp className="w-6 h-6 text-amber-400" />
          Performance Highlights
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
            <div className="text-emerald-400 text-3xl font-bold">+240%</div>
            <div className="text-sm text-gray-400 mt-1">5-Year Total Return</div>
            <div className="text-xs text-gray-600 mt-2">vs S&P 500: +84%</div>
          </div>
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
            <div className="text-emerald-400 text-3xl font-bold">+6%</div>
            <div className="text-sm text-gray-400 mt-1">In 2022 (S&P: -20%)</div>
            <div className="text-xs text-gray-600 mt-2">Capital preservation when it matters</div>
          </div>
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
            <div className="text-amber-400 text-3xl font-bold">24%</div>
            <div className="text-sm text-gray-400 mt-1">Max Drawdown</div>
            <div className="text-xs text-gray-600 mt-2">Avg hedge fund: 30% to 50%</div>
          </div>
        </div>
      </section>

      {/* Benchmark Comparison */}
      <section className="max-w-5xl mx-auto px-4 sm:px-6 pb-12">
        <h2 className="text-2xl font-bold text-white mb-6 flex items-center gap-2">
          <BarChart3 className="w-6 h-6 text-amber-400" />
          5-Year Benchmark Comparison
        </h2>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <div className="space-y-5">
            {BENCHMARKS.map((b) => (
              <div key={b.name}>
                <div className="flex justify-between items-center mb-2">
                  <span className="text-sm font-medium text-gray-300">{b.name}</span>
                  <span className={`text-sm font-bold ${b.name === 'RigaCap Ensemble' ? 'text-amber-400' : 'text-gray-400'}`}>{b.label}</span>
                </div>
                <div className="h-4 bg-gray-800 rounded-full overflow-hidden">
                  <div
                    className={`h-full bg-gradient-to-r ${b.color} rounded-full transition-all duration-1000`}
                    style={{ width: `${(b.value / 280) * 100}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Methodology */}
      <section className="max-w-5xl mx-auto px-4 sm:px-6 pb-12">
        <h2 className="text-2xl font-bold text-white mb-6 flex items-center gap-2">
          <Shield className="w-6 h-6 text-amber-400" />
          Walk-Forward Methodology
        </h2>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 sm:p-8">
          <div className="grid sm:grid-cols-2 gap-6">
            <div>
              <h3 className="text-white font-semibold mb-2">What is walk-forward testing?</h3>
              <p className="text-gray-400 text-sm leading-relaxed">
                Unlike backtesting, walk-forward simulation tests each year using only data available at the time.
                Parameters are optimized on past data, then locked and tested on the next unseen period — exactly
                how the strategy would have performed in real time.
              </p>
            </div>
            <div>
              <h3 className="text-white font-semibold mb-2">Why it matters</h3>
              <p className="text-gray-400 text-sm leading-relaxed">
                Most backtests suffer from hindsight bias — they implicitly use future information to pick winning
                parameters. Walk-forward validation eliminates this by never allowing the model to see future data
                during optimization.
              </p>
            </div>
            <div>
              <h3 className="text-white font-semibold mb-2">Ensemble strategy</h3>
              <p className="text-gray-400 text-sm leading-relaxed">
                Our approach combines three proven factors: breakout timing, momentum quality ranking,
                and adaptive risk management with trailing stops. All three must align before generating a signal.
              </p>
            </div>
            <div>
              <h3 className="text-white font-semibold mb-2">Rebalancing</h3>
              <p className="text-gray-400 text-sm leading-relaxed">
                The portfolio reoptimizes biweekly across up to 8 positions. Parameters adapt
                through 7 distinct market regimes — from strong bull to panic/crash — without manual intervention.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Capital Protection Callout */}
      <section className="max-w-5xl mx-auto px-4 sm:px-6 pb-12">
        <div className="bg-gradient-to-r from-emerald-900/30 to-emerald-800/20 border border-emerald-700/30 rounded-xl p-6 sm:p-8 text-center">
          <Shield className="w-8 h-8 text-emerald-400 mx-auto mb-3" />
          <div className="text-3xl font-bold text-emerald-400 mb-1">+6% in 2022</div>
          <p className="text-emerald-200/70 text-sm">While the S&P 500 fell 20%, our system stayed positive. 7-regime detection moved to cash before the crash — and max drawdown has never exceeded 25%.</p>
        </div>
      </section>

      {/* Disclaimer */}
      <section className="max-w-5xl mx-auto px-4 sm:px-6 pb-12">
        <div className="bg-gray-900/50 border border-gray-800 rounded-xl p-6 text-xs text-gray-500 leading-relaxed">
          <p className="font-semibold text-gray-400 mb-2">Important Disclaimer</p>
          <p>
            Past performance is not indicative of future results. All results shown are from walk-forward simulations
            using historical data and do not represent actual trading returns. Investing involves risk, including the
            possible loss of principal. RigaCap provides algorithmic signals and educational information only — we are
            not financial advisors. Always do your own research and consider consulting a licensed professional before
            making investment decisions. See our{' '}
            <Link to="/terms" className="text-amber-400 hover:text-amber-300 underline">Terms of Service</Link> for
            full details.
          </p>
        </div>
      </section>

      {/* Weekly newsletter signup */}
      <section className="max-w-3xl mx-auto px-4 sm:px-6 pb-12">
        <MarketMeasuredSignup source="track_record_page" variant="dark" />
      </section>

      {/* CTA */}
      <section className="max-w-5xl mx-auto px-4 sm:px-6 pb-16">
        <div className="bg-gradient-to-br from-indigo-900 to-purple-900 rounded-xl p-8 sm:p-12 text-center">
          <h2 className="text-2xl sm:text-3xl font-bold text-white mb-3">Ready to Start?</h2>
          <p className="text-blue-200/70 mb-6 max-w-lg mx-auto">
            Get access to the same Ensemble strategy that produced these results — delivered to your dashboard and inbox daily.
          </p>
          <Link
            to="/"
            className="inline-flex items-center gap-2 px-8 py-4 bg-white text-indigo-700 font-semibold rounded-xl shadow-lg hover:shadow-xl transform hover:-translate-y-0.5 transition-all"
          >
            Start Your Free Trial
            <ArrowRight className="w-5 h-5" />
          </Link>
        </div>
      </section>

      {/* Footer */}
      <div className="max-w-5xl mx-auto px-4 sm:px-6 pb-8 pt-4 border-t border-gray-800 text-center text-sm text-gray-500">
        &copy; {new Date().getFullYear()} RigaCap, LLC. All rights reserved.
      </div>
    </div>
  );
}
