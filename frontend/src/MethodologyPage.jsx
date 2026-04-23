import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, Shield, BarChart3, AlertTriangle, Database, Settings, Clock } from 'lucide-react';

export default function MethodologyPage() {
  useEffect(() => { document.title = 'Methodology & Assumptions | RigaCap'; }, []);

  return (
    <div className="min-h-screen bg-gray-950 text-gray-300">
      <nav className="bg-gray-900 border-b border-gray-800">
        <div className="max-w-4xl mx-auto px-4 py-4 flex items-center gap-4">
          <Link to="/track-record" className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors">
            <ArrowLeft size={18} />
            <span className="text-sm">Back to Track Record</span>
          </Link>
        </div>
      </nav>

      <section className="max-w-4xl mx-auto px-4 sm:px-6 py-12">
        <div className="flex items-center gap-3 mb-2">
          <Shield className="w-7 h-7 text-amber-400" />
          <h1 className="text-3xl font-bold text-white">Methodology & Assumptions</h1>
        </div>
        <p className="text-gray-400 mb-10">
          Full disclosure of how our walk-forward simulations work, what they assume, and where the numbers come from.
        </p>

        {/* Simulation Assumptions */}
        <section className="mb-10">
          <h2 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-amber-400" />
            What the Simulations Assume
          </h2>
          <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-800/50 text-left">
                  <th className="px-5 py-3 text-gray-400 font-medium">Assumption</th>
                  <th className="px-5 py-3 text-gray-400 font-medium">Value</th>
                  <th className="px-5 py-3 text-gray-400 font-medium hidden sm:table-cell">Impact</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                <tr>
                  <td className="px-5 py-3 text-gray-300">Slippage</td>
                  <td className="px-5 py-3 text-amber-400 font-medium">0%</td>
                  <td className="px-5 py-3 text-gray-500 hidden sm:table-cell">Trades execute at exact closing price. Real execution may differ by 0.05–0.2%.</td>
                </tr>
                <tr>
                  <td className="px-5 py-3 text-gray-300">Commissions</td>
                  <td className="px-5 py-3 text-amber-400 font-medium">$0</td>
                  <td className="px-5 py-3 text-gray-500 hidden sm:table-cell">Assumes commission-free broker (standard at most brokers today).</td>
                </tr>
                <tr>
                  <td className="px-5 py-3 text-gray-300">SPY benchmark dividends</td>
                  <td className="px-5 py-3 text-amber-400 font-medium">Not reinvested</td>
                  <td className="px-5 py-3 text-gray-500 hidden sm:table-cell">Price return only. Understates SPY by ~1.5–2% annually.</td>
                </tr>
                <tr>
                  <td className="px-5 py-3 text-gray-300">Market impact</td>
                  <td className="px-5 py-3 text-amber-400 font-medium">None modeled</td>
                  <td className="px-5 py-3 text-gray-500 hidden sm:table-cell">No price impact from position entry/exit. Minimal for portfolios under $500K.</td>
                </tr>
                <tr>
                  <td className="px-5 py-3 text-gray-300">Data adjustments</td>
                  <td className="px-5 py-3 text-emerald-400 font-medium">Split-adjusted</td>
                  <td className="px-5 py-3 text-gray-500 hidden sm:table-cell">Stock splits handled automatically. No dividend adjustment on individual stocks.</td>
                </tr>
                <tr>
                  <td className="px-5 py-3 text-gray-300">Initial capital</td>
                  <td className="px-5 py-3 text-gray-300 font-medium">$100,000</td>
                  <td className="px-5 py-3 text-gray-500 hidden sm:table-cell">Simulations start with $100K. Returns are percentage-based, scalable to most portfolio sizes.</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p className="text-xs text-gray-600 mt-3">
            Zero slippage and zero commissions favor simulated returns over real-world results. We disclose this bias rather than hide it.
          </p>
        </section>

        {/* Position Sizing & Risk */}
        <section className="mb-10">
          <h2 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
            <Settings className="w-5 h-5 text-amber-400" />
            Position Sizing & Risk Controls
          </h2>
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 space-y-4">
            <div className="grid sm:grid-cols-2 gap-4">
              <div>
                <div className="text-gray-500 text-xs uppercase tracking-wider mb-1">Max positions</div>
                <div className="text-white font-semibold">4–8 (adaptive)</div>
                <div className="text-gray-500 text-xs mt-1">Adjusts biweekly based on market conditions</div>
              </div>
              <div>
                <div className="text-gray-500 text-xs uppercase tracking-wider mb-1">Position size</div>
                <div className="text-white font-semibold">12–20% of capital</div>
                <div className="text-gray-500 text-xs mt-1">Per position; total exposure up to 80%</div>
              </div>
              <div>
                <div className="text-gray-500 text-xs uppercase tracking-wider mb-1">Trailing stop</div>
                <div className="text-white font-semibold">12–18% from high water mark</div>
                <div className="text-gray-500 text-xs mt-1">Primary exit rule; tightens after +12% profit</div>
              </div>
              <div>
                <div className="text-gray-500 text-xs uppercase tracking-wider mb-1">Market regime filter</div>
                <div className="text-white font-semibold">SPY &gt; 200-day MA</div>
                <div className="text-gray-500 text-xs mt-1">Reduces exposure or exits when regime deteriorates</div>
              </div>
            </div>
            <div className="pt-3 border-t border-gray-800">
              <div className="text-gray-500 text-xs uppercase tracking-wider mb-1">Emergency pause (Cascade Guard)</div>
              <div className="text-gray-300 text-sm">
                When 3+ positions hit trailing stop on the same day, the system freezes all new entries for 10 trading days.
                This prevented re-entry during cascade selloffs and added significant return over the simulation period.
              </div>
            </div>
          </div>
        </section>

        {/* Walk-Forward Method */}
        <section className="mb-10">
          <h2 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
            <Clock className="w-5 h-5 text-amber-400" />
            Walk-Forward Process
          </h2>
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
            <div className="space-y-4 text-sm text-gray-400 leading-relaxed">
              <p>
                Walk-forward simulation divides the test period into <strong className="text-gray-200">138 biweekly periods</strong> (14 days each).
                At the start of each period, strategy parameters are optimized using only data available up to that date —
                no future information is ever used.
              </p>
              <p>
                The optimizer evaluates parameters over a <strong className="text-gray-200">60-day lookback window</strong>, then locks
                those parameters for the next 14 days of live trading. This repeats for every period, producing an equity
                curve that reflects real-time decision-making.
              </p>
              <p>
                To test robustness, we run the same process across <strong className="text-gray-200">multiple start dates</strong> (Jan–Apr 2021).
                The track record page shows the average, best, and worst outcomes across all start dates — not a single cherry-picked run.
              </p>
              <div className="grid sm:grid-cols-3 gap-4 pt-3 border-t border-gray-800">
                <div>
                  <div className="text-gray-500 text-xs uppercase tracking-wider mb-1">Optimized per period</div>
                  <div className="text-gray-300">Trailing stop %, position size, momentum weights, DWAP threshold, breakout window</div>
                </div>
                <div>
                  <div className="text-gray-500 text-xs uppercase tracking-wider mb-1">Fixed across periods</div>
                  <div className="text-gray-300">Strategy type (Ensemble), market regime logic, universe, rebalance frequency</div>
                </div>
                <div>
                  <div className="text-gray-500 text-xs uppercase tracking-wider mb-1">Optimizer</div>
                  <div className="text-gray-300">Optuna TPE (Bayesian), multi-objective: maximize Sharpe, minimize drawdown</div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Universe & Data */}
        <section className="mb-10">
          <h2 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
            <Database className="w-5 h-5 text-amber-400" />
            Universe & Data
          </h2>
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 space-y-4 text-sm text-gray-400 leading-relaxed">
            <p>
              The system scans <strong className="text-gray-200">~6,500 US stocks</strong> across NASDAQ and NYSE daily.
              All ETFs, leveraged products, inverse funds, commodities, bonds, and crypto products are excluded — only individual equities.
            </p>
            <div className="grid sm:grid-cols-2 gap-4">
              <div>
                <div className="text-gray-500 text-xs uppercase tracking-wider mb-1">Minimum daily volume</div>
                <div className="text-gray-300">500,000 shares</div>
              </div>
              <div>
                <div className="text-gray-500 text-xs uppercase tracking-wider mb-1">Minimum price</div>
                <div className="text-gray-300">$15.00</div>
              </div>
              <div>
                <div className="text-gray-500 text-xs uppercase tracking-wider mb-1">Data source</div>
                <div className="text-gray-300">Alpaca SIP consolidated feed (all exchanges)</div>
              </div>
              <div>
                <div className="text-gray-500 text-xs uppercase tracking-wider mb-1">Fallback</div>
                <div className="text-gray-300">yfinance (for index symbols like ^VIX, ^GSPC)</div>
              </div>
            </div>
          </div>
        </section>

        {/* Capacity */}
        <section className="mb-10">
          <h2 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-amber-400" />
            Strategy Capacity
          </h2>
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 text-sm text-gray-400 leading-relaxed">
            <p>
              With a 500,000-share minimum volume filter and $15+ price floor, typical signal candidates
              trade $7.5M–$50M+ daily. At 4 positions of 20% each, a $500K portfolio deploys ~$400K across
              4 stocks — well under 1% of daily volume for most signal candidates.
            </p>
            <p className="mt-3">
              Strategy capacity is estimated at <strong className="text-gray-200">$2–5M AUM</strong> before market impact
              becomes material. Beyond that, position sizing or universe adjustments would be required.
              This is not currently a constraint for individual subscribers.
            </p>
          </div>
        </section>

        {/* Disclaimer */}
        <section className="mb-10">
          <div className="bg-amber-900/20 border border-amber-700/30 rounded-xl p-6 text-sm text-amber-200/80 leading-relaxed">
            <p className="font-semibold text-amber-300 mb-2">Important</p>
            <p>
              All results shown are from walk-forward simulations using historical data and do not represent actual trading returns.
              Simulations assume zero slippage and zero commissions, which favors simulated returns over real-world results.
              SPY benchmark comparisons use price return only (excluding dividends).
              Past performance is not indicative of future results. Investing involves risk, including the possible loss of principal.
              RigaCap provides algorithmic signals and educational information only — we are not registered investment advisors.
              See our{' '}
              <Link to="/terms" className="text-amber-400 hover:text-amber-300 underline">Terms of Service</Link> for full details.
            </p>
          </div>
        </section>
      </section>

      <div className="max-w-4xl mx-auto px-4 sm:px-6 pb-8 pt-4 border-t border-gray-800 text-center text-sm text-gray-500">
        &copy; {new Date().getFullYear()} RigaCap, LLC. All rights reserved.
      </div>
    </div>
  );
}
