import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';
import TopNav from './components/TopNav';

const SectionLabel = ({ children }) => (
  <div className="flex items-center gap-3 mb-5">
    <span className="inline-block w-6 h-px bg-claret" />
    <span className="font-body text-[0.78rem] font-medium tracking-[0.18em] uppercase text-ink-mute">{children}</span>
  </div>
);

const Navbar = () => <TopNav />;

export default function MethodologyPageV2() {
  useEffect(() => { document.title = 'Methodology & Assumptions | RigaCap'; }, []);

  return (
    <div className="min-h-screen bg-paper font-body text-ink text-[17px] leading-[1.65] antialiased">
      <Navbar />

      {/* Hero */}
      <section className="pt-16 pb-0 sm:pt-20">
        <div className="max-w-[800px] mx-auto px-4 sm:px-8">
          <SectionLabel>Methodology</SectionLabel>
          <h1 className="font-display font-normal text-ink mb-4 tracking-[-0.025em]" style={{ fontSize: 'clamp(2.2rem, 4.5vw, 3.5rem)', fontVariationSettings: '"opsz" 144' }}>
            How the numbers <em className="text-claret italic">are made.</em>
          </h1>
          <p className="text-ink-mute text-[1.05rem] leading-[1.65] max-w-[60ch] mb-0">
            Full disclosure of how our walk-forward simulations work, what they assume, and where the biases are.
            We'd rather you understand the limitations before subscribing than discover them after.
          </p>
        </div>
      </section>

      {/* Simulation Assumptions */}
      <section className="py-16 border-t border-rule mt-16">
        <div className="max-w-[800px] mx-auto px-4 sm:px-8">
          <SectionLabel>What the Simulations Assume</SectionLabel>
          <h2 className="font-display text-ink mb-6 tracking-[-0.02em]" style={{ fontSize: 'clamp(1.6rem, 3vw, 2.25rem)', fontVariationSettings: '"opsz" 96' }}>
            Every assumption that <em className="text-claret italic">favors</em> the simulation.
          </h2>

          <div className="overflow-x-auto">
            <table className="w-full border-collapse" style={{ fontFeatureSettings: '"tnum"' }}>
              <thead>
                <tr>
                  <th className="text-left py-3 pr-4 font-body font-medium text-[0.75rem] tracking-[0.15em] uppercase text-ink-mute border-b border-rule-dark">Assumption</th>
                  <th className="text-left py-3 px-4 font-body font-medium text-[0.75rem] tracking-[0.15em] uppercase text-ink-mute border-b border-rule-dark">Value</th>
                  <th className="text-left py-3 pl-4 font-body font-medium text-[0.75rem] tracking-[0.15em] uppercase text-ink-mute border-b border-rule-dark hidden sm:table-cell">Impact</th>
                </tr>
              </thead>
              <tbody>
                {[
                  ['Slippage', '0%', 'Trades execute at exact closing price. Real execution may differ by 0.05–0.2%.', true],
                  ['Commissions', '$0', 'Assumes commission-free broker (standard at most brokers today).', true],
                  ['SPY benchmark dividends', 'Not reinvested', 'Price return only. Understates SPY by ~1.5–2% annually.', true],
                  ['Market impact', 'None modeled', 'No price impact from position entry/exit. Minimal for portfolios under $500K.', true],
                  ['Data adjustments', 'Split-adjusted', 'Stock splits handled automatically. No dividend adjustment on individual stocks.', false],
                  ['Initial capital', '$100,000', 'Returns are percentage-based, scalable to most portfolio sizes.', false],
                ].map(([assumption, value, impact, isBias]) => (
                  <tr key={assumption} className="border-b border-rule">
                    <td className="py-4 pr-4 text-[0.95rem]">{assumption}</td>
                    <td className={`py-4 px-4 font-mono text-[0.9rem] font-medium ${isBias ? 'text-claret' : 'text-ink'}`}>{value}</td>
                    <td className="py-4 pl-4 text-[0.9rem] text-ink-mute hidden sm:table-cell">{impact}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-4 text-[0.85rem] text-ink-light leading-relaxed">
            Zero slippage and zero commissions favor simulated returns over real-world results. We disclose this bias rather than hide it.
          </p>
        </div>
      </section>

      {/* Walk-Forward Process */}
      <section className="py-16 border-t border-rule">
        <div className="max-w-[800px] mx-auto px-4 sm:px-8">
          <SectionLabel>Walk-Forward Process</SectionLabel>
          <h2 className="font-display text-ink mb-8 tracking-[-0.02em]" style={{ fontSize: 'clamp(1.6rem, 3vw, 2.25rem)', fontVariationSettings: '"opsz" 96' }}>
            How we prevent <em className="text-claret italic">hindsight bias.</em>
          </h2>

          <div className="space-y-5 text-[1.05rem] leading-[1.75] text-ink max-w-[62ch]">
            <p>
              Walk-forward simulation tests the strategy across biweekly periods over the full 5-year window. Strategy
              parameters are <strong className="font-medium">fixed at the start of the test and applied forward</strong> &mdash;
              no future information is ever used, and no per-period re-tuning hides hindsight bias.
            </p>
            <p>
              The period structure governs <strong className="font-medium">rebalancing cadence</strong>, not re-optimization.
              At each period boundary, positions are evaluated against the same locked rule set. This produces an equity
              curve that reflects what real-time decision-making would have looked like with that configuration.
            </p>
            <p>
              To test robustness, we run the same process across <strong className="font-medium">multiple start dates</strong> (Jan&ndash;Apr 2021).
              The track record page shows the average, best, and worst outcomes across all start dates &mdash; not a single cherry-picked run.
            </p>
          </div>

          <div className="grid sm:grid-cols-3 gap-8 mt-10 pt-8 border-t border-rule">
            {[
              ['Tuned via', 'Bayesian parameter optimization (Optuna TPE), multi-objective: maximize Sharpe, minimize drawdown. The configuration is selected once, then locked.'],
              ['Locked across periods', 'Position sizing, exit rules, signal thresholds, regime logic. No per-period re-tuning, no hindsight bias.'],
              ['Tested across', 'Multiple start dates over a 5-year window. Average, best, and worst outcomes all published.'],
            ].map(([label, text]) => (
              <div key={label}>
                <div className="font-body text-[0.75rem] font-medium tracking-[0.15em] uppercase text-ink-mute mb-2">{label}</div>
                <p className="text-ink text-[0.95rem] leading-relaxed">{text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Position Sizing & Risk */}
      <section className="py-16 border-t border-rule">
        <div className="max-w-[800px] mx-auto px-4 sm:px-8">
          <SectionLabel>Position Sizing & Risk Controls</SectionLabel>
          <h2 className="font-display text-ink mb-8 tracking-[-0.02em]" style={{ fontSize: 'clamp(1.6rem, 3vw, 2.25rem)', fontVariationSettings: '"opsz" 96' }}>
            How capital is <em className="text-claret italic">deployed and protected.</em>
          </h2>

          <div className="grid sm:grid-cols-2 gap-x-12 gap-y-8">
            {[
              ['Max positions', '5–7', 'Concentrated by design; not diluted across many weak signals'],
              ['Position size', '12–20% of capital', 'Per position; total exposure up to ~80%'],
              ['Trailing stop', '12–18% from high water mark', 'Primary exit rule; tightens after +12% profit'],
              ['Market regime filter', '7-regime detection', 'Cascade Guard pauses entries when panic-grade stress is detected'],
            ].map(([label, value, desc]) => (
              <div key={label}>
                <div className="font-body text-[0.75rem] font-medium tracking-[0.15em] uppercase text-ink-mute mb-1">{label}</div>
                <div className="font-display text-[1.1rem] font-medium text-ink" style={{ fontVariationSettings: '"opsz" 48' }}>{value}</div>
                <div className="text-ink-mute text-[0.88rem] mt-1">{desc}</div>
              </div>
            ))}
          </div>

          <div className="mt-10 pt-8 border-t border-rule">
            <div className="font-body text-[0.75rem] font-medium tracking-[0.15em] uppercase text-ink-mute mb-2">Cascade Guard (validated safeguard)</div>
            <p className="text-ink text-[0.98rem] leading-relaxed max-w-[58ch]">
              When 3+ positions hit trailing stop on the same day, the system freezes all new entries for 10 trading days.
              Validated against a no-Cascade-Guard counterfactual: the safeguard contributed approximately
              <strong className="font-medium"> +37 percentage points of return</strong> across the 5-year test period
              (~+3.7 pp annualized) by avoiding forced re-entries during cascade selloffs.
            </p>
          </div>
        </div>
      </section>

      {/* Universe & Data */}
      <section className="py-16 border-t border-rule">
        <div className="max-w-[800px] mx-auto px-4 sm:px-8">
          <SectionLabel>Universe & Data</SectionLabel>
          <h2 className="font-display text-ink mb-8 tracking-[-0.02em]" style={{ fontSize: 'clamp(1.6rem, 3vw, 2.25rem)', fontVariationSettings: '"opsz" 96' }}>
            What we scan and <em className="text-claret italic">what we exclude.</em>
          </h2>

          <p className="text-[1.05rem] leading-[1.75] text-ink max-w-[62ch] mb-8">
            The system scans <strong className="font-medium">~6,500 US stocks</strong> across NASDAQ and NYSE daily.
            All ETFs, leveraged products, inverse funds, commodities, bonds, and crypto products are excluded &mdash; only individual equities.
          </p>

          <div className="grid sm:grid-cols-2 gap-x-12 gap-y-6">
            {[
              ['Minimum daily volume', '500,000 shares'],
              ['Minimum price', '$15.00'],
              ['Data source', 'Alpaca SIP consolidated feed (all exchanges)'],
              ['Fallback', 'yfinance (for index symbols like ^VIX, ^GSPC)'],
            ].map(([label, value]) => (
              <div key={label}>
                <div className="font-body text-[0.75rem] font-medium tracking-[0.15em] uppercase text-ink-mute mb-1">{label}</div>
                <div className="text-ink text-[0.95rem]">{value}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Capacity */}
      <section className="py-16 border-t border-rule">
        <div className="max-w-[800px] mx-auto px-4 sm:px-8">
          <SectionLabel>Strategy Capacity</SectionLabel>
          <h2 className="font-display text-ink mb-6 tracking-[-0.02em]" style={{ fontSize: 'clamp(1.6rem, 3vw, 2.25rem)', fontVariationSettings: '"opsz" 96' }}>
            The honest answer: <em className="text-claret italic">it depends.</em>
          </h2>

          <div className="overflow-x-auto mb-6">
            <table className="w-full border-collapse">
              <thead>
                <tr>
                  <th className="text-left py-3 pr-4 font-body font-medium text-[0.75rem] tracking-[0.15em] uppercase text-ink-mute border-b border-rule-dark">Scenario</th>
                  <th className="text-left py-3 pl-4 font-body font-medium text-[0.75rem] tracking-[0.15em] uppercase text-ink-mute border-b border-rule-dark">Capacity estimate</th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-b border-rule">
                  <td className="py-4 pr-4 text-[0.95rem]">Typical signal on a large-cap name ($50M+ daily volume)</td>
                  <td className="py-4 pl-4 text-[0.95rem] text-ink">Comfortable at current subscriber levels; collective AUM up to ~$15&ndash;25M deployable</td>
                </tr>
                <tr className="border-b border-rule">
                  <td className="py-4 pr-4 text-[0.95rem]">Signal near the universe boundary (~$7.5M daily volume)</td>
                  <td className="py-4 pl-4 text-[0.95rem] text-ink">Tighter. Collective AUM above ~$2&ndash;3M starts producing noticeable slippage</td>
                </tr>
                <tr>
                  <td className="py-4 pr-4 text-[0.95rem]">Distribution across a typical month of signals</td>
                  <td className="py-4 pl-4 text-[0.95rem] text-ink">Most signals land in the first category; a minority land closer to the second</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div className="space-y-4 text-[1.05rem] leading-[1.75] text-ink max-w-[62ch]">
            <p>
              <strong className="font-medium">What we monitor.</strong> Once a signal is published, we track the stock's price action
              in the minutes and hours that follow, measuring the gap between our published entry price and what was actually
              achievable in the market during the execution window.
            </p>
            <p>
              <strong className="font-medium">What we may change.</strong> If collective execution quality degrades materially, options include:
              raising the liquidity filter, staggering signal delivery, closing new subscriptions, or raising prices.
              We'd rather preserve signal quality for existing subscribers than grow past what the strategy can support.
            </p>
          </div>
        </div>
      </section>

      {/* Execution Timing */}
      <section className="py-16 border-t border-rule">
        <div className="max-w-[800px] mx-auto px-4 sm:px-8">
          <SectionLabel>Execution Timing</SectionLabel>
          <h2 className="font-display text-ink mb-6 tracking-[-0.02em]" style={{ fontSize: 'clamp(1.6rem, 3vw, 2.25rem)', fontVariationSettings: '"opsz" 96' }}>
            Simulation vs. <em className="text-claret italic">live execution.</em>
          </h2>

          <div className="space-y-4 text-[1.05rem] leading-[1.75] text-ink max-w-[62ch]">
            <p>
              The walk-forward simulation uses <strong className="font-medium">end-of-day prices</strong> for both entries and exits.
              In live operation, the system polls open positions every <strong className="font-medium">5 minutes during market hours</strong> and executes on trigger conditions when they occur intraday.
            </p>
            <p>
              <strong className="font-medium">Where live execution may outperform simulation:</strong> On trailing-stop exits,
              a 5-minute polling system exits at the moment the stop level is breached. An end-of-day simulation records the exit
              at whatever price the stock closes at &mdash; which, on days of continued decline, can be meaningfully below the actual stop level.
            </p>
            <p>
              <strong className="font-medium">Where live execution may underperform:</strong> Intraday polling introduces whipsaw exits
              triggered by volatility spikes that an EOD system would have ridden through, gap moves that blow past stop levels
              between polls, and false triggers on intraday noise.
            </p>
            <p className="font-display italic text-ink-mute" style={{ fontVariationSettings: '"opsz" 24' }}>
              Net effect: unquantified. We do not present any performance figure as being enhanced by intraday execution.
            </p>
          </div>
        </div>
      </section>

      {/* Disclaimer */}
      <section className="py-16 border-t border-rule">
        <div className="max-w-[800px] mx-auto px-4 sm:px-8">
          <div className="bg-paper-card border-l-[3px] border-claret p-8">
            <h3 className="font-display text-[1.15rem] font-semibold text-ink mb-3">Important</h3>
            <p className="text-ink-mute text-[0.95rem] leading-[1.7]">
              All results shown are from walk-forward simulations using historical data and do not represent actual trading returns.
              Simulations assume zero slippage and zero commissions, which favors simulated returns over real-world results.
              SPY benchmark comparisons use price return only (excluding dividends).
              For information purposes only and not a solicitation to invest, purchase, or sell securities in which RigaCap has an interest.
              Past performance does not guarantee future results. Investing involves risk, including the possible loss of principal.
              RigaCap, LLC is not a registered investment advisor.
              See our <Link to="/terms" className="text-claret underline underline-offset-2 decoration-1">Terms of Service</Link> for full details.
            </p>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-paper-deep border-t border-rule py-8">
        <div className="max-w-[800px] mx-auto px-4 sm:px-8 flex flex-col sm:flex-row justify-between items-start gap-4">
          <p className="text-[0.78rem] text-ink-light max-w-[50ch] leading-relaxed">
            For information purposes only. Past performance does not guarantee future results.
          </p>
          <p className="text-[0.78rem] text-ink-light">&copy; 2026 RigaCap, LLC</p>
        </div>
      </footer>
    </div>
  );
}
