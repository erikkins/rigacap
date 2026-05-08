import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import TopNav from './components/TopNav';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

async function fetchAuth(path, opts = {}) {
  // Match App.jsx auth pattern: token lives under 'accessToken'; on 401 try
  // a refresh-token roundtrip before giving up so admin sessions survive
  // longer than the access-token TTL.
  const doFetch = () => {
    const token = localStorage.getItem('accessToken');
    return fetch(`${API_BASE}${path}`, {
      ...opts,
      headers: {
        'Content-Type': 'application/json',
        Authorization: token ? `Bearer ${token}` : '',
        ...(opts.headers || {}),
      },
    });
  };
  let res = await doFetch();
  if (res.status === 401 && localStorage.getItem('refreshToken')) {
    const refresh = await fetch(`${API_BASE}/api/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: localStorage.getItem('refreshToken') }),
    });
    if (refresh.ok) {
      const data = await refresh.json();
      localStorage.setItem('accessToken', data.access_token);
      if (data.refresh_token) localStorage.setItem('refreshToken', data.refresh_token);
      res = await doFetch();
    }
  }
  return res;
}

function fmtDate(ts) {
  if (!ts) return '';
  try {
    const ms = typeof ts === 'number' && ts < 1e12 ? ts * 1000 : ts;
    return new Date(ms).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  } catch {
    return String(ts);
  }
}

export default function SymbolTriagePage() {
  const { symbol } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionState, setActionState] = useState({ busy: false, message: null });
  const [renameTo, setRenameTo] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchAuth(`/api/admin/symbol-triage/${encodeURIComponent(symbol)}`);
      if (res.status === 401 || res.status === 403) {
        setError('You must be signed in as an admin to use this page.');
        return;
      }
      if (!res.ok) {
        const txt = await res.text();
        setError(`Server error ${res.status}: ${txt.slice(0, 200)}`);
        return;
      }
      const json = await res.json();
      setData(json);
    } catch (e) {
      setError(`Network error: ${e.message}`);
    } finally {
      setLoading(false);
    }
  }, [symbol]);

  useEffect(() => {
    document.title = `Triage: ${symbol} | RigaCap admin`;
    load();
  }, [symbol, load]);

  const action = async (verb, body = null) => {
    if (actionState.busy) return;
    if (!window.confirm(`Confirm: ${verb.replace(/-/g, ' ')} for ${symbol}?`)) return;
    setActionState({ busy: true, message: null });
    try {
      const res = await fetchAuth(`/api/admin/symbol-triage/${encodeURIComponent(symbol)}/${verb}`, {
        method: 'POST',
        body: body ? JSON.stringify(body) : null,
      });
      const json = await res.json();
      setActionState({ busy: false, message: json.detail || json.status });
      if (res.ok) await load();
    } catch (e) {
      setActionState({ busy: false, message: `Failed: ${e.message}` });
    }
  };

  return (
    <div className="min-h-screen bg-paper font-body text-ink antialiased">
      <TopNav />
      <div className="max-w-[820px] mx-auto px-4 sm:px-8 py-10">
        <Link to="/admin" className="font-mono text-[0.78rem] tracking-[0.15em] uppercase text-ink-mute hover:text-ink no-underline">
          ← Admin
        </Link>

        <h1
          className="font-display text-[3rem] mt-6 mb-2 leading-none tracking-[-0.02em]"
          style={{ fontVariationSettings: '"opsz" 96', fontWeight: 400 }}
        >
          {symbol}
          <span className="text-claret">.</span>
        </h1>
        <p className="font-display italic text-ink-mute text-[1.1rem] mb-8" style={{ fontVariationSettings: '"opsz" 24' }}>
          Symbol triage
        </p>

        {loading && <p className="text-ink-mute">Loading triage data…</p>}
        {error && (
          <div className="bg-paper-card border-l-4 border-claret p-4 mb-6">
            <p className="font-mono text-[0.85rem] text-claret">{error}</p>
          </div>
        )}

        {data && !loading && (
          <>
            {/* Summary stat row */}
            <div className="grid grid-cols-2 md:grid-cols-4 border-y border-rule py-4 mb-8">
              <div className="px-3 border-r border-rule">
                <div className="font-mono text-[0.65rem] tracking-[0.18em] uppercase text-ink-mute mb-1">Days missing</div>
                <div className="font-display text-[1.6rem]" style={{ fontVariationSettings: '"opsz" 48' }}>{data.days_missing ?? '—'}</div>
              </div>
              <div className="px-3 border-r border-rule">
                <div className="font-mono text-[0.65rem] tracking-[0.18em] uppercase text-ink-mute mb-1">Status</div>
                <div className="font-display text-[1.1rem] mt-2">{data.status || 'unknown'}</div>
              </div>
              <div className="px-3 border-r border-rule">
                <div className="font-mono text-[0.65rem] tracking-[0.18em] uppercase text-ink-mute mb-1">Held by user?</div>
                <div className="font-display text-[1.1rem] mt-2">
                  {data.in_open_position ? <span className="text-claret font-semibold">YES — urgent</span> : 'no'}
                </div>
              </div>
              <div className="px-3">
                <div className="font-mono text-[0.65rem] tracking-[0.18em] uppercase text-ink-mute mb-1">Last close</div>
                <div className="font-display text-[1.1rem] mt-2">
                  {data.last_known_bar?.close ? `$${data.last_known_bar.close.toFixed(2)}` : '—'}
                  {data.last_known_bar?.date && (
                    <span className="text-ink-mute text-[0.78rem] block">{data.last_known_bar.date}</span>
                  )}
                </div>
              </div>
            </div>

            {/* AI summary */}
            <section className="mb-8">
              <h2 className="font-display text-[1.5rem] mb-3" style={{ fontVariationSettings: '"opsz" 48' }}>
                AI <em className="text-claret">context.</em>
              </h2>
              <div className="bg-paper-card border-l-[3px] border-claret p-5 leading-relaxed text-[1rem] whitespace-pre-line">
                {data.ai_summary}
              </div>
            </section>

            {/* News headlines */}
            {data.news_headlines && data.news_headlines.length > 0 && (
              <section className="mb-8">
                <h2 className="font-display text-[1.3rem] mb-3" style={{ fontVariationSettings: '"opsz" 48' }}>
                  Recent headlines
                </h2>
                <ul className="border-t border-rule">
                  {data.news_headlines.map((h, i) => (
                    <li key={i} className="border-b border-rule py-3 flex items-start justify-between gap-4">
                      <div className="flex-1">
                        <a
                          href={h.link}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="font-display text-[0.98rem] text-ink hover:text-claret no-underline leading-snug"
                          style={{ fontVariationSettings: '"opsz" 24' }}
                        >
                          {h.title || '(untitled)'}
                        </a>
                        <div className="font-mono text-[0.72rem] text-ink-light mt-1">
                          {h.publisher || ''}
                          {h.providerPublishTime && ` · ${fmtDate(h.providerPublishTime)}`}
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {/* Alpaca status */}
            <section className="mb-8">
              <h2 className="font-display text-[1.3rem] mb-3" style={{ fontVariationSettings: '"opsz" 48' }}>
                Alpaca asset lookup
              </h2>
              {data.alpaca_asset ? (
                <pre className="bg-paper-card border border-rule p-4 font-mono text-[0.78rem] overflow-x-auto">
                  {JSON.stringify(data.alpaca_asset, null, 2)}
                </pre>
              ) : (
                <div className="bg-paper-card border-l-[3px] border-claret p-4 font-mono text-[0.85rem]">
                  {data.alpaca_error || 'Alpaca returned no asset for this symbol — likely delisted or never listed.'}
                </div>
              )}
            </section>

            {/* Action panel */}
            <section className="border-t-2 border-ink pt-6 mt-10">
              <h2 className="font-display text-[1.5rem] mb-4" style={{ fontVariationSettings: '"opsz" 48' }}>
                Resolve
              </h2>

              {actionState.message && (
                <div className="bg-paper-card border-l-[3px] border-claret p-3 mb-4 font-mono text-[0.85rem]">
                  {actionState.message}
                </div>
              )}

              <div className="grid gap-3">
                <button
                  onClick={() => action('mark-delisted')}
                  disabled={actionState.busy}
                  className="text-left border border-claret px-5 py-3 hover:bg-claret hover:text-paper transition-colors disabled:opacity-40"
                >
                  <span className="font-display font-medium">Mark delisted</span>
                  <span className="block text-[0.85rem] text-ink-mute group-hover:text-paper-card mt-0.5">
                    Sets status=delisted, clears the missing-streak. Symbol drops out of future hygiene digests.
                  </span>
                </button>

                <div className="border border-rule px-5 py-3">
                  <div className="font-display font-medium mb-2">Mark renamed</div>
                  <p className="text-[0.85rem] text-ink-mute mb-3">
                    Records the new ticker and clears the streak. Records audit trail in quarantine_reason.
                  </p>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={renameTo}
                      onChange={(e) => setRenameTo(e.target.value.toUpperCase())}
                      placeholder="NEW_TICKER"
                      className="flex-1 border border-rule px-3 py-2 font-mono text-[0.95rem] bg-paper"
                    />
                    <button
                      onClick={() => renameTo && action('mark-renamed', { new_ticker: renameTo })}
                      disabled={!renameTo || renameTo === symbol || actionState.busy}
                      className="border border-claret px-4 py-2 hover:bg-claret hover:text-paper transition-colors disabled:opacity-40 font-display font-medium"
                    >
                      Save rename
                    </button>
                  </div>
                </div>

                <button
                  onClick={() => action('repoll-now')}
                  disabled={actionState.busy}
                  className="text-left border border-rule px-5 py-3 hover:bg-paper-card transition-colors disabled:opacity-40"
                >
                  <span className="font-display font-medium">Re-poll Alpaca now</span>
                  <span className="block text-[0.85rem] text-ink-mute mt-0.5">
                    Forces a fresh asset check. If found, clears the missing-streak.
                  </span>
                </button>
              </div>
            </section>
          </>
        )}
      </div>
    </div>
  );
}
