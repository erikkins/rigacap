import React, { useState, useEffect, useMemo } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceArea,
} from 'recharts';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const REGIME_DARK_COLORS = {
  strong_bull: { bg: 'rgba(16, 185, 129, 0.15)', color: '#10B981', name: 'Strong Bull' },
  weak_bull: { bg: 'rgba(132, 204, 22, 0.12)', color: '#84CC16', name: 'Weak Bull' },
  rotating_bull: { bg: 'rgba(139, 92, 246, 0.12)', color: '#8B5CF6', name: 'Rotating Bull' },
  range_bound: { bg: 'rgba(245, 158, 11, 0.12)', color: '#F59E0B', name: 'Range-Bound' },
  weak_bear: { bg: 'rgba(249, 115, 22, 0.12)', color: '#F97316', name: 'Weak Bear' },
  panic_crash: { bg: 'rgba(239, 68, 68, 0.15)', color: '#EF4444', name: 'Panic/Crash' },
  recovery: { bg: 'rgba(6, 182, 212, 0.12)', color: '#06B6D4', name: 'Recovery' },
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

  const outperformance = data.equity && data.spy_equity
    ? ((data.equity / data.spy_equity - 1) * 100).toFixed(1)
    : null;

  const regime = data._regime;

  return (
    <div className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 shadow-xl text-xs">
      <div className="text-gray-400 mb-1">{data.date}</div>
      <div className="flex items-center gap-2 mb-0.5">
        <span className="w-2 h-2 rounded-full bg-blue-500 inline-block" />
        <span className="text-white font-medium">Portfolio: {formatCurrency(data.equity)}</span>
      </div>
      <div className="flex items-center gap-2 mb-0.5">
        <span className="w-2 h-2 rounded-full bg-amber-500 inline-block" />
        <span className="text-gray-300">SPY: {formatCurrency(data.spy_equity)}</span>
      </div>
      {outperformance && !compact && (
        <div className={`mt-1 font-medium ${parseFloat(outperformance) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
          {parseFloat(outperformance) >= 0 ? '+' : ''}{outperformance}% vs SPY
        </div>
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

  // Annotate chart data with regime info for tooltip
  const chartData = useMemo(() => {
    if (!data?.equity_curve) return [];
    const periods = data.regime_periods || [];

    return data.equity_curve.map(point => {
      // Find which regime this date falls in
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

  // Map regime periods to chart data points for ReferenceArea
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

      // Extend to next period's start so bands meet edge-to-edge
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

  // Unique regimes for legend
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

  // Thin chart data for compact view (every ~7th point)
  const displayData = useMemo(() => {
    if (!compact || chartData.length < 100) return chartData;
    const step = Math.max(1, Math.floor(chartData.length / 80));
    const result = [];
    for (let i = 0; i < chartData.length; i += step) result.push(chartData[i]);
    // Always include last point
    if (result[result.length - 1] !== chartData[chartData.length - 1]) {
      result.push(chartData[chartData.length - 1]);
    }
    return result;
  }, [chartData, compact]);

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
    return null; // Fail silently — page content still shows
  }

  // Compute X-axis tick interval
  const tickInterval = compact ? Math.floor(displayData.length / 3) : Math.floor(displayData.length / 6);

  return (
    <div>
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={displayData} margin={{ top: 10, right: 10, left: compact ? 0 : 10, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" vertical={false} />

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
            stroke="#6B7280"
            tick={{ fill: '#9CA3AF', fontSize: compact ? 10 : 11 }}
            tickFormatter={formatDate}
            interval={tickInterval}
            axisLine={{ stroke: '#374151' }}
            tickLine={false}
          />
          <YAxis
            stroke="#6B7280"
            tick={{ fill: '#9CA3AF', fontSize: compact ? 10 : 11 }}
            tickFormatter={formatCurrency}
            axisLine={false}
            tickLine={false}
            width={compact ? 50 : 65}
          />
          <Tooltip content={<CustomTooltip compact={compact} />} />

          {/* SPY benchmark — dashed amber */}
          <Line
            type="monotone"
            dataKey="spy_equity"
            stroke="#F59E0B"
            strokeWidth={compact ? 1.5 : 2}
            strokeDasharray="6 3"
            dot={false}
            activeDot={false}
            name="SPY"
          />

          {/* Portfolio equity — solid blue */}
          <Line
            type="monotone"
            dataKey="equity"
            stroke="#3B82F6"
            strokeWidth={compact ? 2 : 2.5}
            dot={false}
            activeDot={{ r: 4, fill: '#3B82F6', stroke: '#1E40AF' }}
            name="Portfolio"
          />
        </LineChart>
      </ResponsiveContainer>

      {/* Legend */}
      {!compact && (
        <div className="mt-4 space-y-3">
          {/* Line legend */}
          <div className="flex items-center justify-center gap-6 text-xs">
            <span className="flex items-center gap-1.5">
              <span className="w-5 h-0.5 bg-blue-500 inline-block rounded" />
              <span className="text-gray-400">RigaCap Ensemble</span>
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-5 h-0.5 inline-block rounded" style={{ background: '#F59E0B', opacity: 0.7 }} />
              <span className="text-gray-400">S&P 500 (SPY)</span>
            </span>
          </div>

          {/* Regime legend */}
          {uniqueRegimes.length > 0 && (
            <div className="pt-2 border-t border-gray-800">
              <p className="text-xs text-gray-600 mb-2 text-center">Market Regimes</p>
              <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-1 text-xs">
                {uniqueRegimes.map(r => (
                  <span key={r.type} className="flex items-center gap-1.5">
                    <span
                      className="w-3 h-3 rounded-sm"
                      style={{ backgroundColor: r.bg, border: `1px solid ${r.color}` }}
                    />
                    <span style={{ color: r.color }}>{r.name}</span>
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
