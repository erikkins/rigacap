import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Mail, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const TURNSTILE_SITE_KEY = import.meta.env.VITE_TURNSTILE_SITE_KEY;

export default function MarketMeasuredSignup({ source = 'landing', variant = 'light' }) {
  const [email, setEmail] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null);
  const [turnstileToken, setTurnstileToken] = useState('');
  const turnstileRef = useRef(null);
  const turnstileWidgetId = useRef(null);
  const emailInputRef = useRef(null);

  // If arrived from a forwarded email (?subscribe=market_measured), scroll
  // the form into view and focus the email input. Override the source for
  // GA4/DB attribution so we can measure forward-driven signups.
  const params = new URLSearchParams(typeof window !== 'undefined' ? window.location.search : '');
  const arrivedFromForward = params.get('subscribe') === 'market_measured';
  const effectiveSource = arrivedFromForward ? 'forward' : source;

  useEffect(() => {
    if (!arrivedFromForward) return;
    const t = setTimeout(() => {
      emailInputRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      emailInputRef.current?.focus({ preventScroll: true });
    }, 250);
    return () => clearTimeout(t);
  }, [arrivedFromForward]);

  useEffect(() => {
    if (!TURNSTILE_SITE_KEY) return;
    const renderWidget = () => {
      if (window.turnstile && turnstileRef.current && turnstileWidgetId.current === null) {
        turnstileWidgetId.current = window.turnstile.render(turnstileRef.current, {
          sitekey: TURNSTILE_SITE_KEY,
          theme: variant === 'dark' ? 'dark' : 'light',
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
  }, [variant]);

  const resetTurnstile = useCallback(() => {
    if (window.turnstile && turnstileWidgetId.current !== null) {
      window.turnstile.reset(turnstileWidgetId.current);
      setTurnstileToken('');
    }
  }, []);

  const submit = async (e) => {
    e.preventDefault();
    if (!email.trim()) return;
    if (!turnstileToken && TURNSTILE_SITE_KEY) {
      setResult({ success: false, message: 'Please complete the verification.' });
      return;
    }
    setSubmitting(true);
    setResult(null);
    try {
      const res = await fetch(`${API_BASE}/api/public/subscribe-newsletter`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: email.trim(),
          turnstile_token: turnstileToken || 'dev-bypass',
          report_type: 'market_measured',
          source: effectiveSource,
        }),
      });
      const data = await res.json();
      if (res.ok) {
        setResult({ success: true, message: data.message });
        setEmail('');
      } else {
        setResult({ success: false, message: data.detail || 'Something went wrong.' });
        resetTurnstile();
      }
    } catch {
      setResult({ success: false, message: 'Network error. Please try again.' });
      resetTurnstile();
    } finally {
      setSubmitting(false);
    }
  };

  const isDark = variant === 'dark';
  const container = isDark
    ? 'bg-slate-900/60 border-slate-700 text-slate-100'
    : 'bg-white border-gray-200 text-gray-900';
  const input = isDark
    ? 'bg-slate-800 border-slate-700 text-slate-100 placeholder-slate-500 focus:border-amber-400'
    : 'bg-white border-gray-300 text-gray-900 placeholder-gray-400 focus:border-indigo-500';
  const button = isDark
    ? 'bg-amber-400 hover:bg-amber-300 text-slate-900'
    : 'bg-indigo-600 hover:bg-indigo-700 text-white';

  return (
    <div className={`rounded-2xl border p-6 sm:p-8 ${container}`}>
      <div className="flex items-start gap-3 mb-2">
        <Mail className={isDark ? 'w-5 h-5 text-amber-400 mt-0.5' : 'w-5 h-5 text-indigo-600 mt-0.5'} />
        <div>
          <h3 className="text-lg font-semibold">The market, measured. Delivered Sundays.</h3>
          <p className={isDark ? 'text-sm text-slate-400 mt-1' : 'text-sm text-gray-600 mt-1'}>
            A weekly read of what the system is seeing. Free. No spam. Unsubscribe anytime.
          </p>
        </div>
      </div>

      <form onSubmit={submit} className="mt-4 space-y-3">
        <div className="flex flex-col sm:flex-row gap-2">
          <input
            ref={emailInputRef}
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            className={`flex-1 px-4 py-3 rounded-lg border focus:ring-2 focus:ring-offset-0 focus:ring-indigo-500/30 focus:outline-none ${input}`}
          />
          <button
            type="submit"
            disabled={submitting || !email.trim()}
            className={`px-5 py-3 rounded-lg font-semibold disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 ${button}`}
          >
            {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Subscribe'}
          </button>
        </div>

        {TURNSTILE_SITE_KEY && <div ref={turnstileRef} className="mt-2" />}

        {result && (
          <div
            className={`flex items-center gap-2 text-sm mt-2 ${
              result.success
                ? isDark ? 'text-emerald-400' : 'text-emerald-600'
                : isDark ? 'text-red-400' : 'text-red-600'
            }`}
          >
            {result.success ? <CheckCircle className="w-4 h-4" /> : <AlertCircle className="w-4 h-4" />}
            <span>{result.message}</span>
          </div>
        )}
      </form>
    </div>
  );
}
