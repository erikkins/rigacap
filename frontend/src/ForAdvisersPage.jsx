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
            <span className="hidden sm:inline">Model delivery · Walk-forward backtest</span>
          </div>
          <nav className="flex items-center justify-between py-4">
            <Link to="/" className="flex items-center gap-2.5 no-underline">
              <svg width="20" height="24" viewBox="0 0 20 24"><path d="M10 1 L13 9 L10 23 L7 9 Z" fill="#7A2430" /></svg>
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
              Clients don't fire you at <em className="text-claret italic">−17%.</em><br />They fire you at <em className="text-claret italic">−35%.</em>
            </div>
            <div>
              <div className="text-[0.7rem] tracking-[0.05em] uppercase text-ink-mute font-semibold mb-3">Worst drawdown · 2017–2026</div>
              {[
                ['Raw momentum', '100%', '−35%', false],
                ['RigaCap', '48.5%', '−17%', true],
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
              ['Behaviorally holdable', 'Your biggest portfolio risk isn’t the market — it’s a client capitulating at the bottom. A 17% worst-case drawdown is one a client can sit through. A 35% one isn’t.'],
              ['Diligence you can present', 'Survivorship-free, point-in-time, walk-forward, out-of-sample. The methodology stands up in a committee meeting, not just a marketing deck.'],
              ['A complement, not a core', 'A disciplined momentum sleeve that sits alongside an indexed core — uncorrelated discipline, sized to your mandate.'],
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
            <strong className="text-ink">How it works.</strong> RigaCap delivers <strong className="text-ink">signals and a model allocation</strong> — entries, exits, and sizing. You implement across client accounts through your own custodian; <strong className="text-ink">RigaCap never touches client capital, and you remain the fiduciary.</strong> Performance shown is backtested (~14% / 0.92 Sharpe / 17% max DD, 2017–2026); the strategy runs live and its real-time track record is now accruing — underwrite conservatively until that record builds, which we publish.
          </div>
        </section>

        {/* CTA band */}
        <section className="py-11 border-t-2 border-ink text-center">
          <h2 className="font-display font-medium text-ink text-[1.7rem]" style={{ fontVariationSettings: '"opsz" 72' }}>Use it yourself. Offer it to your clients.</h2>
          <p className="text-ink-mute text-[0.95rem] mt-2.5 mb-5 max-w-[520px] mx-auto">
            Start a free trial on your own account — the same engine our subscribers run. When you're ready to deliver the sleeve across client books, talk to us about model delivery and licensing.
          </p>
          <div className="flex gap-3 justify-center flex-wrap">
            <Link to="/" className="inline-flex items-center gap-2 bg-claret text-white font-semibold px-6 py-3.5 rounded-[3px] text-[0.95rem] no-underline hover:bg-claret-light transition-colors">Start your free trial <ArrowRight className="w-4 h-4" /></Link>
            <a href="mailto:erik@rigacap.com?subject=RigaCap%20model%20delivery" className="inline-flex items-center border border-rule-dark text-ink font-semibold px-6 py-3.5 rounded-[3px] text-[0.95rem] no-underline hover:border-ink transition-colors">Talk about model delivery</a>
          </div>
        </section>

        {/* Footer */}
        <footer className="py-8 border-t border-rule text-ink-light text-[0.72rem] leading-[1.7]">
          RigaCap publishes impersonal, regularly-circulated commentary under the publisher's exemption. Not personalized investment advice; advisers remain responsible for suitability and fiduciary duties to their clients. Signals and model delivery only — RigaCap does not custody or manage client assets. Past performance, including backtested performance, does not guarantee future results.
        </footer>
      </div>
    </div>
  );
}
