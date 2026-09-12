import React, { useState, useEffect, useRef } from 'react';
import { PERF } from './perf_numbers';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from './contexts/AuthContext';
import { logPublicEvent, stashAdOrigin } from './lib/publicEvent';
import LoginModal from './components/LoginModal';
import PortfolioOverlay from './components/PortfolioOverlay';
import MarketMeasuredSignup from './components/MarketMeasuredSignup';
import ExploreMore from './components/ExploreMore';
import TopNav from './components/TopNav';

// Conversion landing page for the momentum/growth searcher ("momentum stocks", "breakout
// signals", "best growth stocks", "how to ride winners"). The Maximizer door. It attracts the
// DISCIPLINED momentum investor and repels the day-trader by leading with the hold period
// (~29 trading days, ~monthly turnover) — an alert-junkie self-selects out immediately. The
// honest edge no signals service can match: momentum WITH a capital-preservation floor (Maximizer
// is built atop the Preserver base). Numbers come from the PERF SSOT so nothing can drift.

const S = PERF.supporting;

const Eyebrow = ({ children }) => (
  <div className="flex items-center gap-3 mb-5">
    <span className="inline-block w-6 h-px bg-claret" />
    <span className="font-body text-[0.78rem] font-medium tracking-[0.18em] uppercase text-ink-mute">
      {children}
    </span>
  </div>
);

export default function MomentumPage() {
  const navigate = useNavigate();
  const { isAuthenticated, loading } = useAuth();
  const [showLoginModal, setShowLoginModal] = useState(false);
  // Returning from an in-app browser via the "open in browser" escape link → auto-reopen the modal.
  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    if (p.get('signin') === '1') {
      setShowLoginModal(true);
      p.delete('signin');
      const qs = p.toString();
      window.history.replaceState({}, '', window.location.pathname + (qs ? `?${qs}` : ''));
    }
  }, []);
  const [isReturningVisitor] = useState(() => localStorage.getItem('rigacap_returning') === 'true');
  const ctaRef = useRef(null);
  const interacted = useRef(false);   // scrolled deep or clicked a CTA
  const exitFired = useRef(false);    // bounce/exit event already sent

  useEffect(() => {
    document.title = 'Momentum, with a floor | RigaCap';
  }, []);

  useEffect(() => {
    if (!loading && isAuthenticated) navigate('/app', { replace: true });
  }, [isAuthenticated, loading, navigate]);

  // Cookieless funnel/engagement telemetry — SAME event names as /should-i-sell so the two doors
  // are directly comparable (path distinguishes them). scroll_50 = past the fold; reach_cta = the
  // offer was seen; bounce = left without engaging. 'pageview' is fired by the global beacon.
  useEffect(() => {
    const onScroll = () => {
      const doc = document.documentElement;
      const depth = (window.scrollY + window.innerHeight) / (doc.scrollHeight || 1);
      if (!interacted.current && depth >= 0.5) {
        interacted.current = true;
        logPublicEvent('scroll_50');
      }
    };
    window.addEventListener('scroll', onScroll, { passive: true });

    let observer;
    if (ctaRef.current && 'IntersectionObserver' in window) {
      let seen = false;
      observer = new IntersectionObserver((entries) => {
        if (!seen && entries.some((e) => e.isIntersecting)) {
          seen = true;
          interacted.current = true;
          logPublicEvent('reach_cta');
        }
      }, { threshold: 0.4 });
      observer.observe(ctaRef.current);
    }

    const onHide = () => {
      if (document.visibilityState === 'hidden' && !interacted.current && !exitFired.current) {
        exitFired.current = true;
        logPublicEvent('bounce');
      }
    };
    document.addEventListener('visibilitychange', onHide);

    return () => {
      window.removeEventListener('scroll', onScroll);
      document.removeEventListener('visibilitychange', onHide);
      if (observer) observer.disconnect();
    };
  }, []);

  const handleGetStarted = () => {
    interacted.current = true;
    if (window.gtag) window.gtag('event', 'begin_checkout', { currency: 'USD', item_variant: 'maximizer' });
    // Momentum door → default checkout to the Maximizer tier (breakout book + Preserver floor).
    try { localStorage.setItem('rigacap_want_maximizer', '1'); } catch { /* ignore */ }
    if (isAuthenticated) { navigate('/app', { replace: true }); return; }
    logPublicEvent('signup_open');
    stashAdOrigin();
    setShowLoginModal(true);
  };

  const scrollToWhy = () => {
    const el = document.getElementById('why');
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  return (
    <div className="min-h-screen bg-paper font-body text-ink text-[17px] leading-[1.65] antialiased">
      <TopNav onGetStarted={handleGetStarted} />

      {/* ① HERO — meet the momentum appetite, but filter the day-trader on horizon */}
      <section className="max-w-3xl mx-auto px-4 sm:px-8 pt-16 pb-14 sm:pt-24 sm:pb-20">
        <Eyebrow>For the investor who wants to ride winners</Eyebrow>
        <h1 className="font-display text-[2.3rem] sm:text-[3.1rem] font-medium leading-[1.08] tracking-tight text-ink"
            style={{ fontVariationSettings: '"opsz" 96' }}>
          Ride the breakout.
          <span className="block text-claret mt-2">Keep the floor.</span>
        </h1>
        <p className="mt-7 text-[1.15rem] text-ink-mute max-w-2xl">
          Momentum is the most durable edge in markets &mdash; and the fastest way to blow up if you
          chase it without a rule. RigaCap Maximizer trades it with discipline: confirmed breakouts,
          held about a month, with a capital-preservation floor underneath so a good run never turns
          into a round trip.
        </p>
        <div className="mt-9 flex flex-col sm:flex-row items-start sm:items-center gap-4">
          <button
            onClick={() => { logPublicEvent('cta_hero'); handleGetStarted(); }}
            className="bg-claret text-paper font-body font-medium text-[1.02rem] px-7 py-3.5 rounded hover:bg-claret-light transition-colors"
          >
            See what the breakout book is holding now
          </button>
          <button onClick={scrollToWhy}
            className="font-display italic text-[1rem] text-ink-mute hover:text-claret transition-colors"
            style={{ fontVariationSettings: '"opsz" 24' }}>
            How the engine works &darr;
          </button>
        </div>
      </section>

      {/* Portfolio Overlay (Tier 1) — softer first click; public, counts only. */}
      <PortfolioOverlay path="/momentum" onGetStarted={handleGetStarted} />

      {/* ② THE REAL RISK — momentum works; chasing it is what kills people */}
      <section id="why" className="bg-paper-card border-y border-rule py-16">
        <div className="max-w-3xl mx-auto px-4 sm:px-8">
          <Eyebrow>The real risk</Eyebrow>
          <h2 className="font-display text-[1.9rem] sm:text-[2.3rem] font-medium leading-[1.15] tracking-tight text-ink"
              style={{ fontVariationSettings: '"opsz" 48' }}>
            Momentum doesn&rsquo;t blow people up. Chasing it does.
          </h2>
          <div className="mt-6 space-y-4 text-[1.08rem] text-ink-mute max-w-2xl">
            <p>
              Winners keep winning &mdash; that&rsquo;s the most durable edge there is. But most people
              who chase it lose anyway: they buy the breakout late, marry the position, and give the
              whole move back on the reversal. Then they over-trade the next one, and the churn taxes
              the edge to death.
            </p>
            <p>
              The money was never in <em>finding</em> the breakout. It&rsquo;s in the discipline around
              it &mdash; a gated entry so you&rsquo;re not chasing, a mechanical exit so you actually
              sell the winner, and a floor for the day momentum breaks the whole market.
            </p>
          </div>
        </div>
      </section>

      {/* ③ THE ANSWER — the engine */}
      <section className="py-16">
        <div className="max-w-3xl mx-auto px-4 sm:px-8">
          <Eyebrow>The answer</Eyebrow>
          <h2 className="font-display text-[1.9rem] sm:text-[2.3rem] font-medium leading-[1.15] tracking-tight text-ink"
              style={{ fontVariationSettings: '"opsz" 48' }}>
            Offense &mdash; with a seatbelt.
          </h2>
          <p className="mt-6 text-[1.08rem] text-ink-mute max-w-2xl">
            Maximizer is a rules engine, not an alert feed. It hunts breakouts hard when the regime
            rewards it, then enforces the exits your nerves won&rsquo;t.
          </p>
          <div className="mt-10 grid gap-6 sm:grid-cols-3">
            {[
              { h: 'Enters on confirmed breakouts', p: 'Not every green candle — a name near its 50-day high, on a real volume surge, ranked by momentum quality. Fewer, better entries, so you’re never the one chasing the top.' },
              { h: 'Sells on time, not on nerves', p: 'Each breakout is held 29 trading days, then rotated. A volatility target quietly dials exposure down when the market turns choppy. No white-knuckle exits, no round trips.' },
              { h: 'A floor underneath the growth', p: 'Maximizer sits on the Preserver base — so when a real capitulation hits, the same rule that protects conservative capital raises cash for you too.' },
            ].map((c, i) => (
              <div key={i} className="border border-rule rounded bg-paper-card p-6">
                <div className="font-mono text-[0.7rem] text-claret mb-3">0{i + 1}</div>
                <h3 className="font-display text-[1.15rem] font-medium text-ink mb-2"
                    style={{ fontVariationSettings: '"opsz" 32' }}>{c.h}</h3>
                <p className="text-[0.96rem] text-ink-mute leading-[1.55]">{c.p}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ④ PROOF — the upside AND the held floor */}
      <section className="bg-paper-card border-y border-rule py-16">
        <div className="max-w-3xl mx-auto px-4 sm:px-8">
          <Eyebrow>The proof</Eyebrow>
          <h2 className="font-display text-[1.9rem] sm:text-[2.3rem] font-medium leading-[1.15] tracking-tight text-ink"
              style={{ fontVariationSettings: '"opsz" 48' }}>
            A higher ceiling &mdash; without the usual momentum crater.
          </h2>

          <div className="mt-8 overflow-x-auto">
            <table className="w-full text-[1rem]" style={{ fontFeatureSettings: '"tnum"' }}>
              <thead>
                <tr className="text-[0.7rem] uppercase tracking-[0.14em] text-ink-mute border-b border-rule">
                  <th className="text-left py-2.5 pr-3">&nbsp;</th>
                  <th className="text-right py-2.5 px-3">S&amp;P 500</th>
                  <th className="text-right py-2.5 pl-3 text-claret">RigaCap Maximizer</th>
                </tr>
              </thead>
              <tbody className="font-mono">
                <tr className="border-b border-rule/60">
                  <td className="py-3 pr-3 font-body">5-year annualized</td>
                  <td className="py-3 px-3 text-right text-ink">{PERF.benchmarks.spy_5yr.cagr}%</td>
                  <td className="py-3 pl-3 text-right text-positive font-medium">{PERF.maximizer.yr5.cagr}%</td>
                </tr>
                <tr className="border-b border-rule/60">
                  <td className="py-3 pr-3 font-body">A momentum year (2020)</td>
                  <td className="py-3 px-3 text-right text-ink">+{S.yr2020.spy}%</td>
                  <td className="py-3 pl-3 text-right text-positive font-medium">+{S.yr2020.maximizer}%</td>
                </tr>
                <tr className="border-b border-rule/60">
                  <td className="py-3 pr-3 font-body">2022 bear market</td>
                  <td className="py-3 px-3 text-right text-negative">{S.yr2022.spy}%</td>
                  <td className="py-3 pl-3 text-right text-ink font-medium">{S.yr2022.maximizer}%</td>
                </tr>
                <tr>
                  <td className="py-3 pr-3 font-body">Worst drop (last 5 yrs)</td>
                  <td className="py-3 px-3 text-right text-negative">{PERF.benchmarks.spy_5yr.maxdd}%</td>
                  <td className="py-3 pl-3 text-right text-ink font-medium">{PERF.maximizer.yr5.maxdd}%</td>
                </tr>
              </tbody>
            </table>
          </div>

          <p className="mt-6 text-[1.08rem] text-ink-mute max-w-2xl">
            That&rsquo;s the whole idea: a higher ceiling when momentum pays &mdash; but because the
            Preserver floor is always underneath, the worst drawdown stayed to about
            <strong className="text-ink font-medium"> half the market&rsquo;s</strong>. Growth you can
            actually stay invested in.
          </p>
          <p className="mt-4 text-[0.82rem] text-ink-light">
            Walk-forward results, survivorship-free, vintage {PERF.vintage}. The breakout book is the
            newest component, so plan conservatively. Past results are not a promise of future returns.
          </p>
        </div>
      </section>

      {/* ⑤ HONEST — who it's for / not for (the day-trader repel) */}
      <section className="py-16">
        <div className="max-w-3xl mx-auto px-4 sm:px-8">
          <Eyebrow>Honest fit</Eyebrow>
          <h2 className="font-display text-[1.9rem] sm:text-[2.3rem] font-medium leading-[1.15] tracking-tight text-ink"
              style={{ fontVariationSettings: '"opsz" 48' }}>
            This isn&rsquo;t a day-trading feed &mdash; on purpose.
          </h2>
          <div className="mt-8 grid gap-6 sm:grid-cols-2">
            <div className="border border-rule rounded bg-paper-card p-6">
              <div className="font-mono text-[0.7rem] uppercase tracking-[0.14em] text-positive mb-3">It&rsquo;s for you if</div>
              <p className="text-[1rem] text-ink-mute leading-[1.55]">
                You want real momentum exposure but you&rsquo;ve been burned chasing tops &mdash; or you
                just can&rsquo;t make yourself sell a winner. You want an engine that enforces the entry
                <em> and</em> the exit, with a floor when it all turns.
              </p>
            </div>
            <div className="border border-rule rounded bg-paper-card p-6">
              <div className="font-mono text-[0.7rem] uppercase tracking-[0.14em] text-claret mb-3">It&rsquo;s not for you if</div>
              <p className="text-[1rem] text-ink-mute leading-[1.55]">
                You want intraday alerts, scalps, options plays, or a fresh hot ticker every morning.
                Maximizer trades about monthly and holds for weeks. If that feels slow, we&rsquo;re
                honestly not your service.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ⑥ CTA — primary trial */}
      <section ref={ctaRef} className="bg-ink text-paper py-16">
        <div className="max-w-3xl mx-auto px-4 sm:px-8 text-center">
          <h2 className="font-display text-[1.7rem] sm:text-[2.5rem] font-medium leading-[1.14] tracking-tight [text-wrap:balance]"
              style={{ fontVariationSettings: '"opsz" 72' }}>
            <span className="block">Chase momentum all you want.</span>
            <span className="block mt-1">Just don&rsquo;t do it without a floor.</span>
          </h2>
          <button
            onClick={() => { logPublicEvent('cta_trial'); handleGetStarted(); }}
            className="mt-8 bg-claret text-paper font-body font-medium text-[1.05rem] px-8 py-4 rounded hover:bg-claret-light transition-colors"
          >
            Start free &mdash; no card
          </button>
          <p className="mt-3 text-[0.9rem] text-paper/60">Maximizer includes the Preserver floor &middot; cancel anytime</p>
        </div>
      </section>

      {/* Soft catch — the curious-but-not-ready momentum reader */}
      <section className="bg-paper-card border-b border-rule py-14">
        <div className="max-w-xl mx-auto px-4 sm:px-8">
          <p className="font-display italic text-[1.05rem] text-ink-mute mb-1 text-center"
             style={{ fontVariationSettings: '"opsz" 28' }}>
            Not ready to commit? Watch what the breakout book does next &mdash; free, no card.
          </p>
          <MarketMeasuredSignup source="momentum" onSubscribed={() => logPublicEvent('newsletter_submit')} />
        </div>
      </section>

      {/* Explore the deeper site (shared with /should-i-sell) */}
      <ExploreMore heading="Want to see the receipts before you start? Dig in." />

      {/* ⑦ Footer */}
      <footer className="bg-paper border-t border-rule py-10">
        <div className="max-w-3xl mx-auto px-4 sm:px-8 flex flex-col sm:flex-row items-center justify-between gap-4 text-[0.85rem] text-ink-mute">
          <span className="font-display italic" style={{ fontVariationSettings: '"opsz" 24' }}>
            Signals only &mdash; you execute at your own broker.
          </span>
          <div className="flex items-center gap-4">
            <Link to="/track-record" className="hover:text-claret no-underline text-ink-mute">Track record</Link>
            <Link to="/terms" className="hover:text-claret no-underline text-ink-mute">Terms</Link>
            <Link to="/privacy" className="hover:text-claret no-underline text-ink-mute">Privacy</Link>
          </div>
        </div>
      </footer>

      {showLoginModal && (
        <LoginModal
          onClose={() => setShowLoginModal(false)}
          onSuccess={() => { localStorage.setItem('rigacap_returning', 'true'); setShowLoginModal(false); navigate('/app', { replace: true }); }}
          initialMode={isReturningVisitor ? 'login' : 'register'}
          selectedPlan="founding"
        />
      )}
    </div>
  );
}
