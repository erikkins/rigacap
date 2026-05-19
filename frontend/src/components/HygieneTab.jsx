import React, { useState, useEffect, useCallback } from 'react';
import { CheckCircle, AlertCircle, RefreshCw, ExternalLink } from 'lucide-react';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

function ActionPill({ action }) {
  const map = {
    delist: { bg: 'bg-claret/10', text: 'text-claret', label: 'Delist' },
    rename: { bg: 'bg-amber-100', text: 'text-amber-800', label: 'Rename' },
    migrate: { bg: 'bg-blue-100', text: 'text-blue-800', label: 'Migrate (ticker reuse)' },
    restore: { bg: 'bg-emerald-100', text: 'text-emerald-800', label: 'Restore' },
    needs_human: { bg: 'bg-gray-100', text: 'text-gray-700', label: 'Needs review' },
  };
  const s = map[action] || map.needs_human;
  return (
    <span className={`inline-block px-2 py-0.5 text-[0.7rem] font-medium uppercase tracking-wide ${s.bg} ${s.text} rounded`}>
      {s.label}
    </span>
  );
}

function ItemRow({ item, selected, onToggle, onApproveOne, onRename }) {
  const isRename = item.recommended_action === 'rename';
  return (
    <tr className="border-b border-rule hover:bg-paper-card">
      <td className="px-3 py-2.5 align-top">
        <input
          type="checkbox"
          checked={selected}
          onChange={() => onToggle(item.symbol)}
          disabled={isRename}
          title={isRename ? 'Rename requires a new ticker — handle individually' : ''}
        />
      </td>
      <td className="px-3 py-2.5 align-top">
        <a
          href={`/admin/symbol/${item.symbol}/triage`}
          target="_blank"
          rel="noreferrer"
          className="font-display font-medium text-ink hover:text-claret inline-flex items-center gap-1"
        >
          {item.symbol}
          <ExternalLink size={11} className="opacity-50" />
        </a>
        {item.in_open_position && (
          <span className="ml-2 text-[0.7rem] font-medium text-amber-700 uppercase">Held</span>
        )}
      </td>
      <td className="px-3 py-2.5 align-top">
        <ActionPill action={item.recommended_action} />
      </td>
      <td className="px-3 py-2.5 align-top font-mono text-sm text-ink-mute">
        {item.days_missing != null ? `${item.days_missing}d` : '—'}
      </td>
      <td className="px-3 py-2.5 align-top font-mono text-xs text-ink-mute">
        {item.ai_verdict || '—'}
      </td>
      <td className="px-3 py-2.5 align-top text-xs text-ink-mute leading-snug">
        {item.reasoning}
      </td>
      <td className="px-3 py-2.5 align-top text-right">
        {isRename ? (
          <button
            onClick={() => onRename(item)}
            className="px-3 py-1 text-xs font-medium bg-amber-600 text-white rounded hover:bg-amber-700"
          >
            Set new ticker…
          </button>
        ) : (
          <button
            onClick={() => onApproveOne(item)}
            className="px-3 py-1 text-xs font-medium bg-ink text-paper rounded hover:bg-claret"
          >
            Apply
          </button>
        )}
      </td>
    </tr>
  );
}

function QueueTable({ title, items, onApproveBatch, onRefresh, busy }) {
  const [selected, setSelected] = useState(new Set());

  useEffect(() => {
    // Clear selection when items change (e.g., after a successful batch)
    setSelected(new Set());
  }, [items]);

  const toggle = (sym) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(sym)) next.delete(sym);
      else next.add(sym);
      return next;
    });
  };

  const selectAll = () => {
    const eligible = items.filter((i) => i.recommended_action !== 'rename').map((i) => i.symbol);
    setSelected(new Set(eligible));
  };

  const clearAll = () => setSelected(new Set());

  const applyOne = async (item) => {
    await onApproveBatch([{ symbol: item.symbol, action: item.recommended_action }]);
  };

  const applySelected = async () => {
    const payload = items
      .filter((i) => selected.has(i.symbol) && i.recommended_action !== 'rename')
      .map((i) => ({ symbol: i.symbol, action: i.recommended_action }));
    if (payload.length === 0) return;
    await onApproveBatch(payload);
  };

  const promptRename = async (item) => {
    const newTicker = window.prompt(`Rename ${item.symbol} to which ticker?`);
    if (!newTicker) return;
    await onApproveBatch([{ symbol: item.symbol, action: 'rename', new_ticker: newTicker }]);
  };

  if (!items || items.length === 0) {
    return (
      <div className="bg-paper-card border border-rule rounded p-4 text-sm text-ink-mute">
        {title}: nothing pending.
      </div>
    );
  }

  return (
    <div className="bg-paper-card border border-rule rounded">
      <div className="flex items-center justify-between px-4 py-3 border-b border-rule">
        <h3 className="font-display text-base font-medium">
          {title} <span className="text-ink-mute font-normal">({items.length})</span>
        </h3>
        <div className="flex items-center gap-2">
          <button onClick={selectAll} className="text-xs text-claret hover:underline">Select all</button>
          <button onClick={clearAll} className="text-xs text-ink-mute hover:underline">Clear</button>
          <button
            onClick={applySelected}
            disabled={busy || selected.size === 0}
            className="px-3 py-1.5 text-xs font-medium bg-claret text-white rounded hover:bg-claret-dark disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {busy ? 'Applying…' : `Apply selected (${selected.size})`}
          </button>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-paper-deep text-ink-mute text-[0.7rem] uppercase tracking-wide">
            <tr>
              <th className="px-3 py-2 text-left w-8"></th>
              <th className="px-3 py-2 text-left">Symbol</th>
              <th className="px-3 py-2 text-left">Recommended</th>
              <th className="px-3 py-2 text-left">Missing</th>
              <th className="px-3 py-2 text-left">AI</th>
              <th className="px-3 py-2 text-left">Reasoning</th>
              <th className="px-3 py-2 text-right"></th>
            </tr>
          </thead>
          <tbody>
            {items.map((it) => (
              <ItemRow
                key={`${it.category}:${it.symbol}`}
                item={it}
                selected={selected.has(it.symbol)}
                onToggle={toggle}
                onApproveOne={applyOne}
                onRename={promptRename}
              />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function HygieneTab({ fetchWithAuth }) {
  const [queue, setQueue] = useState(null);
  const [corpActions, setCorpActions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [toast, setToast] = useState(null);

  const flashToast = (msg) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3500);
  };

  const fetchQueue = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const [qRes, caRes] = await Promise.all([
        fetchWithAuth(`${API_URL}/api/admin/hygiene/queue`),
        fetchWithAuth(`${API_URL}/api/admin/hygiene/corp-actions?days=7`),
      ]);
      if (!qRes.ok) throw new Error(`queue fetch ${qRes.status}`);
      if (!caRes.ok) throw new Error(`corp-actions fetch ${caRes.status}`);
      setQueue(await qRes.json());
      const ca = await caRes.json();
      setCorpActions(ca.events || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [fetchWithAuth]);

  useEffect(() => { fetchQueue(); }, [fetchQueue]);

  const approveBatch = async (items) => {
    setBusy(true);
    try {
      const res = await fetchWithAuth(`${API_URL}/api/admin/hygiene/approve-batch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ items }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || `approve failed (${res.status})`);
      flashToast(`Applied ${data.ok_count}/${data.total}`);
      await fetchQueue();
    } catch (e) {
      flashToast(`Error: ${e.message}`);
    } finally {
      setBusy(false);
    }
  };

  const approveAllRecommend = async () => {
    if (!window.confirm('Apply every recommendation in the queue (excluding renames)?')) return;
    setBusy(true);
    try {
      const res = await fetchWithAuth(`${API_URL}/api/admin/hygiene/approve-all-recommend`, {
        method: 'POST',
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || `approve-all failed (${res.status})`);
      flashToast(`Applied ${data.ok_count}/${data.total}. Skipped ${data.skipped?.length || 0} renames.`);
      await fetchQueue();
    } catch (e) {
      flashToast(`Error: ${e.message}`);
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12 text-ink-mute">
        <RefreshCw className="animate-spin mr-2" size={18} /> Loading hygiene queue…
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded p-4 text-red-800">
        <p className="font-medium">Failed to load hygiene queue</p>
        <p className="text-sm mt-1">{error}</p>
        <button onClick={fetchQueue} className="mt-2 text-sm underline">Retry</button>
      </div>
    );
  }

  const summary = queue?.summary || {};
  const recommend = queue?.recommend || [];
  const exceptions = queue?.exceptions || [];
  const recentAuto = queue?.recent_auto || [];

  return (
    <div className="space-y-6">
      {/* Toast */}
      {toast && (
        <div className="fixed top-20 right-4 z-50 bg-ink text-paper px-4 py-2 rounded shadow-lg text-sm">
          {toast}
        </div>
      )}

      {/* Summary panel */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="bg-paper-card border border-rule rounded p-4">
          <p className="text-xs uppercase tracking-wide text-ink-mute">Auto-resolved (24h)</p>
          <p className="font-display text-2xl font-medium text-ink mt-1">{summary.auto_24h ?? 0}</p>
        </div>
        <div className="bg-paper-card border border-rule rounded p-4">
          <p className="text-xs uppercase tracking-wide text-ink-mute">One-click recommendations</p>
          <p className="font-display text-2xl font-medium text-claret mt-1">{summary.recommend_count ?? 0}</p>
        </div>
        <div className="bg-paper-card border border-rule rounded p-4">
          <p className="text-xs uppercase tracking-wide text-ink-mute">Exceptions</p>
          <p className="font-display text-2xl font-medium text-amber-700 mt-1">{summary.exception_count ?? 0}</p>
        </div>
        <div className="bg-paper-card border border-rule rounded p-4">
          <p className="text-xs uppercase tracking-wide text-ink-mute">Ticker-reuse pending</p>
          <p className="font-display text-2xl font-medium text-blue-700 mt-1">{summary.reuse_count ?? 0}</p>
        </div>
      </div>

      {/* Top-bar actions */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-ink-mute">
          Items the system pre-classified for you. Apply directly — no per-symbol drill-down needed.
        </p>
        <div className="flex items-center gap-2">
          <button
            onClick={fetchQueue}
            disabled={busy}
            className="px-3 py-1.5 text-sm bg-paper border border-rule rounded hover:bg-paper-card flex items-center gap-1.5"
          >
            <RefreshCw size={14} /> Refresh
          </button>
          {recommend.length > 0 && (
            <button
              onClick={approveAllRecommend}
              disabled={busy}
              className="px-4 py-1.5 text-sm font-medium bg-claret text-white rounded hover:bg-claret-dark disabled:opacity-50"
            >
              {busy ? 'Working…' : `Approve all ${recommend.length} recommendations`}
            </button>
          )}
        </div>
      </div>

      {/* Recommend queue */}
      <QueueTable
        title="Recommended actions"
        items={recommend}
        onApproveBatch={approveBatch}
        busy={busy}
        onRefresh={fetchQueue}
      />

      {/* Exceptions queue */}
      <QueueTable
        title="Exceptions — needs your eyes"
        items={exceptions}
        onApproveBatch={approveBatch}
        busy={busy}
        onRefresh={fetchQueue}
      />

      {/* Recent auto-actions log */}
      <div className="bg-paper-card border border-rule rounded">
        <div className="px-4 py-3 border-b border-rule flex items-center gap-2">
          <CheckCircle size={16} className="text-positive" />
          <h3 className="font-display text-base font-medium">Auto-resolved (last 24h)</h3>
          <span className="text-xs text-ink-mute">({recentAuto.length})</span>
        </div>
        {recentAuto.length === 0 ? (
          <div className="px-4 py-3 text-sm text-ink-mute">Nothing auto-actioned in the last day.</div>
        ) : (
          <div className="max-h-64 overflow-y-auto">
            <table className="w-full text-sm">
              <tbody>
                {recentAuto.map((ev, idx) => (
                  <tr key={`${ev.symbol}-${ev.when}-${idx}`} className="border-b border-rule last:border-0">
                    <td className="px-3 py-1.5 font-mono">{ev.symbol}</td>
                    <td className="px-3 py-1.5 text-xs text-ink-mute">{ev.action}</td>
                    <td className="px-3 py-1.5 text-xs text-ink-mute text-right">
                      {ev.when ? new Date(ev.when).toLocaleString() : ''}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Corp actions log */}
      <div className="bg-paper-card border border-rule rounded">
        <div className="px-4 py-3 border-b border-rule flex items-center gap-2">
          <AlertCircle size={16} className="text-ink-mute" />
          <h3 className="font-display text-base font-medium">Corporate actions (last 7 days)</h3>
          <span className="text-xs text-ink-mute">({corpActions.length})</span>
        </div>
        {corpActions.length === 0 ? (
          <div className="px-4 py-3 text-sm text-ink-mute">No corp-action events in the last week.</div>
        ) : (
          <div className="max-h-64 overflow-y-auto">
            <table className="w-full text-sm">
              <thead className="bg-paper-deep text-ink-mute text-[0.7rem] uppercase tracking-wide sticky top-0">
                <tr>
                  <th className="px-3 py-1.5 text-left">Symbol</th>
                  <th className="px-3 py-1.5 text-left">Event</th>
                  <th className="px-3 py-1.5 text-left">Date</th>
                  <th className="px-3 py-1.5 text-right">Detected</th>
                </tr>
              </thead>
              <tbody>
                {corpActions.map((ev, idx) => (
                  <tr key={`${ev.symbol}-${ev.event_type}-${idx}`} className="border-b border-rule last:border-0">
                    <td className="px-3 py-1.5 font-mono">{ev.symbol}</td>
                    <td className="px-3 py-1.5 text-xs">{ev.event_type}</td>
                    <td className="px-3 py-1.5 text-xs text-ink-mute">{ev.event_date || '—'}</td>
                    <td className="px-3 py-1.5 text-xs text-ink-mute text-right">
                      {ev.detected_at ? new Date(ev.detected_at).toLocaleDateString() : ''}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
