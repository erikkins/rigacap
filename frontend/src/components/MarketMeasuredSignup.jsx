import React, { useState, useEffect, useRef, useCallback } from 'react';
import { CheckCircle, AlertCircle, Loader2 } from 'lucide-react';

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
          theme: 'light',
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

  return (
    <div className="border-t border-b border-rule py-8">
      <h3 className="font-display text-[1.25rem] font-medium text-ink tracking-tight mb-1" style={{ fontVariationSettings: '"opsz" 48' }}>
        The market, measured.
      </h3>
      <p className="font-display italic text-ink-mute text-[0.95rem] mb-5" style={{ fontVariationSettings: '"opsz" 24' }}>
        A weekly read of what the system is seeing. Free. Delivered Sundays.
      </p>

      <form onSubmit={submit} className="space-y-3">
        <div className="flex flex-col sm:flex-row gap-2">
          <input
            ref={emailInputRef}
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            className="flex-1 px-4 py-3 border border-rule-dark bg-paper-card font-mono text-[0.9rem] text-ink placeholder-ink-light focus:outline-none focus:border-ink"
          />
          <button
            type="submit"
            disabled={submitting || !email.trim()}
            className="px-6 py-3 bg-ink text-paper font-body text-[0.85rem] font-medium tracking-wide hover:bg-claret transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Subscribe'}
          </button>
        </div>

        {TURNSTILE_SITE_KEY && <div ref={turnstileRef} className="mt-2" />}

        {result && (
          <div className={`flex items-center gap-2 font-mono text-[0.82rem] mt-2 ${result.success ? 'text-positive' : 'text-negative'}`}>
            {result.success ? <CheckCircle className="w-4 h-4" /> : <AlertCircle className="w-4 h-4" />}
            <span>{result.message}</span>
          </div>
        )}
      </form>

      <p className="font-mono text-[0.7rem] text-ink-light mt-3 tracking-wide">No spam. Unsubscribe anytime.</p>
    </div>
  );
}
