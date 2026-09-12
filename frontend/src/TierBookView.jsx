import React, { useState } from 'react';

// Preserver holding gauge — MOBILE-FIRST. Visualizes the price journey on a
// stop→high-water-mark band: the green fill is your CUSHION above the trailing
// stop; the empty gap on the right is how far price has pulled back from its
// high. Entry (thin tick) and today (solid marker) are placed within the band.
// Full-width, no hover dependency (labels always visible), legible at 360px.
function HoldingGauge({ entry, now, hwm, stop }) {
  const lo = Number(stop) || 0;
  const hi = Math.max(Number(hwm) || 0, lo + 0.01);
  const range = (hi - lo) || 1;
  const clamp = (x) => Math.max(0, Math.min(100, ((Number(x) || lo) - lo) / range * 100));
  const nowPct = clamp(now);
  const entryPct = clamp(entry);
  const cushion = now > 0 ? Math.max(0, (now - lo) / now * 100) : 0;
  return (
    <div>
      <div className="relative h-2.5 rounded-full bg-paper-deep">
        {/* cushion fill: stop → today */}
        <div className="absolute inset-y-0 left-0 rounded-full bg-positive/35" style={{ width: `${nowPct}%` }} />
        {/* entry tick */}
        <div className="absolute top-1/2 -translate-y-1/2 h-3.5 w-px bg-ink-mute/70"
             style={{ left: `${entryPct}%` }} title={`Entry $${Number(entry).toFixed(2)}`} />
        {/* today marker */}
        <div className="absolute top-1/2 -translate-y-1/2 h-4 w-[3px] rounded-full bg-ink"
             style={{ left: `calc(${nowPct}% - 1.5px)` }} title={`Today $${Number(now).toFixed(2)}`} />
      </div>
      <div className="flex items-center justify-between mt-1.5 font-mono text-[0.58rem] leading-none text-ink-mute">
        <span title="Trailing stop">stop ${Math.round(lo)}</span>
        <span className="text-claret font-medium">{cushion.toFixed(0)}% cushion to stop</span>
        <span title="High-water mark">high ${Math.round(hi)}</span>
      </div>
    </div>
  );
}

// Capital-scaled MIRROR of a tier's model book. The user sets their capital once; we scale
// the book's positions to it (implied_shares = book_shares x capital/book_value) so their
// portfolio auto-mirrors the book with zero per-trade entry. Maximizer = breakout book
// (day-X/29 exits); Preserver = t30v book (30% trailing). (Jul 24 2026)
export default function TierBookView({ book, onSetCapital, onRowClick, radar, actions, hideCapitalEditor = false, compact = false, marketNote = null, isHeld = () => false }) {
  // Green "you hold this" dot — the same held-language as the Mirror, on the mirror book.
  const HeldDot = ({ sym }) => (isHeld(sym)
    ? <span title="In your portfolio" aria-label="You hold this" className="text-positive text-[0.6rem] mr-1.5 align-middle">●</span>
    : null);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(String(book?.capital ?? 100000));
  const [saving, setSaving] = useState(false);

  if (!book) return null;
  const isMax = book.tier === 'maximizer';
  const usd0 = (v) => v == null ? '—' : `$${Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
  // Shares are the convenience conversion of the (exact) dollar target — most people place
  // whole-share orders and fractional 2-decimals reads as false precision. Round to whole;
  // the "<1" guard flags names where the account is too small to hold a full share cleanly.
  const sh = (v) => {
    if (v == null) return '—';
    const n = Number(v);
    if (n > 0 && n < 1) return '<1';
    return Math.round(n).toLocaleString();
  };

  const save = async () => {
    const val = Number(String(draft).replace(/[^0-9.]/g, ''));
    if (!(val >= 100 && val <= 10000000)) { setEditing(false); return; }
    setSaving(true);
    try { await onSetCapital(val); } finally { setSaving(false); setEditing(false); }
  };

  return (
    <div className="border border-rule rounded bg-paper-card mb-6">
      {/* Header */}
      <div className="px-4 sm:px-5 py-4 border-b border-rule flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="font-display text-[1.2rem] font-medium text-ink tracking-tight flex items-center gap-2" style={{ fontVariationSettings: '"opsz" 48' }}>
            {isMax && <span className="text-claret text-[0.7rem]">◆</span>}
            Your {isMax ? 'Maximizer' : 'Preserver'} Book
          </h2>
          <p className="font-display italic text-[0.82rem] text-ink-mute mt-0.5" style={{ fontVariationSettings: '"opsz" 24' }}>
            Auto-mirrored to the model book — no manual entry. {isMax ? 'Breakouts, held 29 trading days.' : '30% trailing stop, let winners run.'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {book.new_today > 0 && (
            <span className="font-mono text-[0.62rem] uppercase tracking-[0.14em] bg-claret text-paper px-2 py-0.5 rounded">
              {book.new_today} new today
            </span>
          )}
          {/* Regime chip removed from the book header — it lives in the top regime bar, and the
              extra line made the two book headers different heights (market-read / capital rows
              no longer aligned in the side-by-side). */}
        </div>
      </div>

      {/* Market read — this book's own view (Preserver = measured regime read; Maximizer =
          breakout-posture briefing). Shown under the header in the two-book side-by-side. */}
      {marketNote && (
        /* data-market-read: the parent (Dashboard) MEASURES both books' reads and pins them to
           the taller one so the Your Capital ribbons below line up pixel-perfect — min-height
           can't guarantee it when the two reads differ in length. md+ only; mobile stacks. */
        <div data-market-read className="px-4 sm:px-5 py-2.5 border-b border-rule bg-paper-deep/40">
          <span className="font-body text-[0.56rem] font-medium tracking-[0.18em] uppercase text-ink-mute">Market read</span>
          <p className="font-display italic text-[0.82rem] text-ink-mute mt-0.5 leading-snug" style={{ fontVariationSettings: '"opsz" 24' }}>{marketNote}</p>
        </div>
      )}

      {/* Today's Actions — the "sync your broker" ribbon (Maximizer). */}
      {actions && ((actions.buys || []).length > 0 || (actions.sells || []).length > 0) && (
        <div className="px-4 sm:px-5 py-2.5 border-b border-rule bg-paper-deep flex flex-wrap items-center gap-x-4 gap-y-1 text-[0.82rem]">
          <span className="font-body text-[0.6rem] font-medium tracking-[0.18em] uppercase text-ink-mute">Today's actions</span>
          {(actions.buys || []).length > 0 && (
            <span className="text-positive font-mono">+ Enter {actions.buys.map(b => b.symbol).join(', ')}</span>
          )}
          {(actions.sells || []).length > 0 && (
            <span className="text-claret font-mono">Sell {actions.sells.map(s => `${s.symbol} (day 29)`).join(', ')}</span>
          )}
          {(actions.buys || []).length === 0 && (actions.sells || []).length === 0 && (
            <span className="text-ink-mute italic">No entries or exits today.</span>
          )}
        </div>
      )}

      {/* Capital + summary */}
      <div className="px-4 sm:px-5 py-4 grid grid-cols-2 sm:grid-cols-4 gap-4 border-b border-rule">
        <div>
          <div className="text-[0.6rem] uppercase tracking-[0.16em] text-ink-mute mb-1">Your capital</div>
          {hideCapitalEditor ? (
            /* Shared-capital mode (two books side-by-side): show the value, edit lives on the
               other book so one control drives both. */
            <div className="font-mono text-[1.15rem] text-ink">{usd0(book.capital)}</div>
          ) : editing ? (
            <div className="flex items-center gap-1">
              <input
                autoFocus value={draft} onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && save()}
                className="w-24 border border-ink rounded px-2 py-1 font-mono text-[0.95rem]"
              />
              <button onClick={save} disabled={saving} className="text-[0.7rem] uppercase tracking-wide bg-ink text-paper px-2 py-1 rounded">{saving ? '…' : 'Set'}</button>
            </div>
          ) : (
            <button onClick={() => { setDraft(String(book.capital)); setEditing(true); }} className="font-mono text-[1.15rem] text-ink hover:text-claret transition-colors">
              {usd0(book.capital)} <span className="text-[0.6rem] text-ink-mute">edit</span>
            </button>
          )}
        </div>
        <div>
          <div className="text-[0.6rem] uppercase tracking-[0.16em] text-ink-mute mb-1">Invested</div>
          <div className="font-mono text-[1.15rem] text-ink">{usd0(book.invested_value)}</div>
          <div className="font-mono text-[0.6rem] text-ink-mute">{book.invested_pct}% of book</div>
        </div>
        <div>
          <div className="text-[0.6rem] uppercase tracking-[0.16em] text-ink-mute mb-1">Cash</div>
          <div className="font-mono text-[1.15rem] text-ink">{usd0(book.cash_value)}</div>
          <div className="font-mono text-[0.6rem] text-ink-mute">{book.cash_pct}%</div>
        </div>
        <div>
          <div className="text-[0.6rem] uppercase tracking-[0.16em] text-ink-mute mb-1">Holdings</div>
          <div className="font-mono text-[1.15rem] text-ink">{book.holdings?.length || 0}</div>
          <div className="font-mono text-[0.6rem] text-ink-mute">names</div>
        </div>
      </div>

      {/* Vol-Target exposure gauge (Maximizer only) — the Barroso vol-brake. Sits AFTER the
          capital row so it lines up with the Preserver book's capital row in the side-by-side. */}
      {book.vol_scale != null && (
        <div className="px-4 sm:px-5 py-3 border-b border-rule">
          <div className="flex items-center justify-between mb-1">
            <span className="font-body text-[0.6rem] font-medium tracking-[0.18em] uppercase text-ink-mute">Vol-target exposure</span>
            <span className="font-mono text-[0.82rem] text-ink">{Math.round(book.vol_scale * 100)}%{book.vol_scale >= 0.999 ? ' · full' : ' · trimming risk'}</span>
          </div>
          <div className="h-2 bg-paper-deep rounded overflow-hidden">
            <div className="h-full bg-claret" style={{ width: `${Math.min(100, Math.round(book.vol_scale * 100))}%` }} />
          </div>
          <div className="mt-1.5 font-display italic text-[0.72rem] text-ink-light" style={{ fontVariationSettings: '"opsz" 24' }}>
            Auto-adjusts to keep risk steady — 100% is full exposure; it dials back (more cash, automatically) when breakouts turn volatile.
          </div>
        </div>
      )}

      {/* Holdings — Maximizer uses the compact table + 29-day hold-clock. Preserver uses the
          MOBILE-FIRST gauge cards standalone, but in `compact` mode (side-by-side two-book view)
          it renders the SAME table with a cushion-to-stop bar in the Exit column, so the two
          books line up row-for-row. No horizontal scroll on a phone — 76% of traffic is mobile. */}
      {(isMax || compact) ? (
        <div className="overflow-x-auto">
          <table className="w-full" style={{ fontFeatureSettings: '"tnum"' }}>
            <thead>
              <tr className="text-[0.58rem] uppercase tracking-[0.16em] text-ink-mute border-b border-rule">
                <th className="text-left py-2 px-3 sm:px-5">Symbol</th>
                <th className="text-right py-2 px-3 hidden sm:table-cell">Weight</th>
                <th className="text-right py-2 px-3">Price</th>
                <th className="text-right py-2 px-3">Your shares</th>
                <th className="text-right py-2 px-3">Your value</th>
                <th className="text-left py-2 px-3">Exit</th>
                <th className="text-right py-2 px-3 hidden sm:table-cell">P&L</th>
              </tr>
            </thead>
            <tbody>
              {(book.holdings || []).map((h) => (
                <tr
                  key={h.symbol}
                  onClick={() => onRowClick && onRowClick(h)}
                  className={`border-b border-rule/50 ${onRowClick ? 'cursor-pointer hover:bg-paper-deep transition-colors' : ''}`}
                >
                  <td className="py-2.5 px-3 sm:px-5">
                    <HeldDot sym={h.symbol} />
                    <span className="font-display text-[1rem] font-medium text-ink" style={{ fontVariationSettings: '"opsz" 32' }}>{h.symbol}</span>
                    {h.is_new && (
                      <span className="font-mono text-[0.55rem] uppercase tracking-[0.14em] text-claret border border-claret/40 px-1 py-0.5 ml-2 align-middle">New</span>
                    )}
                  </td>
                  <td className="py-2.5 px-3 text-right font-mono text-[0.82rem] text-ink-mute hidden sm:table-cell">{h.weight_pct}%</td>
                  <td className="py-2.5 px-3 text-right font-mono text-[0.82rem]">${h.price?.toFixed(2)}</td>
                  <td className="py-2.5 px-3 text-right font-mono text-[0.9rem] text-ink">{sh(h.implied_shares)}</td>
                  <td className="py-2.5 px-3 text-right font-mono text-[0.9rem] text-ink">{usd0(h.implied_value)}</td>
                  <td className="py-2.5 px-3 font-mono text-[0.72rem] whitespace-nowrap">
                    {isMax ? (
                      <div className="min-w-[92px] text-claret">
                        <div className="mb-0.5">day {h.days_held}/{h.hold_days} · ~{h.days_left}d</div>
                        {/* Hold-clock: progress through the 29-day time-stop; near-exit turns solid claret */}
                        <div className="h-1 bg-paper-deep rounded overflow-hidden">
                          <div className={`h-full ${h.days_left <= 5 ? 'bg-claret' : 'bg-claret/50'}`}
                               style={{ width: `${Math.min(100, Math.round((h.days_held / (h.hold_days || 29)) * 100))}%` }} />
                        </div>
                      </div>
                    ) : (() => {
                      // Preserver compact: a thin cushion gauge — the standalone gauge distilled
                      // to one row. Band = stop (left edge) → high-water mark (right edge); green
                      // fill = cushion up to now; thin tick = entry; solid marker = now. Thin
                      // cushion (near the stop) turns claret.
                      const lo = Number(h.trailing_stop_level) || 0;
                      const hi = Math.max(Number(h.high_water_mark) || 0, lo + 0.01);
                      const now = Number(h.price) || lo;
                      const entry = Number(h.entry_price) || lo;
                      const clampPct = (v) => Math.max(0, Math.min(100, ((v - lo) / (hi - lo)) * 100));
                      const nowPct = clampPct(now);
                      const entryPct = clampPct(entry);
                      const cushion = now > 0 ? Math.max(0, (now - lo) / now * 100) : 0;
                      const thin = cushion <= 8;
                      return (
                        <div className="min-w-[108px]">
                          <div className={`mb-1 ${thin ? 'text-claret' : 'text-ink-mute'}`}>{Math.round(cushion)}% to stop</div>
                          <div className="relative h-2 bg-paper-deep rounded">
                            {/* cushion fill: stop → now */}
                            <div className={`absolute inset-y-0 left-0 rounded-l ${thin ? 'bg-claret/40' : 'bg-positive/35'}`} style={{ width: `${nowPct}%` }} />
                            {/* entry tick */}
                            <div className="absolute top-1/2 -translate-y-1/2 h-[11px] w-px bg-ink-mute/70" style={{ left: `${entryPct}%` }} title={`Entry $${entry.toFixed(2)}`} />
                            {/* now marker */}
                            <div className={`absolute top-1/2 -translate-y-1/2 h-3.5 w-[2px] rounded ${thin ? 'bg-claret' : 'bg-ink'}`} style={{ left: `calc(${nowPct}% - 1px)` }} title={`Now $${now.toFixed(2)}`} />
                          </div>
                          <div className="flex justify-between mt-0.5 text-[0.52rem] leading-none text-ink-light">
                            <span>stop ${Math.round(lo)}</span><span>high ${Math.round(hi)}</span>
                          </div>
                        </div>
                      );
                    })()}
                  </td>
                  <td className={`py-2.5 px-3 text-right font-mono text-[0.82rem] hidden sm:table-cell ${h.pnl_pct >= 0 ? 'text-positive' : 'text-negative'}`}>
                    {h.pnl_pct >= 0 ? '+' : ''}{h.pnl_pct}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div>
          {(book.holdings || []).length === 0 ? (
            <div className="px-4 sm:px-5 py-6 text-center font-display italic text-ink-mute text-[0.9rem]" style={{ fontVariationSettings: '"opsz" 24' }}>
              The book is in cash right now — no positions held.
            </div>
          ) : (book.holdings || []).map((h) => (
            <div
              key={h.symbol}
              onClick={() => onRowClick && onRowClick(h)}
              className={`px-4 sm:px-5 py-4 border-b border-rule/60 ${onRowClick ? 'cursor-pointer hover:bg-paper-deep transition-colors' : ''}`}
            >
              <div className="flex items-baseline justify-between gap-2 mb-2.5">
                <div className="flex items-baseline gap-2 min-w-0">
                  <HeldDot sym={h.symbol} />
                  <span className="font-display text-[1.1rem] font-medium text-ink" style={{ fontVariationSettings: '"opsz" 32' }}>{h.symbol}</span>
                  {h.is_new && <span className="font-mono text-[0.55rem] uppercase tracking-[0.14em] text-claret border border-claret/40 px-1 py-0.5">New</span>}
                  <span className="font-mono text-[0.68rem] text-ink-mute whitespace-nowrap">{h.weight_pct}% of book</span>
                </div>
                <span className={`font-mono text-[0.95rem] whitespace-nowrap ${h.pnl_pct >= 0 ? 'text-positive' : 'text-negative'}`}>{h.pnl_pct >= 0 ? '+' : ''}{h.pnl_pct}%</span>
              </div>
              <HoldingGauge entry={h.entry_price} now={h.price} hwm={h.high_water_mark} stop={h.trailing_stop_level} />
              <div className="flex items-center justify-between gap-2 mt-2.5 font-mono text-[0.7rem] text-ink-mute">
                <span>entry ${h.entry_price?.toFixed(2)} → now ${h.price?.toFixed(2)}</span>
                <span className="text-ink whitespace-nowrap">{sh(h.implied_shares)} sh · {usd0(h.implied_value)}</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Breakout Radar — names approaching a 50-day-high breakout (what the book is about to
          enter). Replaces the watchlist for Maximizer. */}
      {(radar || []).length > 0 && (
        <div className="border-t border-rule">
          <div className="px-4 sm:px-5 py-2.5 flex items-baseline justify-between">
            <span className="font-display text-[0.95rem] font-medium tracking-tight text-ink" style={{ fontVariationSettings: '"opsz" 32' }}>Breakout Radar</span>
            <span className="font-display italic text-[0.8rem] text-claret" style={{ fontVariationSettings: '"opsz" 24' }}>approaching trigger</span>
          </div>
          <div className="flex flex-wrap gap-2 px-4 sm:px-5 pb-3">
            {radar.map((r) => (
              <div
                key={r.symbol}
                onClick={() => onRowClick && onRowClick({ symbol: r.symbol, price: r.price, source: 'breakout' })}
                className="border border-rule rounded px-3 py-2 bg-white cursor-pointer hover:bg-paper-deep transition-colors"
              >
                <div className="font-display text-[0.92rem] font-medium text-ink" style={{ fontVariationSettings: '"opsz" 32' }}>{r.symbol}</div>
                <div className="font-mono text-[0.62rem] text-ink-mute">{r.pct_below_50d_high}% below high · vol {r.vol_ratio}x</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="px-4 sm:px-5 py-3 border-t border-rule flex flex-wrap items-center justify-between gap-2 text-[0.7rem] text-ink-mute">
        <span>As of {book.as_of || '—'} · mirror the book to match its results — partial-following diverges.</span>
        <span className="font-display italic" style={{ fontVariationSettings: '"opsz" 24' }}>Signals only — execute via your broker</span>
      </div>
    </div>
  );
}
