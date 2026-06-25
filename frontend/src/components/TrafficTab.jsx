import React, { useState, useEffect } from 'react';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Cookieless pageview report — reads /api/admin/pageviews/summary. Every visitor
// (consent or not) → path, source, paid attribution, mobile share, daily trend.
export default function TrafficTab({ fetchWithAuth }) {
  const [days, setDays] = useState(7);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true); setErr(null);
      try {
        const res = await fetchWithAuth(`${API_URL}/api/admin/pageviews/summary?days=${days}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();
        if (!cancelled) setData(json);
      } catch (e) {
        if (!cancelled) setErr(String(e.message || e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [days, fetchWithAuth]);

  const pct = (n) => (data && data.total ? `${Math.round((n / data.total) * 100)}%` : '—');

  const Stat = ({ label, value, sub }) => (
    <div className="bg-white border border-gray-200 rounded-lg p-4">
      <div className="text-xs uppercase tracking-wide text-gray-500">{label}</div>
      <div className="text-2xl font-semibold text-gray-900 mt-1">{value}</div>
      {sub && <div className="text-xs text-gray-400 mt-0.5">{sub}</div>}
    </div>
  );

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Traffic — cookieless</h2>
          <p className="text-sm text-gray-500">Every visitor, consent or not: path, source &amp; paid (gclid) attribution.</p>
        </div>
        <div className="flex gap-1">
          {[1, 7, 30].map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={`px-3 py-1.5 text-sm rounded border ${days === d ? 'bg-gray-900 text-white border-gray-900' : 'border-gray-300 text-gray-600 hover:border-gray-400'}`}
            >
              {d === 1 ? '24h' : `${d}d`}
            </button>
          ))}
        </div>
      </div>

      {loading && <div className="text-sm text-gray-500">Loading…</div>}
      {err && <div className="text-sm text-red-600">Error: {err}</div>}

      {data && (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <Stat label="Total pageviews" value={data.total} />
            <Stat label="Paid clicks (gclid)" value={data.paid_clicks} sub={`${pct(data.paid_clicks)} of views`} />
            <Stat label="Mobile" value={data.mobile} sub={`${pct(data.mobile)} of views`} />
            <Stat label="Window" value={data.days === 1 ? '24h' : `${data.days}d`} />
          </div>

          <div className="grid md:grid-cols-2 gap-5">
            <div className="bg-white border border-gray-200 rounded-lg p-4">
              <div className="text-sm font-medium text-gray-900 mb-2">Top pages (land → drop)</div>
              <table className="w-full text-sm">
                <tbody>
                  {data.by_path.map((r) => (
                    <tr key={r.path} className="border-t border-gray-100">
                      <td className="py-1.5 text-gray-700 truncate max-w-[240px]">{r.path}</td>
                      <td className="py-1.5 text-right font-mono text-gray-900">{r.count}</td>
                    </tr>
                  ))}
                  {!data.by_path.length && <tr><td className="py-2 text-gray-400">No hits yet</td></tr>}
                </tbody>
              </table>
            </div>
            <div className="bg-white border border-gray-200 rounded-lg p-4">
              <div className="text-sm font-medium text-gray-900 mb-2">By source</div>
              <table className="w-full text-sm">
                <tbody>
                  {data.by_source.map((r) => (
                    <tr key={r.source} className="border-t border-gray-100">
                      <td className="py-1.5 text-gray-700">{r.source}</td>
                      <td className="py-1.5 text-right font-mono text-gray-900">{r.count}</td>
                    </tr>
                  ))}
                  {!data.by_source.length && <tr><td className="py-2 text-gray-400">No hits yet</td></tr>}
                </tbody>
              </table>
            </div>
          </div>

          {data.by_day && data.by_day.length > 0 && (
            <div className="bg-white border border-gray-200 rounded-lg p-4">
              <div className="text-sm font-medium text-gray-900 mb-3">Daily</div>
              <div className="flex items-end gap-1 h-24">
                {(() => {
                  const max = Math.max(...data.by_day.map((x) => x.count), 1);
                  return data.by_day.map((r) => (
                    <div key={r.date} className="flex-1 flex flex-col items-center justify-end" title={`${r.date}: ${r.count}`}>
                      <div className="w-full bg-gray-800 rounded-t" style={{ height: `${Math.max(4, (r.count / max) * 80)}px` }} />
                      <div className="text-[9px] text-gray-400 mt-1">{r.date.slice(5)}</div>
                    </div>
                  ));
                })()}
              </div>
            </div>
          )}

          <p className="text-xs text-gray-400">
            Cookieless first-party beacon — no cookie, no stored IP, no consent banner required. Bots filtered by user-agent.
          </p>
        </>
      )}
    </div>
  );
}
