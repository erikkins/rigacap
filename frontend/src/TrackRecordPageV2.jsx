import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import MarketMeasuredSignup from './components/MarketMeasuredSignup';
import TopNav from './components/TopNav';
import PortfolioRace from './PortfolioRace';

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
              ['8.3%', 'Annualized', 'Walk-forward, 2007–2026'],
              ['19%', 'Max Drawdown', 'vs 57% for raw momentum'],
              ['+32%', 'Last 24 Months', 'annualized · vs S&P +20% · backtest'],
              ['8.5%', 'Recent Max Drawdown', 'last 24 months · vs S&P 17%'],
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

      {/* Portfolio race: $100k · 2007-2026 · daily resolution. Replaces the
          return-only equity chart removed Jun 9 — this one tells the RISK story
          (drawdown badges, era shading, behavioral panic-sell overlay). */}
      <section className="mt-14">
        <div className="max-w-[1120px] mx-auto px-4 sm:px-8">
          <PortfolioRace />
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
                  {['Strategy', 'Annualized', 'Sharpe', 'Max Drawdown'].map((h, i) => (
                    <th key={h} className={`py-3 ${i === 0 ? 'text-left pl-5 pr-4' : 'text-right px-5'} font-body font-medium text-[0.75rem] tracking-[0.15em] uppercase text-ink-mute border-b border-rule-dark`}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <tr className="border-b border-rule">
                  <td className="py-4 pl-5 pr-4 text-[0.95rem] text-ink-mute">Raw 12-month momentum, net of costs</td>
                  <td className="py-4 px-5 text-right font-mono text-[0.95rem] text-ink-mute">13.2%</td>
                  <td className="py-4 px-5 text-right font-mono text-[0.95rem] text-ink-mute">0.69</td>
                  <td className="py-4 px-5 text-right font-mono text-[0.95rem] font-medium" style={{ color: '#8F2D3D' }}>57%</td>
                </tr>
                <tr className="border-b border-rule bg-paper-card">
                  <td className="py-4 pl-5 pr-4 text-[0.95rem] font-semibold text-ink" style={{ boxShadow: 'inset 3px 0 0 #7A2430' }}>RigaCap &mdash; risk-managed</td>
                  <td className="py-4 px-5 text-right font-mono text-[0.95rem] font-medium text-ink">8.3%</td>
                  <td className="py-4 px-5 text-right font-mono text-[0.95rem] font-medium text-ink">0.73</td>
                  <td className="py-4 px-5 text-right font-mono text-[0.95rem] font-semibold" style={{ color: '#2D5F3F' }}>19%</td>
                </tr>
                <tr>
                  <td className="py-4 pl-5 pr-4 text-[0.95rem] italic text-ink-mute">S&P 500 (SPY, price only)</td>
                  <td className="py-4 px-5 text-right font-mono text-[0.95rem] text-ink-mute">9.8%</td>
                  <td className="py-4 px-5 text-right font-mono text-[0.95rem] text-ink-mute">&mdash;</td>
                  <td className="py-4 px-5 text-right font-mono text-[0.95rem] text-ink-mute">55%</td>
                </tr>
              </tbody>
            </table>
          </div>
          {/* SURFACE-MARKER:perf-comparison-table-END */}

          <p className="mt-4 text-[0.85rem] text-ink-light leading-relaxed">
            Continuous walk-forward simulation, 2007&ndash;2026 &mdash; through the 2008 financial crisis, the 2009 momentum crash, COVID, and the 2022 bear. Data from 2016 onward is survivorship-free and strictly point-in-time; pre-2016 history carries a survivorship caveat, disclosed in full in the methodology. Price returns; raw momentum shown net of modeled costs as the unmanaged factor benchmark.
            See <Link to="/methodology" className="text-claret underline underline-offset-2 decoration-1">full methodology</Link> for all assumptions.
          </p>

          {/* Recent 24 months — held-out walk-forward window (Jun 2024 – May 2026) */}
          <div className="mt-12 bg-paper-card border-l-[3px] border-claret p-8">
            <div className="font-body text-[0.75rem] font-medium tracking-[0.15em] uppercase text-ink-mute mb-5">
              The Last 24 Months
            </div>
            <div>
              {[
                ['RigaCap — risk-managed', '+32.0% ann', '8.5% max DD', true],
                ['S&P 500 (price)', '+19.8% ann', '17.1% max DD', false],
                ['Raw momentum (gross)', '+63.1% ann', '35.3% max DD', false],
              ].map(([name, ret, dd, hl]) => (
                <div key={name} className="flex items-center justify-between py-3 border-b border-rule text-[0.95rem]">
                  <div className={hl ? 'font-semibold text-ink' : 'text-ink-mute'}>{name}</div>
                  <div className="flex gap-6 sm:gap-10 font-mono text-[0.9rem]"><span style={{ color: hl ? '#2D5F3F' : undefined }}>{ret}</span><span className="text-ink-mute">{dd}</span></div>
                </div>
              ))}
            </div>
            <p className="mt-6 text-[0.95rem] text-ink leading-[1.6]">
              June 2024 through May 2026, a held-out walk-forward window (backtested, not yet live money): <strong className="font-medium">RigaCap beat the index by 12 points a year at half its drawdown</strong> &mdash; defense isn't the same as sitting out the bull. Raw momentum earned more, gross of costs &mdash; and took a 35% drawdown <em>during a bull market</em> to collect it.
            </p>
          </div>

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
              ['A third of the drawdown', 'vs raw momentum', 'The same momentum factor nets ~13% over two decades with a brutal 57% drawdown. RigaCap trades some of that raw return for a 19% worst case across 21 years \u2014 the risk engineering is the edge.'],
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
              The twenty-one-year span included the 2008 financial crisis &mdash; in which the index lost over half its value and raw momentum lost 46% in a single year &mdash; plus COVID and the 2022 bear. <strong className="font-medium">RigaCap's worst peak-to-trough across all of it stayed near 19%, and it finished its 2022 windows positive</strong> while the S&P fell ~20% &mdash;{' '}
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
