import React, { useState, useEffect, useMemo } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceArea, Area, ComposedChart,
} from 'recharts';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const REGIME_DARK_COLORS = {
  strong_bull: { bg: 'rgba(245, 241, 232, 0.5)', color: '#C9BFAC', name: 'Strong Bull' },
  weak_bull: { bg: 'rgba(237, 231, 216, 0.5)', color: '#C9BFAC', name: 'Weak Bull' },
  rotating_bull: { bg: 'rgba(221, 213, 199, 0.3)', color: '#8A8279', name: 'Rotating Bull' },
  range_bound: { bg: 'rgba(201, 191, 172, 0.2)', color: '#8A8279', name: 'Range-Bound' },
  weak_bear: { bg: 'rgba(138, 130, 121, 0.15)', color: '#5A544E', name: 'Weak Bear' },
  panic_crash: { bg: 'rgba(90, 84, 78, 0.12)', color: '#5A544E', name: 'Panic/Crash' },
  recovery: { bg: 'rgba(221, 213, 199, 0.3)', color: '#8A8279', name: 'Recovery' },
};

function formatCurrency(value) {
  if (value >= 1000000) return `$${(value / 1000000).toFixed(1)}M`;
  if (value >= 1000) return `$${(value / 1000).toFixed(0)}k`;
  return `$${value.toFixed(0)}`;
}

function formatDate(dateStr) {
  const d = new Date(dateStr + 'T00:00:00');
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  return `${months[d.getMonth()]} '${String(d.getFullYear()).slice(2)}`;
}

function CustomTooltip({ active, payload, compact }) {
  if (!active || !payload || !payload.length) return null;
  const data = payload[0]?.payload;
  if (!data) return null;

  const regime = data._regime;

  return (
    <div className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 shadow-xl text-xs">
      <div className="text-gray-400 mb-1">{data.date}</div>
      <div className="flex items-center gap-2 mb-0.5">
        <span className="w-2 h-2 rounded-full bg-blue-500 inline-block" />
        <span className="text-white font-medium">Average: {formatCurrency(data.equity)}</span>
      </div>
      {data.best_equity && !compact && (
        <div className="flex items-center gap-2 mb-0.5">
          <span className="w-2 h-2 rounded-full bg-blue-300 inline-block" />
          <span className="text-blue-300">Best: {formatCurrency(data.best_equity)}</span>
        </div>
      )}
      {data.worst_equity && !compact && (
        <div className="flex items-center gap-2 mb-0.5">
          <span className="w-2 h-2 rounded-full bg-blue-800 inline-block" />
          <span className="text-blue-400">Worst: {formatCurrency(data.worst_equity)}</span>
        </div>
      )}
      <div className="flex items-center gap-2 mb-0.5">
        <span className="w-2 h-2 rounded-full bg-amber-500 inline-block" />
        <span className="text-gray-300">SPY: {formatCurrency(data.spy_equity)}</span>
      </div>
      {data.n_sims && !compact && (
        <div className="text-gray-600 mt-1">{data.n_sims} start dates</div>
      )}
      {regime && !compact && (
        <div className="mt-1 flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-sm" style={{ backgroundColor: regime.color }} />
          <span style={{ color: regime.color }}>{regime.name}</span>
        </div>
      )}
    </div>
  );
}

export default function TrackRecordChart({ compact = false, apiUrl = null }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const url = apiUrl || `${API_BASE}/api/public/track-record`;

  useEffect(() => {
    fetch(url)
      .then(res => {
        if (!res.ok) throw new Error('Failed to load track record');
        return res.json();
      })
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [url]);

  const chartData = useMemo(() => {
    if (!data?.equity_curve) return [];
    const periods = data.regime_periods || [];
    const maxSims = Math.max(...data.equity_curve.map(p => p.n_sims || 1));
    const minRequired = Math.max(2, Math.floor(maxSims * 0.6));

    return data.equity_curve.filter(p => (p.n_sims || 1) >= minRequired).map(point => {
      let regime = null;
      for (const p of periods) {
        if (point.date >= p.start_date && point.date <= p.end_date) {
          const dark = REGIME_DARK_COLORS[p.regime_type];
          regime = { name: p.regime_name, color: dark?.color || p.color };
          break;
        }
      }
      return { ...point, _regime: regime };
    });
  }, [data]);

  const mappedRegimePeriods = useMemo(() => {
    if (!chartData.length || !data?.regime_periods?.length) return [];
    const chartDates = chartData.map(d => d.date);

    return data.regime_periods.map((period, idx) => {
      let startIdx = chartDates.findIndex(d => d >= period.start_date);
      if (startIdx === -1) startIdx = 0;

      let endIdx = chartDates.length - 1;
      for (let i = chartDates.length - 1; i >= 0; i--) {
        if (chartDates[i] <= period.end_date) { endIdx = i; break; }
      }

      const nextPeriod = data.regime_periods[idx + 1];
      if (nextPeriod && endIdx < chartDates.length - 1) {
        const nextStartIdx = chartDates.findIndex(d => d >= nextPeriod.start_date);
        if (nextStartIdx > endIdx) endIdx = nextStartIdx;
      }

      if (startIdx <= endIdx) {
        const dark = REGIME_DARK_COLORS[period.regime_type] || {};
        return {
          ...period,
          x1: chartDates[startIdx],
          x2: chartDates[endIdx],
          bg_color: dark.bg || period.bg_color,
          color: dark.color || period.color,
        };
      }
      return null;
    }).filter(Boolean);
  }, [chartData, data]);

  const uniqueRegimes = useMemo(() => {
    if (!data?.regime_periods) return [];
    const seen = new Map();
    for (const p of data.regime_periods) {
      if (!seen.has(p.regime_type)) {
        const dark = REGIME_DARK_COLORS[p.regime_type] || {};
        seen.set(p.regime_type, {
          type: p.regime_type,
          name: dark.name || p.regime_name,
          color: dark.color || p.color,
          bg: dark.bg || p.bg_color,
        });
      }
    }
    return [...seen.values()];
  }, [data]);

  const displayData = useMemo(() => {
    if (!compact || chartData.length < 100) return chartData;
    const step = Math.max(1, Math.floor(chartData.length / 80));
    const result = [];
    for (let i = 0; i < chartData.length; i += step) result.push(chartData[i]);
    if (result[result.length - 1] !== chartData[chartData.length - 1]) {
      result.push(chartData[chartData.length - 1]);
    }
    return result;
  }, [chartData, compact]);

  const hasBand = displayData.length > 0 && displayData[0].best_equity != null;
  const height = compact ? 200 : 350;

  if (loading) {
    return (
      <div className={`${compact ? '' : 'bg-gray-900 border border-gray-800 rounded-xl p-6'}`}>
        <div className="animate-pulse" style={{ height }}>
          <div className="h-full bg-gray-800 rounded-lg" />
        </div>
      </div>
    );
  }

  if (error || !chartData.length) {
    return null;
  }

  const tickInterval = compact ? Math.floor(displayData.length / 3) : Math.floor(displayData.length / 6);

  return (
    <div>
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart data={displayData} margin={{ top: 10, right: 10, left: compact ? 0 : 10, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#DDD5C7" vertical={false} />

          {/* Regime background bands */}
          {!compact && mappedRegimePeriods.map((period, i) => (
            <ReferenceArea
              key={`regime-${i}`}
              x1={period.x1}
              x2={period.x2}
              fill={period.bg_color}
              stroke={period.color}
              strokeOpacity={0.2}
              fillOpacity={0.8}
            />
          ))}

          <XAxis
            dataKey="date"
            stroke="#C9BFAC"
            tick={{ fill: '#8A8279', fontSize: compact ? 10 : 11, fontFamily: 'IBM Plex Mono, monospace' }}
            tickFormatter={formatDate}
            interval={tickInterval}
            axisLine={{ stroke: '#C9BFAC' }}
            tickLine={false}
          />
          <YAxis
            stroke="#C9BFAC"
            tick={{ fill: '#8A8279', fontSize: compact ? 10 : 11, fontFamily: 'IBM Plex Mono, monospace' }}
            tickFormatter={formatCurrency}
            axisLine={false}
            tickLine={false}
            width={compact ? 50 : 65}
          />
          <Tooltip content={<CustomTooltip compact={compact} />} />

          {/* Confidence band — best to worst range */}
          {hasBand && !compact && (
            <Area
              type="monotone"
              dataKey="best_equity"
              stroke="none"
              fill="rgba(20, 18, 16, 0.06)"
              fillOpacity={1}
              activeDot={false}
              isAnimationActive={false}
            />
          )}
          {hasBand && !compact && (
            <Area
              type="monotone"
              dataKey="worst_equity"
              stroke="none"
              fill="#F5F1E8"
              fillOpacity={1}
              activeDot={false}
              isAnimationActive={false}
            />
          )}

          {/* SPY benchmark — dashed amber */}
          <Line
            type="monotone"
            dataKey="spy_equity"
            stroke="#B8923D"
            strokeWidth={compact ? 1.5 : 2}
            strokeDasharray="6 3"
            dot={false}
            activeDot={false}
            name="SPY"
          />

          {/* Worst case — thin dashed blue */}
          {hasBand && !compact && (
            <Line
              type="monotone"
              dataKey="worst_equity"
              stroke="#141210"
              strokeWidth={1}
              strokeDasharray="4 4"
              strokeOpacity={0.4}
              dot={false}
              activeDot={false}
              name="Worst Start Date"
            />
          )}

          {/* Best case — thin dashed blue */}
          {hasBand && !compact && (
            <Line
              type="monotone"
              dataKey="best_equity"
              stroke="#141210"
              strokeWidth={1}
              strokeDasharray="4 4"
              strokeOpacity={0.4}
              dot={false}
              activeDot={false}
              name="Best Start Date"
            />
          )}

          {/* Average equity — solid blue (primary) */}
          <Line
            type="monotone"
            dataKey="equity"
            stroke="#141210"
            strokeWidth={compact ? 2 : 2.5}
            dot={false}
            activeDot={{ r: 4, fill: '#141210', stroke: '#F5F1E8' }}
            name="Average"
          />
        </ComposedChart>
      </ResponsiveContainer>

      {/* Legend */}
      {!compact && (
        <div className="mt-4 space-y-3">
          <div className="flex items-center justify-center gap-6 text-xs font-mono">
            <span className="flex items-center gap-1.5">
              <span className="w-5 h-0.5 bg-ink inline-block" />
              <span className="text-ink-mute">Average (all start dates)</span>
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-5 h-0.5 inline-block opacity-40 bg-ink" style={{ borderTop: '1px dashed #141210' }} />
              <span className="text-ink-light">Best / Worst start date</span>
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-5 h-0.5 inline-block" style={{ background: '#B8923D' }} />
              <span className="text-ink-mute">S&P 500 (SPY)</span>
            </span>
          </div>

          {/* Regime legend */}
          {uniqueRegimes.length > 0 && (
            <div className="pt-2 border-t border-rule">
              <p className="text-xs text-ink-light mb-2 text-center font-mono tracking-wide">Market Regimes</p>
              <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-1 text-xs font-mono">
                {uniqueRegimes.map(r => (
                  <span key={r.type} className="flex items-center gap-1.5">
                    <span
                      className="w-3 h-3"
                      style={{ backgroundColor: r.bg, border: `1px solid ${r.color}` }}
                    />
                    <span className="text-ink-mute">{r.name}</span>
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
