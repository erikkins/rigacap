import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
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
            Nine years. Every regime. <em className="text-claret italic">No cherry-picking.</em>
          </h1>
          <p className="text-ink-mute text-[1.05rem] leading-[1.65] max-w-[60ch]">
            Performance validated through survivorship-free, point-in-time walk-forward simulation &mdash; no hindsight, no curve-fitting.
            Best, average, and worst outcomes all published.
          </p>
        </div>
      </section>

      {/* Headline Metrics */}
      <section className="mt-14">
        <div className="max-w-[1120px] mx-auto px-4 sm:px-8">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-px bg-rule">
            {[
              ['~14%', 'Annualized', 'Walk-forward, 2017–2026'],
              ['0.92', 'Sharpe Ratio', 'Risk-adjusted performance'],
              ['17%', 'Max Drawdown', 'vs 35% for raw momentum'],
              ['94%', 'Windows Positive', '15 of 16 two-year windows'],
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

      {/* Drawdown chart goes here (underwater viz) — equity-curve chart removed
          Jun 9 2026: it showed return-only, where RigaCap ≈/below SPY (our edge
          is RISK, not return), so it argued against the product. The per-regime
          resilience table below carries the drawdown story until the underwater
          chart lands. */}

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
                  {['Strategy', 'Annualized', 'Sharpe', 'Max Drawdown'].map((h, i) => (
                    <th key={h} className={`py-3 ${i === 0 ? 'text-left pl-5 pr-4' : 'text-right px-5'} font-body font-medium text-[0.75rem] tracking-[0.15em] uppercase text-ink-mute border-b border-rule-dark`}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <tr className="border-b border-rule">
                  <td className="py-4 pl-5 pr-4 text-[0.95rem] text-ink-mute">Raw 12-month momentum</td>
                  <td className="py-4 px-5 text-right font-mono text-[0.95rem] text-ink-mute">22.2%</td>
                  <td className="py-4 px-5 text-right font-mono text-[0.95rem] text-ink-mute">0.67</td>
                  <td className="py-4 px-5 text-right font-mono text-[0.95rem] font-medium" style={{ color: '#8F2D3D' }}>35%</td>
                </tr>
                <tr className="border-b border-rule bg-paper-card">
                  <td className="py-4 pl-5 pr-4 text-[0.95rem] font-semibold text-ink" style={{ boxShadow: 'inset 3px 0 0 #7A2430' }}>RigaCap &mdash; risk-managed</td>
                  <td className="py-4 px-5 text-right font-mono text-[0.95rem] font-medium text-ink">14.0%</td>
                  <td className="py-4 px-5 text-right font-mono text-[0.95rem] font-medium text-ink">0.92</td>
                  <td className="py-4 px-5 text-right font-mono text-[0.95rem] font-semibold" style={{ color: '#2D5F3F' }}>17%</td>
                </tr>
                <tr>
                  <td className="py-4 pl-5 pr-4 text-[0.95rem] italic text-ink-mute">S&P 500 (SPY, price only)</td>
                  <td className="py-4 px-5 text-right font-mono text-[0.95rem] text-ink-mute">~13%</td>
                  <td className="py-4 px-5 text-right font-mono text-[0.95rem] text-ink-mute">~0.6</td>
                  <td className="py-4 px-5 text-right font-mono text-[0.95rem] text-ink-mute">~34%</td>
                </tr>
              </tbody>
            </table>
          </div>
          {/* SURFACE-MARKER:perf-comparison-table-END */}

          <p className="mt-4 text-[0.85rem] text-ink-light leading-relaxed">
            Walk-forward simulation across 16 overlapping two-year windows, 2017&ndash;2026, on survivorship-free data and net of modeled costs. 15 of 16 windows finished positive; the lone exception was roughly flat in the 2017&ndash;18 chop. Raw 12-month momentum shown as the unmanaged factor benchmark.
            See <Link to="/methodology" className="text-claret underline underline-offset-2 decoration-1">full methodology</Link> for all assumptions.
          </p>

          {/* Per-regime resilience */}
          <div className="mt-12 bg-paper-card border-l-[3px] border-claret p-8">
            <div className="font-body text-[0.75rem] font-medium tracking-[0.15em] uppercase text-ink-mute mb-5">
              Tested Through Every Downturn
            </div>
            <div>
              {[
                ['COVID crash & recovery', '2019–21', '+24 to +32%', '9–10%'],
                ['2022 inflation bear', '2022 start', '+8 to +10%', '13–15%'],
                ['2018-Q4 correction', '2017–19', '+2 to +6%', '13–17%'],
              ].map(([regime, window, ret, dd]) => (
                <div key={regime} className="flex items-center justify-between py-3 border-b border-rule text-[0.95rem]">
                  <div><span className="font-medium text-ink">{regime}</span> <span className="text-ink-light text-[0.8rem]">· {window}</span></div>
                  <div className="flex gap-6 sm:gap-10 font-mono text-[0.9rem]"><span style={{ color: '#2D5F3F' }}>{ret} ann</span><span className="text-ink-mute">{dd} max DD</span></div>
                </div>
              ))}
            </div>
            <p className="mt-6 text-[0.95rem] text-ink leading-[1.6]">
              Three materially different stress environments &mdash; a liquidity crash, a vol spike, and a year-long inflation bear. <strong className="font-medium">The drawdown stayed bounded through all of them</strong>, and the strategy finished each window positive. That resilience &mdash; not a headline return &mdash; is the point.
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
              ['Positive through 2022', 'S&P fell ~20%', 'While the S&P had its worst year since 2008, RigaCap\u2019s 2022 windows finished positive \u2014 the risk controls earning their keep in a year-long bear.'],
              ['Half the drawdown', 'vs raw momentum', 'The same momentum factor returns ~22% with a brutal 35% drawdown. RigaCap trades some of that raw return for a 17% worst case \u2014 the risk engineering is the edge.'],
              ['Steps back in stress', 'capital preservation', 'When the market turns hostile and losses cluster, the strategy pauses new entries rather than chase a falling market \u2014 sidestepping the falling knife that turns a bad week into a deep drawdown.'],
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
              The nine-year span included three distinct downturns. <strong className="font-medium">RigaCap finished its 2022 windows in positive territory</strong> while the S&P fell ~20% &mdash;{' '}
              not by luck, but by design. Risk-based sizing and trailing-stop discipline kept the strategy on the right side of risk &mdash; responding to data as it changed, not predicting the drawdown.<br />
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
            For information purposes only and not a solicitation to invest, purchase, or sell securities in which RigaCap has an interest.
            Past performance does not guarantee future results. Investing involves risk, including the possible loss of principal.
            RigaCap, LLC is not a registered investment advisor.
            See our <Link to="/terms" className="text-claret underline underline-offset-2 decoration-1">Terms of Service</Link> for full details.
          </p>
          <p className="text-[0.78rem] text-ink-light mt-4">&copy; 2026 RigaCap, LLC</p>
        </div>
      </section>
    </div>
  );
}
