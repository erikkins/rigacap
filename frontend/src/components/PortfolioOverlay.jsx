import React, { useState } from 'react';
import { logPublicEvent } from '../lib/publicEvent';

// Portfolio Overlay — Tier 1 (public, no signup). Paste tickers → aggregate COUNTS ONLY of how
// they intersect RigaCap's universe + 5-yr signal history (Preserver core ∪ Maximizer breakout).
// Impersonal/factual by design (see design/documents/compliance-portfolio-overlay-brief.md).
// Mounted ONLY on the public landing pages. Trivial to pull (revert the mount).
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

function getSessionId() {
  try {
    let s = sessionStorage.getItem('rigacap_session');
    if (!s) {
      s = Math.random().toString(36).slice(2) + Date.now().toString(36);
      sessionStorage.setItem('rigacap_session', s);
    }
    return s;
  } catch {
    return null;
  }
}

export default function PortfolioOverlay({ path, onGetStarted }) {
  const [raw, setRaw] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [err, setErr] = useState('');

  const check = async () => {
    const tickers = raw
      .split(/[\s,;\n]+/)
      .map((t) => t.trim().toUpperCase())
      .filter(Boolean);
    if (!tickers.length) {
      setErr('Enter a few tickers — e.g. AAPL, NVDA, MSFT.');
      return;
    }
    setErr('');
    setLoading(true);
    setResult(null);
    try {
      const p = new URLSearchParams(window.location.search);
      const res = await fetch(`${API_BASE}/api/public/portfolio-check`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tickers,
          session_id: getSessionId(),
          source: 'landing_widget',
          path: path || window.location.pathname,
          utm_source: p.get('utm_source'),
          utm_campaign: p.get('utm_campaign'),
          gclid: p.get('gclid'),
        }),
      });
      const data = await res.json();
      setResult(data);
      logPublicEvent('portfolio_check', { path });
    } catch (e) {
      setErr('Something went off — try again in a moment.');
    } finally {
      setLoading(false);
    }
  };

  const cta = () => {
    logPublicEvent('portfolio_check_cta', { path });
    if (onGetStarted) onGetStarted();
  };

  const hasHits = result && (result.in_universe_count > 0 || result.ever_qualified_count > 0);

  return (
    <section className="bg-paper-card border-y border-rule py-12">
      <div className="max-w-3xl mx-auto px-4 sm:px-8">
        <p
          className="font-display text-[1.6rem] sm:text-[1.95rem] font-medium text-ink leading-tight"
          style={{ fontVariationSettings: '"opsz" 48' }}
        >
          Before you sell — see what RigaCap makes of your holdings.
        </p>
        <p className="mt-2 text-ink-mute">
          Paste a few tickers. See how many RigaCap tracks, and how many have fired a signal
          in the last five years — no signup, nothing tied to your name.
        </p>
        <div className="mt-5 flex flex-col sm:flex-row gap-3">
          <input
            value={raw}
            onChange={(e) => setRaw(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') check();
            }}
            placeholder="AAPL, NVDA, MSFT, PLTR…"
            aria-label="Your tickers"
            className="flex-1 px-4 py-3 border border-rule rounded bg-paper text-ink placeholder:text-ink-light focus:outline-none focus:border-claret"
          />
          <button
            onClick={check}
            disabled={loading}
            className="bg-ink text-paper font-medium px-6 py-3 rounded hover:bg-claret transition-colors disabled:opacity-50"
          >
            {loading ? 'Checking…' : 'Check'}
          </button>
        </div>
        {err && <p className="mt-3 text-claret text-sm">{err}</p>}
        {result && (
          <div className="mt-6 border-t border-rule pt-5">
            {hasHits ? (
              <>
                <p className="text-[1.15rem] text-ink">
                  <strong>
                    {result.in_universe_count} of your {result.ticker_count}
                  </strong>{' '}
                  are in RigaCap&rsquo;s universe
                  {result.ever_qualified_count > 0 ? (
                    <>
                      {' '}— and <strong>{result.ever_qualified_count}</strong> have triggered a
                      RigaCap signal in the last five years
                      {result.entered_count > 0 && (
                        <> ({result.entered_count} the model actually held)</>
                      )}
                      .
                    </>
                  ) : (
                    <>.</>
                  )}
                </p>
                <button
                  onClick={cta}
                  className="mt-5 bg-claret text-paper font-medium px-7 py-3.5 rounded hover:bg-claret-light transition-colors"
                >
                  See which ones &mdash; start free, no card
                </button>
              </>
            ) : (
              <>
                <p className="text-[1.15rem] text-ink">
                  Your names are off our radar right now — RigaCap tracks ~600 of the most liquid
                  U.S. stocks.
                </p>
                <button
                  onClick={cta}
                  className="mt-5 bg-claret text-paper font-medium px-7 py-3.5 rounded hover:bg-claret-light transition-colors"
                >
                  See what we <em>do</em> track &mdash; start free
                </button>
              </>
            )}
            <p className="mt-4 text-ink-light text-sm">
              Information only — not individualized investment advice.
            </p>
          </div>
        )}
      </div>
    </section>
  );
}
