import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, ArrowRight, Activity, Shield, TrendingUp, Mail, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';
import { formatDate, formatChartDate } from './utils/formatDate';

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
  if (vix == null) return { label: 'N/A', color: 'text-gray-400' };
  if (vix < 15) return { label: 'Calm', color: 'text-emerald-400' };
  if (vix < 20) return { label: 'Normal', color: 'text-gray-400' };
  if (vix < 25) return { label: 'Elevated', color: 'text-amber-400' };
  if (vix < 35) return { label: 'High Fear', color: 'text-orange-400' };
  return { label: 'Extreme Fear', color: 'text-red-400' };
}

export default function MarketRegimePage() {
  useEffect(() => { document.title = 'Market Regime Intelligence | RigaCap'; }, []);
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
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-amber-400 animate-spin" />
      </div>
    );
  }

  if (error || !data || !data.current) {
    return (
      <div className="min-h-screen bg-gray-950 text-gray-300 flex items-center justify-center">
        <div className="text-center">
          <AlertCircle className="w-12 h-12 text-gray-500 mx-auto mb-4" />
          <p className="text-lg">Regime data is being prepared. Check back soon.</p>
          <Link to="/" className="text-amber-400 hover:text-amber-300 mt-4 inline-block">Back to RigaCap</Link>
        </div>
      </div>
    );
  }

  const { current, week_over_week, prior_regime, transition_probabilities, history } = data;

  return (
    <div className="min-h-screen bg-gray-950 text-gray-300">
      {/* Nav */}
      <nav className="bg-gray-900 border-b border-gray-800">
        <div className="max-w-5xl mx-auto px-4 py-4 flex items-center gap-4">
          <Link to="/" className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors">
            <ArrowLeft size={18} />
            <span className="text-sm">Back to RigaCap</span>
          </Link>
        </div>
      </nav>

      {/* Hero */}
      <section className="relative overflow-hidden bg-gradient-to-br from-indigo-900 via-blue-900 to-purple-900">
        <div className="absolute inset-0 overflow-hidden">
          <div className="absolute -top-40 -right-40 w-80 h-80 bg-amber-500/10 rounded-full blur-3xl"></div>
          <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-blue-500/10 rounded-full blur-3xl"></div>
        </div>
        <div className="relative max-w-5xl mx-auto px-4 sm:px-6 py-16 sm:py-20 text-center">
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-white/10 backdrop-blur-sm rounded-full text-sm font-medium mb-6">
            <Activity className="w-4 h-4 text-amber-300" />
            <span className="text-white/90">Updated Daily</span>
          </div>
          <h1 className="text-4xl sm:text-5xl font-bold text-white tracking-tight mb-4">
            Weekly Market Intelligence
          </h1>
          <p className="text-lg text-blue-200 max-w-2xl mx-auto mb-8">
            Our 7-regime detection system analyzes market conditions daily.<br />Know the market's mood before you trade.
          </p>

          {/* Regime Badge */}
          <div
            className="inline-flex items-center gap-3 px-8 py-4 rounded-2xl border-2"
            style={{ borderColor: current.color, backgroundColor: current.bg + '20' }}
          >
            <div className="w-4 h-4 rounded-full" style={{ backgroundColor: current.color }}></div>
            <span className="text-2xl sm:text-3xl font-bold text-white">{current.name}</span>
          </div>

          {week_over_week && week_over_week.startsWith('Shifted') && (
            <p className="mt-4 text-blue-200 text-sm">{week_over_week}</p>
          )}
        </div>
      </section>

      {/* Stats Row */}
      <section className="max-w-5xl mx-auto px-4 sm:px-6 -mt-8 relative z-10">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4">
          <StatCard label="S&P 500" value={current.spy_close ? `$${current.spy_close.toFixed(2)}` : 'N/A'} />
          <StatCard label="Market Fear" value={current.vix_close ? `${getVixLabel(current.vix_close).label} (VIX: ${current.vix_close.toFixed(1)})` : 'N/A'} />
          <StatCard label="Regime Duration" value={`${current.days_in_regime} day${current.days_in_regime !== 1 ? 's' : ''}`} />
          <StatCard label="Outlook" value={current.outlook ? current.outlook.replace('_', ' ').replace(/\b\w/g, c => c.toUpperCase()) : 'N/A'} />
        </div>
      </section>

      {/* Regime Description */}
      <section className="max-w-5xl mx-auto px-4 sm:px-6 mt-8">
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <div className="flex items-start gap-4">
            <div className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0" style={{ backgroundColor: current.color + '20' }}>
              <Shield className="w-5 h-5" style={{ color: current.color }} />
            </div>
            <div>
              <h3 className="text-white font-semibold mb-1">Current Regime: {current.name}</h3>
              {prior_regime && (
                <p className="text-gray-500 text-xs mb-2">
                  Prior regime: <span style={{ color: prior_regime.color }}>{prior_regime.name}</span>
                  {prior_regime.date && <span> (ended {formatDate(prior_regime.date)})</span>}
                </p>
              )}
              <p className="text-gray-400 text-sm leading-relaxed">
                {REGIME_DESCRIPTIONS[current.regime] || 'Market conditions are being analyzed.'}
              </p>
              {current.recommended_action && (
                <div className="mt-3 inline-flex items-center gap-2 px-3 py-1.5 bg-indigo-500/10 border border-indigo-500/20 rounded-lg">
                  <span className="text-xs text-indigo-300 uppercase font-medium">Recommended</span>
                  <span className="text-sm text-white font-medium">
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
        <section className="max-w-5xl mx-auto px-4 sm:px-6 mt-8">
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
            <h2 className="text-white font-semibold mb-4">30-Day Regime Timeline</h2>
            <div className="flex gap-0.5">
              {history.map((day, i) => (
                <div
                  key={i}
                  className="flex-1 h-8 rounded-sm cursor-default group relative"
                  style={{ backgroundColor: day.color }}
                  title={`${formatDate(day.date)}: ${day.name}`}
                >
                  <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 bg-gray-800 text-xs text-white rounded whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10">
                    {formatDate(day.date, { compact: true })}: {day.name}
                  </div>
                </div>
              ))}
            </div>
            <div className="flex justify-between mt-2 text-xs text-gray-500">
              <span>{formatDate(history[0]?.date)}</span>
              <span>{formatDate(history[history.length - 1]?.date)}</span>
            </div>
          </div>
        </section>
      )}

      {/* Transition Probabilities */}
      {transition_probabilities && transition_probabilities.length > 0 && (
        <section className="max-w-5xl mx-auto px-4 sm:px-6 mt-8">
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
            <h2 className="text-white font-semibold mb-4">What's Next? Transition Probabilities</h2>
            <div className="space-y-3">
              {transition_probabilities.map((tp) => (
                <div key={tp.regime} className="flex items-center gap-3">
                  <span className="text-sm text-gray-300 w-32 flex-shrink-0">{tp.name}</span>
                  <div className="flex-1 bg-gray-800 rounded-full h-5 overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-500"
                      style={{ width: `${Math.min(tp.probability, 100)}%`, backgroundColor: tp.color }}
                    ></div>
                  </div>
                  <span className="text-sm text-gray-400 w-12 text-right">{tp.probability}%</span>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* Email Signup */}
      <section className="max-w-5xl mx-auto px-4 sm:px-6 mt-12 mb-8">
        <div className="bg-gradient-to-br from-indigo-900/50 to-blue-900/50 border border-indigo-700/30 rounded-xl p-8 text-center">
          <Mail className="w-10 h-10 text-amber-400 mx-auto mb-4" />
          <h2 className="text-2xl font-bold text-white mb-2">Get This Report Every Monday</h2>
          <p className="text-blue-200 mb-6 max-w-lg mx-auto">
            Free weekly market regime analysis delivered to your inbox. No account required.
          </p>

          {subscribeResult?.success ? (
            <div className="flex items-center justify-center gap-2 text-emerald-400">
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
                  className="flex-1 px-4 py-3 bg-white/10 border border-white/20 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-amber-400/50 focus:border-amber-400/50"
                />
                <button
                  type="submit"
                  disabled={subscribing}
                  className="px-6 py-3 bg-amber-500 hover:bg-amber-400 text-gray-900 font-semibold rounded-lg transition-colors disabled:opacity-50 flex items-center gap-2"
                >
                  {subscribing ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                  Subscribe
                </button>
              </div>
              {TURNSTILE_SITE_KEY && (
                <div ref={turnstileRef} className="mt-3 flex justify-center"></div>
              )}
              {subscribeResult && !subscribeResult.success && (
                <p className="mt-2 text-red-400 text-sm">{subscribeResult.message}</p>
              )}
              <p className="mt-3 text-xs text-blue-300/60">Unsubscribe anytime. We respect your inbox.</p>
            </form>
          )}
        </div>
      </section>

      {/* CTA */}
      <section className="max-w-5xl mx-auto px-4 sm:px-6 pb-16 text-center">
        <p className="text-gray-400 mb-4">Want daily buy/sell signals powered by this regime intelligence?</p>
        <Link
          to="/track-record"
          className="inline-flex items-center gap-2 px-8 py-4 bg-white text-indigo-700 font-semibold rounded-xl shadow-lg hover:shadow-xl transform hover:-translate-y-0.5 transition-all"
        >
          See Our Track Record
          <ArrowRight className="w-5 h-5" />
        </Link>
      </section>

      {/* Footer disclaimer */}
      <footer className="border-t border-gray-800 py-8 text-center">
        <p className="text-xs text-gray-500 max-w-2xl mx-auto px-4">
          Trading involves risk. Past performance does not guarantee future results.
          This is market analysis, not investment advice. Always do your own research.
        </p>
        <div className="mt-4 flex items-center justify-center gap-4 text-xs text-gray-500">
          <Link to="/privacy" className="hover:text-gray-300">Privacy</Link>
          <Link to="/terms" className="hover:text-gray-300">Terms</Link>
          <Link to="/contact" className="hover:text-gray-300">Contact</Link>
        </div>
      </footer>
    </div>
  );
}

function StatCard({ label, value }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 text-center">
      <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">{label}</p>
      <p className="text-lg sm:text-xl font-bold text-white">{value}</p>
    </div>
  );
}
