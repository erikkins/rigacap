import React, { useState, useEffect, useCallback } from 'react';
import { RefreshCw, Mail, Download } from 'lucide-react';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Newsletter signups = the upsell pool (cold traffic that took the soft CTA
// instead of the trial). "Leads" = newsletter subscribers who aren't app users
// yet. Surfaced so we can target an exclusive email at the cohort. (Jun 23 2026)
export default function LeadsTab({ fetchWithAuth }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const res = await fetchWithAuth(`${API_URL}/api/admin/newsletter-signups`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setData(await res.json());
    } catch (e) {
      setError(e.message || 'Failed to load');
    } finally {
      setLoading(false);
    }
  }, [fetchWithAuth]);

  useEffect(() => { load(); }, [load]);

  const copyEmails = () => {
    if (!data?.items) return;
    const emails = data.items.filter(i => !i.unsubscribed_at).map(i => i.email).join(', ');
    navigator.clipboard?.writeText(emails);
  };

  if (loading) return <div className="p-8 text-center text-ink-mute"><RefreshCw className="w-5 h-5 animate-spin inline" /> Loading leads…</div>;
  if (error) return <div className="p-8 text-center text-claret">Error: {error} <button onClick={load} className="underline ml-2">retry</button></div>;
  if (!data) return null;

  const fmt = (s) => s ? new Date(s).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '—';

  return (
    <div className="space-y-5">
      {/* Summary */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-px bg-rule rounded overflow-hidden">
        {[
          ['Total signups', data.count],
          ['Leads (not yet users)', data.lead_count],
          ['Reports', Object.keys(data.by_report || {}).length],
          ['Sources', Object.keys(data.by_source || {}).length],
        ].map(([label, val]) => (
          <div key={label} className="bg-white p-4 text-center">
            <div className="text-2xl font-semibold text-ink">{val}</div>
            <div className="text-xs uppercase tracking-wide text-ink-mute mt-1">{label}</div>
          </div>
        ))}
      </div>

      <div className="flex items-center justify-between">
        <div className="text-sm text-ink-mute">
          By report: {Object.entries(data.by_report || {}).map(([k, v]) => `${k} (${v})`).join(' · ') || '—'}
        </div>
        <div className="flex gap-2">
          <button onClick={copyEmails} className="flex items-center gap-1.5 px-3 py-1.5 text-sm border border-rule-dark rounded hover:bg-paper-card">
            <Mail className="w-4 h-4" /> Copy active emails
          </button>
          <button onClick={load} className="flex items-center gap-1.5 px-3 py-1.5 text-sm border border-rule-dark rounded hover:bg-paper-card">
            <RefreshCw className="w-4 h-4" /> Refresh
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto border border-rule rounded">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-paper-card border-b border-rule text-left text-xs uppercase tracking-wide text-ink-mute">
              <th className="px-3 py-2.5">Email</th>
              <th className="px-3 py-2.5">Report</th>
              <th className="px-3 py-2.5">Source</th>
              <th className="px-3 py-2.5">Signed up</th>
              <th className="px-3 py-2.5">Status</th>
            </tr>
          </thead>
          <tbody>
            {data.items.length === 0 && (
              <tr><td colSpan={5} className="px-3 py-8 text-center text-ink-mute">No newsletter signups yet.</td></tr>
            )}
            {data.items.map((i, idx) => (
              <tr key={`${i.email}-${i.report_type}-${idx}`} className="border-b border-rule hover:bg-paper-card">
                <td className="px-3 py-2.5 font-medium text-ink">{i.email}</td>
                <td className="px-3 py-2.5 text-ink-mute">{i.report_type}</td>
                <td className="px-3 py-2.5 text-ink-mute">{i.source || '—'}</td>
                <td className="px-3 py-2.5 text-ink-mute">{fmt(i.subscribed_at)}</td>
                <td className="px-3 py-2.5">
                  {i.unsubscribed_at ? (
                    <span className="px-2 py-0.5 text-xs rounded bg-gray-100 text-gray-600">Unsubscribed</span>
                  ) : i.is_app_user ? (
                    <span className="px-2 py-0.5 text-xs rounded bg-blue-100 text-blue-800">App user</span>
                  ) : (
                    <span className="px-2 py-0.5 text-xs rounded bg-amber-100 text-amber-800">Lead</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
