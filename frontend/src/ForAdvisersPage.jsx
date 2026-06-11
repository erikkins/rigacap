import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';

const Eyebrow = ({ children }) => (
  <span className="font-body text-[0.72rem] font-semibold tracking-[0.18em] uppercase text-claret">{children}</span>
);

export default function ForAdvisersPage() {
  useEffect(() => { document.title = 'For Advisers | RigaCap'; }, []);
  return (
    <div className="min-h-screen bg-paper font-body text-ink">
      <div className="max-w-[1000px] mx-auto px-4 sm:px-8">

        {/* Masthead */}
        <div className="border-b-2 border-ink mt-3">
          <div className="flex justify-between text-[0.68rem] tracking-[0.14em] uppercase text-ink-light py-2 border-b border-rule">
            <span>For registered advisers &amp; RIAs</span>
            <span className="hidden sm:inline">Signals & sizing · Walk-forward backtested</span>
          </div>
          <nav className="flex items-center justify-between py-4">
            <Link to="/" className="flex items-center gap-2.5 no-underline">
              <svg className="w-7 h-7 shrink-0 relative top-[2px]" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 1024">
                <g transform="matrix(5.27 0 0 5.27 640 511)"><g>
                  <g transform="matrix(0.448 0 0 0.448 -22.4 -28.8)"><path fill="#7A2430" transform="translate(-300,-286)" d="M215.49 348.13C215.49 341.43 220.55 335.98 227.05 335.22L241.64 278.36C238.32 275.99 236.13 272.12 236.13 267.73C236.13 260.51 241.98 254.66 249.2 254.66C255.89 254.66 261.34 259.71 262.11 266.19L309.18 278.16C311.55 274.82 315.42 272.63 319.83 272.63C324 272.63 327.67 274.62 330.06 277.66L391.39 258.85C391.87 252.06 397.46 246.69 404.37 246.69C405.09 246.69 405.78 246.79 406.47 246.91L420.4 223.13C395.44 205.2 364.84 194.62 331.76 194.62C247.75 194.62 179.66 262.72 179.66 346.72C179.66 357.06 180.71 367.15 182.69 376.91L216.05 351.72C215.72 350.57 215.49 349.38 215.49 348.13z"/></g>
                  <g transform="matrix(0.448 0 0 0.448 -11.1 -9)"><path fill="#7A2430" transform="translate(-325,-330)" d="M427.89 228.86L414.54 251.65C416.32 253.88 417.43 256.68 417.43 259.76C417.43 266.98 411.58 272.83 404.37 272.83C400.19 272.83 396.52 270.84 394.13 267.79L332.8 286.61C332.33 293.39 326.73 298.76 319.83 298.76C313.14 298.76 307.69 293.72 306.92 287.24L259.84 275.26C257.76 278.21 254.48 280.2 250.71 280.64L236.12 337.5C239.44 339.87 241.63 343.74 241.63 348.13C241.63 355.35 235.78 361.2 228.56 361.2C226.02 361.2 223.68 360.45 221.67 359.19L185.04 386.86C189.39 402.76 196.25 417.63 205.17 431L343.51 312.12L408.04 312.12L465.59 274.41C456.09 256.86 443.23 241.4 427.89 228.86z"/></g>
                  <g transform="matrix(0.448 0 0 0.448 73.8 -37.1)"><polygon fill="#7A2430" points="-45.31,-14.33 45.31,-39.44 -12.75,39.44 -17.06,3.28"/></g>
                  <g transform="matrix(0.448 0 0 0.448 -48.2 25.7)"><path fill="#141210" transform="translate(-242,-407)" d="M297.69 513.38C291.85 512.18 286.13 510.68 280.53 508.91L280.53 405.3L233.16 446.01L233.16 485.18C189.93 454.31 161.67 403.77 161.67 346.72C161.67 321.48 167.23 297.53 177.14 275.97L153.41 275.97C144.69 297.88 139.84 321.74 139.84 346.72C139.84 452.54 225.93 538.63 331.76 538.63C336.23 538.63 340.66 538.42 345.06 538.12L345.06 349.85L297.69 390.55L297.69 513.38z"/></g>
                  <g transform="matrix(0.448 0 0 0.448 41.6 31.4)"><path fill="#141210" transform="translate(-443,-420)" d="M523.16 333.38L501.27 333.38C501.62 337.79 501.85 342.23 501.85 346.72C501.85 381 491.63 412.92 474.11 439.65L474.11 304.24L426.75 335.28L426.75 487.65C421.24 491.37 415.52 494.78 409.58 497.85L409.58 341.74L362.22 341.74L362.22 536.19C453.61 521.55 523.67 442.17 523.67 346.72C523.67 342.23 523.46 337.79 523.16 333.38z"/></g>
                  <g transform="matrix(0.448 0 0 0.448 -11.8 -60.8)"><path fill="#141210" transform="translate(-324,-214)" d="M331.75 169.32C390.45 169.32 442.58 197.98 474.89 242.04L483.06 239.78C449.46 192.37 394.16 161.37 331.75 161.37C258.06 161.37 194.28 204.6 164.43 267.02L173.29 267.02C202.53 209.12 262.58 169.32 331.75 169.32z"/></g>
                </g></g>
              </svg>
              <span className="font-display font-semibold text-[1.4rem] text-ink" style={{ fontVariationSettings: '"opsz" 48' }}>RigaCap</span>
              <span className="text-[0.68rem] tracking-[0.12em] uppercase text-claret border border-rule-dark rounded-full px-2.5 py-1 font-semibold">For Advisers</span>
            </Link>
            <Link to="/" className="bg-claret text-white font-semibold px-4 py-2.5 rounded-[3px] text-[0.85rem] no-underline hover:bg-claret-light transition-colors">Start free trial</Link>
          </nav>
        </div>

        {/* Hero */}
        <section className="pt-12 pb-4">
          <Eyebrow>A momentum allocation, built for client books</Eyebrow>
          <h1 className="font-display font-medium text-ink mt-3.5 tracking-[-0.015em] leading-[1.04]" style={{ fontSize: 'clamp(2.4rem, 5vw, 3.4rem)', fontVariationSettings: '"opsz" 144' }}>
            A momentum sleeve you<br />can actually <em className="text-claret italic">defend.</em>
          </h1>
          <p className="mt-5 text-[1.18rem] text-[#3a342e] max-w-[600px] leading-[1.55]">
            Survivorship-free, walk-forward-validated, and drawdown-controlled — a systematic momentum
            allocation you can hold a client book through, and explain in a single meeting.
          </p>
          <div className="flex flex-wrap gap-3 items-center mt-7">
            <Link to="/" className="bg-claret text-white font-semibold px-5 py-3 rounded-[3px] text-[0.9rem] no-underline hover:bg-claret-light transition-colors">Start your free trial</Link>
            <Link to="/methodology" className="border border-rule-dark text-ink font-semibold px-5 py-3 rounded-[3px] text-[0.9rem] no-underline hover:border-ink transition-colors">Read the methodology</Link>
            <span className="text-[0.78rem] text-ink-light">Same engine our subscribers run · you stay the fiduciary</span>
          </div>

          {/* Insight box */}
          <div className="mt-11 bg-paper-card border border-rule border-t-[3px] border-t-ink p-7 sm:p-8 grid sm:grid-cols-[1.1fr_1fr] gap-8 items-center">
            <div className="font-display font-medium text-[1.7rem] leading-[1.25] tracking-[-0.01em]" style={{ fontVariationSettings: '"opsz" 72' }}>
              Clients don't fire you at <em className="text-claret italic">−19%.</em><br />They fire you at <em className="text-claret italic">−57%.</em>
            </div>
            <div>
              <div className="text-[0.7rem] tracking-[0.05em] uppercase text-ink-mute font-semibold mb-3">Worst drawdown · 2007–2026</div>
              {[
                ['Raw momentum', '100%', '−57%', false],
                ['S&P 500', '96%', '−55%', false],
                ['RigaCap', '34%', '−19%', true],
              ].map(([label, w, val, good]) => (
                <div key={label} className="grid grid-cols-[1fr_56px] items-center gap-3 my-2.5">
                  <div>
                    <div className="text-[0.78rem] text-ink-mute mb-1">{label}</div>
                    <div className="h-[22px] rounded-[2px] relative" style={{ background: '#e7e0d2' }}>
                      <div className="absolute left-0 top-0 bottom-0 rounded-[2px]" style={{ width: w, background: good ? '#2D5F3F' : 'repeating-linear-gradient(45deg,#8F2D3D,#8F2D3D 8px,#7c2533 8px,#7c2533 16px)' }} />
                    </div>
                  </div>
                  <div className="font-display font-semibold text-[1.1rem] text-right" style={{ color: good ? '#2D5F3F' : '#8F2D3D', fontVariationSettings: '"opsz" 36' }}>{val}</div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Why advisers use it */}
        <section className="py-12 border-t border-rule mt-2">
          <Eyebrow>Why advisers use it</Eyebrow>
          <h2 className="font-display font-medium text-ink mt-2.5 tracking-[-0.01em]" style={{ fontSize: 'clamp(1.6rem, 3vw, 2rem)', fontVariationSettings: '"opsz" 96' }}>The drawdown is the deliverable.</h2>
          <div className="grid sm:grid-cols-3 gap-x-8 gap-y-6 mt-7 border-t border-rule pt-7">
            {[
              ['Behaviorally holdable', 'Your biggest portfolio risk isn’t the market — it’s a client capitulating at the bottom. A 19% worst case across twenty-one years — through 2008, COVID, and 2022 — is one a client can sit through. The index’s 55% and raw momentum’s 57% aren’t.'],
              ['Diligence you can present', 'Survivorship-free, point-in-time, walk-forward, out-of-sample. The methodology stands up in a committee meeting, not just a marketing deck.'],
              ['A complement, not a core', 'A disciplined momentum sleeve that sits alongside an indexed core — 0.43 monthly correlation to the S&P over 21 years, sized to your mandate.'],
            ].map(([h, p]) => (
              <div key={h}>
                <h3 className="font-display text-[1.05rem] font-semibold text-claret mb-1.5" style={{ fontVariationSettings: '"opsz" 36' }}>{h}</h3>
                <p className="text-[0.88rem] text-[#4a443d] leading-[1.55]">{p}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Independent analyst review pull-quotes */}
        <section className="py-12 border-t border-rule">
          <Eyebrow>From an independent analyst's review · June 2026</Eyebrow>
          <div className="mt-7 grid sm:grid-cols-[1.3fr_1fr] gap-10 items-start">
            <blockquote className="font-display italic text-ink leading-[1.5] tracking-[-0.01em]" style={{ fontSize: 'clamp(1.3rem, 2.4vw, 1.7rem)', fontVariationSettings: '"opsz" 72' }}>
              &ldquo;You are structurally buying a put option on the market &mdash; and the premium is paid in
              underperformance during extended bull runs. Sold as behavioral capital insurance to wealthy
              individuals and RIAs, it is a <em className="text-claret">world-class offering.</em>&rdquo;
            </blockquote>
            <div className="space-y-4">
              <div className="bg-paper-card border-l-[3px] border-claret p-5">
                <div className="font-display text-[1.6rem] text-ink" style={{ fontVariationSettings: '"opsz" 96' }}>A&minus;</div>
                <div className="text-[0.82rem] text-ink-mute leading-snug mt-1">&ldquo;Elite Behavior-Adjusted Alpha&rdquo; &mdash; final grade after full diligence, including the strategy's relative-underperformance disclosures</div>
              </div>
              <p className="text-[0.85rem] text-ink-light leading-relaxed">
                &ldquo;Wealth managers are desperate for tools that stop clients from calling and panicking during
                crashes&hellip; an outsourced, institutional-grade risk-mitigation narrative.&rdquo; The full review
                pressed hardest on our weakest numbers &mdash; all of which are published on the
                {' '}<a href="/methodology" className="text-claret underline underline-offset-2 decoration-1">methodology page</a>.
              </p>
            </div>
          </div>
        </section>

        {/* The months clients call about */}
        <section className="py-12 border-t border-rule">
          <Eyebrow>When clients call</Eyebrow>
          <h2 className="font-display font-medium text-ink mt-2.5 tracking-[-0.01em]" style={{ fontSize: 'clamp(1.6rem, 3vw, 2rem)', fontVariationSettings: '"opsz" 96' }}>
            The index's six worst months, <em className="text-claret italic">and where we were.</em>
          </h2>
          <div className="grid sm:grid-cols-[1.2fr_1fr] gap-10 mt-7 items-start">
            <table className="w-full border-collapse" style={{ fontFeatureSettings: '"tnum"' }}>
              <thead>
                <tr>
                  {['Month', 'S&P 500', 'RigaCap'].map((h, i) => (
                    <th key={h} className={`py-2.5 ${i === 0 ? 'text-left' : 'text-right'} font-body font-medium text-[0.72rem] tracking-[0.14em] uppercase text-ink-mute border-b border-rule-dark`}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {[
                  ['Oct 2008', '−16.5%', '0.0%', 'in cash'],
                  ['Mar 2020', '−13.1%', '−4.7%', ''],
                  ['Feb 2009', '−10.7%', '0.0%', 'in cash'],
                  ['Sep 2008', '−9.9%', '0.0%', 'in cash'],
                  ['Sep 2022', '−9.6%', '0.0%', 'in cash'],
                  ['Dec 2018', '−9.3%', '−1.3%', ''],
                ].map(([m, s, r, note]) => (
                  <tr key={m} className="border-b border-rule">
                    <td className="py-2.5 text-[0.9rem] text-ink-mute">{m}</td>
                    <td className="py-2.5 text-right font-mono text-[0.9rem]" style={{ color: '#8F2D3D' }}>{s}</td>
                    <td className="py-2.5 text-right font-mono text-[0.9rem] font-medium" style={{ color: '#2D5F3F' }}>
                      {r}{note && <span className="font-body italic text-ink-light text-[0.78rem]"> · {note}</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="text-[0.95rem] text-ink leading-[1.7]">
              <p>
                Across 21 backtested years, RigaCap averaged <strong className="font-medium">−1.0% in the index's down months</strong> (the
                index averaged −3.9% in those same months) while keeping <strong className="font-medium">+1.7% per month</strong> when the
                index was rising. Four of the index's six worst months, the regime filter had the strategy in cash before the month began.
              </p>
              <p className="mt-3 text-[0.85rem] text-ink-light">
                That asymmetry — roughly a quarter of the downside, meaningful participation in the upside — is what a 0.43 correlation
                feels like to a client. Backtested, price returns; see <a href="/methodology" className="text-claret underline underline-offset-2 decoration-1">methodology</a>.
              </p>
            </div>
          </div>
        </section>

        {/* Operational reality */}
        <section className="py-12 border-t border-rule">
          <Eyebrow>The questions you'll ask anyway</Eyebrow>
          <div className="grid sm:grid-cols-3 gap-x-8 gap-y-6 mt-6 border-t border-rule pt-7">
            {[
              ['Turnover & taxes', 'Roughly 50–60 trades a year across 20 positions; typical holds run weeks to months, so gains skew short-term. Most advisers deploy it in tax-advantaged accounts, or accept the tax drag as the cost of the drawdown profile in taxable ones.'],
              ['Workflow', 'Signals and the model book update daily after the close; entries and exits arrive by email with sizing. Implementation is yours, through your custodian — typically minutes a day, not hours.'],
              ['What clients see', 'A track record page and methodology you can hand them directly — every number backtested, labeled, and reproducible, with the live record accruing in public. Nothing you’d need to walk back later.'],
            ].map(([h, p]) => (
              <div key={h}>
                <h3 className="font-display text-[1.05rem] font-semibold text-claret mb-1.5" style={{ fontVariationSettings: '"opsz" 36' }}>{h}</h3>
                <p className="text-[0.88rem] text-[#4a443d] leading-[1.55]">{p}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Diligence */}
        <section className="py-12 border-t border-rule">
          <Eyebrow>Built to survive due diligence</Eyebrow>
          <h2 className="font-display font-medium text-ink mt-2.5 tracking-[-0.01em]" style={{ fontSize: 'clamp(1.6rem, 3vw, 2rem)', fontVariationSettings: '"opsz" 96' }}>Engineered for the questions you'll be asked.</h2>
          <div className="grid sm:grid-cols-2 gap-x-8 gap-y-6 mt-7 border-t border-rule pt-7">
            {[
              ['Survivorship-free construction', 'Delisted, merged, and bankrupt names reconstructed from SEC filings. No accidental winners-only inflation.'],
              ['Point-in-time, no look-ahead', 'Universe, prices, and corporate actions adjusted strictly as-of each date.'],
              ['Walk-forward, out-of-sample', 'Validated on dates the parameters never saw; overfit configurations documented and discarded.'],
              ['Honest, discounted, transparent', 'Backtest figures published net of modeled costs and explicitly discounted for the absence of a live record.'],
            ].map(([h, p]) => (
              <div key={h}>
                <h4 className="text-[0.95rem] font-semibold text-ink mb-1"><span className="text-claret mr-1.5">—</span>{h}</h4>
                <p className="text-[0.88rem] text-[#4a443d] leading-[1.55]">{p}</p>
              </div>
            ))}
          </div>
          <div className="mt-7 bg-paper-card border border-rule border-l-[3px] border-l-claret p-5 text-[0.88rem] text-[#3a342e] leading-[1.6]">
            <strong className="text-ink">How it works.</strong> RigaCap delivers <strong className="text-ink">signals and a model allocation</strong> — entries, exits, and sizing. You implement across client accounts through your own custodian; <strong className="text-ink">RigaCap never touches client capital, and you remain the fiduciary.</strong> Performance shown is backtested:
            <table className="w-full border-collapse my-4" style={{ fontFeatureSettings: '"tnum"' }}>
              <thead>
                <tr>
                  {['', 'Annualized', 'Sharpe', 'Calmar', 'Max Drawdown'].map((h, i) => (
                    <th key={h || 'span'} className={`py-2 ${i === 0 ? 'text-left' : 'text-right pl-4'} font-body font-medium text-[0.68rem] tracking-[0.14em] uppercase text-ink-mute border-b border-rule-dark`}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <tr className="border-b border-rule">
                  <td className="py-2.5 text-[0.85rem] text-ink font-medium">21 years · 2007–2026 <span className="font-normal text-ink-light italic">— the foundation</span></td>
                  <td className="py-2.5 text-right font-mono text-[0.9rem] text-ink">8.3%</td>
                  <td className="py-2.5 text-right font-mono text-[0.9rem] text-ink">0.73</td>
                  <td className="py-2.5 text-right font-mono text-[0.9rem] text-ink">0.43</td>
                  <td className="py-2.5 text-right font-mono text-[0.9rem] font-medium" style={{ color: '#2D5F3F' }}>19%</td>
                </tr>
                <tr className="border-b border-rule">
                  <td className="py-2.5 text-[0.85rem] text-ink font-medium">Last 24 months <span className="font-normal text-ink-light italic">— held-out window</span></td>
                  <td className="py-2.5 text-right font-mono text-[0.9rem] font-semibold" style={{ color: '#2D5F3F' }}>+32.0%</td>
                  <td className="py-2.5 text-right font-mono text-[0.9rem] font-semibold text-ink">2.20</td>
                  <td className="py-2.5 text-right font-mono text-[0.9rem] font-semibold text-ink">3.76</td>
                  <td className="py-2.5 text-right font-mono text-[0.9rem] font-medium" style={{ color: '#2D5F3F' }}>8.5%</td>
                </tr>
              </tbody>
            </table>
            The strategy runs live and its real-time track record is now accruing — underwrite conservatively until that record builds, which we publish.
          </div>
        </section>

        {/* CTA band */}
        <section className="py-11 border-t-2 border-ink text-center">
          <h2 className="font-display font-medium text-ink text-[1.7rem]" style={{ fontVariationSettings: '"opsz" 72' }}>Use it yourself. Offer it to your clients.</h2>
          <p className="text-ink-mute text-[0.95rem] mt-2.5 mb-5 max-w-[520px] mx-auto">
            Start a free trial on your own account — the same engine our subscribers run. When you're ready to implement the sleeve across client books, talk to us about firm licensing.
          </p>
          <div className="flex gap-3 justify-center flex-wrap">
            <Link to="/" className="inline-flex items-center gap-2 bg-claret text-white font-semibold px-6 py-3.5 rounded-[3px] text-[0.95rem] no-underline hover:bg-claret-light transition-colors">Start your free trial <ArrowRight className="w-4 h-4" /></Link>
            <a href="mailto:erik@rigacap.com?subject=RigaCap%20firm%20licensing" className="inline-flex items-center border border-rule-dark text-ink font-semibold px-6 py-3.5 rounded-[3px] text-[0.95rem] no-underline hover:border-ink transition-colors">Talk about firm licensing</a>
          </div>
        </section>

        {/* Footer */}
        <footer className="py-8 border-t border-rule text-ink-light text-[0.72rem] leading-[1.7]">
          RigaCap publishes impersonal, regularly-circulated commentary under the publisher's exemption. Not personalized investment advice; advisers remain responsible for suitability and fiduciary duties to their clients. Signals only — RigaCap does not custody or manage client assets. Past performance, including backtested performance, does not guarantee future results.
        </footer>
      </div>
    </div>
  );
}
