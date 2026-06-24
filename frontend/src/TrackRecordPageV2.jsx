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

// Performance data — single source for BOTH the desktop table and the mobile
// card stack. On mobile the table reflows to per-strategy cards so every metric
// (incl. Max Drawdown — the whole pitch) is visible without a hidden horizontal
// scroll. Added Jun 16 2026: an ad group lands directly on /track-record and
// 100% of paid clicks are mobile, so the drawdown columns must not be off-screen.
const GREEN = '#2D5F3F', RED = '#8F2D3D';
const RECENT_ROWS = [
  { name: 'RigaCap — risk-managed', hi: true, cells: [
    { v: '+32.0%', tone: 'ink', w: 'font-medium' }, { v: '2.20', tone: 'ink', w: 'font-medium' },
    { v: '3.76', hex: GREEN, w: 'font-semibold' }, { v: '8.5%', hex: GREEN, w: 'font-semibold' }] },
  { name: 'S&P 500 (price)', cells: [
    { v: '+19.9%', tone: 'mute' }, { v: '1.18', tone: 'mute' }, { v: '1.05', tone: 'mute' }, { v: '19.0%', tone: 'mute' }] },
  { name: 'Raw momentum (gross)', cells: [
    { v: '+71.9%', tone: 'mute' }, { v: '1.35', tone: 'mute' }, { v: '1.91', tone: 'mute' }, { v: '37.7%', hex: RED, w: 'font-medium' }] },
];
const FOUNDATION_ROWS = [
  { name: 'Raw 12-month momentum, net of costs', cells: [
    { v: '13.2%', tone: 'mute' }, { v: '0.69', tone: 'mute' }, { v: '57%', hex: RED, w: 'font-medium' }] },
  { name: 'RigaCap — risk-managed', hi: true, cells: [
    { v: '8.3%', tone: 'ink', w: 'font-medium' }, { v: '0.73', tone: 'ink', w: 'font-medium' }, { v: '19%', hex: GREEN, w: 'font-semibold' }] },
  { name: 'S&P 500 (SPY, price only)', italic: true, cells: [
    { v: '9.8%', tone: 'mute' }, { v: '—', tone: 'mute' }, { v: '55%', tone: 'mute' }] },
];

const cellCls = (c) => `font-mono text-[1.05rem] ${c.w || ''} ${c.hex ? '' : (c.tone === 'ink' ? 'text-ink' : 'text-ink-mute')}`;
const cellStyle = (c) => (c.hex ? { color: c.hex } : undefined);

const PerfTable = ({ label, columns, rows }) => (
  <>
    <div className="font-body text-[0.8rem] font-medium tracking-[0.15em] uppercase text-ink-mute mb-4">{label}</div>
    {/* Desktop: table (unchanged look) */}
    <div className="hidden sm:block overflow-x-auto mb-4">
      <table className="w-full border-collapse" style={{ fontFeatureSettings: '"tnum"' }}>
        <thead>
          <tr>
            <th className="py-3 text-left pl-5 pr-4 font-body font-medium text-[0.8rem] tracking-[0.15em] uppercase text-ink-mute border-b border-rule-dark">Strategy</th>
            {columns.map((h) => (
              <th key={h} className="py-3 text-right px-5 font-body font-medium text-[0.8rem] tracking-[0.15em] uppercase text-ink-mute border-b border-rule-dark">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.name} className={`border-b border-rule ${r.hi ? 'bg-paper-card' : ''}`}>
              <td className={`py-4 pl-5 pr-4 text-[1.05rem] ${r.hi ? 'font-semibold text-ink' : (r.italic ? 'italic text-ink-mute' : 'text-ink-mute')}`} style={r.hi ? { boxShadow: 'inset 3px 0 0 #7A2430' } : undefined}>{r.name}</td>
              {r.cells.map((c, i) => (
                <td key={i} className={`py-4 px-5 text-right ${cellCls(c)}`} style={cellStyle(c)}>{c.v}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
    {/* Mobile: per-strategy cards — no horizontal scroll, every metric visible */}
    <div className="sm:hidden space-y-px bg-rule mb-4">
      {rows.map((r) => (
        <div key={r.name} className="bg-paper-card p-4" style={r.hi ? { boxShadow: 'inset 3px 0 0 #7A2430' } : undefined}>
          <div className={`text-[1.05rem] mb-3 ${r.hi ? 'font-semibold text-ink' : (r.italic ? 'italic text-ink-mute' : 'text-ink')}`}>{r.name}</div>
          <div className="grid grid-cols-2 gap-x-5 gap-y-2.5">
            {columns.map((col, i) => (
              <div key={col} className="flex items-baseline justify-between border-b border-rule pb-1.5">
                <span className="font-body text-[0.74rem] font-medium tracking-[0.1em] uppercase text-ink-mute">{col}</span>
                <span className={cellCls(r.cells[i])} style={cellStyle(r.cells[i])}>{r.cells[i].v}</span>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  </>
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
            Twenty-one years. Three crashes. <em className="text-claret italic">No cherry-picking.</em>
          </h1>
          <p className="text-ink-mute text-[1.05rem] leading-[1.65]">
            Performance validated through twenty-one years of point-in-time walk-forward simulation &mdash; no hindsight, no curve-fitting.
            The wins, the losses, and the worst drawdown all published.
          </p>
        </div>
      </section>

      {/* Headline Metrics */}
      <section className="mt-14">
        <div className="max-w-[1120px] mx-auto px-4 sm:px-8">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-px bg-rule">
            {[
              ['+32%', 'Last 24 Months', 'annualized · vs S&P +20% · backtest'],
              ['2.20', 'Recent Sharpe', 'last 24 months · vs S&P 1.18'],
              ['8.3%', 'Annualized', 'Walk-forward, 2007–2026'],
              ['19%', 'Max Drawdown', '21 years · vs 57% for raw momentum'],
            ].map(([value, label, subtitle]) => (
              <div key={label} className="bg-paper-card p-6 sm:p-8 text-center">
                <div className="font-display text-3xl sm:text-4xl font-normal text-ink tracking-tight" style={{ fontVariationSettings: '"opsz" 144' }}>{value}</div>
                <div className="font-body text-[0.8rem] font-medium tracking-[0.12em] uppercase text-ink-mute mt-2">{label}</div>
                <div className="text-[0.88rem] text-ink-light mt-1">{subtitle}</div>
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

          {/* Recent 24 months — held-out walk-forward window (Jun 2024 – May 2026) */}
          <PerfTable label="The Last 24 Months" columns={['Annualized', 'Sharpe', 'Calmar', 'Max Drawdown']} rows={RECENT_ROWS} />
          <p className="mb-12 text-[1rem] text-ink leading-[1.65]">
            June 2024 through May 2026, a held-out walk-forward window (backtested, not yet live money):
            <strong className="font-medium"> RigaCap beat the index by 12 points a year at well under half its drawdown</strong> &mdash;
            twice the S&amp;P's Sharpe, three-and-a-half times its Calmar. Raw momentum earned more, gross of costs &mdash;
            and took a 38% drawdown <em>during a bull market</em> to collect it. Defense isn't the same as sitting out the bull.
          </p>

          {/* SURFACE-MARKER:perf-comparison-table-START */}
          <PerfTable label="The Two-Decade Foundation · 2007–2026" columns={['Annualized', 'Sharpe', 'Max Drawdown']} rows={FOUNDATION_ROWS} />
          {/* SURFACE-MARKER:perf-comparison-table-END */}

          <p className="mt-4 text-[0.93rem] text-ink-light leading-relaxed">
            Continuous walk-forward simulation, 2007&ndash;2026 &mdash; through the 2008 financial crisis, the 2009 momentum crash, COVID, and the 2022 bear. Data from 2016 onward is survivorship-free and strictly point-in-time; pre-2016 history carries a survivorship caveat, disclosed in full in the methodology. Price returns; raw momentum shown net of modeled costs as the unmanaged factor benchmark.
            See <Link to="/methodology" className="text-claret underline underline-offset-2 decoration-1">full methodology</Link> for all assumptions.
          </p>

          <div className="mt-6 border-l-[3px] border-claret pl-5 py-1">
            <p className="text-[1.05rem] text-ink leading-relaxed mb-0">
              <span className="font-medium">For context on that 0.73:</span> Sharpe ratios above 1 live in short windows and
              overfit backtests &mdash; over decades, the scale compresses. The S&amp;P 500 scored <span className="font-mono">0.54</span> across
              this same 21-year window. The highest lifetime figure ever measured for any stock or fund with 30+ years of
              history is Warren Buffett's <span className="font-mono">0.79</span> (Frazzini, Kabiller &amp; Pedersen,
              &ldquo;Buffett&rsquo;s Alpha,&rdquo; 2018). Ours is backtested and his is real &mdash; but that is the
              neighborhood two honest decades put you in.
            </p>
          </div>


          {/* Per-regime resilience */}
          <div className="mt-12 bg-paper-card border-l-[3px] border-claret p-8">
            <div className="font-body text-[0.8rem] font-medium tracking-[0.15em] uppercase text-ink-mute mb-5">
              Tested Through Every Downturn
            </div>
            <div>
              {[
                ['2008 financial crisis', 'S&P −37.7%', '−0.5%', 'in cash by design'],
                ['COVID crash year', 'S&P +15.2%', '+31.9%', 'exit & re-entry'],
                ['2022 inflation bear', 'S&P −19.9%', '−7.5%', 'shallow & recoverable'],
                ['2018 whipsaw (our worst)', 'S&P −7.0%', '−12.3%', 'the honest wart'],
              ].map(([regime, window, ret, dd]) => (
                <div key={regime} className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between py-3 border-b border-rule text-[1.05rem]">
                  <div><span className="font-medium text-ink">{regime}</span> <span className="text-ink-light text-[0.88rem]">· {window}</span></div>
                  <div className="flex items-baseline gap-3 font-mono text-[1rem]"><span className="w-16 sm:w-20 sm:text-right" style={{ color: ret.startsWith('−') || ret.startsWith('-') ? '#8F2D3D' : '#2D5F3F' }}>{ret}</span><span className="text-ink-mute italic font-body sm:w-48 sm:text-right">{dd}</span></div>
                </div>
              ))}
            </div>
            <p className="mt-6 text-[1.05rem] text-ink leading-[1.6]">
              Calendar years, continuous run &mdash; including our worst one, because you should see it. A liquidity collapse the strategy sat out almost entirely, a crash year it turned into its best, a bear it cut to a third of the index's loss &mdash; and a whipsaw year it lost more than the index. <strong className="font-medium">The drawdown stayed bounded through all of it.</strong> That resilience &mdash; not a headline return &mdash; is the point.
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
              ['\u22120.5% through 2008', 'S&P fell 38%', 'While the index lost over a third in the worst financial year since the Depression, RigaCap ended 2008 essentially flat \u2014 the regime filter had it in cash by design.'],
              ['A third of the drawdown', 'vs raw momentum', 'The same momentum factor nets ~13% over two decades with a brutal 57% drawdown. RigaCap trades some of that raw return for a 19% worst case across 21 years \u2014 the risk engineering is the edge.'],
              ['Steps back in stress', 'capital preservation', 'When the market turns hostile and losses cluster, the strategy pauses new entries rather than chase a falling market \u2014 sidestepping the falling knife that turns a bad week into a deep drawdown.'],
            ].map(([title, subtitle, desc]) => (
              <div key={title} className="bg-paper-card p-8">
                <div className="font-display text-2xl text-ink mb-1" style={{ fontVariationSettings: '"opsz" 96' }}>{title}</div>
                <div className="font-mono text-[0.8rem] text-claret tracking-[0.1em] uppercase mb-3">{subtitle}</div>
                <p className="text-ink-mute text-[1rem] leading-relaxed">{desc}</p>
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
              The twenty-one-year span included the 2008 financial crisis &mdash; in which the index lost over half its value and raw momentum lost 46% in a single year &mdash; plus COVID and the 2022 bear. <strong className="font-medium">RigaCap's worst peak-to-trough across all of it stayed near 19%; it ended 2008 essentially flat and held its 2022 loss to a third of the index's</strong> &mdash;{' '}
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
            className="inline-flex items-center gap-2 px-8 py-4 bg-paper text-ink text-[1.05rem] font-medium rounded-[2px] no-underline hover:bg-paper-deep transition-colors"
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
