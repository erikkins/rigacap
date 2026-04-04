import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, TrendingUp, BarChart3, Shield, Activity, ArrowRight } from 'lucide-react';
import TrackRecordChart from './components/TrackRecordChart';

const YEARLY_DATA = [
  { period: '2021', return: '+8.3%', range: '-14% to +55%', spy: '+21.0%', context: 'Post-COVID rally, strategy ramp-up', positive: true },
  { period: '2022', return: '+6.0%', range: '+4% to +8%', spy: '-20.4%', context: 'Fed rate hikes — RigaCap stayed positive while SPY fell 20%', positive: true },
  { period: '2023', return: '+4.5%', range: '+2% to +10%', spy: '+23.4%', context: 'Cautious positioning during AI-driven recovery', positive: true },
  { period: '2024', return: '+20.3%', range: '+20% to +22%', spy: '+23.8%', context: 'Election volatility, near parity with SPY', positive: true },
  { period: '2025', return: '+57.4%', range: '+57% to +60%', spy: '+18.3%', context: 'Breakout year — tripled SPY returns', positive: true },
];

const HEADLINE_METRICS = [
  { value: '+152%', label: '5-Year Avg Return', subtitle: 'Range: +93% to +267%', color: 'text-emerald-400' },
  { value: '~20%', label: 'Annualized Return', subtitle: 'Range: 14% to 30%', color: 'text-emerald-400' },
  { value: '0.85', label: 'Avg Sharpe Ratio', subtitle: 'Best: 0.95', color: 'text-amber-400' },
  { value: '-20.6%', label: 'Avg Max Drawdown', subtitle: 'Worst: -23.9%', color: 'text-red-400' },
];

const BENCHMARKS = [
  { name: 'RigaCap Ensemble (avg)', value: 152, label: '+152%', color: 'from-amber-400 to-amber-500' },
  { name: 'RigaCap Best Case', value: 267, label: '+267%', color: 'from-amber-300 to-amber-400', dashed: true },
  { name: 'S&P 500', value: 84, label: '+84%', color: 'from-gray-400 to-gray-500' },
];

export default function TrackRecordPage() {
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
                  <th className="text-left px-4 sm:px-6 py-3 text-xs uppercase tracking-wider text-gray-500 font-semibold">Year</th>
                  <th className="text-right px-4 sm:px-6 py-3 text-xs uppercase tracking-wider text-gray-500 font-semibold">Avg Return</th>
                  <th className="text-right px-4 sm:px-6 py-3 text-xs uppercase tracking-wider text-gray-500 font-semibold hidden sm:table-cell">Range</th>
                  <th className="text-right px-4 sm:px-6 py-3 text-xs uppercase tracking-wider text-gray-500 font-semibold">S&P 500</th>
                  <th className="text-left px-4 sm:px-6 py-3 text-xs uppercase tracking-wider text-gray-500 font-semibold hidden sm:table-cell">Context</th>
                </tr>
              </thead>
              <tbody>
                {YEARLY_DATA.map((row) => (
                  <tr key={row.period} className="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors">
                    <td className="px-4 sm:px-6 py-4 font-medium text-white">{row.period}</td>
                    <td className={`px-4 sm:px-6 py-4 text-right font-semibold ${row.positive ? 'text-emerald-400' : 'text-red-400'}`}>{row.return}</td>
                    <td className="px-4 sm:px-6 py-4 text-right text-gray-500 text-xs hidden sm:table-cell">{row.range}</td>
                    <td className="px-4 sm:px-6 py-4 text-right text-gray-400">{row.spy}</td>
                    <td className="px-4 sm:px-6 py-4 text-gray-500 text-xs hidden sm:table-cell">{row.context}</td>
                  </tr>
                ))}
                {/* Total row */}
                <tr className="bg-amber-500/10 border-t border-amber-500/30">
                  <td className="px-4 sm:px-6 py-4 font-bold text-amber-400">5-Year Avg</td>
                  <td className="px-4 sm:px-6 py-4 text-right font-bold text-emerald-400">+152%</td>
                  <td className="px-4 sm:px-6 py-4 text-right font-bold text-gray-400 text-xs hidden sm:table-cell">+93% to +267%</td>
                  <td className="px-4 sm:px-6 py-4 text-right font-bold text-gray-300">+84%</td>
                  <td className="px-4 sm:px-6 py-4 text-amber-400/70 text-xs hidden sm:table-cell">7/7 start dates positive, all beat SPY</td>
                </tr>
              </tbody>
            </table>
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
                The portfolio reoptimizes biweekly with a maximum of 6 positions at 15% each. Parameters adapt
                through 7 distinct market regimes — from strong bull to panic/crash — without manual intervention.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Win Rate Callout */}
      <section className="max-w-5xl mx-auto px-4 sm:px-6 pb-12">
        <div className="bg-gradient-to-r from-emerald-900/30 to-emerald-800/20 border border-emerald-700/30 rounded-xl p-6 sm:p-8 text-center">
          <Activity className="w-8 h-8 text-emerald-400 mx-auto mb-3" />
          <div className="text-3xl font-bold text-emerald-400 mb-1">100% Win Rate</div>
          <p className="text-emerald-200/70 text-sm">5 of 5 years profitable across all 7 tested start dates — including 2022 where RigaCap gained +6% while the S&P 500 fell -20%</p>
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
