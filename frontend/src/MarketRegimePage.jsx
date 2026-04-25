import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, ArrowRight, Activity, Shield, TrendingUp, Mail, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';
import { formatDate, formatChartDate } from './utils/formatDate';
import MarketMeasuredSignup from './components/MarketMeasuredSignup';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const TURNSTILE_SITE_KEY = import.meta.env.VITE_TURNSTILE_SITE_KEY;

const REGIME_DESCRIPTIONS = {
  strong_bull: 'Markets are trending strongly upward with broad participation across sectors.',
  weak_bull: 'Markets are rising but with narrow leadership and lower conviction.',
  rotating_bull: 'Markets are up overall, but leadership is rotating between sectors.',
  range_bound: 'Markets are moving sideways without a clear directional trend.',
  weak_bear: 'Markets are drifting lower with increasing caution among investors.',
  panic_crash: 'Markets are in sharp decline with elevated fear and volatility.',
  recovery: 'Markets are bouncing back from a downturn with improving breadth.',
};

function getVixLabel(vix) {
  if (vix == null) return { label: 'N/A', color: 'text-ink-mute' };
  if (vix < 15) return { label: 'Calm', color: 'text-positive' };
  if (vix < 20) return { label: 'Normal', color: 'text-ink-mute' };
  if (vix < 25) return { label: 'Elevated', color: 'text-claret' };
  if (vix < 35) return { label: 'High Fear', color: 'text-negative' };
  return { label: 'Extreme Fear', color: 'text-negative' };
}

export default function MarketRegimePage() {
  useEffect(() => { document.title = 'Market Regime Intelligence | RigaCap';
    const meta = document.querySelector('meta[name="description"]');
    if (meta) meta.setAttribute('content', 'Free weekly market regime analysis. Our 7-regime detection system analyzes market conditions daily so you know the mood before you trade.');

    // OG tags for social sharing
    document.querySelector('meta[property="og:title"]')?.setAttribute('content', 'Weekly Market Regime Intelligence | RigaCap');
    document.querySelector('meta[property="og:description"]')?.setAttribute('content', 'Free weekly market regime analysis. Our 7-regime detection system analyzes market conditions daily so you know the mood before you trade.');
    document.querySelector('meta[property="og:url"]')?.setAttribute('content', 'https://rigacap.com/market-regime');
    document.querySelector('meta[name="twitter:title"]')?.setAttribute('content', 'Weekly Market Regime Intelligence | RigaCap');
    document.querySelector('meta[name="twitter:description"]')?.setAttribute('content', 'Free weekly market regime analysis. Our 7-regime detection system analyzes market conditions daily so you know the mood before you trade.');
    // JSON-LD schema
    const existingSchema = document.querySelector('script[type="application/ld+json"]');
    if (existingSchema) existingSchema.remove();
    const schema = document.createElement('script');
    schema.type = 'application/ld+json';
    schema.text = JSON.stringify({
      "@context": "https://schema.org",
      "@type": "WebPage",
      "name": "Weekly Market Regime Intelligence",
      "description": "Free weekly market regime analysis. Our 7-regime detection system analyzes market conditions daily so you know the mood before you trade.",
      "author": {"@type": "Organization", "name": "RigaCap"},
      "publisher": {"@type": "Organization", "name": "RigaCap", "url": "https://rigacap.com"},
      "url": "https://rigacap.com/market-regime",
    });
    document.head.appendChild(schema);
    return () => { if (schema.parentNode) schema.remove(); };
  }, []);

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Subscribe form state
  const [email, setEmail] = useState('');
  const [subscribing, setSubscribing] = useState(false);
  const [subscribeResult, setSubscribeResult] = useState(null);
  const [turnstileToken, setTurnstileToken] = useState('');
  const turnstileRef = useRef(null);
  const turnstileWidgetId = useRef(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/public/regime-report`)
      .then(res => res.json())
      .then(d => { setData(d); setLoading(false); })
      .catch(e => { setError(e.message); setLoading(false); });
  }, []);

  // Load Turnstile widget — re-run when data loads (ref becomes available)
  useEffect(() => {
    if (!TURNSTILE_SITE_KEY || !data) return;

    const renderWidget = () => {
      if (window.turnstile && turnstileRef.current && turnstileWidgetId.current === null) {
        turnstileWidgetId.current = window.turnstile.render(turnstileRef.current, {
          sitekey: TURNSTILE_SITE_KEY,
          callback: (token) => setTurnstileToken(token),
          'error-callback': () => setTurnstileToken(''),
          'expired-callback': () => setTurnstileToken(''),
        });
      }
    };

    if (window.turnstile) {
      renderWidget();
    } else {
      const interval = setInterval(() => {
        if (window.turnstile) {
          renderWidget();
          clearInterval(interval);
        }
      }, 200);
      return () => clearInterval(interval);
    }
  }, [data]);

  const resetTurnstile = useCallback(() => {
    if (window.turnstile && turnstileWidgetId.current !== null) {
      window.turnstile.reset(turnstileWidgetId.current);
      setTurnstileToken('');
    }
  }, []);

  const handleSubscribe = async (e) => {
    e.preventDefault();
    if (!email.trim()) return;
    if (!turnstileToken && TURNSTILE_SITE_KEY) {
      setSubscribeResult({ success: false, message: 'Please complete the verification' });
      return;
    }

    setSubscribing(true);
    setSubscribeResult(null);

    try {
      const res = await fetch(`${API_BASE}/api/public/subscribe`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: email.trim(),
          turnstile_token: turnstileToken || 'dev-bypass',
          source: 'regime_report',
        }),
      });
      const result = await res.json();
      if (res.ok) {
        setSubscribeResult({ success: true, message: result.message });
        setEmail('');
      } else {
        setSubscribeResult({ success: false, message: result.detail || 'Something went wrong' });
        resetTurnstile();
      }
    } catch {
      setSubscribeResult({ success: false, message: 'Network error. Please try again.' });
      resetTurnstile();
    } finally {
      setSubscribing(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-paper flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-claret animate-spin" />
      </div>
    );
  }

  if (error || !data || !data.current) {
    return (
      <div className="min-h-screen bg-paper font-body text-ink flex items-center justify-center">
        <div className="text-center">
          <AlertCircle className="w-12 h-12 text-ink-light mx-auto mb-4" />
          <p className="text-lg text-ink-mute">Regime data is being prepared. Check back soon.</p>
          <Link to="/" className="text-claret hover:text-claret/80 mt-4 inline-block">Back to RigaCap</Link>
        </div>
      </div>
    );
  }

  const { current, week_over_week, prior_regime, transition_probabilities, history } = data;

  return (
    <div className="min-h-screen bg-paper font-body text-ink">
      {/* Nav */}
      <nav className="sticky top-0 z-50 bg-paper/95 backdrop-blur-sm border-b border-rule">
        <div className="max-w-3xl mx-auto px-4 py-4 flex items-center gap-4">
          <Link to="/" className="flex items-center gap-2 text-ink-mute hover:text-ink transition-colors">
            <ArrowLeft size={18} />
            <span className="text-sm">Back to RigaCap</span>
          </Link>
        </div>
      </nav>

      {/* Hero */}
      <section className="border-b border-rule">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 py-16 sm:py-20 text-center">
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-claret/10 rounded text-sm font-medium mb-6">
            <Activity className="w-4 h-4 text-claret" />
            <span className="text-ink-mute">Updated Daily</span>
          </div>
          <h1 className="font-display text-4xl sm:text-5xl font-bold text-ink tracking-tight mb-4" style={{ fontVariationSettings: '"opsz" 48' }}>
            Weekly Market Intelligence
          </h1>
          <p className="text-lg text-ink-mute max-w-2xl mx-auto mb-8">
            Our 7-regime detection system analyzes market conditions daily.<br />Know the market's mood before you trade.
          </p>

          {/* Regime Badge */}
          <div
            className="inline-flex items-center gap-3 px-8 py-4 rounded border-2"
            style={{ borderColor: current.color, backgroundColor: current.bg + '20' }}
          >
            <div className="w-4 h-4 rounded-full" style={{ backgroundColor: current.color }}></div>
            <span className="font-display text-2xl sm:text-3xl font-bold text-ink">{current.name}</span>
          </div>

          {week_over_week && week_over_week.startsWith('Shifted') && (
            <p className="mt-4 text-ink-mute text-sm">{week_over_week}</p>
          )}
        </div>
      </section>

      {/* Stats Row */}
      <section className="max-w-3xl mx-auto px-4 sm:px-6 -mt-8 relative z-10">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4">
          <StatCard label="S&P 500" value={current.spy_close ? `$${current.spy_close.toFixed(2)}` : 'N/A'} />
          <StatCard label="Market Fear" value={current.vix_close ? `${getVixLabel(current.vix_close).label} (VIX: ${current.vix_close.toFixed(1)})` : 'N/A'} />
          <StatCard label="Regime Duration" value={`${current.days_in_regime} day${current.days_in_regime !== 1 ? 's' : ''}`} />
          <StatCard label="Outlook" value={current.outlook ? current.outlook.replace('_', ' ').replace(/\b\w/g, c => c.toUpperCase()) : 'N/A'} />
        </div>
      </section>

      {/* Regime Description */}
      <section className="max-w-3xl mx-auto px-4 sm:px-6 mt-8">
        <div className="bg-paper-card border border-rule rounded p-6">
          <div className="flex items-start gap-4">
            <div className="w-10 h-10 rounded flex items-center justify-center flex-shrink-0" style={{ backgroundColor: current.color + '20' }}>
              <Shield className="w-5 h-5" style={{ color: current.color }} />
            </div>
            <div>
              <h3 className="text-ink font-semibold mb-1">Current Regime: {current.name}</h3>
              {prior_regime && (
                <p className="text-ink-light text-xs mb-2">
                  Prior regime: <span style={{ color: prior_regime.color }}>{prior_regime.name}</span>
                  {prior_regime.date && <span> (ended {formatDate(prior_regime.date)})</span>}
                </p>
              )}
              <p className="text-ink-mute text-sm leading-relaxed">
                {REGIME_DESCRIPTIONS[current.regime] || 'Market conditions are being analyzed.'}
              </p>
              {current.recommended_action && (
                <div className="mt-3 inline-flex items-center gap-2 px-3 py-1.5 bg-claret/10 border border-claret/20 rounded">
                  <span className="text-xs text-claret uppercase font-medium">Recommended</span>
                  <span className="text-sm text-ink font-medium">
                    {current.recommended_action.replace('_', ' ').replace(/\b\w/g, c => c.toUpperCase())}
                  </span>
                </div>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* 30-Day Timeline */}
      {history && history.length > 0 && (
        <section className="max-w-3xl mx-auto px-4 sm:px-6 mt-8">
          <div className="bg-paper-card border border-rule rounded p-6">
            <h2 className="font-display text-ink font-semibold mb-4" style={{ fontVariationSettings: '"opsz" 48' }}>30-Day Regime Timeline</h2>
            <div className="flex gap-0.5">
              {history.map((day, i) => (
                <div
                  key={i}
                  className="flex-1 h-8 rounded-sm cursor-default group relative"
                  style={{ backgroundColor: day.color }}
                  title={`${formatDate(day.date)}: ${day.name}`}
                >
                  <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 bg-paper-deep text-xs text-ink rounded whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10">
                    {formatDate(day.date, { compact: true })}: {day.name}
                  </div>
                </div>
              ))}
            </div>
            <div className="flex justify-between mt-2 text-xs text-ink-light">
              <span>{formatDate(history[0]?.date)}</span>
              <span>{formatDate(history[history.length - 1]?.date)}</span>
            </div>
          </div>
        </section>
      )}

      {/* Transition Probabilities */}
      {transition_probabilities && transition_probabilities.length > 0 && (
        <section className="max-w-3xl mx-auto px-4 sm:px-6 mt-8">
          <div className="bg-paper-card border border-rule rounded p-6">
            <h2 className="font-display text-ink font-semibold mb-4" style={{ fontVariationSettings: '"opsz" 48' }}>What's Next? Transition Probabilities</h2>
            <div className="space-y-3">
              {transition_probabilities.map((tp) => (
                <div key={tp.regime} className="flex items-center gap-3">
                  <span className="text-sm text-ink-mute w-32 flex-shrink-0">{tp.name}</span>
                  <div className="flex-1 bg-paper-deep rounded-full h-5 overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-500"
                      style={{ width: `${Math.min(tp.probability, 100)}%`, backgroundColor: tp.color }}
                    ></div>
                  </div>
                  <span className="text-sm text-ink-mute w-12 text-right">{tp.probability}%</span>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* Email Signup */}
      <section className="max-w-3xl mx-auto px-4 sm:px-6 mt-12 mb-8">
        <div className="bg-paper-card border border-rule rounded p-8 text-center">
          <Mail className="w-10 h-10 text-claret mx-auto mb-4" />
          <h2 className="font-display text-2xl font-bold text-ink mb-2" style={{ fontVariationSettings: '"opsz" 48' }}>Get This Report Every Monday</h2>
          <p className="text-ink-mute mb-6 max-w-lg mx-auto">
            Free weekly market regime analysis delivered to your inbox. No account required.
          </p>

          {subscribeResult?.success ? (
            <div className="flex items-center justify-center gap-2 text-positive">
              <CheckCircle className="w-5 h-5" />
              <span className="font-medium">{subscribeResult.message}</span>
            </div>
          ) : (
            <form onSubmit={handleSubscribe} className="max-w-md mx-auto">
              <div className="flex gap-2">
                <input
                  type="email"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  placeholder="your@email.com"
                  required
                  className="flex-1 px-4 py-3 bg-paper border border-rule rounded text-ink placeholder-ink-light focus:outline-none focus:ring-2 focus:ring-claret/30 focus:border-claret/50"
                />
                <button
                  type="submit"
                  disabled={subscribing}
                  className="px-6 py-3 bg-ink text-paper hover:bg-claret font-semibold rounded transition-colors disabled:opacity-50 flex items-center gap-2"
                >
                  {subscribing ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                  Subscribe
                </button>
              </div>
              {TURNSTILE_SITE_KEY && (
                <div ref={turnstileRef} className="mt-3 flex justify-center"></div>
              )}
              {subscribeResult && !subscribeResult.success && (
                <p className="mt-2 text-negative text-sm">{subscribeResult.message}</p>
              )}
              <p className="mt-3 text-xs text-ink-light">Unsubscribe anytime. We respect your inbox.</p>
            </form>
          )}
        </div>
      </section>

      {/* Weekly newsletter signup */}
      <section className="max-w-3xl mx-auto px-4 sm:px-6 pb-12">
        <MarketMeasuredSignup source="market_regime_page" />
      </section>

      {/* CTA */}
      <section className="max-w-3xl mx-auto px-4 sm:px-6 pb-16 text-center">
        <p className="text-ink-mute mb-4">Want daily buy/sell signals powered by this regime intelligence?</p>
        <Link
          to="/track-record"
          className="inline-flex items-center gap-2 px-8 py-4 bg-ink text-paper hover:bg-claret font-semibold rounded transition-colors"
        >
          See Our Track Record
          <ArrowRight className="w-5 h-5" />
        </Link>
      </section>

      {/* Footer disclaimer */}
      <footer className="border-t border-rule py-8 text-center">
        <p className="text-xs text-ink-light max-w-2xl mx-auto px-4">
          Trading involves risk. Past performance does not guarantee future results.
          This is market analysis, not investment advice. Always do your own research.
        </p>
        <div className="mt-4 flex items-center justify-center gap-4 text-xs text-ink-light">
          <Link to="/privacy" className="hover:text-ink">Privacy</Link>
          <Link to="/terms" className="hover:text-ink">Terms</Link>
          <Link to="/contact" className="hover:text-ink">Contact</Link>
        </div>
      </footer>
    </div>
  );
}

function StatCard({ label, value }) {
  return (
    <div className="bg-paper-card border border-rule rounded p-4 text-center">
      <p className="text-xs text-ink-light uppercase tracking-wider mb-1">{label}</p>
      <p className="text-lg sm:text-xl font-bold text-ink">{value}</p>
    </div>
  );
}
