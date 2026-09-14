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

// Conversion landing page for the anxiety searcher ("should I sell my stocks",
// "how to protect my portfolio", "market crash protection"). Built for someone who
// is scared RIGHT NOW: it meets the fear first, reframes the behavioral risk, shows
// how the system decides for them, proves it with the crash-year record, is honest
// about fit, and only then asks. Preserve tier. Numbers come from the PERF SSOT so
// this can never drift from the rest of the site.

const S = PERF.supporting;

const Eyebrow = ({ children }) => (
  <div className="flex items-center gap-3 mb-5">
    <span className="inline-block w-6 h-px bg-claret" />
    <span className="font-body text-[0.78rem] font-medium tracking-[0.18em] uppercase text-ink-mute">
      {children}
    </span>
  </div>
);

export default function ShouldISellPage() {
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
    document.title = 'Should I sell my stocks? | RigaCap';
  }, []);

  useEffect(() => {
    if (!loading && isAuthenticated) navigate('/app', { replace: true });
  }, [isAuthenticated, loading, navigate]);

  // Cookieless funnel/engagement telemetry (aggregate counts only, no per-visitor ID).
  // scroll_50 = read past the fold; reach_cta = the offer was seen; bounce = left
  // without engaging. The landing ('pageview') is fired by the global PageViewBeacon.
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
        logPublicEvent('bounce');  // landed, never engaged, left
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
    if (window.gtag) window.gtag('event', 'begin_checkout', { currency: 'USD', item_variant: 'founding' });
    try { localStorage.removeItem('rigacap_want_maximizer'); } catch { /* ignore */ }
    if (isAuthenticated) { navigate('/app', { replace: true }); return; }
    // Committed intent-to-pay: log it, and stash the ad origin so the Stripe
    // redirect (which fires later, on /app, after signup) attributes back here.
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

      {/* ① HERO — mirror the question, defuse the panic */}
      <section className="max-w-3xl mx-auto px-4 sm:px-8 pt-16 pb-14 sm:pt-24 sm:pb-20">
        <Eyebrow>A calmer read on a scary day</Eyebrow>
        <h1 className="font-display text-[2.3rem] sm:text-[3.1rem] font-medium leading-[1.08] tracking-tight text-ink"
            style={{ fontVariationSettings: '"opsz" 96' }}>
          Thinking about selling?
          <span className="block text-claret mt-2">Don&rsquo;t make that call alone.</span>
        </h1>
        <p className="mt-7 text-[1.15rem] text-ink-mute max-w-2xl">
          A rules-based system tells you exactly when to hold, when to raise cash, and when to
          buy back in &mdash; so fear doesn&rsquo;t make the most expensive decision for you.
        </p>
        <div className="mt-9 flex flex-col sm:flex-row items-start sm:items-center gap-4">
          <button
            onClick={() => { logPublicEvent('cta_hero'); handleGetStarted(); }}
            className="bg-claret text-paper font-body font-medium text-[1.02rem] px-7 py-3.5 rounded hover:bg-claret-light transition-colors"
          >
            See what it says to do
          </button>
          <button onClick={scrollToWhy}
            className="font-display italic text-[1rem] text-ink-mute hover:text-claret transition-colors"
            style={{ fontVariationSettings: '"opsz" 24' }}>
            First, take a breath &mdash; here&rsquo;s why &darr;
          </button>
        </div>
      </section>

      {/* ② THE REAL RISK — behavioral reframe. Sits directly below the fold: words,
          zero friction, continues the emotional thread. (Ticker tool moved down to
          the last interactive beat — 30-day data showed only ~2% of landers used it,
          so it doesn't earn a prime near-fold slot.) */}
      <section id="why" className="bg-paper-card border-y border-rule py-16">
        <div className="max-w-3xl mx-auto px-4 sm:px-8">
          <Eyebrow>The real risk</Eyebrow>
          <h2 className="font-display text-[1.9rem] sm:text-[2.3rem] font-medium leading-[1.15] tracking-tight text-ink"
              style={{ fontVariationSettings: '"opsz" 48' }}>
            You don&rsquo;t lose to bad stocks.<br />You lose to bad timing &mdash; your own.
          </h2>
          <div className="mt-6 space-y-4 text-[1.08rem] text-ink-mute max-w-2xl">
            <p>
              The average investor underperforms the very funds they own, because they buy calm and
              sell fear. The market recovers; the seller doesn&rsquo;t.
            </p>
            <p>
              Selling now doesn&rsquo;t remove the risk. It converts a paper loss into a permanent one
              &mdash; and then leaves you with the hardest question in investing: <em>when do I get
              back in?</em> Almost nobody times the re-entry. They wait for it to &ldquo;feel
              safe,&rdquo; which is another way of saying they wait until the rebound has already
              happened.
            </p>
          </div>
        </div>
      </section>

      {/* ③ THE ANSWER — a system that decides so you don't have to */}
      <section className="py-16">
        <div className="max-w-3xl mx-auto px-4 sm:px-8">
          <Eyebrow>The answer</Eyebrow>
          <h2 className="font-display text-[1.9rem] sm:text-[2.3rem] font-medium leading-[1.15] tracking-tight text-ink"
              style={{ fontVariationSettings: '"opsz" 48' }}>
            Replace the 2 a.m. gut call with a rule.
          </h2>
          <p className="mt-6 text-[1.08rem] text-ink-mute max-w-2xl">
            RigaCap isn&rsquo;t a stock-picking service. It&rsquo;s a discipline engine &mdash; built
            around the drawdown, not the rally. It makes the sell-or-hold decision on a rule, so your
            fear doesn&rsquo;t make it for you.
          </p>
          <div className="mt-10 grid gap-6 sm:grid-cols-3">
            {[
              { h: 'Stays in through the noise', p: 'Most scary days are just noise. A wide, rule-based stop lets good positions keep working instead of shaking you out on a red week.' },
              { h: 'Raises cash in real capitulation', p: 'When it isn’t noise — when the market truly breaks down — it steps to cash on a rule, not a headline. No hero calls, no freezing.' },
              { h: 'Gets you back in on a signal', p: 'The hardest part of selling is knowing when to return. The system tells you — so you never have to guess the bottom.' },
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

      {/* ④ PROOF — how it behaved when it mattered */}
      <section className="bg-paper-card border-y border-rule py-16">
        <div className="max-w-3xl mx-auto px-4 sm:px-8">
          <Eyebrow>The proof</Eyebrow>
          <h2 className="font-display text-[1.9rem] sm:text-[2.3rem] font-medium leading-[1.15] tracking-tight text-ink"
              style={{ fontVariationSettings: '"opsz" 48' }}>
            The test of a defense isn&rsquo;t a good year. It&rsquo;s a bad one.
          </h2>

          <div className="mt-8 overflow-x-auto">
            <table className="w-full text-[1rem]" style={{ fontFeatureSettings: '"tnum"' }}>
              <thead>
                <tr className="text-[0.7rem] uppercase tracking-[0.14em] text-ink-mute border-b border-rule">
                  <th className="text-left py-2.5 pr-3">When the market broke</th>
                  <th className="text-right py-2.5 px-3">S&amp;P 500</th>
                  <th className="text-right py-2.5 pl-3 text-claret">RigaCap Preserver</th>
                </tr>
              </thead>
              <tbody className="font-mono">
                <tr className="border-b border-rule/60">
                  <td className="py-3 pr-3 font-body">2008 financial crisis</td>
                  <td className="py-3 px-3 text-right text-negative">{S.yr2008.spy}%</td>
                  <td className="py-3 pl-3 text-right text-positive font-medium">+{S.yr2008.preserver}%</td>
                </tr>
                <tr className="border-b border-rule/60">
                  <td className="py-3 pr-3 font-body">2022 bear market</td>
                  <td className="py-3 px-3 text-right text-negative">{S.yr2022.spy}%</td>
                  <td className="py-3 pl-3 text-right text-ink font-medium">{S.yr2022.preserver}%</td>
                </tr>
                <tr className="border-b border-rule/60">
                  <td className="py-3 pr-3 font-body">Worst drop (last 5 yrs)</td>
                  <td className="py-3 px-3 text-right text-negative">{PERF.benchmarks.spy_5yr.maxdd}%</td>
                  <td className="py-3 pl-3 text-right text-ink font-medium">{PERF.preserver.yr5.maxdd}%</td>
                </tr>
                <tr>
                  <td className="py-3 pr-3 font-body">Longest time underwater</td>
                  <td className="py-3 px-3 text-right text-negative">{S.longest_underwater_yrs.spy} yrs</td>
                  <td className="py-3 pl-3 text-right text-ink font-medium">{S.longest_underwater_yrs.preserver} yrs</td>
                </tr>
              </tbody>
            </table>
          </div>

          <p className="mt-6 text-[1.08rem] text-ink-mute max-w-2xl">
            Over five years, Preserver felt only about a quarter of the market&rsquo;s <em>down</em>
            months ({S.down_month_capture.preserver} vs {S.down_month_capture.spy}). That&rsquo;s the
            whole point: not beating the market every single year &mdash; <strong className="text-ink font-medium">not
            blowing up when everyone else does.</strong>
          </p>
          <p className="mt-4 text-[0.82rem] text-ink-light">
            Walk-forward results, survivorship-free, vintage {PERF.vintage}. Past results are not a
            promise of future returns.
          </p>
        </div>
      </section>

      {/* ⑤ HONEST — who it's for / not for */}
      <section className="py-16">
        <div className="max-w-3xl mx-auto px-4 sm:px-8">
          <Eyebrow>Honest fit</Eyebrow>
          <h2 className="font-display text-[1.9rem] sm:text-[2.3rem] font-medium leading-[1.15] tracking-tight text-ink"
              style={{ fontVariationSettings: '"opsz" 48' }}>
            This isn&rsquo;t for everyone &mdash; on purpose.
          </h2>
          <div className="mt-8 grid gap-6 sm:grid-cols-2">
            <div className="border border-rule rounded bg-paper-card p-6">
              <div className="font-mono text-[0.7rem] uppercase tracking-[0.14em] text-positive mb-3">It&rsquo;s for you if</div>
              <p className="text-[1rem] text-ink-mute leading-[1.55]">
                You have real money at stake, you know you&rsquo;re prone to panic-selling, and you
                want the decision taken out of your hands and put on a rule.
              </p>
            </div>
            <div className="border border-rule rounded bg-paper-card p-6">
              <div className="font-mono text-[0.7rem] uppercase tracking-[0.14em] text-claret mb-3">It&rsquo;s not for you if</div>
              <p className="text-[1rem] text-ink-mute leading-[1.55]">
                You&rsquo;re a day-trader, chasing the hottest stock, or you&rsquo;ll second-guess the
                system the first time it trails a roaring bull market. In a melt-up, disciplined
                defense costs a little. That&rsquo;s the premium &mdash; like any insurance.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Portfolio Overlay (Tier 1) — softer, personalized last beat before the ask.
          Public, counts only. Convinced by the reframe/system/proof → now check your
          own holdings against it, then start. */}
      <PortfolioOverlay path="/should-i-sell" onGetStarted={handleGetStarted} />

      {/* ⑥ CTA — primary trial + soft catch */}
      <section ref={ctaRef} className="bg-ink text-paper py-16">
        <div className="max-w-3xl mx-auto px-4 sm:px-8 text-center">
          <h2 className="font-display text-[1.7rem] sm:text-[2.5rem] font-medium leading-[1.14] tracking-tight [text-wrap:balance]"
              style={{ fontVariationSettings: '"opsz" 72' }}>
            <span className="block">Your money doesn&rsquo;t need a hero.</span>
            <span className="block mt-1">It needs a rule.</span>
          </h2>
          <button
            onClick={() => { logPublicEvent('cta_trial'); handleGetStarted(); }}
            className="mt-8 bg-claret text-paper font-body font-medium text-[1.05rem] px-8 py-4 rounded hover:bg-claret-light transition-colors"
          >
            Start free &mdash; no card
          </button>
          <p className="mt-3 text-[0.9rem] text-paper/60">Full access &middot; cancel anytime</p>
        </div>
      </section>

      {/* Soft catch — the not-yet-ready panicker (light section; the signup is light-styled) */}
      <section className="bg-paper-card border-b border-rule py-14">
        <div className="max-w-xl mx-auto px-4 sm:px-8">
          <p className="font-display italic text-[1.05rem] text-ink-mute mb-1 text-center"
             style={{ fontVariationSettings: '"opsz" 28' }}>
            Not ready to commit? See where the system stands right now &mdash; free, no card.
          </p>
          <MarketMeasuredSignup source="should_i_sell" onSubscribed={() => logPublicEvent('newsletter_submit')} />
        </div>
      </section>

      {/* Explore the deeper site — catch the not-yet-ready lander instead of dead-ending them */}
      <ExploreMore heading="Still deciding? The evidence is worth a look." />

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
