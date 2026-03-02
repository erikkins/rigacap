import React, { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine, Legend, ReferenceArea, ComposedChart, Area, Bar } from 'recharts';
import { PlayCircle, RefreshCw, TrendingUp, Calendar, ArrowRight, AlertCircle, Zap, Brain, ChevronDown, ChevronUp, Eye, EyeOff, BarChart2, X, ArrowUpRight, ArrowDownRight } from 'lucide-react';

import { formatDate, formatChartDate } from '../utils/formatDate';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Trade Chart Modal - Shows buy/sell points for a specific trade
const TradeChartModal = ({ trade, onClose, fetchWithAuth }) => {
  const [priceData, setPriceData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchTradeData = async () => {
      setLoading(true);
      setError(null);
      try {
        // Calculate days needed: from 30 days before entry to 30 days after exit
        const entryDate = new Date(trade.entry_date);
        const exitDate = new Date(trade.exit_date);
        const today = new Date();
        const daysSinceEntry = Math.ceil((today - entryDate) / (1000 * 60 * 60 * 24));
        const daysNeeded = daysSinceEntry + 60; // Extra buffer

        const response = await fetchWithAuth(`${API_URL}/api/stock/${trade.symbol}/history?days=${daysNeeded}`);
        if (!response.ok) throw new Error('Failed to fetch chart data');

        const result = await response.json();
        let chartData = result.data || [];

        // Filter to show transaction window: 30 days before entry to 30 days after exit
        const windowStart = new Date(entryDate);
        windowStart.setDate(windowStart.getDate() - 30);
        const windowEnd = new Date(exitDate);
        windowEnd.setDate(windowEnd.getDate() + 30);
        // Don't go past today
        const maxEnd = new Date();
        const effectiveEnd = windowEnd > maxEnd ? maxEnd : windowEnd;

        chartData = chartData.filter(d => {
          const date = new Date(d.date);
          return date >= windowStart && date <= effectiveEnd;
        });

        setPriceData(chartData);
      } catch (err) {
        console.error('Trade chart error:', err);
        setError('Failed to load chart data');
      } finally {
        setLoading(false);
      }
    };

    fetchTradeData();
  }, [trade, fetchWithAuth]);

  const isProfit = trade.pnl_pct >= 0;
  const holdingDays = Math.ceil((new Date(trade.exit_date) - new Date(trade.entry_date)) / (1000 * 60 * 60 * 24));

  // Add markers to price data for entry/exit points
  const chartData = priceData.map(d => ({
    ...d,
    isEntry: d.date === trade.entry_date,
    isExit: d.date === trade.exit_date,
  }));

  // Custom dot renderer for B/S markers
  const renderDot = (props) => {
    const { cx, cy, payload } = props;
    if (!payload) return null;

    if (payload.isEntry) {
      return (
        <g key={`entry-${payload.date}`}>
          <circle cx={cx} cy={cy} r={14} fill="#10B981" />
          <text x={cx} y={cy + 5} textAnchor="middle" fill="white" fontSize={12} fontWeight="bold">B</text>
        </g>
      );
    }
    if (payload.isExit) {
      return (
        <g key={`exit-${payload.date}`}>
          <circle cx={cx} cy={cy} r={14} fill={isProfit ? '#F59E0B' : '#EF4444'} />
          <text x={cx} y={cy + 5} textAnchor="middle" fill="white" fontSize={12} fontWeight="bold">S</text>
        </g>
      );
    }
    return null;
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl max-w-4xl w-full max-h-[90vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-100 relative flex-shrink-0">
          <button onClick={onClose} className="absolute top-4 right-4 p-2 hover:bg-gray-100 rounded-lg z-10">
            <X size={24} className="text-gray-400" />
          </button>

          <div className="pr-12">
            <div className="flex items-center gap-3 flex-wrap">
              <h2 className="text-2xl font-bold text-gray-900">{trade.symbol}</h2>
              <span className={`px-3 py-1 rounded-full text-sm font-semibold flex items-center gap-1 ${
                isProfit ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700'
              }`}>
                {isProfit ? <ArrowUpRight size={16} /> : <ArrowDownRight size={16} />}
                {isProfit ? '+' : ''}{trade.pnl_pct?.toFixed(1)}%
              </span>
              <span className="px-2 py-1 bg-gray-100 text-gray-700 text-xs font-medium rounded-full">
                {trade.strategy_name}
              </span>
            </div>

            <div className="mt-3 grid grid-cols-2 md:grid-cols-5 gap-4 text-sm">
              <div className="bg-emerald-50 rounded-lg p-2 text-center">
                <p className="text-xs text-gray-500">Entry</p>
                <p className="font-semibold text-emerald-700">${trade.entry_price?.toFixed(2)}</p>
                <p className="text-xs text-gray-400">{formatDate(trade.entry_date)}</p>
              </div>
              <div className={`rounded-lg p-2 text-center ${isProfit ? 'bg-emerald-50' : 'bg-red-50'}`}>
                <p className="text-xs text-gray-500">Exit</p>
                <p className={`font-semibold ${isProfit ? 'text-emerald-700' : 'text-red-700'}`}>${trade.exit_price?.toFixed(2)}</p>
                <p className="text-xs text-gray-400">{formatDate(trade.exit_date)}</p>
              </div>
              <div className={`rounded-lg p-2 text-center ${isProfit ? 'bg-emerald-50' : 'bg-red-50'}`}>
                <p className="text-xs text-gray-500">P&L</p>
                <p className={`font-semibold ${isProfit ? 'text-emerald-700' : 'text-red-700'}`}>
                  {isProfit ? '+' : ''}${trade.pnl_dollars?.toFixed(0)}
                </p>
                <p className="text-xs text-gray-400">{trade.shares?.toFixed(0)} shares</p>
              </div>
              <div className="bg-gray-50 rounded-lg p-2 text-center">
                <p className="text-xs text-gray-500">Held</p>
                <p className="font-semibold text-gray-700">{holdingDays} days</p>
              </div>
              <div className="bg-amber-50 rounded-lg p-2 text-center">
                <p className="text-xs text-gray-500">Exit Reason</p>
                <p className="font-semibold text-amber-700 text-xs">{trade.exit_reason?.replace('_', ' ')}</p>
              </div>
            </div>
          </div>
        </div>

        {/* Chart */}
        <div className="flex-1 p-6 overflow-y-auto">
          <div className="mb-2 text-xs text-gray-500 text-center">
            Transaction window: 30 days before entry → 30 days after exit
          </div>

          {loading ? (
            <div className="flex items-center justify-center h-64">
              <RefreshCw className="w-8 h-8 text-gray-400 animate-spin" />
            </div>
          ) : error ? (
            <div className="text-center py-12 text-red-500">{error}</div>
          ) : priceData.length === 0 ? (
            <div className="text-center py-12 text-gray-500">No price data available</div>
          ) : (
            <ResponsiveContainer width="100%" height={350}>
              <ComposedChart data={chartData}>
                <defs>
                  <linearGradient id="tradeGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3B82F6" stopOpacity={0.15}/>
                    <stop offset="95%" stopColor="#3B82F6" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" vertical={false} />
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 11 }}
                  stroke="#9CA3AF"
                  tickFormatter={(val) => formatChartDate(val)}
                  interval={Math.floor(priceData.length / 8)}
                />
                <YAxis
                  yAxisId="price"
                  tick={{ fontSize: 11 }}
                  stroke="#9CA3AF"
                  domain={['dataMin - 5', 'dataMax + 5']}
                  tickFormatter={(val) => `$${val.toFixed(0)}`}
                />
                <YAxis
                  yAxisId="volume"
                  orientation="right"
                  tick={{ fontSize: 10 }}
                  stroke="#D1D5DB"
                  tickFormatter={(val) => `${(val / 1000000).toFixed(0)}M`}
                />
                <Tooltip
                  content={({ active, payload, label }) => {
                    if (!active || !payload?.length) return null;
                    const d = payload[0]?.payload;
                    const isEntryDay = d?.date === trade.entry_date;
                    const isExitDay = d?.date === trade.exit_date;
                    return (
                      <div className={`bg-white p-3 rounded-lg shadow-lg border text-sm ${
                        isEntryDay ? 'border-emerald-400 border-2' :
                        isExitDay ? 'border-amber-400 border-2' : 'border-gray-200'
                      }`}>
                        <p className="font-medium text-gray-900 mb-1">
                          {formatDate(label)}
                          {isEntryDay && <span className="ml-2 text-emerald-600 font-bold">BUY</span>}
                          {isExitDay && <span className="ml-2 text-amber-600 font-bold">SELL</span>}
                        </p>
                        <p className="text-blue-600">Close: ${d?.close?.toFixed(2)}</p>
                        {isEntryDay && <p className="text-emerald-600 font-medium">Entry: ${trade.entry_price?.toFixed(2)}</p>}
                        {isExitDay && <p className="text-amber-600 font-medium">Exit: ${trade.exit_price?.toFixed(2)}</p>}
                        {d?.volume > 0 && <p className="text-gray-400">Vol: {(d.volume / 1000000).toFixed(1)}M</p>}
                      </div>
                    );
                  }}
                />
                <Bar yAxisId="volume" dataKey="volume" fill="#E5E7EB" opacity={0.5} />
                <Area
                  yAxisId="price"
                  type="monotone"
                  dataKey="close"
                  stroke="#3B82F6"
                  strokeWidth={2}
                  fill="url(#tradeGradient)"
                  dot={renderDot}
                />


              </ComposedChart>
            </ResponsiveContainer>
          )}

          {/* Legend */}
          <div className="flex items-center justify-center gap-6 mt-4 text-xs text-gray-500">
            <span className="flex items-center gap-1.5">
              <span className="w-5 h-5 rounded-full bg-emerald-500 text-white text-xs font-bold flex items-center justify-center">B</span> Buy
            </span>
            <span className="flex items-center gap-1.5">
              <span className={`w-5 h-5 rounded-full text-white text-xs font-bold flex items-center justify-center ${isProfit ? 'bg-amber-500' : 'bg-red-500'}`}>S</span> Sell
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-8 h-0.5 bg-blue-500"></span> Price
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default function WalkForwardSimulator({ fetchWithAuth }) {
  const [startDate, setStartDate] = useState(() => {
    const d = new Date();
    d.setMonth(d.getMonth() - 6); // Default 6 months for faster simulation
    return d.toISOString().split('T')[0];
  });
  const [endDate, setEndDate] = useState(() => new Date().toISOString().split('T')[0]);
  const [frequency, setFrequency] = useState('biweekly');
  const [minScoreDiff, setMinScoreDiff] = useState(10);
  const [enableAI, setEnableAI] = useState(true);
  const [maxSymbols, setMaxSymbols] = useState(50);
  const [strategies, setStrategies] = useState([]);
  const [selectedStrategyId, setSelectedStrategyId] = useState(''); // '' = auto-select
  const [loading, setLoading] = useState(false);
  const [jobId, setJobId] = useState(null);
  const [jobStatus, setJobStatus] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [history, setHistory] = useState([]);
  const [showAIDetails, setShowAIDetails] = useState(false);
  const [showParamEvolution, setShowParamEvolution] = useState(false);
  const [showTrades, setShowTrades] = useState(false);
  const [selectedTrade, setSelectedTrade] = useState(null);
  const [regimePeriods, setRegimePeriods] = useState([]);
  const [showRegimes, setShowRegimes] = useState(true);
  const [currentRegime, setCurrentRegime] = useState(null);
  const [loadingRegimes, setLoadingRegimes] = useState(false);

  // Fetch available strategies
  const fetchStrategies = async () => {
    try {
      const response = await fetchWithAuth(`${API_URL}/api/admin/strategies`);
      if (response.ok) {
        const data = await response.json();
        // API returns a list directly, not {strategies: [...]}
        setStrategies(Array.isArray(data) ? data : (data.strategies || []));
      }
    } catch (err) {
      console.error('Failed to fetch strategies:', err);
    }
  };

  useEffect(() => {
    fetchHistory();
    fetchStrategies();
    fetchCurrentRegime();
  }, []);

  const fetchHistory = async () => {
    try {
      const response = await fetchWithAuth(`${API_URL}/api/admin/strategies/walk-forward/history?limit=5`);
      if (response.ok) {
        const data = await response.json();
        setHistory(data.simulations || []);
      }
    } catch (err) {
      console.error('Failed to fetch history:', err);
    }
  };

  // Fetch current market regime
  const fetchCurrentRegime = async () => {
    try {
      const response = await fetchWithAuth(`${API_URL}/api/admin/market-regime/current`);
      if (response.ok) {
        const data = await response.json();
        setCurrentRegime(data);
      }
    } catch (err) {
      console.error('Failed to fetch current regime:', err);
    }
  };

  // Fetch regime periods for chart visualization
  const fetchRegimePeriods = async (start, end) => {
    setLoadingRegimes(true);
    console.log('[RegimePeriods] Fetching for range:', start, 'to', end);
    try {
      const params = new URLSearchParams();
      if (start) params.append('start_date', start);
      if (end) params.append('end_date', end);

      const response = await fetchWithAuth(`${API_URL}/api/admin/market-regime/periods?${params}`);
      if (response.ok) {
        const data = await response.json();
        console.log('[RegimePeriods] Received', data.periods?.length || 0, 'periods');
        if (data.periods?.length > 0) {
          console.log('[RegimePeriods] First period:', data.periods[0]);
          console.log('[RegimePeriods] Last period:', data.periods[data.periods.length - 1]);
          console.log('[RegimePeriods] Regime changes:', data.regime_changes?.length || 0);
        }
        setRegimePeriods(data.periods || []);
        // Log regime changes for debugging
        if (data.regime_changes?.length > 0) {
          console.log('[RegimePeriods] Regime changes detected:', data.regime_changes);
        } else {
          console.log('[RegimePeriods] No regime changes - market stayed in same regime');
        }
      } else {
        const text = await response.text();
        console.error('[RegimePeriods] API error:', response.status, text);
      }
    } catch (err) {
      console.error('[RegimePeriods] Failed to fetch:', err);
    } finally {
      setLoadingRegimes(false);
    }
  };

  // Poll for job status
  const pollJobStatus = async (id) => {
    try {
      const response = await fetchWithAuth(
        `${API_URL}/api/admin/strategies/walk-forward/status/${id}`
      );

      if (response.ok) {
        const data = await response.json();
        setJobStatus(data.status);

        if (data.status === 'completed') {
          setResult(data);
          setLoading(false);
          setJobId(null);
          fetchHistory();
          // Fetch regime periods for the simulation date range
          if (data.start_date && data.end_date) {
            fetchRegimePeriods(data.start_date.split('T')[0], data.end_date.split('T')[0]);
          }
        } else if (data.status === 'failed') {
          setError(data.error || 'Simulation failed');
          setLoading(false);
          setJobId(null);
        } else {
          // Still running, poll again in 3 seconds
          setTimeout(() => pollJobStatus(id), 3000);
        }
      } else {
        setError('Failed to check job status');
        setLoading(false);
      }
    } catch (err) {
      setError(err.message);
      setLoading(false);
    }
  };

  const runSimulation = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    setJobId(null);
    setJobStatus(null);

    try {
      const params = new URLSearchParams({
        start_date: startDate,
        end_date: endDate,
        frequency: frequency,
        min_score_diff: minScoreDiff,
        enable_ai: selectedStrategyId ? false : enableAI, // Disable AI if fixed strategy
        max_symbols: maxSymbols
      });
      if (selectedStrategyId) {
        params.append('strategy_id', selectedStrategyId);
      }

      // Use the /start endpoint which now returns results directly
      const response = await fetchWithAuth(
        `${API_URL}/api/admin/strategies/walk-forward/start?${params}`,
        { method: 'POST' }
      );

      if (response.ok) {
        const data = await response.json();
        // Check if results are returned directly or if we need to poll
        if (data.status === 'completed') {
          setResult(data);
          fetchHistory();
          fetchRegimePeriods(startDate, endDate);
          setLoading(false);
        } else if (data.job_id) {
          // Legacy polling mode (shouldn't happen with new backend)
          setJobId(data.job_id);
          setJobStatus('pending');
          setTimeout(() => pollJobStatus(data.job_id), 2000);
        } else {
          setResult(data);
          fetchHistory();
          fetchRegimePeriods(startDate, endDate);
          setLoading(false);
        }
      } else {
        // Read body as text first to avoid "Body is disturbed" error
        const text = await response.text();
        try {
          const err = JSON.parse(text);
          setError(err.detail || 'Simulation failed');
        } catch {
          setError(`Server error (${response.status}): ${text.slice(0, 200)}`);
        }
        setLoading(false);
      }
    } catch (err) {
      setError(err.message || 'Failed to run simulation');
      setLoading(false);
    }
  };

  const loadSimulation = async (simId) => {
    setError(null);
    setLoading(true);
    try {
      const response = await fetchWithAuth(`${API_URL}/api/admin/strategies/walk-forward/${simId}`);
      if (response.ok) {
        const data = await response.json();
        setResult({
          ...data,
          switch_history: data.switch_history || []
        });
        // Fetch regime periods for the loaded simulation
        if (data.start_date && data.end_date) {
          const startStr = data.start_date.split('T')[0];
          const endStr = data.end_date.split('T')[0];
          fetchRegimePeriods(startStr, endStr);
        }
      } else {
        const text = await response.text();
        try {
          const err = JSON.parse(text);
          setError(`Failed to load simulation: ${err.detail || 'Unknown error'}`);
        } catch {
          setError(`Failed to load simulation (${response.status})`);
        }
      }
    } catch (err) {
      console.error('Failed to load simulation:', err);
      setError(`Failed to load simulation: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  // Prepare chart data
  const chartData = result?.equity_curve?.map((point, i) => {
    // Use is_switch from point (already computed server-side)
    // Also check switch_history for additional info about the switch
    const switchEvent = point.is_switch ? result.switch_history?.find(s =>
      // Match by strategy name or check if this is near a switch date
      s.to_strategy === point.strategy || s.to_strategy_name === point.strategy
    ) : null;
    return {
      ...point,
      equityValue: point.equity,
      spyEquity: point.spy_equity,
      hasSwitch: point.is_switch || false,
      switchTo: switchEvent?.to_strategy || switchEvent?.to_strategy_name || point.strategy,
      isAISwitch: point.is_ai || switchEvent?.is_ai_generated || false
    };
  }) || [];

  // Map regime periods to actual chart data points for proper ReferenceArea rendering
  // Recharts categorical x-axis requires x1/x2 to be actual data values
  const mappedRegimePeriods = React.useMemo(() => {
    if (!chartData.length || !regimePeriods.length) return [];

    const chartDates = chartData.map(d => d.date);

    return regimePeriods.map((period, idx) => {
      // Find the first chart date >= period start
      let startIdx = chartDates.findIndex(d => d >= period.start_date);
      if (startIdx === -1) startIdx = 0;

      // Find the last chart date <= period end
      let endIdx = chartDates.length - 1;
      for (let i = chartDates.length - 1; i >= 0; i--) {
        if (chartDates[i] <= period.end_date) {
          endIdx = i;
          break;
        }
      }

      // Extend x2 to the next chart point so adjacent regime bands meet edge-to-edge
      // (without this, biweekly chart points leave gaps where regimes change mid-interval)
      const nextPeriod = regimePeriods[idx + 1];
      if (nextPeriod && endIdx < chartDates.length - 1) {
        const nextStartIdx = chartDates.findIndex(d => d >= nextPeriod.start_date);
        if (nextStartIdx > endIdx) {
          endIdx = nextStartIdx;
        }
      }

      // Only include if we have valid range
      if (startIdx <= endIdx) {
        return {
          ...period,
          x1: chartDates[startIdx],
          x2: chartDates[endIdx]
        };
      }
      return null;
    }).filter(Boolean);
  }, [chartData, regimePeriods]);

  // Debug: log when mapped periods change
  React.useEffect(() => {
    if (mappedRegimePeriods.length > 0) {
      console.log('[MappedRegimes] Total periods:', mappedRegimePeriods.length);
      mappedRegimePeriods.forEach((p, i) => {
        console.log(`[MappedRegimes] ${i}: ${p.regime_name} (${p.x1} to ${p.x2})`);
      });
    }
  }, [mappedRegimePeriods]);

  // Count AI vs regular switches
  const aiSwitches = result?.num_ai_switches || 0;
  const regularSwitches = (result?.num_strategy_switches || 0) - aiSwitches;

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-200 bg-gradient-to-r from-blue-50 to-indigo-50">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-blue-100 rounded-lg">
            <TrendingUp className="w-5 h-5 text-blue-600" />
          </div>
          <div>
            <h3 className="font-semibold text-gray-900">Walk-Forward Simulation</h3>
            <p className="text-sm text-gray-600">Test auto-switch logic over historical periods</p>
          </div>
        </div>
      </div>

      <div className="p-6 space-y-6">
        {/* Configuration */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Start Date</label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">End Date</label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Reoptimization</label>
            <select
              value={frequency}
              onChange={(e) => setFrequency(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="weekly">Weekly</option>
              <option value="biweekly">Biweekly</option>
              <option value="monthly">Monthly</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Min Score Diff</label>
            <input
              type="number"
              value={minScoreDiff}
              onChange={(e) => setMinScoreDiff(parseFloat(e.target.value))}
              min="0"
              max="50"
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
        </div>

        {/* Symbol Universe Selection */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Symbol Universe</label>
          <div className="flex gap-2">
            {[
              { value: 50, label: 'Fast (50)', desc: 'Quick test' },
              { value: 100, label: 'Medium (100)', desc: 'Good balance' },
              { value: 250, label: 'Large (250)', desc: 'More coverage' },
              { value: 500, label: 'Full (500)', desc: 'All liquid stocks' },
            ].map(opt => (
              <button
                key={opt.value}
                onClick={() => setMaxSymbols(opt.value)}
                className={`flex-1 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  maxSymbols === opt.value
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
          {maxSymbols > 100 && (
            <p className="text-xs text-amber-600 mt-2">
              Larger universes run as background jobs and may take several minutes.
            </p>
          )}
        </div>

        {/* Strategy Selection */}
        <div className="space-y-2">
          <label className="text-sm font-medium text-gray-700 flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-blue-600" />
            Strategy
          </label>
          <select
            value={selectedStrategyId}
            onChange={(e) => setSelectedStrategyId(e.target.value)}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          >
            <option value="">Auto-select best strategy (with switching)</option>
            {strategies.map(s => (
              <option key={s.id} value={s.id}>
                {s.name} ({s.strategy_type})
              </option>
            ))}
          </select>
          {selectedStrategyId && (
            <p className="text-xs text-blue-600">
              Fixed strategy mode: Will use only this strategy without switching or AI optimization.
            </p>
          )}
        </div>

        {/* AI Optimization Toggle - disabled when using fixed strategy */}
        <div className={`flex items-center justify-between p-4 rounded-xl border ${
          selectedStrategyId
            ? 'bg-gray-100 border-gray-200 opacity-60'
            : 'bg-gradient-to-r from-purple-50 to-indigo-50 border-purple-200'
        }`}>
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-lg ${selectedStrategyId ? 'bg-gray-200' : 'bg-purple-100'}`}>
              <Brain className={`w-5 h-5 ${selectedStrategyId ? 'text-gray-400' : 'text-purple-600'}`} />
            </div>
            <div>
              <p className="font-medium text-gray-900">AI Parameter Optimization</p>
              <p className="text-sm text-gray-600">
                {selectedStrategyId
                  ? 'Disabled when using fixed strategy'
                  : 'Detect emerging trends and adapt parameters at each period'}
              </p>
            </div>
          </div>
          <label className={`relative inline-flex items-center ${selectedStrategyId ? 'cursor-not-allowed' : 'cursor-pointer'}`}>
            <input
              type="checkbox"
              checked={selectedStrategyId ? false : enableAI}
              onChange={(e) => setEnableAI(e.target.checked)}
              disabled={!!selectedStrategyId}
              className="sr-only peer"
            />
            <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-purple-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-purple-600 peer-disabled:opacity-50"></div>
          </label>
        </div>

        {/* Current Market Regime Display */}
        {currentRegime && (
          <div className="p-4 rounded-xl border" style={{
            background: currentRegime.conditions ? `linear-gradient(to right, ${currentRegime.conditions.bg_color || 'rgba(209, 213, 219, 0.1)'}, white)` : 'white',
            borderColor: currentRegime.color || '#D1D5DB'
          }}>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg" style={{ backgroundColor: `${currentRegime.color}20` }}>
                  <BarChart2 className="w-5 h-5" style={{ color: currentRegime.color }} />
                </div>
                <div>
                  <p className="font-medium text-gray-900">
                    Current Regime: <span style={{ color: currentRegime.color }}>{currentRegime.regime_name}</span>
                  </p>
                  <p className="text-sm text-gray-600">{currentRegime.description}</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className={`text-xs px-2 py-1 rounded-full ${
                  currentRegime.risk_level === 'low' ? 'bg-green-100 text-green-700' :
                  currentRegime.risk_level === 'extreme' ? 'bg-red-100 text-red-700' :
                  currentRegime.risk_level === 'high' ? 'bg-orange-100 text-orange-700' :
                  'bg-yellow-100 text-yellow-700'
                }`}>
                  {currentRegime.risk_level?.toUpperCase()} risk
                </span>
                <span className="text-xs text-gray-500">
                  {currentRegime.confidence?.toFixed(0)}% confidence
                </span>
              </div>
            </div>
            {/* Market Conditions Summary */}
            {currentRegime.conditions && (
              <div className="mt-3 flex flex-wrap gap-2 text-xs">
                <span className="px-2 py-1 bg-white/80 rounded border border-gray-200">
                  SPY vs 200MA: <span className={currentRegime.conditions.spy_vs_200ma_pct >= 0 ? 'text-green-600' : 'text-red-600'}>
                    {currentRegime.conditions.spy_vs_200ma_pct >= 0 ? '+' : ''}{currentRegime.conditions.spy_vs_200ma_pct?.toFixed(1)}%
                  </span>
                </span>
                <span className="px-2 py-1 bg-white/80 rounded border border-gray-200">
                  Fear: <span className="font-medium">{currentRegime.conditions.vix_level?.toFixed(1)}</span>
                  <span className="text-gray-400 ml-1">(VIX {currentRegime.conditions.vix_percentile?.toFixed(0)}%ile)</span>
                </span>
                <span className="px-2 py-1 bg-white/80 rounded border border-gray-200">
                  Breadth: <span className="font-medium">{currentRegime.conditions.breadth_pct?.toFixed(0)}%</span> above 50MA
                </span>
                <span className="px-2 py-1 bg-white/80 rounded border border-gray-200">
                  Trend: <span className={currentRegime.conditions.trend_strength >= 0 ? 'text-green-600' : 'text-red-600'}>
                    {currentRegime.conditions.trend_strength >= 0 ? '+' : ''}{currentRegime.conditions.trend_strength?.toFixed(1)}
                  </span>
                </span>
              </div>
            )}
          </div>
        )}

        {/* Run Button */}
        <button
          onClick={runSimulation}
          disabled={loading}
          className="w-full flex items-center justify-center gap-2 px-6 py-3 bg-blue-600 text-white rounded-xl font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? (
            <>
              <RefreshCw className="w-5 h-5 animate-spin" />
              {jobStatus === 'pending' ? 'Starting simulation...' :
               jobStatus === 'running' ? `Running simulation (Job #${jobId})...` :
               'Running Simulation...'}
            </>
          ) : (
            <>
              <PlayCircle className="w-5 h-5" />
              Run Walk-Forward Simulation
              {maxSymbols > 100 && <span className="text-xs opacity-75">(Background)</span>}
            </>
          )}
        </button>

        {/* Info Note */}
        <p className="text-xs text-gray-500 text-center">
          Evaluates all strategies (Momentum, DWAP Classic, DWAP Hybrid) at each period and picks the best performer.
          {enableAI && ' AI optimization finds best parameters for current market conditions.'}
        </p>

        {/* Job Status */}
        {loading && jobId && (
          <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
            <div className="flex items-center gap-3">
              <RefreshCw className="w-5 h-5 text-blue-600 animate-spin" />
              <div>
                <p className="font-medium text-blue-900">Background Job #{jobId}</p>
                <p className="text-sm text-blue-700">
                  Status: <span className="font-medium">{jobStatus}</span>
                  {jobStatus === 'running' && ' - Processing... This may take a few minutes for large universes.'}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Error Display */}
        {error && (
          <div className="p-4 bg-red-50 border border-red-200 rounded-lg flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-red-500 mt-0.5" />
            <div>
              <p className="font-medium text-red-800">Simulation Failed</p>
              <p className="text-sm text-red-600">{error}</p>
            </div>
          </div>
        )}

        {/* Results */}
        {result && (
          <div className="space-y-6">
            {/* Performance Summary */}
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              <div className="p-4 bg-gradient-to-br from-emerald-50 to-green-50 rounded-xl text-center">
                <p className="text-sm text-gray-600 mb-1">Total Return</p>
                <p className={`text-2xl font-bold ${result.total_return_pct >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                  {result.total_return_pct >= 0 ? '+' : ''}{result.total_return_pct?.toFixed(1)}%
                </p>
              </div>
              <div className="p-4 bg-gray-50 rounded-xl text-center">
                <p className="text-sm text-gray-600 mb-1">Sharpe Ratio</p>
                <p className="text-2xl font-bold text-gray-900">{result.sharpe_ratio?.toFixed(2)}</p>
              </div>
              <div className="p-4 bg-red-50 rounded-xl text-center">
                <p className="text-sm text-gray-600 mb-1">Max Drawdown</p>
                <p className="text-2xl font-bold text-red-600">-{result.max_drawdown_pct?.toFixed(1)}%</p>
              </div>
              <div className="p-4 bg-blue-50 rounded-xl text-center">
                <p className="text-sm text-gray-600 mb-1">Total Switches</p>
                <p className="text-2xl font-bold text-blue-600">{result.num_strategy_switches}</p>
                {aiSwitches > 0 && (
                  <p className="text-xs text-purple-600 mt-1">
                    <Brain size={10} className="inline mr-1" />
                    {aiSwitches} AI-driven
                  </p>
                )}
              </div>
              <div className="p-4 bg-amber-50 rounded-xl text-center">
                <p className="text-sm text-gray-600 mb-1">SPY Benchmark</p>
                <p className={`text-2xl font-bold ${result.benchmark_return_pct >= 0 ? 'text-amber-600' : 'text-red-600'}`}>
                  {result.benchmark_return_pct >= 0 ? '+' : ''}{result.benchmark_return_pct?.toFixed(1)}%
                </p>
              </div>
            </div>

            {/* Alpha vs Benchmark */}
            <div className={`p-4 rounded-xl ${
              result.total_return_pct > result.benchmark_return_pct
                ? 'bg-emerald-50 border border-emerald-200'
                : 'bg-red-50 border border-red-200'
            }`}>
              <p className="text-center">
                <span className="font-medium">
                  {result.total_return_pct > result.benchmark_return_pct ? 'Outperformed' : 'Underperformed'}
                </span>
                <span className="text-gray-600"> SPY by </span>
                <span className={`font-bold ${
                  result.total_return_pct > result.benchmark_return_pct ? 'text-emerald-700' : 'text-red-700'
                }`}>
                  {Math.abs(result.total_return_pct - result.benchmark_return_pct).toFixed(1)}%
                </span>
              </p>
            </div>

            {/* Period Debug Info */}
            {result.errors && result.errors.length > 0 && (
              <div className="p-4 bg-blue-50 border border-blue-200 rounded-xl">
                <p className="font-medium text-blue-800 mb-2">Period Details ({result.errors.length} periods)</p>
                <ul className="text-sm text-blue-700 space-y-1 max-h-40 overflow-y-auto">
                  {result.errors.map((info, i) => (
                    <li key={i} className="font-mono text-xs">{info}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Debug: Show equity curve data points */}
            {result.equity_curve && (
              <details className="p-3 bg-gray-50 border border-gray-200 rounded-lg text-xs">
                <summary className="cursor-pointer font-medium text-gray-700">
                  Debug: {result.equity_curve.length} equity points
                  (first: ${result.equity_curve[0]?.equity?.toLocaleString()},
                   last: ${result.equity_curve[result.equity_curve.length-1]?.equity?.toLocaleString()})
                </summary>
                <pre className="mt-2 text-xs overflow-auto max-h-32">
                  {JSON.stringify(result.equity_curve?.slice(0, 5), null, 2)}
                </pre>
              </details>
            )}

            {/* Equity Curve Chart */}
            {chartData.length > 0 && (
              <div className="p-4 border border-gray-200 rounded-xl">
                <div className="flex items-center justify-between mb-4">
                  <h4 className="font-medium text-gray-900">Equity Curve</h4>
                  <div className="flex items-center gap-3">
                    {loadingRegimes && (
                      <span className="text-xs text-gray-400">Loading regimes...</span>
                    )}
                    {!loadingRegimes && mappedRegimePeriods.length > 0 && (
                      <span className="text-xs text-purple-600">
                        {mappedRegimePeriods.length} regime period{mappedRegimePeriods.length !== 1 ? 's' : ''}
                      </span>
                    )}
                    {!loadingRegimes && regimePeriods.length > 0 && mappedRegimePeriods.length === 0 && showRegimes && (
                      <span className="text-xs text-amber-600">Regime dates don't match chart</span>
                    )}
                    {!loadingRegimes && regimePeriods.length === 0 && showRegimes && (
                      <span className="text-xs text-amber-600">No regime data</span>
                    )}
                    <button
                      onClick={() => setShowRegimes(!showRegimes)}
                      className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                        showRegimes
                          ? 'bg-blue-100 text-blue-700 border border-blue-200'
                          : 'bg-gray-100 text-gray-600 border border-gray-200'
                      }`}
                    >
                      {showRegimes ? <Eye className="w-4 h-4" /> : <EyeOff className="w-4 h-4" />}
                      {showRegimes ? 'Regimes On' : 'Regimes Off'}
                    </button>
                  </div>
                </div>
                <ResponsiveContainer width="100%" height={300}>
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                    {/* Market Regime Background Areas */}
                    {showRegimes && mappedRegimePeriods.map((period, i) => (
                      <ReferenceArea
                        key={`regime-${i}`}
                        x1={period.x1}
                        x2={period.x2}
                        fill={period.bg_color || 'rgba(200, 200, 200, 0.1)'}
                        stroke={period.color}
                        strokeOpacity={0.3}
                        fillOpacity={0.6}
                      />
                    ))}
                    <XAxis
                      dataKey="date"
                      tick={{ fontSize: 11 }}
                      tickFormatter={(val) => formatChartDate(val)}
                    />
                    <YAxis
                      tick={{ fontSize: 11 }}
                      tickFormatter={(val) => `$${(val / 1000).toFixed(0)}k`}
                      domain={['auto', 'auto']}
                    />
                    <Tooltip
                      content={({ active, payload, label }) => {
                        if (!active || !payload?.length) return null;
                        const data = payload[0]?.payload;
                        // Find regime for this date
                        const regime = regimePeriods.find(p =>
                          label >= p.start_date && label <= p.end_date
                        );
                        return (
                          <div className="bg-white p-3 rounded-lg shadow-lg border border-gray-200 text-sm">
                            <p className="font-medium">{formatDate(label)}</p>
                            <p className="text-blue-600">Portfolio: ${data?.equity?.toLocaleString()}</p>
                            {data?.spyEquity && (
                              <p className="text-amber-600">SPY: ${Math.round(data.spyEquity).toLocaleString()}</p>
                            )}
                            <p className="text-gray-500">Strategy: {data?.strategy}</p>
                            {regime && (
                              <p className="font-medium" style={{ color: regime.color }}>
                                Regime: {regime.regime_name}
                              </p>
                            )}
                            {data?.hasSwitch && (
                              <p className="text-purple-600 font-medium">
                                Switched to: {data?.switchTo}
                              </p>
                            )}
                          </div>
                        );
                      }}
                    />
                    <Legend />
                    <Line
                      type="monotone"
                      dataKey="equityValue"
                      stroke="#3B82F6"
                      strokeWidth={2}
                      dot={false}
                      name="Portfolio"
                    />
                    <Line
                      type="monotone"
                      dataKey="spyEquity"
                      stroke="#F59E0B"
                      strokeWidth={2}
                      strokeDasharray="5 5"
                      dot={false}
                      name="SPY Benchmark"
                    />
                    {/* Switch markers - AI switches in purple, regular in green */}
                    {chartData.filter(d => d.hasSwitch && d.isAISwitch).map((d, i) => (
                      <ReferenceLine
                        key={`ai-${i}`}
                        x={d.date}
                        stroke="#8B5CF6"
                        strokeWidth={2}
                        label={{ value: 'AI', position: 'top', fontSize: 10, fill: '#8B5CF6' }}
                      />
                    ))}
                    {chartData.filter(d => d.hasSwitch && !d.isAISwitch).map((d, i) => (
                      <ReferenceLine
                        key={`reg-${i}`}
                        x={d.date}
                        stroke="#10B981"
                        strokeDasharray="3 3"
                        strokeWidth={2}
                      />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
                <div className="flex items-center justify-center gap-4 mt-2 text-xs text-gray-500">
                  <span className="flex items-center gap-1">
                    <span className="w-4 h-0.5 bg-blue-500"></span> Portfolio
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="w-4 h-0.5 bg-amber-500" style={{borderTop: '2px dashed #F59E0B'}}></span> SPY
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="w-4 h-0.5 bg-purple-500"></span> AI Switch
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="w-4 h-0.5 bg-emerald-500"></span> Strategy Switch
                  </span>
                </div>
                {/* Regime Legend */}
                {showRegimes && regimePeriods.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-gray-200">
                    <p className="text-xs text-gray-500 mb-2 text-center">Market Regimes:</p>
                    <div className="flex flex-wrap items-center justify-center gap-3 text-xs">
                      {/* Get unique regimes */}
                      {[...new Map(regimePeriods.map(p => [p.regime_type, p])).values()].map((period, i) => (
                        <span key={i} className="flex items-center gap-1.5">
                          <span
                            className="w-3 h-3 rounded-sm"
                            style={{ backgroundColor: period.bg_color, border: `1px solid ${period.color}` }}
                          ></span>
                          <span style={{ color: period.color }}>{period.regime_name}</span>
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Switch Timeline */}
            {result.switch_history && result.switch_history.length > 0 && (
              <div className="border border-gray-200 rounded-xl overflow-hidden">
                <div className="px-4 py-3 bg-gray-50 border-b border-gray-200">
                  <h4 className="font-medium text-gray-900">Switch Timeline</h4>
                </div>
                <div className="divide-y divide-gray-200">
                  {result.switch_history.map((s, i) => (
                    <div key={i} className={`px-4 py-3 ${s.is_ai_generated ? 'bg-purple-50' : ''}`}>
                      <div className="flex items-center gap-4">
                        <div className="w-24 text-sm text-gray-500">
                          {formatDate(s.date)}
                        </div>
                        <div className="flex items-center gap-2 flex-1">
                          {s.from_strategy ? (
                            <>
                              <span className="px-2 py-1 bg-gray-100 text-gray-700 rounded text-sm">
                                {s.from_strategy}
                              </span>
                              <ArrowRight size={16} className="text-gray-400" />
                            </>
                          ) : null}
                          <span className={`px-2 py-1 rounded text-sm font-medium ${
                            s.is_ai_generated
                              ? 'bg-purple-100 text-purple-700'
                              : 'bg-emerald-100 text-emerald-700'
                          }`}>
                            {s.is_ai_generated && <Brain size={12} className="inline mr-1" />}
                            {s.to_strategy}
                          </span>
                        </div>
                        <div className="text-sm text-gray-500">
                          {s.score_before != null && s.score_after != null && (
                            <span className={s.score_after > s.score_before ? 'text-emerald-600' : 'text-gray-600'}>
                              +{(s.score_after - (s.score_before || 0)).toFixed(0)} pts
                            </span>
                          )}
                        </div>
                      </div>
                      {/* AI Parameters Display */}
                      {s.is_ai_generated && s.ai_params && (
                        <div className="mt-2 ml-24 p-2 bg-purple-100/50 rounded-lg">
                          <div className="text-xs font-medium text-purple-700 mb-1">AI-Optimized Parameters:</div>
                          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
                            {s.ai_params.trailing_stop_pct && (
                              <div className="bg-white/60 px-2 py-1 rounded">
                                <span className="text-gray-500">Trail Stop:</span>{' '}
                                <span className="font-medium text-purple-800">{s.ai_params.trailing_stop_pct}%</span>
                              </div>
                            )}
                            {s.ai_params.max_positions && (
                              <div className="bg-white/60 px-2 py-1 rounded">
                                <span className="text-gray-500">Max Pos:</span>{' '}
                                <span className="font-medium text-purple-800">{s.ai_params.max_positions}</span>
                              </div>
                            )}
                            {s.ai_params.position_size_pct && (
                              <div className="bg-white/60 px-2 py-1 rounded">
                                <span className="text-gray-500">Pos Size:</span>{' '}
                                <span className="font-medium text-purple-800">{s.ai_params.position_size_pct}%</span>
                              </div>
                            )}
                            {s.ai_params.short_momentum_days && (
                              <div className="bg-white/60 px-2 py-1 rounded">
                                <span className="text-gray-500">Short Mom:</span>{' '}
                                <span className="font-medium text-purple-800">{s.ai_params.short_momentum_days}d</span>
                              </div>
                            )}
                            {s.ai_params.near_50d_high_pct && (
                              <div className="bg-white/60 px-2 py-1 rounded">
                                <span className="text-gray-500">Near High:</span>{' '}
                                <span className="font-medium text-purple-800">{s.ai_params.near_50d_high_pct}%</span>
                              </div>
                            )}
                            {s.ai_params.stop_loss_pct > 0 && (
                              <div className="bg-white/60 px-2 py-1 rounded">
                                <span className="text-gray-500">Stop Loss:</span>{' '}
                                <span className="font-medium text-purple-800">{s.ai_params.stop_loss_pct}%</span>
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* AI Optimizations Details */}
            {result.ai_optimizations && result.ai_optimizations.length > 0 && (
              <div className="border border-purple-200 rounded-xl overflow-hidden">
                <button
                  onClick={() => setShowAIDetails(!showAIDetails)}
                  className="w-full px-4 py-3 bg-gradient-to-r from-purple-50 to-indigo-50 border-b border-purple-200 flex items-center justify-between"
                >
                  <div className="flex items-center gap-2">
                    <Brain className="w-5 h-5 text-purple-600" />
                    <h4 className="font-medium text-gray-900">AI Optimization History</h4>
                    <span className="text-sm text-purple-600">({result.ai_optimizations.length} periods)</span>
                  </div>
                  {showAIDetails ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
                </button>
                {showAIDetails && (
                  <div className="divide-y divide-purple-100 max-h-96 overflow-y-auto">
                    {result.ai_optimizations.map((ai, i) => (
                      <div key={i} className="px-4 py-3">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-sm font-medium text-gray-700">
                            {formatDate(ai.date)}
                          </span>
                          <div className="flex items-center gap-2">
                            {/* Regime Badge with risk level */}
                            <span className={`text-xs px-2 py-1 rounded-full ${
                              ai.market_regime === 'rotating_bull' ? 'bg-violet-100 text-violet-700' :
                              ai.market_regime?.includes('bull') ? 'bg-emerald-100 text-emerald-700' :
                              ai.market_regime?.includes('bear') || ai.market_regime === 'panic_crash' ? 'bg-red-100 text-red-700' :
                              ai.market_regime === 'recovery' ? 'bg-blue-100 text-blue-700' :
                              'bg-gray-100 text-gray-700'
                            }`}>
                              {ai.market_regime?.replace('_', ' ').toUpperCase()}
                            </span>
                            {/* Risk Level */}
                            {ai.regime_risk_level && (
                              <span className={`text-xs px-2 py-1 rounded ${
                                ai.regime_risk_level === 'low' ? 'bg-green-50 text-green-600' :
                                ai.regime_risk_level === 'extreme' ? 'bg-red-50 text-red-600' :
                                ai.regime_risk_level === 'high' ? 'bg-orange-50 text-orange-600' :
                                'bg-yellow-50 text-yellow-600'
                              }`}>
                                {ai.regime_risk_level} risk
                              </span>
                            )}
                          </div>
                        </div>
                        {/* Enhanced Metrics Grid */}
                        <div className="grid grid-cols-4 gap-2 text-sm mb-2">
                          <div>
                            <span className="text-gray-500">Sharpe:</span>{' '}
                            <span className="font-medium">{ai.expected_sharpe?.toFixed(2)}</span>
                          </div>
                          <div>
                            <span className="text-gray-500">Sortino:</span>{' '}
                            <span className="font-medium">{ai.expected_sortino?.toFixed(2) || '-'}</span>
                          </div>
                          <div>
                            <span className="text-gray-500">Calmar:</span>{' '}
                            <span className="font-medium">{ai.expected_calmar?.toFixed(2) || '-'}</span>
                          </div>
                          <div>
                            <span className="text-gray-500">PF:</span>{' '}
                            <span className="font-medium">{ai.expected_profit_factor?.toFixed(2) || '-'}</span>
                          </div>
                        </div>
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3 text-sm">
                            <span className={`font-medium ${ai.expected_return_pct >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                              {ai.expected_return_pct >= 0 ? '+' : ''}{ai.expected_return_pct?.toFixed(1)}% return
                            </span>
                            {ai.combinations_tested > 0 && (
                              <span className="text-gray-400 text-xs">
                                {ai.combinations_tested} combos tested
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-2">
                            {ai.adaptive_score > 0 && (
                              <span className="text-xs text-purple-600 font-medium">
                                Score: {ai.adaptive_score?.toFixed(1)}
                              </span>
                            )}
                            <span className={`text-xs px-2 py-0.5 rounded ${
                              ai.was_adopted ? 'bg-purple-100 text-purple-700' : 'bg-gray-100 text-gray-600'
                            }`}>
                              {ai.was_adopted ? 'Adopted' : 'Not adopted'}
                            </span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Parameter Evolution */}
            {result.parameter_evolution && result.parameter_evolution.length > 0 && (
              <div className="border border-gray-200 rounded-xl overflow-hidden">
                <button
                  onClick={() => setShowParamEvolution(!showParamEvolution)}
                  className="w-full px-4 py-3 bg-gray-50 border-b border-gray-200 flex items-center justify-between"
                >
                  <div className="flex items-center gap-2">
                    <Zap className="w-5 h-5 text-blue-600" />
                    <h4 className="font-medium text-gray-900">Parameter Evolution</h4>
                  </div>
                  {showParamEvolution ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
                </button>
                {showParamEvolution && (
                  <div className="divide-y divide-gray-100 max-h-80 overflow-y-auto">
                    {result.parameter_evolution.slice(-10).reverse().map((p, i) => (
                      <div key={i} className="px-4 py-3">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-sm font-medium text-gray-700">
                            {formatDate(p.date)} - {p.strategy_name}
                          </span>
                          <span className={`text-xs px-2 py-1 rounded-full ${
                            p.source === 'ai_generated' ? 'bg-purple-100 text-purple-700' : 'bg-gray-100 text-gray-700'
                          }`}>
                            {p.source === 'ai_generated' ? 'AI' : 'Library'}
                          </span>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          {Object.entries(p.params || {}).slice(0, 6).map(([key, value]) => (
                            <span key={key} className="text-xs bg-gray-100 px-2 py-1 rounded">
                              {key.replace(/_/g, ' ')}: <span className="font-medium">{value}</span>
                            </span>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Trades Executed */}
            {result.trades && result.trades.length > 0 && (
              <div className="border border-emerald-200 rounded-xl overflow-hidden">
                <button
                  onClick={() => setShowTrades(!showTrades)}
                  className="w-full px-4 py-3 bg-gradient-to-r from-emerald-50 to-green-50 border-b border-emerald-200 flex items-center justify-between"
                >
                  <div className="flex items-center gap-2">
                    <BarChart2 className="w-5 h-5 text-emerald-600" />
                    <h4 className="font-medium text-gray-900">Trades Executed</h4>
                    <span className="text-sm text-emerald-600">({result.trades.length} trades)</span>
                    <span className="text-xs text-gray-400 hidden md:inline">• Click any trade to view chart</span>
                  </div>
                  {showTrades ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
                </button>
                {showTrades && (
                  <div className="max-h-96 overflow-y-auto">
                    <table className="w-full text-sm">
                      <thead className="bg-gray-50 sticky top-0">
                        <tr>
                          <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">Symbol</th>
                          <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">Strategy</th>
                          <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">Entry</th>
                          <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">Exit</th>
                          <th className="px-3 py-2 text-right text-xs font-medium text-gray-500">Entry $</th>
                          <th className="px-3 py-2 text-right text-xs font-medium text-gray-500">Exit $</th>
                          <th className="px-3 py-2 text-right text-xs font-medium text-gray-500">P&L %</th>
                          <th className="px-3 py-2 text-right text-xs font-medium text-gray-500">P&L $</th>
                          <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">Reason</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {result.trades.map((trade, i) => (
                          <tr
                            key={i}
                            onClick={() => setSelectedTrade(trade)}
                            className={`cursor-pointer transition-colors hover:bg-blue-50 ${trade.pnl_pct >= 0 ? 'bg-emerald-50/30' : 'bg-red-50/30'}`}
                            title="Click to view chart"
                          >
                            <td className="px-3 py-2 font-medium text-gray-900">
                              <span className="flex items-center gap-1">
                                {trade.symbol}
                                <BarChart2 className="w-3 h-3 text-gray-400" />
                              </span>
                            </td>
                            <td className="px-3 py-2 text-gray-600 text-xs">{trade.strategy_name?.replace('AI-', '')}</td>
                            <td className="px-3 py-2 text-gray-600">{formatDate(trade.entry_date)}</td>
                            <td className="px-3 py-2 text-gray-600">{formatDate(trade.exit_date)}</td>
                            <td className="px-3 py-2 text-right text-gray-600">${trade.entry_price?.toFixed(2)}</td>
                            <td className="px-3 py-2 text-right text-gray-600">${trade.exit_price?.toFixed(2)}</td>
                            <td className={`px-3 py-2 text-right font-medium ${trade.pnl_pct >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                              {trade.pnl_pct >= 0 ? '+' : ''}{trade.pnl_pct?.toFixed(1)}%
                            </td>
                            <td className={`px-3 py-2 text-right font-medium ${trade.pnl_dollars >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                              {trade.pnl_dollars >= 0 ? '+' : ''}${trade.pnl_dollars?.toFixed(0)}
                            </td>
                            <td className="px-3 py-2 text-xs text-gray-500">{trade.exit_reason?.replace('_', ' ')}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Previous Simulations */}
        {history.length > 0 && (
          <div className="border border-gray-200 rounded-xl overflow-hidden">
            <div className="px-4 py-3 bg-gray-50 border-b border-gray-200">
              <h4 className="font-medium text-gray-900">Previous Simulations</h4>
            </div>
            <div className="divide-y divide-gray-200">
              {history.map((sim) => (
                <button
                  key={sim.id}
                  onClick={() => loadSimulation(sim.id)}
                  className="w-full px-4 py-3 flex items-center gap-4 hover:bg-gray-50 text-left"
                >
                  <Calendar size={16} className="text-gray-400" />
                  <span className="text-sm">
                    {formatDate(sim.start_date, { includeYear: true })} - {formatDate(sim.end_date, { includeYear: true })}
                  </span>
                  <span className={`text-sm font-medium ${sim.total_return_pct >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                    {sim.total_return_pct >= 0 ? '+' : ''}{sim.total_return_pct?.toFixed(1)}%
                  </span>
                  <span className="text-xs text-gray-500 ml-auto">
                    {sim.num_strategy_switches} switches
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Trade Chart Modal */}
      {selectedTrade && (
        <TradeChartModal
          trade={selectedTrade}
          onClose={() => setSelectedTrade(null)}
          fetchWithAuth={fetchWithAuth}
        />
      )}
    </div>
  );
}
