import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import TrackRecordChart from './components/TrackRecordChart';
import MarketMeasuredSignup from './components/MarketMeasuredSignup';
import TopNav from './components/TopNav';

const SectionLabel = ({ children }) => (
  <div className="flex items-center gap-3 mb-5">
    <span className="inline-block w-6 h-px bg-claret" />
    <span className="font-body text-[0.78rem] font-medium tracking-[0.18em] uppercase text-ink-mute">{children}</span>
  </div>
);

const Navbar = () => <TopNav />;

export default function TrackRecordPageV2() {
  useEffect(() => { document.title = 'Track Record | RigaCap'; }, []);

  return (
    <div className="min-h-screen bg-paper font-body text-ink text-[17px] leading-[1.65] antialiased">
      <Navbar />

      {/* Hero */}
      <section className="pt-16 pb-0 sm:pt-20">
        <div className="max-w-[1120px] mx-auto px-4 sm:px-8">
          <SectionLabel>Track Record</SectionLabel>
          <h1 className="font-display font-normal text-ink mb-4 tracking-[-0.025em]" style={{ fontSize: 'clamp(2.2rem, 4.5vw, 3.5rem)', fontVariationSettings: '"opsz" 144' }}>
            Five years. Many start dates. <em className="text-claret italic">No cherry-picking.</em>
          </h1>
          <p className="text-ink-mute text-[1.05rem] leading-[1.65] max-w-[60ch]">
            Year-by-year performance validated through walk-forward simulation &mdash; no hindsight bias, no curve-fitting.
            Best, average, and worst outcomes all published.
          </p>
        </div>
      </section>

      {/* Headline Metrics */}
      <section className="mt-14">
        <div className="max-w-[1120px] mx-auto px-4 sm:px-8">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-px bg-rule">
            {[
              ['+160%', 'Average Return', 'multiple start dates, same strategy'],
              ['+109%', 'Worst Start Date', 'Still positive, still ahead of SPY'],
              ['0.92', 'Avg Sharpe Ratio', 'Risk-adjusted performance'],
              ['20%', 'Avg Max Drawdown', 'Peak to trough'],
            ].map(([value, label, subtitle]) => (
              <div key={label} className="bg-paper-card p-6 sm:p-8 text-center">
                <div className="font-display text-3xl sm:text-4xl font-normal text-ink tracking-tight" style={{ fontVariationSettings: '"opsz" 144' }}>{value}</div>
                <div className="font-body text-[0.75rem] font-medium tracking-[0.12em] uppercase text-ink-mute mt-2">{label}</div>
                <div className="text-[0.8rem] text-ink-light mt-1">{subtitle}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Equity Curve */}
      <section className="py-16 border-t border-rule mt-12">
        <div className="max-w-[1120px] mx-auto px-4 sm:px-8">
          <SectionLabel>Equity Curve</SectionLabel>
          <h2 className="font-display text-ink mb-8 tracking-[-0.02em]" style={{ fontSize: 'clamp(1.6rem, 3vw, 2.25rem)', fontVariationSettings: '"opsz" 96' }}>
            5-Year Growth &mdash; <em className="text-claret italic">multiple start dates vs S&P 500.</em>
          </h2>

          <div className="bg-paper-card border border-rule p-4 sm:p-8">
            <TrackRecordChart />
            <p className="text-[0.82rem] text-ink-light mt-4 text-center">
              Solid line: average across multiple start dates. Shaded band: best to worst. All use the same strategy and parameters.
            </p>
          </div>
        </div>
      </section>

      {/* Performance Table */}
      <section className="py-16 border-t border-rule">
        <div className="max-w-[1120px] mx-auto px-4 sm:px-8">
          <SectionLabel>Performance Summary</SectionLabel>
          <h2 className="font-display text-ink mb-8 tracking-[-0.02em]" style={{ fontSize: 'clamp(1.6rem, 3vw, 2.25rem)', fontVariationSettings: '"opsz" 96' }}>
            The numbers, <em className="text-claret italic">walk-forward.</em>
          </h2>

          {/* SURFACE-MARKER:perf-comparison-table-START */}
          <div className="overflow-x-auto">
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
                <tr className="border-b border-rule bg-paper-card">
                  <td className="py-4 pr-4 text-[0.95rem] font-semibold text-ink">RigaCap walk-forward (avg. of multiple start dates)</td>
                  <td className="py-4 px-5 text-right font-mono text-[0.95rem] font-medium text-ink">+160%</td>
                  <td className="py-4 px-5 text-right font-mono text-[0.95rem] font-medium text-ink">~21.5%</td>
                  <td className="py-4 px-5 text-right font-mono text-[0.95rem] font-medium text-ink">0.92</td>
                  <td className="py-4 px-5 text-right font-mono text-[0.95rem] font-medium text-ink">20%</td>
                </tr>
                <tr>
                  <td className="py-4 pr-4 text-[0.95rem] italic text-ink-mute">S&P 500 (SPY, price only)</td>
                  <td className="py-4 px-5 text-right font-mono text-[0.95rem] text-ink-mute">+93%</td>
                  <td className="py-4 px-5 text-right font-mono text-[0.95rem] text-ink-mute">~13%</td>
                  <td className="py-4 px-5 text-right font-mono text-[0.95rem] text-ink-mute">&mdash;</td>
                  <td className="py-4 px-5 text-right font-mono text-[0.95rem] text-ink-mute">&mdash;</td>
                </tr>
              </tbody>
            </table>
          </div>
          {/* SURFACE-MARKER:perf-comparison-table-END */}

          <p className="mt-4 text-[0.85rem] text-ink-light leading-relaxed">
            Walk-forward simulation across multiple start dates from early 2021, each measured over a full 5-year window. Rebalance frictions modeled in-simulation; realized end-of-day fills used. Best: +252%. Worst: +109%.
            See <Link to="/methodology" className="text-claret underline underline-offset-2 decoration-1">full methodology</Link> for all assumptions.
          </p>

          {/* 11-year companion result — long-window consistency check */}
          <div className="mt-12 bg-paper-card border-l-[3px] border-claret p-8">
            <div className="font-body text-[0.75rem] font-medium tracking-[0.15em] uppercase text-ink-mute mb-3">
              The 11-Year Consistency Check
            </div>
            <div className="grid sm:grid-cols-4 gap-6 mt-4">
              <div>
                <div className="font-display text-[1.6rem] font-medium text-ink leading-none" style={{ fontVariationSettings: '"opsz" 96' }}>+675%</div>
                <div className="text-[0.78rem] text-ink-mute mt-1.5">11-year total return</div>
              </div>
              <div>
                <div className="font-display text-[1.6rem] font-medium text-claret leading-none" style={{ fontVariationSettings: '"opsz" 96' }}>~21.6%</div>
                <div className="text-[0.78rem] text-ink-mute mt-1.5">Annualized</div>
              </div>
              <div>
                <div className="font-display text-[1.6rem] font-medium text-ink leading-none" style={{ fontVariationSettings: '"opsz" 96' }}>0.95</div>
                <div className="text-[0.78rem] text-ink-mute mt-1.5">Sharpe</div>
              </div>
              <div>
                <div className="font-display text-[1.6rem] font-medium text-ink leading-none" style={{ fontVariationSettings: '"opsz" 96' }}>28%</div>
                <div className="text-[0.78rem] text-ink-mute mt-1.5">Max drawdown</div>
              </div>
            </div>
            <p className="mt-6 text-[0.95rem] text-ink leading-[1.6]">
              Same strategy, run from October 2015 through April 2026 — a full ten-and-a-half-year window covering the 2018 vol spikes, the COVID crash, the 2022 bear market, and the AI rally. The annualized return came in at <strong className="font-medium">~21.6%</strong>, within rounding of the 5-year multi-start average of <strong className="font-medium">~21.1%</strong>. Two different windows, two different validation methods, the same compound growth rate.
            </p>
            <p className="mt-3 text-[0.85rem] text-ink-light leading-relaxed">
              The longer window includes more bear cycles, so the max drawdown reads slightly higher (28% vs the 5-year's 20%). SPY over the same 11-year window: +318% (about ~14% annualized).
            </p>
          </div>
        </div>
      </section>

      {/* Highlights */}
      <section className="py-16 border-t border-rule">
        <div className="max-w-[1120px] mx-auto px-4 sm:px-8">
          <SectionLabel>Highlights</SectionLabel>

          <div className="grid sm:grid-cols-3 gap-px bg-rule">
            {[
              ['Positive in 2022', 'S&P fell 20%', 'Every start date ended 2022 in positive territory while broad markets had their worst year since 2008 \u2014 averaging around +8%.'],
              ['2.5x win/loss ratio', '42% win rate', 'Less than half the trades win, but the average winner returns roughly 2.5\u00d7 the size of the average loser. That asymmetry is the engine.'],
              ['+37pp from Cascade Guard', '~3.7pp annualized', 'When multiple positions hit their trailing stop on the same day, the system pauses new entries for ten days \u2014 preventing forced re-entries during cascading market stress. Validated against a full no-Cascade-Guard counterfactual.'],
            ].map(([title, subtitle, desc]) => (
              <div key={title} className="bg-paper-card p-8">
                <div className="font-display text-2xl text-ink mb-1" style={{ fontVariationSettings: '"opsz" 96' }}>{title}</div>
                <div className="font-mono text-[0.75rem] text-claret tracking-[0.1em] uppercase mb-3">{subtitle}</div>
                <p className="text-ink-mute text-[0.92rem] leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Bear Market Callout */}
      <section className="py-16 border-t border-rule">
        <div className="max-w-[800px] mx-auto px-4 sm:px-8">
          <div className="bg-paper-card border-l-[3px] border-claret p-8">
            <h3 className="font-display text-[1.15rem] font-semibold text-ink mb-3">The bear-market test.</h3>
            <p className="text-ink leading-[1.7]">
              The five-year window included one major bear market. <strong className="font-medium">Every start date ended 2022 in positive territory</strong> while the S&P fell 20% &mdash;{' '}
              not by luck, but by design. Regime-aware position sizing and trailing-stop discipline kept the strategy on the right side of risk through the year &mdash; responding to data as it changed, not predicting the drawdown.<br />
              <em className="font-display italic text-claret">That behavior, not the headline return, is the reason to subscribe.</em>
            </p>
          </div>
        </div>
      </section>

      {/* Newsletter */}
      <section className="bg-paper-card py-16 border-t border-rule">
        <div className="max-w-3xl mx-auto px-4 sm:px-8">
          <MarketMeasuredSignup source="track_record_v2" />
        </div>
      </section>

      {/* CTA */}
      <section className="bg-ink py-20">
        <div className="max-w-3xl mx-auto px-4 sm:px-8 text-center">
          <h2 className="font-display text-paper text-3xl mb-4 tracking-tight" style={{ fontVariationSettings: '"opsz" 96' }}>
            The discipline speaks for itself.
          </h2>
          <p className="font-body text-paper/60 mb-8">
            7-day free trial. Full access. Cancel anytime.
          </p>
          <Link
            to="/"
            className="inline-flex items-center gap-2 px-8 py-4 bg-paper text-ink text-[0.95rem] font-medium rounded-[2px] no-underline hover:bg-paper-deep transition-colors"
          >
            Start Free Trial
            <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </section>

      {/* Disclaimer + Footer */}
      <section className="py-12 border-t border-rule">
        <div className="max-w-[800px] mx-auto px-4 sm:px-8">
          <p className="text-[0.78rem] text-ink-light leading-relaxed">
            All results shown are from walk-forward simulations using historical data and do not represent actual trading returns.
            Past performance is not indicative of future results. Investing involves risk, including the possible loss of principal.
            RigaCap provides algorithmic signals and educational information only &mdash; we are not registered investment advisors.
            See our <Link to="/terms" className="text-claret underline underline-offset-2 decoration-1">Terms of Service</Link> for full details.
          </p>
          <p className="text-[0.78rem] text-ink-light mt-4">&copy; 2026 RigaCap, LLC</p>
        </div>
      </section>
    </div>
  );
}
