import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import TrackRecordChart from './components/TrackRecordChart';
import MarketMeasuredSignup from './components/MarketMeasuredSignup';

const SectionLabel = ({ children }) => (
  <div className="flex items-center gap-3 mb-5">
    <span className="inline-block w-6 h-px bg-claret" />
    <span className="font-body text-[0.78rem] font-medium tracking-[0.18em] uppercase text-ink-mute">{children}</span>
  </div>
);

const Navbar = () => (
  <nav className="sticky top-0 z-50 bg-paper/95 backdrop-blur-sm border-b border-rule">
    <div className="max-w-[1120px] mx-auto px-4 sm:px-8 py-5 flex items-center justify-between">
      <Link to="/" className="font-display text-2xl font-semibold text-ink tracking-tight no-underline" style={{ fontVariationSettings: '"opsz" 144' }}>
        RigaCap<span className="text-claret">.</span>
      </Link>
      <div className="flex items-center gap-9">
        <Link to="/methodology" className="text-[0.9rem] text-ink-mute no-underline hover:text-ink transition-colors">Methodology</Link>
        <Link to="/" className="text-[0.9rem] text-ink-mute no-underline hover:text-ink transition-colors">Home</Link>
      </div>
    </div>
  </nav>
);

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
            Five years. Eight start dates. <em className="text-claret italic">No cherry-picking.</em>
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
              ['+204%', 'Average Return', 'multiple start dates, same strategy'],
              ['+86%', 'Worst Start Date', 'Still positive, still ahead of SPY'],
              ['0.95', 'Avg Sharpe Ratio', 'Risk-adjusted performance'],
              ['32%', 'Avg Max Drawdown', 'Peak to trough'],
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
            The numbers, <em className="text-claret italic">friction-adjusted.</em>
          </h2>

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
                <tr className="border-b border-rule">
                  <td className="py-4 pr-4 text-[0.95rem]">Simulation (avg. of multiple start dates)</td>
                  <td className="py-4 px-5 text-right font-mono text-[0.95rem]">+204%</td>
                  <td className="py-4 px-5 text-right font-mono text-[0.95rem]">~23%</td>
                  <td className="py-4 px-5 text-right font-mono text-[0.95rem]">0.95</td>
                  <td className="py-4 px-5 text-right font-mono text-[0.95rem]">32%</td>
                </tr>
                <tr className="border-b border-rule bg-paper-card">
                  <td className="py-4 pr-4 text-[0.95rem] font-semibold text-ink">Friction-adjusted estimate</td>
                  <td className="py-4 px-5 text-right font-mono text-[0.95rem] font-medium text-ink">+173%</td>
                  <td className="py-4 px-5 text-right font-mono text-[0.95rem] font-medium text-ink">~21.5%</td>
                  <td className="py-4 px-5 text-right font-mono text-[0.95rem] text-ink-mute">&mdash;</td>
                  <td className="py-4 px-5 text-right font-mono text-[0.95rem] text-ink-mute">&mdash;</td>
                </tr>
                <tr>
                  <td className="py-4 pr-4 text-[0.95rem] italic text-ink-mute">S&P 500 (SPY, price only)</td>
                  <td className="py-4 px-5 text-right font-mono text-[0.95rem] text-ink-mute">+84%</td>
                  <td className="py-4 px-5 text-right font-mono text-[0.95rem] text-ink-mute">~13%</td>
                  <td className="py-4 px-5 text-right font-mono text-[0.95rem] text-ink-mute">&mdash;</td>
                  <td className="py-4 px-5 text-right font-mono text-[0.95rem] text-ink-mute">&mdash;</td>
                </tr>
              </tbody>
            </table>
          </div>

          <p className="mt-4 text-[0.85rem] text-ink-light leading-relaxed">
            Friction-adjusted figures estimate realistic slippage and commissions. Simulation assumes zero of both and uses end-of-day prices.
            See <Link to="/methodology" className="text-claret underline underline-offset-2 decoration-1">full methodology</Link> for all assumptions.
          </p>
        </div>
      </section>

      {/* Highlights */}
      <section className="py-16 border-t border-rule">
        <div className="max-w-[1120px] mx-auto px-4 sm:px-8">
          <SectionLabel>Highlights</SectionLabel>

          <div className="grid sm:grid-cols-3 gap-px bg-rule">
            {[
              ['Flat in 2022', 'S&P fell 20%', 'Capital preservation when it matters. Regime detection moved to cash before the worst of the drawdown.'],
              ['333 trades', '48.6% win rate', '1.77x win/loss ratio. Less than half the trades win, but winners are substantially larger than losers.'],
              ['7 emergency pauses', 'Cascade Guard', 'System froze entries when multiple stops hit the same day &mdash; preventing re-entry during cascade selloffs.'],
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
              The five-year window included one major bear market. The system ended it flat while the S&P fell 20% &mdash;{' '}
              <strong className="font-medium">not by luck, but by design.</strong> Regime detection triggered de-risking before the drawdown
              and kept the system in cash until conditions improved.{' '}
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
