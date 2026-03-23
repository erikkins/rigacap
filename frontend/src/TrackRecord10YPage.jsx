import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, TrendingUp, BarChart3, Shield, Activity, ArrowRight, Clock } from 'lucide-react';
import TrackRecordChart from './components/TrackRecordChart';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const MARKET_CONTEXT = {
  '2016': 'Post-election rally',
  '2017': 'Low-vol bull run',
  '2018': 'Volmageddon, Q4 selloff',
  '2019': 'Fed pivot, trade war',
  '2020': 'COVID crash + recovery',
  '2021': 'Post-COVID melt-up',
  '2022': 'Rate hikes, tech crash',
  '2023': 'AI-driven recovery',
  '2024': 'Election volatility',
  '2025': 'Strong bull, tariff shock',
};

export default function TrackRecord10YPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/public/track-record-10y`)
      .then(res => {
        if (!res.ok) throw new Error('Failed to load 10-year track record');
        return res.json();
      })
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const metrics = data?.metrics || {};
  const yearlyStats = data?.yearly_stats || [];

  const HEADLINE_METRICS = [
    { value: metrics.total_return_pct ? `+${metrics.total_return_pct}%` : '...', label: '10-Year Total Return', color: 'text-emerald-400' },
    { value: metrics.total_return_pct ? `${((Math.pow(1 + metrics.total_return_pct / 100, 1/10) - 1) * 100).toFixed(0)}%` : '...', label: 'Annualized Return', color: 'text-emerald-400' },
    { value: metrics.sharpe_ratio?.toFixed(2) || '...', label: 'Sharpe Ratio', subtitle: 'Across all market regimes', color: 'text-amber-400' },
    { value: metrics.max_drawdown_pct ? `${metrics.max_drawdown_pct.toFixed(1)}%` : '...', label: 'Max Drawdown', color: 'text-red-400' },
  ];

  const maxReturn = Math.max(metrics.total_return_pct || 600, 600);
  const BENCHMARKS = [
    { name: 'RigaCap Ensemble', value: metrics.total_return_pct || 599, label: `+${metrics.total_return_pct || 599}%`, color: 'from-amber-400 to-amber-500' },
    { name: 'NASDAQ-100', value: 350, label: '~+350%', color: 'from-blue-400 to-blue-500' },
    { name: 'S&P 500', value: metrics.benchmark_return_pct || 257, label: `+${metrics.benchmark_return_pct || 257}%`, color: 'from-gray-400 to-gray-500' },
  ];

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
            <Clock className="w-4 h-4 text-amber-300" />
            <span className="text-white/90">10 Years Walk-Forward Validated</span>
          </div>
          <h1 className="text-4xl sm:text-5xl font-bold text-white tracking-tight mb-4">
            Full-Decade Track Record
          </h1>
          <p className="text-lg text-blue-200/80 max-w-2xl mx-auto">
            10 years. 2 bear markets. A pandemic crash. 3 bull runs. One strategy — tested through every regime without hindsight bias.
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
            10-Year Equity Curve — RigaCap vs S&P 500
          </h2>
          {loading ? (
            <div className="animate-pulse h-[350px] bg-gray-800 rounded-lg" />
          ) : error ? (
            <div className="text-red-400 text-sm py-8 text-center">{error}</div>
          ) : (
            <TrackRecordChart apiUrl={`${API_BASE}/api/public/track-record-10y`} />
          )}
        </div>
      </section>

      {/* Year-by-Year Table */}
      <section className="max-w-5xl mx-auto px-4 sm:px-6 py-12">
        <h2 className="text-2xl font-bold text-white mb-6 flex items-center gap-2">
          <TrendingUp className="w-6 h-6 text-amber-400" />
          Year-by-Year Performance
        </h2>
        <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800">
                  <th className="text-left px-4 sm:px-6 py-3 text-xs uppercase tracking-wider text-gray-500 font-semibold">Period</th>
                  <th className="text-right px-4 sm:px-6 py-3 text-xs uppercase tracking-wider text-gray-500 font-semibold">Return</th>
                  <th className="text-right px-4 sm:px-6 py-3 text-xs uppercase tracking-wider text-gray-500 font-semibold">Sharpe</th>
                  <th className="text-right px-4 sm:px-6 py-3 text-xs uppercase tracking-wider text-gray-500 font-semibold">Max Drawdown</th>
                  <th className="text-left px-4 sm:px-6 py-3 text-xs uppercase tracking-wider text-gray-500 font-semibold hidden sm:table-cell">Market Context</th>
                </tr>
              </thead>
              <tbody>
                {yearlyStats.map((row) => (
                  <tr key={row.period} className="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors">
                    <td className="px-4 sm:px-6 py-4 font-medium text-white">{row.period}</td>
                    <td className={`px-4 sm:px-6 py-4 text-right font-semibold ${row.positive ? 'text-emerald-400' : 'text-red-400'}`}>
                      {row.return_pct > 0 ? '+' : ''}{row.return_pct}%
                    </td>
                    <td className={`px-4 sm:px-6 py-4 text-right ${row.sharpe >= 0 ? 'text-gray-300' : 'text-red-400'}`}>
                      {row.sharpe.toFixed(2)}
                    </td>
                    <td className="px-4 sm:px-6 py-4 text-right text-gray-400">{row.max_dd_pct}%</td>
                    <td className="px-4 sm:px-6 py-4 text-gray-500 text-xs hidden sm:table-cell">
                      {MARKET_CONTEXT[row.period.split('\u2013')[0]] || ''}
                    </td>
                  </tr>
                ))}
                {/* Total row */}
                {yearlyStats.length > 0 && (
                  <tr className="bg-amber-500/10 border-t border-amber-500/30">
                    <td className="px-4 sm:px-6 py-4 font-bold text-amber-400">10-Year Total</td>
                    <td className="px-4 sm:px-6 py-4 text-right font-bold text-emerald-400">+{metrics.total_return_pct}%</td>
                    <td className="px-4 sm:px-6 py-4 text-right font-bold text-amber-400">{metrics.sharpe_ratio?.toFixed(2)}</td>
                    <td className="px-4 sm:px-6 py-4 text-right font-bold text-gray-300">{metrics.max_drawdown_pct?.toFixed(1)}%</td>
                    <td className="px-4 sm:px-6 py-4 text-amber-400/70 text-xs hidden sm:table-cell">Feb 2016 – Feb 2026</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* Benchmark Comparison */}
      <section className="max-w-5xl mx-auto px-4 sm:px-6 pb-12">
        <h2 className="text-2xl font-bold text-white mb-6 flex items-center gap-2">
          <BarChart3 className="w-6 h-6 text-amber-400" />
          10-Year Benchmark Comparison
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
                    style={{ width: `${(b.value / maxReturn) * 100}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Durability Callout */}
      <section className="max-w-5xl mx-auto px-4 sm:px-6 pb-12">
        <div className="bg-gradient-to-r from-emerald-900/30 to-emerald-800/20 border border-emerald-700/30 rounded-xl p-6 sm:p-8 text-center">
          <Shield className="w-8 h-8 text-emerald-400 mx-auto mb-3" />
          <div className="text-3xl font-bold text-emerald-400 mb-1">
            {metrics.positive_years}/{metrics.total_years} Years Profitable
          </div>
          <p className="text-emerald-200/70 text-sm max-w-xl mx-auto">
            Survived the 2018 volatility spike, COVID crash, 2022 bear market, and tariff shocks — delivering +{metrics.total_return_pct}% while SPY returned +{metrics.benchmark_return_pct}%.
          </p>
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
                Unlike backtesting, walk-forward simulation tests each period using only data available at the time.
                Parameters are optimized on past data, then locked and tested on the next unseen period — exactly
                how the strategy would have performed in real time.
              </p>
            </div>
            <div>
              <h3 className="text-white font-semibold mb-2">Why 10 years matters</h3>
              <p className="text-gray-400 text-sm leading-relaxed">
                A 5-year test might catch one bear market. A full decade covers the 2018 volatility spike,
                the COVID pandemic crash, the 2022 rate-hike bear market, and multiple bull cycles —
                proving the strategy adapts across all conditions.
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
              <h3 className="text-white font-semibold mb-2">Regime-aware trading</h3>
              <p className="text-gray-400 text-sm leading-relaxed">
                The system detects 7 distinct market regimes in real-time — from strong bull to panic/crash — and
                adjusts position sizing and risk tolerance automatically. The regime bands on the chart show when
                each regime was active.
              </p>
            </div>
          </div>
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
        &copy; {new Date().getFullYear()} RigaCap. All rights reserved.
      </div>
    </div>
  );
}
