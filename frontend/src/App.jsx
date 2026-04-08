import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import {
  LineChart, Line, AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ComposedChart, Bar, ReferenceLine, ReferenceDot, Legend
} from 'recharts';
import {
  TrendingUp, TrendingDown, RefreshCw, Settings, Bell, User, LogOut,
  DollarSign, Target, Shield, Activity, PieChart as PieIcon, History,
  ArrowUpRight, ArrowDownRight, Clock, Zap, X, ChevronRight, Eye,
  Calendar, BarChart3, Wallet, LogIn, AlertCircle, Loader2, CreditCard, Lock,
  Briefcase, Mail, Gift, Copy, Check, Filter, Info
} from 'lucide-react';
import LandingPage from './LandingPage';
import TrackRecordPage from './TrackRecordPage';
import TrackRecord10YPage from './TrackRecord10YPage';
import MarketRegimePage from './MarketRegimePage';
import { PrivacyPage, TermsPage, ContactPage } from './LegalPages';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import LoginModal from './components/LoginModal';
import { formatDate, formatChartDate } from './utils/formatDate';
import AdminDashboard from './components/AdminDashboard';
import SubscriptionBanner from './components/SubscriptionBanner';
import { ForgotPasswordPage, ResetPasswordPage } from './components/PasswordReset';
import CookieConsent from './components/CookieConsent';
import TwoFactorSettings from './components/TwoFactorSettings';
// DoubleSignals, MomentumRankings, ApproachingTrigger removed — absorbed into unified dashboard

// ============================================================================
// API Configuration
// ============================================================================

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// CDN URLs removed — signals served through authenticated API to prevent free access

// localStorage cache keys
const CACHE_KEYS = {
  SIGNALS: 'rigacap_signals_cache',
  POSITIONS: 'rigacap_positions_cache',
  MISSED: 'rigacap_missed_cache',
  BACKTEST: 'rigacap_backtest_cache',
  DASHBOARD: 'rigacap_dashboard_cache',
  VIEW_MODE: 'rigacap_view_mode',
  CACHE_TIME: 'rigacap_cache_time',
  WELCOME_SEEN: 'rigacap_welcome_seen',
  SECTOR_FILTERS: 'rigacap_sector_filters',
  SECTOR_FILTER_OPEN: 'rigacap_sector_filter_open'
};

// Cache duration: 5 minutes for signals, 1 hour for user data
const CACHE_DURATION = {
  SIGNALS: 5 * 60 * 1000,  // 5 minutes
  USER_DATA: 60 * 60 * 1000  // 1 hour
};

// VIX level → human-readable label
const getVixLabel = (vix) => {
  if (vix == null) return { label: 'N/A', color: 'text-gray-400' };
  if (vix < 15) return { label: 'Calm', color: 'text-emerald-600' };
  if (vix < 20) return { label: 'Normal', color: 'text-gray-500' };
  if (vix < 25) return { label: 'Elevated', color: 'text-amber-600' };
  if (vix < 35) return { label: 'High Fear', color: 'text-orange-600' };
  return { label: 'Extreme Fear', color: 'text-red-600' };
};

// Helper to get cached data
const getCache = (key) => {
  try {
    const cached = localStorage.getItem(key);
    if (cached) return JSON.parse(cached);
  } catch (e) {
    console.log('Cache read error:', e);
  }
  return null;
};

// Helper to set cached data
const setCache = (key, data) => {
  try {
    localStorage.setItem(key, JSON.stringify(data));
    localStorage.setItem(CACHE_KEYS.CACHE_TIME + '_' + key, Date.now().toString());
  } catch (e) {
    console.log('Cache write error:', e);
  }
};

// Helper to check if cache is still valid
const isCacheValid = (key, maxAge) => {
  try {
    const cacheTime = localStorage.getItem(CACHE_KEYS.CACHE_TIME + '_' + key);
    if (!cacheTime) return false;
    return (Date.now() - parseInt(cacheTime)) < maxAge;
  } catch (e) {
    return false;
  }
};

const api = {
  _refreshPromise: null,
  _authHeaders() {
    const token = localStorage.getItem('accessToken');
    return token ? { 'Authorization': `Bearer ${token}` } : {};
  },
  async _refreshToken() {
    // Mutex: if a refresh is already in-flight, wait for it instead of firing another
    if (this._refreshPromise) return this._refreshPromise;
    this._refreshPromise = (async () => {
      const refreshToken = localStorage.getItem('refreshToken');
      if (!refreshToken) return false;
      try {
        const res = await fetch(`${API_BASE}/api/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
        if (!res.ok) return false;
        const data = await res.json();
        localStorage.setItem('accessToken', data.access_token);
        if (data.refresh_token) localStorage.setItem('refreshToken', data.refresh_token);
        return true;
      } catch { return false; }
    })();
    try { return await this._refreshPromise; } finally { this._refreshPromise = null; }
  },
  async _fetchWithRetry(endpoint, options = {}) {
    let res = await fetch(`${API_BASE}${endpoint}`, { ...options, headers: { ...options.headers, ...this._authHeaders() } });
    if (res.status === 401 && localStorage.getItem('refreshToken')) {
      const refreshed = await this._refreshToken();
      if (refreshed) {
        res = await fetch(`${API_BASE}${endpoint}`, { ...options, headers: { ...options.headers, ...this._authHeaders() } });
      }
    }
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  },
  async get(endpoint) {
    return this._fetchWithRetry(endpoint);
  },
  async post(endpoint, data) {
    return this._fetchWithRetry(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
  },
  async patch(endpoint, data) {
    return this._fetchWithRetry(endpoint, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
  },
  async delete(endpoint) {
    return this._fetchWithRetry(endpoint, { method: 'DELETE' });
  }
};

// Normalize signal data types (S3 JSON may have strings instead of numbers/booleans)
const normalizeSignal = (signal) => ({
  ...signal,
  signal_strength: typeof signal.signal_strength === 'string' ? parseFloat(signal.signal_strength) : (signal.signal_strength || 0),
  is_strong: signal.is_strong === true || signal.is_strong === 'True' || signal.is_strong === 'true',
  price: typeof signal.price === 'string' ? parseFloat(signal.price) : signal.price,
  dwap: typeof signal.dwap === 'string' ? parseFloat(signal.dwap) : signal.dwap,
  pct_above_dwap: typeof signal.pct_above_dwap === 'string' ? parseFloat(signal.pct_above_dwap) : signal.pct_above_dwap,
  volume: typeof signal.volume === 'string' ? parseInt(signal.volume, 10) : signal.volume,
});

// Note: AuthContext, useAuth, LoginModal, AdminDashboard, SubscriptionBanner
// are now imported from separate files

// ============================================================================
// Components
// ============================================================================

// Custom triangle markers for buy/sell points on charts
const BuyMarker = ({ cx, cy, payload }) => (
  <svg x={cx - 10} y={cy - 20} width={20} height={20} viewBox="0 0 20 20" style={{ cursor: 'pointer' }}>
    <title>BUY POINT: {payload?.date} @ ${payload?.close?.toFixed(2)}</title>
    <polygon
      points="10,2 18,18 2,18"
      fill="#10B981"
      stroke="#059669"
      strokeWidth="1"
    />
    <text x="10" y="14" textAnchor="middle" fontSize="8" fill="white" fontWeight="bold">B</text>
  </svg>
);

const SellMarker = ({ cx, cy, payload }) => (
  <svg x={cx - 10} y={cy} width={20} height={20} viewBox="0 0 20 20" style={{ cursor: 'pointer' }}>
    <title>SELL POINT (+20%): {payload?.date} @ ${payload?.close?.toFixed(2)}</title>
    <polygon
      points="10,18 18,2 2,2"
      fill="#EF4444"
      stroke="#DC2626"
      strokeWidth="1"
    />
    <text x="10" y="12" textAnchor="middle" fontSize="8" fill="white" fontWeight="bold">S</text>
  </svg>
);

// Loading Spinner
const LoadingSpinner = ({ message = "Loading..." }) => (
  <div className="flex flex-col items-center justify-center py-12">
    <Loader2 className="w-8 h-8 text-blue-600 animate-spin mb-3" />
    <p className="text-gray-500">{message}</p>
  </div>
);

// Error Display
const ErrorDisplay = ({ message, onRetry }) => (
  <div className="flex flex-col items-center justify-center py-12">
    <AlertCircle className="w-12 h-12 text-red-400 mb-3" />
    <p className="text-red-600 mb-4">{message}</p>
    {onRetry && (
      <button onClick={onRetry} className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
        Retry
      </button>
    )}
  </div>
);

// LoginModal is now imported from ./components/LoginModal

// Buy Modal Component
const BuyModal = ({ symbol, price, stockInfo, onClose, onBuy, viewMode = 'advanced', timeTravelDate = null }) => {
  const [shares, setShares] = useState(Math.floor(10000 / price)); // Default ~$10k position
  const [entryPrice, setEntryPrice] = useState(price);
  const [submitting, setSubmitting] = useState(false);

  const totalCost = shares * entryPrice;
  const trailingStop = entryPrice * 0.85; // 15% trailing stop

  const handleBuy = async () => {
    setSubmitting(true);
    try {
      const result = await api.post('/api/portfolio/positions', {
        symbol,
        shares,
        price: entryPrice,
        ...(timeTravelDate && { entry_date: timeTravelDate }),
      });
      onBuy(result.position);
      onClose();
    } catch (err) {
      console.error('Buy failed:', err);
      alert('Failed to create position. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-[60] p-4">
      <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100 bg-gradient-to-r from-emerald-500 to-green-600">
          <h2 className="text-xl font-bold text-white">Buy {symbol}</h2>
          {stockInfo?.name && <p className="text-emerald-100 text-sm">{stockInfo.name}</p>}
          {timeTravelDate && <p className="text-emerald-200 text-xs mt-1">Entry date: {timeTravelDate}</p>}
        </div>

        <div className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Number of Shares</label>
            <input
              type="number"
              value={shares}
              onChange={(e) => setShares(Math.max(1, parseInt(e.target.value) || 0))}
              className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
              min="1"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Entry Price</label>
            <input
              type="number"
              step="0.01"
              value={entryPrice}
              onChange={(e) => setEntryPrice(parseFloat(e.target.value) || 0)}
              className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
            />
          </div>

          <div className="bg-gray-50 rounded-xl p-4 space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-gray-500">Total Cost</span>
              <span className="font-semibold">${totalCost.toLocaleString(undefined, { maximumFractionDigits: 2 })}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-gray-500">{viewMode === 'simple' ? '15% Safety Net' : 'Trailing Stop (15%)'}</span>
              <span className="text-red-500 font-medium">${trailingStop.toFixed(2)}</span>
            </div>
            {viewMode !== 'simple' && (
              <div className="flex justify-between text-sm">
                <span className="text-gray-500">Exit Strategy</span>
                <span className="text-gray-600 font-medium">Let winners run</span>
              </div>
            )}
          </div>
        </div>

        <div className="px-6 py-4 border-t border-gray-100 flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-3 text-gray-600 hover:bg-gray-100 rounded-xl font-medium"
          >
            Cancel
          </button>
          <button
            onClick={handleBuy}
            disabled={submitting || shares < 1 || entryPrice <= 0}
            className="flex-1 px-4 py-3 bg-emerald-600 text-white rounded-xl font-medium hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <DollarSign size={18} />}
            {submitting ? 'Saving...' : 'Track Position'}
          </button>
        </div>
      </div>
    </div>
  );
};

// Sell Modal Component (for closing positions)
const SellModal = ({ symbol, position, currentPrice, stockInfo, onClose, onSell }) => {
  const [shares, setShares] = useState(position?.shares || 0);
  const [exitPrice, setExitPrice] = useState(currentPrice);
  const [submitting, setSubmitting] = useState(false);

  const entryPrice = position?.entry_price || 0;
  const totalProceeds = shares * exitPrice;
  const totalCost = shares * entryPrice;
  const pnl = totalProceeds - totalCost;
  const pnlPct = entryPrice > 0 ? ((exitPrice - entryPrice) / entryPrice) * 100 : 0;

  const handleSell = async () => {
    setSubmitting(true);
    try {
      await api.delete(`/api/portfolio/positions/${position.id}?exit_price=${exitPrice}`);
      onSell();
      onClose();
    } catch (err) {
      console.error('Sell failed:', err);
      alert('Failed to close position. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-[60] p-4">
      <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full overflow-hidden">
        <div className={`px-6 py-4 border-b border-gray-100 ${pnl >= 0 ? 'bg-gradient-to-r from-emerald-500 to-green-600' : 'bg-gradient-to-r from-red-500 to-rose-600'}`}>
          <h2 className="text-xl font-bold text-white">Sell {symbol}</h2>
          {stockInfo?.name && <p className="text-white/80 text-sm">{stockInfo.name}</p>}
        </div>

        <div className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Number of Shares</label>
            <input
              type="number"
              value={shares}
              onChange={(e) => setShares(Math.max(0, Math.min(position?.shares || 0, parseFloat(e.target.value) || 0)))}
              className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
              max={position?.shares || 0}
            />
            <p className="text-xs text-gray-400 mt-1">Max: {position?.shares || 0} shares</p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Exit Price</label>
            <input
              type="number"
              step="0.01"
              value={exitPrice}
              onChange={(e) => setExitPrice(parseFloat(e.target.value) || 0)}
              className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
            />
          </div>

          <div className="bg-gray-50 rounded-xl p-4 space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-gray-500">Entry Price</span>
              <span className="font-medium">${entryPrice.toFixed(2)}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-gray-500">Total Proceeds</span>
              <span className="font-semibold">${totalProceeds.toLocaleString(undefined, { maximumFractionDigits: 2 })}</span>
            </div>
            <div className="border-t border-gray-200 my-2"></div>
            <div className="flex justify-between text-sm">
              <span className="text-gray-500">Profit/Loss</span>
              <span className={`font-bold ${pnl >= 0 ? 'text-emerald-600' : 'text-red-500'}`}>
                {pnl >= 0 ? '+' : ''}{pnl.toLocaleString(undefined, { maximumFractionDigits: 2 })} ({pnlPct >= 0 ? '+' : ''}{pnlPct.toFixed(1)}%)
              </span>
            </div>
          </div>
        </div>

        <div className="px-6 py-4 border-t border-gray-100 flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-3 text-gray-600 hover:bg-gray-100 rounded-xl font-medium"
          >
            Cancel
          </button>
          <button
            onClick={handleSell}
            disabled={submitting || shares <= 0 || exitPrice <= 0}
            className={`flex-1 px-4 py-3 text-white rounded-xl font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 ${pnl >= 0 ? 'bg-emerald-600 hover:bg-emerald-700' : 'bg-red-600 hover:bg-red-700'}`}
          >
            {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <DollarSign size={18} />}
            {submitting ? 'Selling...' : 'Confirm Sale'}
          </button>
        </div>
      </div>
    </div>
  );
};

// Stock Chart Modal
const StockChartModal = ({ symbol, type, data, onClose, onAction, liveQuote, viewMode = 'advanced', timeTravelDate = null }) => {
  const [timeRange, setTimeRange] = useState('1Y');
  const [priceData, setPriceData] = useState([]);
  const [stockInfo, setStockInfo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showBuyModal, setShowBuyModal] = useState(false);
  const [showSellModal, setShowSellModal] = useState(false);
  const [currentLiveQuote, setCurrentLiveQuote] = useState(liveQuote);

  // Poll for live quote updates while modal is open
  useEffect(() => {
    const fetchLiveQuote = async () => {
      try {
        const response = await api.get(`/api/quotes/live?symbols=${symbol}`);
        if (response.quotes?.[symbol]) {
          setCurrentLiveQuote(response.quotes[symbol]);
        }
      } catch (err) {
        // Silently fail - live quotes are optional
      }
    };

    // Initial fetch and poll every 15 seconds while modal is open
    fetchLiveQuote();
    const interval = setInterval(fetchLiveQuote, 15000);
    return () => clearInterval(interval);
  }, [symbol]);

  // Fetch company info once when modal opens
  useEffect(() => {
    const fetchInfo = async () => {
      try {
        const info = await api.get(`/api/signals/info/${symbol}`);
        setStockInfo(info);
      } catch (err) {
        console.log('Could not fetch stock info');
      }
    };
    fetchInfo();
  }, [symbol]);

  useEffect(() => {
    const fetchHistory = async () => {
      setLoading(true);
      setError(null);
      try {
        // For missed opportunities, fetch enough data to show the transaction window
        let days = { '1M': 30, '3M': 90, '6M': 180, '1Y': 252, '2Y': 504 }[timeRange] || 252;

        // For missed opportunities, we need enough data to cover entry_date - 30 days
        if (type === 'missed' && data?.entry_date) {
          const entryDate = new Date(data.entry_date);
          const today = new Date();
          const daysSinceEntry = Math.ceil((today - entryDate) / (1000 * 60 * 60 * 24));
          days = Math.max(days, daysSinceEntry + 60); // Extra buffer for 30 days before entry
        }

        const response = await api.get(`/api/stock/${symbol}/history?days=${days}`);
        let chartData = response.data || [];

        // For missed opportunities, filter to show transaction window (30 days before buy, 30 days after sell)
        if (type === 'missed' && data?.entry_date && data?.sell_date) {
          const entryDate = new Date(data.entry_date);
          const sellDate = new Date(data.sell_date);
          const windowStart = new Date(entryDate);
          windowStart.setDate(windowStart.getDate() - 30);
          const windowEnd = new Date(sellDate);
          windowEnd.setDate(windowEnd.getDate() + 30);

          chartData = chartData.filter(d => {
            const date = new Date(d.date);
            return date >= windowStart && date <= windowEnd;
          });
        }

        setPriceData(chartData);
      } catch (err) {
        setError('Failed to load chart data');
        setPriceData([]);
      } finally {
        setLoading(false);
      }
    };
    fetchHistory();
  }, [symbol, timeRange, type, data?.entry_date, data?.sell_date]);

  // Format market cap for display
  const formatMarketCap = (mcap) => {
    if (!mcap) return '';
    const num = parseFloat(mcap.replace(/,/g, ''));
    if (isNaN(num)) return mcap;
    if (num >= 1e12) return `$${(num / 1e12).toFixed(2)}T`;
    if (num >= 1e9) return `$${(num / 1e9).toFixed(1)}B`;
    if (num >= 1e6) return `$${(num / 1e6).toFixed(0)}M`;
    return `$${num.toLocaleString()}`;
  };

  // Use live quote if available, otherwise fall back to chart data
  const livePrice = currentLiveQuote?.price;
  const currentPrice = livePrice || priceData[priceData.length - 1]?.close || data?.current_price || data?.price || 0;
  const startPrice = priceData[0]?.close || currentPrice;
  const changePct = startPrice > 0 ? ((currentPrice - startPrice) / startPrice * 100).toFixed(1) : 0;
  const isPositive = changePct >= 0;

  // Add live price point to chart data if available
  const chartDataWithLive = livePrice && priceData.length > 0
    ? [...priceData, {
        date: new Date().toISOString().split('T')[0],
        close: livePrice,
        open: livePrice,
        high: livePrice,
        low: livePrice,
        isLive: true, // Flag for special rendering
      }]
    : priceData;

  // Find entry point index for positions
  const entryPointIndex = type === 'position' && data?.entry_date
    ? chartDataWithLive.findIndex(d => d.date === data.entry_date)
    : -1;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl max-w-4xl w-full max-h-[90vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-100 relative flex-shrink-0">
          {/* Close button - top right */}
          <button onClick={onClose} className="absolute top-4 right-4 p-2 hover:bg-gray-100 rounded-lg z-10">
            <X size={24} className="text-gray-400" />
          </button>

          <div className="pr-12">
            <div className="flex items-center gap-3 flex-wrap">
              <h2 className="text-2xl font-bold text-gray-900">{symbol}</h2>
              {data?.is_strong && (
                <span className="px-2 py-1 bg-emerald-100 text-emerald-700 text-xs font-semibold rounded-full flex items-center gap-1">
                  <Zap size={12} /> STRONG SIGNAL
                </span>
              )}
              {type === 'position' && (
                <span className="px-2 py-1 bg-blue-100 text-blue-700 text-xs font-semibold rounded-full">
                  OPEN POSITION
                </span>
              )}
              {type === 'missed' && (
                <span className="px-2 py-1 bg-amber-100 text-amber-700 text-xs font-semibold rounded-full flex items-center gap-1">
                  <Clock size={12} /> MISSED +{data?.would_be_return?.toFixed(0) || '?'}%
                </span>
              )}
              {data?.signal_strength > 0 && (
                <span className={`px-2 py-1 text-xs font-semibold rounded-full ${
                  data.signal_strength >= 70 ? 'bg-emerald-100 text-emerald-700' :
                  data.signal_strength >= 50 ? 'bg-blue-100 text-blue-700' :
                  'bg-yellow-100 text-yellow-700'
                }`}>
                  Strength: {data.signal_strength.toFixed(0)}
                </span>
              )}
            </div>
            {/* Company Name & Sector */}
            {stockInfo?.name && (
              <div className="mt-1">
                <p className="text-gray-600 text-sm">{stockInfo.name}</p>
                {stockInfo?.sector && (
                  <span className="inline-block mt-1 px-2 py-0.5 bg-indigo-100 text-indigo-700 text-xs font-medium rounded-full">
                    {stockInfo.sector}{stockInfo?.industry ? ` - ${stockInfo.industry}` : ''}
                  </span>
                )}
              </div>
            )}
            <div className="flex items-center gap-4 mt-2">
              <span className="text-2xl font-semibold">${currentPrice.toFixed(2)}</span>
              {currentLiveQuote && (
                <span className={`flex items-center text-sm font-medium ${currentLiveQuote.change_pct >= 0 ? 'text-emerald-600' : 'text-red-500'}`}>
                  {currentLiveQuote.change_pct >= 0 ? <ArrowUpRight size={16} /> : <ArrowDownRight size={16} />}
                  {currentLiveQuote.change_pct >= 0 ? '+' : ''}{currentLiveQuote.change_pct?.toFixed(2)}% today
                </span>
              )}
              <span className={`flex items-center text-sm font-medium ${isPositive ? 'text-emerald-600' : 'text-red-500'}`}>
                {isPositive ? <ArrowUpRight size={16} /> : <ArrowDownRight size={16} />}
                {isPositive ? '+' : ''}{changePct}% ({timeRange})
              </span>
              {currentLiveQuote && (
                <span className="flex items-center gap-1 text-xs text-blue-500">
                  <Activity size={12} className="animate-pulse" /> Live
                </span>
              )}
              {stockInfo?.market_cap && (
                <span className="text-sm text-gray-500">
                  Market Cap: {formatMarketCap(stockInfo.market_cap)}
                </span>
              )}
            </div>
            {/* Company Description - scrollable */}
            {stockInfo?.description && (
              <div className="mt-2 max-h-20 overflow-y-auto">
                <p className="text-sm text-gray-500">{stockInfo.description}</p>
              </div>
            )}
          </div>
        </div>

        {/* Scrollable content area */}
        <div className="flex-1 overflow-y-auto">
          {/* Time Range */}
          <div className="px-6 py-3 border-b border-gray-100 flex gap-2 items-center">
          {type === 'missed' ? (
            <div className="flex items-center gap-2">
              <span className="px-4 py-1.5 rounded-lg text-sm font-medium bg-amber-100 text-amber-700">
                Transaction Window
              </span>
              <span className="text-sm text-gray-500">
                {formatDate(data?.entry_date)} → {formatDate(data?.sell_date)} (±30 days)
              </span>
            </div>
          ) : (
            ['1M', '3M', '6M', '1Y', '2Y'].map((range) => (
              <button
                key={range}
                onClick={() => setTimeRange(range)}
                className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  timeRange === range ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                {range}
              </button>
            ))
          )}
        </div>

        {/* Chart */}
        <div className="p-6">
          {loading ? (
            <LoadingSpinner message="Loading chart data..." />
          ) : error ? (
            <ErrorDisplay message={error} />
          ) : priceData.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              <BarChart3 className="w-12 h-12 mx-auto text-gray-300 mb-3" />
              <p>No price data available</p>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={320}>
              <ComposedChart data={chartDataWithLive}>
                <defs>
                  <linearGradient id="priceGradient" x1="0" y1="0" x2="0" y2="1">
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
                  interval={Math.floor(priceData.length / 6)}
                />
                <YAxis
                  yAxisId="price"
                  tick={{ fontSize: 11 }}
                  stroke="#9CA3AF"
                  domain={['dataMin - 10', 'dataMax + 10']}
                  tickFormatter={(val) => `$${val.toFixed(0)}`}
                />
                {viewMode !== 'simple' && (
                  <YAxis
                    yAxisId="volume"
                    orientation="right"
                    tick={{ fontSize: 10 }}
                    stroke="#D1D5DB"
                    tickFormatter={(val) => `${(val / 1000000).toFixed(0)}M`}
                  />
                )}
                <Tooltip
                  content={({ active, payload, label }) => {
                    if (!active || !payload?.length) return null;
                    const d = payload[0]?.payload;
                    const isEntryDay = d?.date === data?.entry_date;
                    const isSellDay = d?.date === data?.sell_date;
                    const borderClass = isEntryDay ? 'border-emerald-400 border-2' :
                                       isSellDay ? 'border-amber-400 border-2' : 'border-gray-200';
                    if (viewMode === 'simple') {
                      return (
                        <div className={`bg-white p-3 rounded-lg shadow-lg border ${borderClass} text-sm`}>
                          <p className="font-medium text-gray-900 mb-1">{formatDate(label)}</p>
                          <p className="text-blue-600">Price: ${d?.close?.toFixed(2)}</p>
                          {isEntryDay && <p className="text-emerald-600 font-medium">Entry Point</p>}
                          {isSellDay && <p className="text-amber-600 font-medium">Exit Point</p>}
                          {d?.isLive && <p className="text-blue-500 font-medium">Live Price</p>}
                        </div>
                      );
                    }
                    return (
                      <div className={`bg-white p-3 rounded-lg shadow-lg border ${borderClass} text-sm`}>
                        <p className="font-medium text-gray-900 mb-1">
                          {formatDate(label)}
                          {isEntryDay && <span className="ml-2 text-emerald-600 font-bold">BUY POINT</span>}
                          {isSellDay && <span className="ml-2 text-amber-600 font-bold">SELL POINT (+20%)</span>}
                        </p>
                        <p className="text-blue-600">Price: ${d?.close?.toFixed(2)}</p>
                        {isEntryDay && data?.entry_price && (
                          <p className="text-emerald-600 font-medium">Entry: ${data.entry_price.toFixed(2)}</p>
                        )}
                        {isSellDay && data?.sell_price && (
                          <p className="text-amber-600 font-medium">Exit: ${data.sell_price.toFixed(2)}</p>
                        )}
                        {d?.dwap && (
                          <>
                            <p className="text-purple-600">Wtd Avg: ${d.dwap.toFixed(2)}</p>
                            <p className="text-yellow-600">Breakout (+5%): ${(d.dwap * 1.05).toFixed(2)}</p>
                          </>
                        )}
                        {d?.ma_50 && <p className="text-orange-500">MA50: ${d.ma_50.toFixed(2)}</p>}
                        {d?.volume > 0 && <p className="text-gray-400">Vol: {(d.volume / 1000000).toFixed(1)}M</p>}
                        {d?.isLive && <p className="text-blue-500 font-medium">Live Price</p>}
                      </div>
                    );
                  }}
                />
                {viewMode !== 'simple' && <Bar yAxisId="volume" dataKey="volume" fill="#E5E7EB" opacity={0.5} />}
                {viewMode !== 'simple' && chartDataWithLive.some(d => d.dwap) && (
                  <>
                    <Line yAxisId="price" type="monotone" dataKey="dwap" stroke="#8B5CF6" strokeWidth={2} dot={false} name="Wtd Avg" />
                    {/* Breakout trigger line (+5% above weighted avg) */}
                    <Line
                      yAxisId="price"
                      type="monotone"
                      dataKey={(d) => d.dwap ? d.dwap * 1.05 : null}
                      stroke="#FBBF24"
                      strokeWidth={2}
                      strokeDasharray="6 3"
                      dot={false}
                      name="Breakout +5%"
                      connectNulls={false}
                    />
                  </>
                )}
                {viewMode !== 'simple' && chartDataWithLive.some(d => d.ma_50) && (
                  <Line yAxisId="price" type="monotone" dataKey="ma_50" stroke="#F97316" strokeWidth={1.5} dot={false} strokeDasharray="5 5" name="MA50" />
                )}
                <Area yAxisId="price" type="monotone" dataKey="close" stroke="#3B82F6" strokeWidth={2} fill="url(#priceGradient)" name="Price" />

                {/* Reference lines with smart label placement to avoid overlaps */}
                {(() => {
                  // Collect all active reference lines with their y-values
                  const lines = [];
                  const entryPrice = data?.entry_price;
                  const basePrice = entryPrice || data?.price;

                  if ((type === 'position' || type === 'missed') && entryPrice) {
                    lines.push({ id: 'buy', y: entryPrice });
                  }
                  if (type === 'missed' && data?.sell_price) {
                    lines.push({ id: 'sell', y: data.sell_price });
                  }
                  if (data?.trailing_stop_level) {
                    lines.push({ id: 'stop', y: data.trailing_stop_level });
                  }
                  if (data?.high_water_mark && entryPrice && data.high_water_mark > entryPrice * 1.01) {
                    lines.push({ id: 'high', y: data.high_water_mark });
                  }
                  if (basePrice && (type === 'position' || type === 'signal')) {
                    lines.push({ id: 'gain20', y: basePrice * 1.20 });
                  }

                  // Include the current price (last point of the price line) as a
                  // collision source — right-aligned labels sit where the price line ends
                  const lastClose = chartDataWithLive.length > 0
                    ? chartDataWithLive[chartDataWithLive.length - 1]?.close
                    : null;
                  if (lastClose) {
                    lines.push({ id: '_price', y: lastClose });
                  }

                  // For each line, check if its default label position would be
                  // intersected by another line OR the price line. If so, flip.
                  // "Close" = within 3% of the line's price (label height zone).
                  const closenessThreshold = 0.03;

                  const hasConflict = (myY, myId, side) => {
                    // side: 'above' or 'below' — check if another line sits in that zone
                    if (!myY) return false;
                    return lines.some(l => {
                      if (l.id === myId) return false;
                      const diff = (l.y - myY) / myY;
                      if (side === 'above') return diff > 0 && diff < closenessThreshold;
                      return diff < 0 && diff > -closenessThreshold;
                    });
                  };

                  // Also check if the price line crosses through the label zone
                  // (price is within threshold on either side of the reference line)
                  const priceCrosses = (myY, myId) => {
                    if (!myY || !lastClose) return false;
                    if (myId === '_price') return false;
                    const diff = Math.abs(lastClose - myY) / myY;
                    return diff < closenessThreshold;
                  };

                  // Default positions and their flip logic
                  // Buy: label above left, flip below if another line/price is just above
                  const buyConflictAbove = hasConflict(entryPrice, 'buy', 'above') || priceCrosses(entryPrice, 'buy');
                  const buyPos = !buyConflictAbove ? 'insideTopLeft' : 'insideBottomLeft';

                  // High: label above right, flip below if crowded or price crosses
                  const highY = data?.high_water_mark;
                  const highConflictAbove = hasConflict(highY, 'high', 'above') || priceCrosses(highY, 'high');
                  const highPos = !highConflictAbove ? 'insideTopRight' : 'insideBottomRight';

                  // Stop: label below right, flip above if crowded or price crosses
                  const stopY = data?.trailing_stop_level;
                  const stopConflictBelow = hasConflict(stopY, 'stop', 'below') || priceCrosses(stopY, 'stop');
                  const stopPos = !stopConflictBelow ? 'insideBottomRight' : 'insideTopRight';

                  // +20%: label above right, flip below if crowded or price crosses
                  const gain20Y = basePrice ? basePrice * 1.20 : 0;
                  const gain20ConflictAbove = hasConflict(gain20Y, 'gain20', 'above') || priceCrosses(gain20Y, 'gain20');
                  const gain20Pos = !gain20ConflictAbove ? 'insideTopRight' : 'insideBottomRight';

                  // Sell (missed): label above right, flip if crowded or price crosses
                  const sellY = data?.sell_price;
                  const sellConflictAbove = hasConflict(sellY, 'sell', 'above') || priceCrosses(sellY, 'sell');
                  const sellPos = !sellConflictAbove ? 'insideTopRight' : 'insideBottomRight';

                  return (
                    <>
                      {/* Entry/Buy price */}
                      {(type === 'position' || type === 'missed') && entryPrice && (
                        <ReferenceLine
                          yAxisId="price"
                          y={entryPrice}
                          stroke="#10B981"
                          strokeWidth={2}
                          strokeDasharray="8 4"
                          label={{
                            value: `Buy $${entryPrice.toFixed(2)}`,
                            fill: '#10B981',
                            fontWeight: 'bold',
                            fontSize: 12,
                            position: buyPos
                          }}
                        />
                      )}

                      {/* Exit/Sell price (missed opportunities) */}
                      {type === 'missed' && sellY && (
                        <ReferenceLine
                          yAxisId="price"
                          y={sellY}
                          stroke="#F59E0B"
                          strokeWidth={2}
                          strokeDasharray="8 4"
                          label={{
                            value: `Sell $${sellY.toFixed(2)}${data?.exit_reason ? ` (${{'trailing_stop':'trailing stop','rebalance_exit':'portfolio rebalance','simulation_end':'portfolio rebalance','profit_target':'profit target','stop_loss':'stop loss'}[data.exit_reason] || data.exit_reason.replace(/_/g, ' ')})` : ''}`,
                            fill: '#F59E0B',
                            fontWeight: 'bold',
                            fontSize: 12,
                            position: sellPos
                          }}
                        />
                      )}

                      {/* Trailing stop */}
                      {stopY && (
                        <ReferenceLine
                          yAxisId="price"
                          y={stopY}
                          stroke="#EF4444"
                          strokeWidth={1.5}
                          strokeDasharray="4 4"
                          label={{
                            value: `Trailing Stop $${stopY.toFixed(2)}`,
                            fill: '#EF4444',
                            fontSize: 10,
                            position: stopPos
                          }}
                        />
                      )}

                      {/* High water mark */}
                      {highY && entryPrice && highY > entryPrice * 1.01 && (
                        <ReferenceLine
                          yAxisId="price"
                          y={highY}
                          stroke="#8B5CF6"
                          strokeWidth={1}
                          strokeDasharray="3 3"
                          label={{
                            value: `High $${highY.toFixed(2)}`,
                            fill: '#8B5CF6',
                            fontSize: 10,
                            position: highPos
                          }}
                        />
                      )}

                      {/* +20% gain reference */}
                      {basePrice && (type === 'position' || type === 'signal') && (
                        <ReferenceLine
                          yAxisId="price"
                          y={gain20Y}
                          stroke="#10B981"
                          strokeWidth={1}
                          strokeDasharray="6 4"
                          label={{
                            value: `+20% $${gain20Y.toFixed(2)}`,
                            fill: '#10B981',
                            fontSize: 10,
                            position: gain20Pos
                          }}
                        />
                      )}
                    </>
                  );
                })()}

                {/* Buy point marker - triangle at entry date */}
                {(() => {
                  if (!data?.entry_date || chartDataWithLive.length === 0) return null;

                  // Normalize entry date to YYYY-MM-DD format for comparison
                  const entryDateStr = data.entry_date.split('T')[0];

                  // Find exact match or closest date on/after entry date
                  let entryMatch = chartDataWithLive.find(d => d.date === entryDateStr);
                  if (!entryMatch) {
                    // Find closest date on or after entry_date (entry might be on weekend/holiday)
                    entryMatch = chartDataWithLive.find(d => d.date >= entryDateStr);
                  }
                  if (!entryMatch) {
                    // If entry is before all chart data, don't show marker (it's out of view)
                    return null;
                  }

                  // Use actual entry_price for y position (not close price which may differ)
                  const yPrice = data.entry_price || entryMatch.close;
                  if (!yPrice || !entryMatch.date) return null;

                  return (
                    <ReferenceDot
                      yAxisId="price"
                      x={entryMatch.date}
                      y={yPrice}
                      shape={(props) => <BuyMarker {...props} payload={{...entryMatch, close: yPrice}} />}
                    />
                  );
                })()}

                {/* Sell point marker - triangle at sell date (for trades) */}
                {(() => {
                  if (!data?.sell_date || chartDataWithLive.length === 0) return null;

                  // Normalize sell date to YYYY-MM-DD format for comparison
                  const sellDateStr = data.sell_date.split('T')[0];

                  // Find exact match or closest date on/after sell date
                  let sellMatch = chartDataWithLive.find(d => d.date === sellDateStr);
                  if (!sellMatch) {
                    sellMatch = chartDataWithLive.find(d => d.date >= sellDateStr);
                  }
                  if (!sellMatch) {
                    // If sell date is after all chart data, use last point
                    sellMatch = chartDataWithLive[chartDataWithLive.length - 1];
                  }
                  if (!sellMatch?.date) return null;
                  return sellMatch ? (
                    <ReferenceDot
                      yAxisId="price"
                      x={sellMatch.date}
                      y={sellMatch.close || data.sell_price}
                      shape={(props) => <SellMarker {...props} payload={sellMatch} />}
                    />
                  ) : null;
                })()}

                {/* Signal point marker - triangle at current date for NEW signals only (not missed opportunities) */}
                {type === 'signal' && !data?.exit_date && chartDataWithLive.length > 0 && !livePrice && (
                  <ReferenceDot
                    yAxisId="price"
                    x={chartDataWithLive[chartDataWithLive.length - 1]?.date}
                    y={chartDataWithLive[chartDataWithLive.length - 1]?.close}
                    shape={BuyMarker}
                  />
                )}

                {/* DWAP breakout date vertical line */}
                {type === 'signal' && data?.dwap_crossover_date && (() => {
                  const dateStr = data.dwap_crossover_date.split('T')[0];
                  const match = chartDataWithLive.find(d => d.date === dateStr) || chartDataWithLive.find(d => d.date >= dateStr);
                  if (!match) return null;
                  return (
                    <ReferenceLine
                      yAxisId="price"
                      x={match.date}
                      stroke="#C9A54E"
                      strokeWidth={1}
                      strokeDasharray="6 4"
                      label={{ value: 'BREAKOUT', fill: '#C9A54E', fontSize: 10, position: 'top' }}
                    />
                  );
                })()}

                {/* Ensemble entry date vertical line */}
                {type === 'signal' && data?.ensemble_entry_date && (() => {
                  const dateStr = data.ensemble_entry_date.split('T')[0];
                  const match = chartDataWithLive.find(d => d.date === dateStr) || chartDataWithLive.find(d => d.date >= dateStr);
                  if (!match) return null;
                  return (
                    <ReferenceLine
                      yAxisId="price"
                      x={match.date}
                      stroke="#22C55E"
                      strokeWidth={1}
                      strokeDasharray="6 4"
                      label={{ value: 'ENTRY', fill: '#22C55E', fontSize: 10, position: 'top' }}
                    />
                  );
                })()}

                {/* Live price marker - pulsing dot at current live price */}
                {livePrice && chartDataWithLive.length > 0 && (
                  <ReferenceDot
                    yAxisId="price"
                    x={chartDataWithLive[chartDataWithLive.length - 1]?.date}
                    y={livePrice}
                    r={8}
                    fill="#3B82F6"
                    stroke="#fff"
                    strokeWidth={2}
                  />
                )}
              </ComposedChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Details */}
        <div className="px-6 py-4 bg-gray-50 border-t border-gray-100">
          {/* Recommendation banner */}
          {data?.recommendation && (
            <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg text-sm text-blue-800">
              <strong>Recommendation:</strong> {data.recommendation}
            </div>
          )}

          <div className={`grid ${viewMode === 'simple' ? 'grid-cols-2' : 'grid-cols-2 sm:grid-cols-4'} gap-4`}>
            {type === 'signal' ? (
              viewMode === 'simple' ? (
                <>
                  <div className="text-center">
                    <p className="text-sm text-gray-500">Price</p>
                    <p className="text-lg font-semibold">${data?.price?.toFixed(2)}</p>
                  </div>
                  <div className="text-center">
                    <p className="text-sm text-gray-500">Potential</p>
                    <p className="text-lg font-semibold text-emerald-600">Strong</p>
                  </div>
                </>
              ) : (
                <>
                  <div className="text-center">
                    <p className="text-sm text-gray-500">Breakout</p>
                    <p className="text-lg font-semibold text-emerald-600">+{data?.pct_above_dwap}%</p>
                  </div>
                  <div className="text-center">
                    <p className="text-sm text-gray-500">Mom Rank</p>
                    <p className={`text-lg font-semibold ${data?.momentum_rank <= 5 ? 'text-emerald-600' : 'text-gray-700'}`}>#{data?.momentum_rank || '-'}</p>
                  </div>
                  <div className="text-center">
                    <p className="text-sm text-gray-500">Trailing Stop</p>
                    <p className="text-lg font-semibold text-red-500">15%</p>
                  </div>
                  <div className="text-center">
                    <p className="text-sm text-gray-500">+20% Gain</p>
                    <p className="text-lg font-semibold text-emerald-600">${data?.price ? (data.price * 1.20).toFixed(2) : '-'}</p>
                  </div>
                </>
              )
            ) : type === 'missed' ? (
              viewMode === 'simple' ? (
                <>
                  <div className="text-center">
                    <p className="text-sm text-gray-500">Return</p>
                    <p className="text-lg font-semibold text-emerald-600">
                      +{data?.would_be_return?.toFixed(1)}%
                    </p>
                  </div>
                  <div className="text-center">
                    <p className="text-sm text-gray-500">Days Held</p>
                    <p className="text-lg font-semibold">{data?.days_held || '-'}</p>
                  </div>
                </>
              ) : (
                <>
                  <div className="text-center">
                    <p className="text-sm text-gray-500">Buy Date</p>
                    <p className="text-lg font-semibold">{formatDate(data?.entry_date)}</p>
                    <p className="text-xs text-emerald-600">${data?.entry_price?.toFixed(2)}</p>
                  </div>
                  <div className="text-center">
                    <p className="text-sm text-gray-500">Sell Date</p>
                    <p className="text-lg font-semibold">{formatDate(data?.sell_date)}</p>
                    <p className="text-xs text-emerald-600">${data?.sell_price?.toFixed(2)}</p>
                  </div>
                  <div className="text-center">
                    <p className="text-sm text-gray-500">Return</p>
                    <p className="text-lg font-semibold text-emerald-600">
                      +{data?.would_be_return?.toFixed(1)}%
                    </p>
                  </div>
                  <div className="text-center">
                    <p className="text-sm text-gray-500">Days Held</p>
                    <p className="text-lg font-semibold">{data?.days_held || '-'}</p>
                  </div>
                </>
              )
            ) : (
              viewMode === 'simple' ? (
                <>
                  <div className="text-center">
                    <p className="text-sm text-gray-500">Price</p>
                    <p className="text-lg font-semibold">${data?.current_price?.toFixed(2) || data?.entry_price?.toFixed(2)}</p>
                  </div>
                  <div className="text-center">
                    <p className="text-sm text-gray-500">P&L</p>
                    <p className={`text-lg font-semibold ${data?.pnl_pct >= 0 ? 'text-emerald-600' : 'text-red-500'}`}>
                      {data?.pnl_pct >= 0 ? '+' : ''}{data?.pnl_pct?.toFixed(1)}%
                    </p>
                  </div>
                </>
              ) : (
                <>
                  <div className="text-center">
                    <p className="text-sm text-gray-500">Entry Price</p>
                    <p className="text-lg font-semibold">${data?.entry_price?.toFixed(2)}</p>
                    <p className="text-xs text-gray-400">{formatDate(data?.entry_date)}</p>
                  </div>
                  <div className="text-center">
                    <p className="text-sm text-gray-500">Current P&L</p>
                    <p className={`text-lg font-semibold ${data?.pnl_pct >= 0 ? 'text-emerald-600' : 'text-red-500'}`}>
                      {data?.pnl_pct >= 0 ? '+' : ''}{data?.pnl_pct?.toFixed(1)}%
                    </p>
                    <p className={`text-xs ${data?.pnl_dollars >= 0 ? 'text-emerald-500' : 'text-red-400'}`}>
                      ${data?.pnl_dollars?.toFixed(0) || ((data?.current_price - data?.entry_price) * data?.shares).toFixed(0)}
                    </p>
                  </div>
                  <div className="text-center">
                    <p className="text-sm text-gray-500">Trailing Stop</p>
                    <p className="text-lg font-semibold text-red-500">
                      {data?.trailing_stop_level ? `$${data.trailing_stop_level.toFixed(2)}` : '-'}
                    </p>
                    {data?.distance_to_stop_pct != null && (
                      <p className={`text-xs ${data.distance_to_stop_pct < 5 ? 'text-red-400' : 'text-gray-400'}`}>
                        {data.distance_to_stop_pct.toFixed(1)}% away
                      </p>
                    )}
                  </div>
                  <div className="text-center">
                    <p className="text-sm text-gray-500">High Water</p>
                    <p className="text-lg font-semibold text-purple-600">
                      {data?.high_water_mark ? `$${data.high_water_mark.toFixed(2)}` : '-'}
                    </p>
                  </div>
                </>
              )
            )}
          </div>

          {/* Technical Indicators - Signal only, Advanced mode only */}
          {viewMode !== 'simple' && type === 'signal' && (data?.ma_50 || stockInfo?.ma_50) && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-4 pt-4 border-t border-gray-200">
              <div className="text-center">
                <p className="text-sm text-gray-500">50-Day MA</p>
                <p className="text-lg font-semibold">${(data?.ma_50 || stockInfo?.ma_50)?.toFixed(2)}</p>
              </div>
              <div className="text-center">
                <p className="text-sm text-gray-500">200-Day MA</p>
                <p className="text-lg font-semibold">${(data?.ma_200 || stockInfo?.ma_200)?.toFixed(2)}</p>
              </div>
              <div className="text-center">
                <p className="text-sm text-gray-500">52-Week High</p>
                <p className="text-lg font-semibold">${(data?.high_52w || stockInfo?.high_52w)?.toFixed(2)}</p>
              </div>
              <div className="text-center">
                <p className="text-sm text-gray-500">Weighted Avg</p>
                <p className="text-lg font-semibold">${data?.dwap?.toFixed(2)}</p>
              </div>
            </div>
          )}
        </div>
        </div>

        {/* Actions - fixed footer */}
        <div className="px-6 py-4 border-t border-gray-100 flex justify-end gap-3 flex-shrink-0 bg-white">
          <button onClick={onClose} className="px-6 py-2.5 text-gray-600 hover:bg-gray-100 rounded-xl font-medium">
            Close
          </button>
          {type === 'signal' && !data?.exit_date && (
            <button
              onClick={() => setShowBuyModal(true)}
              className="px-6 py-2.5 bg-emerald-600 text-white rounded-xl font-medium hover:bg-emerald-700 flex items-center gap-2"
            >
              <DollarSign size={18} />
              Track Position
            </button>
          )}
          {type === 'position' && (
            <button
              onClick={() => setShowSellModal(true)}
              className="px-6 py-2.5 bg-red-600 text-white rounded-xl font-medium hover:bg-red-700 flex items-center gap-2"
            >
              <DollarSign size={18} />
              Mark as Sold
            </button>
          )}
          {type === 'missed' && (
            <div className="px-4 py-2 bg-amber-50 text-amber-700 rounded-xl text-sm">
              This opportunity has already passed
            </div>
          )}
        </div>
      </div>

      {/* Buy Modal */}
      {showBuyModal && (
        <BuyModal
          symbol={symbol}
          price={currentPrice}
          stockInfo={stockInfo}
          viewMode={viewMode}
          timeTravelDate={timeTravelDate}
          onClose={() => setShowBuyModal(false)}
          onBuy={(positionData) => {
            onAction && onAction(positionData);
          }}
        />
      )}

      {/* Sell Modal */}
      {showSellModal && (
        <SellModal
          symbol={symbol}
          position={data}
          currentPrice={currentPrice}
          stockInfo={stockInfo}
          onClose={() => setShowSellModal(false)}
          onSell={() => {
            onAction && onAction();
          }}
        />
      )}
    </div>
  );
};

// Metric Card
const MetricCard = ({ title, value, subtitle, trend, icon: Icon }) => (
  <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5 hover:shadow-md transition-all">
    <div className="flex items-start justify-between">
      <div>
        <p className="text-sm text-gray-500 font-medium">{title}</p>
        <p className={`text-2xl font-bold mt-1 ${trend === 'up' ? 'text-emerald-600' : trend === 'down' ? 'text-red-500' : 'text-gray-900'}`}>{value}</p>
        {subtitle && <p className="text-xs text-gray-400 mt-1">{subtitle}</p>}
      </div>
      {Icon && (
        <div className={`p-2 rounded-lg ${trend === 'up' ? 'bg-emerald-50 text-emerald-600' : trend === 'down' ? 'bg-red-50 text-red-500' : 'bg-gray-50 text-gray-400'}`}>
          <Icon size={20} />
        </div>
      )}
    </div>
  </div>
);

// Signal Strength indicator
const SignalStrengthBar = ({ strength }) => {
  const numStrength = typeof strength === 'string' ? parseFloat(strength) : (strength || 0);
  const color = numStrength >= 70 ? 'bg-emerald-500' : numStrength >= 50 ? 'bg-blue-500' : numStrength >= 30 ? 'bg-yellow-500' : 'bg-gray-400';
  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-2 bg-gray-200 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full transition-all`} style={{ width: `${numStrength}%` }} />
      </div>
      <span className="text-xs font-semibold text-gray-600">{Math.round(numStrength)}</span>
    </div>
  );
};

// Signal Card
const SignalCard = ({ signal, onClick }) => {
  const displayPrice = signal.live_price || signal.price;
  const hasLiveData = !!signal.live_price;

  return (
    <div onClick={() => onClick(signal)} className={`bg-white rounded-lg border-l-4 ${signal.is_strong ? 'border-emerald-500' : 'border-blue-500'} shadow-sm p-4 hover:shadow-md transition-all cursor-pointer group`}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-lg font-bold text-gray-900">{signal.symbol}</span>
          {signal.is_strong && <span className="px-2 py-0.5 bg-emerald-100 text-emerald-700 text-xs font-semibold rounded-full flex items-center gap-1"><Zap size={12} /> STRONG</span>}
        </div>
        <div className="flex items-center gap-2">
          <div className="text-right">
            <span className="text-lg font-semibold text-gray-900">${displayPrice?.toFixed(2)}</span>
            {hasLiveData && signal.live_change_pct !== undefined && (
              <span className={`ml-2 text-sm ${signal.live_change_pct >= 0 ? 'text-emerald-600' : 'text-red-500'}`}>
                {signal.live_change_pct >= 0 ? '+' : ''}{signal.live_change_pct?.toFixed(2)}%
              </span>
            )}
          </div>
          <ChevronRight size={18} className="text-gray-400 group-hover:text-blue-600 transition-colors" />
        </div>
      </div>
      <div className="grid grid-cols-3 gap-2 text-sm">
        <div className="flex items-center gap-1">
          <TrendingUp size={14} className="text-emerald-500" />
          <span className="text-gray-500">Breakout:</span>
          <span className="font-medium text-emerald-600">+{signal.pct_above_dwap}%</span>
        </div>
        <div className="flex items-center gap-1">
          <Activity size={14} className="text-blue-500" />
          <span className="text-gray-500">Vol:</span>
          <span className="font-medium">{signal.volume_ratio}x</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="text-gray-500">Str:</span>
          <SignalStrengthBar strength={signal.signal_strength || 0} />
        </div>
      </div>
      {signal.recommendation && (
        <div className="mt-2 text-xs text-gray-500 italic truncate">{signal.recommendation}</div>
      )}
      {hasLiveData && (
        <div className="mt-1 text-xs text-blue-500 flex items-center gap-1">
          <Activity size={10} className="animate-pulse" /> Live
        </div>
      )}
    </div>
  );
};

// Position Row
const PositionRow = ({ position, onClick }) => {
  const pnlColor = position.pnl_pct >= 0 ? 'text-emerald-600' : 'text-red-500';
  const pnlBg = position.pnl_pct >= 0 ? 'bg-emerald-50' : 'bg-red-50';
  const hasLiveData = position.live_change !== undefined;
  const dayChangeColor = (position.live_change_pct || 0) >= 0 ? 'text-emerald-600' : 'text-red-500';

  // Sell signal indicator
  const sellSignal = position.sell_signal || 'hold';
  const trailingStopPrice = position.trailing_stop_price;
  const distanceToStop = position.distance_to_stop_pct || 0;

  const getSellIndicator = () => {
    if (sellSignal === 'sell') {
      return {
        color: 'text-red-600',
        bg: 'bg-red-100',
        icon: <TrendingDown size={14} className="text-red-600" />,
        label: 'SELL',
        sublabel: `Stop: $${trailingStopPrice?.toFixed(2)}`
      };
    } else if (sellSignal === 'warning') {
      return {
        color: 'text-amber-600',
        bg: 'bg-amber-100',
        icon: <AlertCircle size={14} className="text-amber-600" />,
        label: `${distanceToStop?.toFixed(0)}%`,
        sublabel: `Stop: $${trailingStopPrice?.toFixed(2)}`
      };
    } else {
      return {
        color: 'text-emerald-600',
        bg: 'bg-emerald-50',
        icon: <Shield size={14} className="text-emerald-500" />,
        label: `${distanceToStop?.toFixed(0)}%`,
        sublabel: `Stop: $${trailingStopPrice?.toFixed(2)}`
      };
    }
  };

  const indicator = getSellIndicator();

  return (
    <tr onClick={() => onClick(position)} className="hover:bg-blue-50 transition-colors cursor-pointer group">
      <td className="py-3 px-4">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-gray-900">{position.symbol}</span>
          {hasLiveData && <Activity size={10} className="text-blue-500 animate-pulse" />}
          <Eye size={14} className="text-gray-300 group-hover:text-blue-500" />
        </div>
      </td>
      <td className="py-3 px-4 text-gray-600">{position.shares?.toFixed(2)}</td>
      <td className="py-3 px-4 text-gray-600">${position.entry_price?.toFixed(2)}</td>
      <td className="py-3 px-4">
        <div className="flex flex-col">
          <span className="font-medium text-gray-900">${position.current_price?.toFixed(2)}</span>
          {hasLiveData && (
            <span className={`text-xs ${dayChangeColor}`}>
              {position.live_change_pct >= 0 ? '+' : ''}{position.live_change_pct?.toFixed(2)}% today
            </span>
          )}
        </div>
      </td>
      <td className="py-3 px-4"><span className={`inline-flex items-center gap-1 px-2 py-1 rounded-md font-semibold text-sm ${pnlBg} ${pnlColor}`}>{position.pnl_pct >= 0 ? '+' : ''}{position.pnl_pct?.toFixed(1)}%</span></td>
      <td className="py-3 px-4">
        <div className="flex flex-col items-center">
          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${indicator.bg} ${indicator.color}`}>
            {indicator.icon}
            {indicator.label}
          </span>
          <span className="text-xs text-gray-400 mt-0.5">{indicator.sublabel}</span>
        </div>
      </td>
      <td className="py-3 px-4 text-gray-500"><Clock size={14} className="inline mr-1" />{position.days_held}d</td>
    </tr>
  );
};

// ============================================================================
// Welcome Tour
// ============================================================================

const TOUR_STEPS = [
  {
    title: 'Your Buy Signals',
    description: 'When our Ensemble finds a high-conviction opportunity, it shows up here. BUY means it\'s active. BUY NOW means it just triggered today. These are signals — you execute trades through your own broker.',
    renderIllustration: () => (
      <div className="flex flex-col items-center gap-3">
        <Zap size={32} className="text-blue-600" />
        <div className="w-full max-w-xs space-y-2">
          <div className="flex items-center justify-between bg-white rounded-lg px-3 py-2 shadow-sm">
            <div className="flex items-center gap-2">
              <span className="font-semibold text-sm text-gray-800">NVDA</span>
              <span className="text-xs text-gray-500">$142.50</span>
            </div>
            <span className="text-[10px] font-bold bg-green-100 text-green-700 px-2 py-0.5 rounded-full">BUY NOW</span>
          </div>
          <div className="flex items-center justify-between bg-white rounded-lg px-3 py-2 shadow-sm">
            <div className="flex items-center gap-2">
              <span className="font-semibold text-sm text-gray-800">AVGO</span>
              <span className="text-xs text-gray-500">$198.30</span>
            </div>
            <span className="text-[10px] font-bold bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">BUY</span>
          </div>
        </div>
      </div>
    ),
  },
  {
    title: 'Open Positions',
    description: 'After you act on a signal, track it here. See your P&L in real-time, and we\'ll tell you when our trailing stop says it\'s time to sell.',
    renderIllustration: () => (
      <div className="flex flex-col items-center gap-3">
        <Briefcase size={32} className="text-blue-600" />
        <div className="w-full max-w-xs bg-white rounded-lg px-3 py-2 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <span className="font-semibold text-sm text-gray-800">AAPL</span>
              <span className="text-xs text-gray-500 ml-2">50 shares</span>
            </div>
            <div className="text-right">
              <span className="text-sm font-semibold text-green-600">+$1,240</span>
              <span className="text-xs text-green-600 ml-1">+8.2%</span>
            </div>
          </div>
          <div className="mt-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
            <div className="h-full bg-green-500 rounded-full" style={{ width: '68%' }} />
          </div>
          <div className="flex justify-between mt-1">
            <span className="text-[10px] text-gray-400">Entry $151.20</span>
            <span className="text-[10px] text-gray-400">Stop $140.10</span>
          </div>
        </div>
      </div>
    ),
  },
  {
    title: 'Missed Opportunities',
    description: 'Didn\'t catch a signal in time? This section shows profitable trades you could have taken — so you know the system is working even when you\'re away.',
    renderIllustration: () => (
      <div className="flex flex-col items-center gap-3">
        <TrendingUp size={32} className="text-blue-600" />
        <div className="w-full max-w-xs space-y-2">
          <div className="flex items-center justify-between bg-white rounded-lg px-3 py-2 shadow-sm opacity-70">
            <div className="flex items-center gap-2">
              <span className="font-semibold text-sm text-gray-800">META</span>
              <span className="text-xs text-gray-400">Signal: Jan 28</span>
            </div>
            <span className="text-sm font-semibold text-green-600">+14.3%</span>
          </div>
          <div className="flex items-center justify-between bg-white rounded-lg px-3 py-2 shadow-sm opacity-70">
            <div className="flex items-center gap-2">
              <span className="font-semibold text-sm text-gray-800">AMZN</span>
              <span className="text-xs text-gray-400">Signal: Jan 22</span>
            </div>
            <span className="text-sm font-semibold text-green-600">+9.7%</span>
          </div>
        </div>
      </div>
    ),
  },
  {
    title: 'Simple vs Advanced',
    description: 'Toggle between Simple (clean, just the essentials) and Advanced (momentum scores, breakout strength, Sharpe ratios — the full picture). Find it in the top-right corner.',
    renderIllustration: () => (
      <div className="flex flex-col items-center gap-3">
        <div className="flex items-center gap-4">
          <div className="flex flex-col items-center gap-1">
            <div className="w-12 h-12 rounded-xl bg-blue-100 flex items-center justify-center">
              <Eye size={24} className="text-blue-600" />
            </div>
            <span className="text-xs font-medium text-gray-600">Simple</span>
          </div>
          <ChevronRight size={20} className="text-gray-300" />
          <div className="flex flex-col items-center gap-1">
            <div className="w-12 h-12 rounded-xl bg-indigo-100 flex items-center justify-center">
              <Settings size={24} className="text-indigo-600" />
            </div>
            <span className="text-xs font-medium text-gray-600">Advanced</span>
          </div>
        </div>
        <div className="w-full max-w-xs bg-white rounded-lg px-3 py-2 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-500">Momentum Score</span>
            <span className="text-xs font-mono text-indigo-600">87.4</span>
          </div>
          <div className="flex items-center justify-between mt-1">
            <span className="text-xs text-gray-500">Breakout</span>
            <span className="text-xs font-mono text-indigo-600">+5.8%</span>
          </div>
          <div className="flex items-center justify-between mt-1">
            <span className="text-xs text-gray-500">Sharpe Ratio</span>
            <span className="text-xs font-mono text-indigo-600">1.42</span>
          </div>
        </div>
      </div>
    ),
  },
  {
    title: 'Nightly Emails',
    description: 'Every evening, you\'ll get an email with today\'s signals, your portfolio status, and the current market regime. Expect ~15 signals per month when conditions are healthy — and zero when they\'re not.',
    renderIllustration: () => (
      <div className="flex items-center justify-center">
        <div className="relative w-64 h-32">
          {[
            { rotate: '-rotate-6', offset: 'left-2 top-2', subject: '⚡ 3 New Breakout Signals' },
            { rotate: 'rotate-0', offset: 'left-6 top-1', subject: '📊 Daily Summary — Strong Bull' },
            { rotate: 'rotate-6', offset: 'left-10 top-2', subject: '🔔 LIVE SIGNAL: NVDA' },
          ].map((card, i) => (
            <div
              key={i}
              className={`absolute ${card.offset} ${card.rotate} w-44 bg-white rounded-lg shadow-md overflow-hidden`}
              style={{ zIndex: i }}
            >
              <div className="bg-[#0f1729] px-3 py-1.5 flex items-center gap-1.5">
                <Mail size={10} className="text-[#c9a84c]" />
                <span className="text-[9px] font-medium text-[#c9a84c]">RigaCap</span>
              </div>
              <div className="px-3 py-2">
                <p className="text-[10px] font-medium text-gray-800 truncate">{card.subject}</p>
                <p className="text-[9px] text-gray-400 mt-0.5">Today at 6:00 PM ET</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    ),
  },
];

function WelcomeTour() {
  const [visible, setVisible] = useState(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get('tour') !== null) return true;
    return localStorage.getItem(CACHE_KEYS.WELCOME_SEEN) !== 'true';
  });
  const [step, setStep] = useState(0);
  const [fadeKey, setFadeKey] = useState(0);

  const dismiss = useCallback(() => {
    setVisible(false);
    localStorage.setItem(CACHE_KEYS.WELCOME_SEEN, 'true');
  }, []);

  const next = useCallback(() => {
    if (step < TOUR_STEPS.length - 1) {
      setStep(s => s + 1);
      setFadeKey(k => k + 1);
    } else {
      dismiss();
    }
  }, [step, dismiss]);

  useEffect(() => {
    if (!visible) return;
    const handler = (e) => {
      if (e.key === 'Escape') dismiss();
      if (e.key === 'ArrowRight') next();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [visible, next, dismiss]);

  if (!visible) return null;

  const current = TOUR_STEPS[step];
  const isLast = step === TOUR_STEPS.length - 1;

  return (
    <div className="fixed inset-0 bg-black/50 z-40 flex items-center justify-center p-4" onClick={dismiss}>
      <div
        className="bg-white rounded-2xl shadow-2xl max-w-lg w-full mx-4 overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Illustration area */}
        <div className="relative h-48 bg-gradient-to-br from-blue-50 to-indigo-50 flex items-center justify-center px-6">
          <button
            onClick={dismiss}
            className="absolute top-3 right-3 text-gray-400 hover:text-gray-600 transition-colors"
          >
            <X size={20} />
          </button>
          <div key={fadeKey} className="animate-fade-in w-full">
            {current.renderIllustration()}
          </div>
        </div>

        {/* Content */}
        <div className="px-6 pt-5 pb-6">
          <div key={`text-${fadeKey}`} className="animate-fade-in">
            <h3 className="text-lg font-bold text-gray-900">{current.title}</h3>
            <p className="mt-2 text-sm text-gray-600 leading-relaxed">{current.description}</p>
          </div>

          {/* Footer: dots + buttons */}
          <div className="flex items-center justify-between mt-6">
            <div className="flex gap-1.5">
              {TOUR_STEPS.map((_, i) => (
                <div
                  key={i}
                  className={`w-2 h-2 rounded-full transition-colors ${
                    i === step ? 'bg-blue-600' : 'bg-gray-300'
                  }`}
                />
              ))}
            </div>
            <div className="flex items-center gap-3">
              {!isLast && (
                <button onClick={dismiss} className="text-sm text-gray-400 hover:text-gray-600 transition-colors">
                  Skip
                </button>
              )}
              <button
                onClick={next}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors"
              >
                {isLast ? 'Get Started →' : 'Next →'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Main Dashboard
// ============================================================================

function Dashboard() {
  const { user, logout, isAdmin, isAuthenticated, loading: authLoading, refreshUser } = useAuth();
  const [checkoutSuccess, setCheckoutSuccess] = useState(false);
  const [signals, setSignals] = useState([]);
  const [positions, setPositions] = useState([]);
  const [trades, setTrades] = useState([]);
  const [missedOpportunities, setMissedOpportunities] = useState([]);
  const [missedSortBy, setMissedSortBy] = useState('date'); // 'date' or 'return'
  const [backtest, setBacktest] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState(() => {
    const saved = sessionStorage.getItem('rigacap_active_tab');
    if (saved === 'admin' && !isAdmin) return 'signals';
    return saved || 'signals';
  });
  const [dashboardData, setDashboardData] = useState(null); // Unified dashboard data
  const [showLoginModal, setShowLoginModal] = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [chartModal, setChartModal] = useState(null);
  const [dataStatus, setDataStatus] = useState({ loaded: 0, status: 'loading' });
  const [marketRegime, setMarketRegime] = useState(null);
  const [regimeExpanded, setRegimeExpanded] = useState(false);
  const [liveQuotes, setLiveQuotes] = useState({});
  const [quotesLastUpdate, setQuotesLastUpdate] = useState(null);
  const [quotesReady, setQuotesReady] = useState(false); // true after first live quotes fetch (or skip)
  const [viewMode, setViewMode] = useState(() => localStorage.getItem(CACHE_KEYS.VIEW_MODE) || 'simple');
  const [excludedSectors, setExcludedSectors] = useState(() => {
    try {
      const saved = localStorage.getItem(CACHE_KEYS.SECTOR_FILTERS);
      return saved ? JSON.parse(saved) : [];
    } catch { return []; }
  });
  const [sectorFilterOpen, setSectorFilterOpen] = useState(() =>
    localStorage.getItem(CACHE_KEYS.SECTOR_FILTER_OPEN) === 'true'
  );
  const [timeTravelDate, setTimeTravelDate] = useState(null); // "YYYY-MM-DD" or null
  const [timeTravelOpen, setTimeTravelOpen] = useState(false);
  const [timeTravelLoading, setTimeTravelLoading] = useState(false);
  const [timeTravelEmailPending, setTimeTravelEmailPending] = useState(false);
  const [timeTravelEmailStatus, setTimeTravelEmailStatus] = useState(null); // null | 'sending' | 'sent' | 'failed'
  const [timeTravelPresets, setTimeTravelPresets] = useState([]); // Computed once from live dashboard data
  const [upgradeLoading, setUpgradeLoading] = useState(false);
  const [showEmailPrefsModal, setShowEmailPrefsModal] = useState(false);
  const [showCancelSurvey, setShowCancelSurvey] = useState(false);
  const [cancelSurveySubmitted, setCancelSurveySubmitted] = useState(false);
  const [showReferralModal, setShowReferralModal] = useState(false);
  const [show2FASettings, setShow2FASettings] = useState(false);
  const [referralCopied, setReferralCopied] = useState(false);
  const [journeyData, setJourneyData] = useState(null);
  const [journeyCopied, setJourneyCopied] = useState(false);
  const [emailPrefs, setEmailPrefs] = useState({ daily_digest: true, sell_alerts: true, double_signals: true, intraday_signals: true });
  const [emailPrefsSaving, setEmailPrefsSaving] = useState(false);
  const [emailPrefsToast, setEmailPrefsToast] = useState(null); // null | 'saved' | 'unsubscribed'
  const [dataFreshness, setDataFreshness] = useState(null); // { status: 'fresh'|'processing'|'stale', message }

  // Data freshness polling — 30s when processing, 60s during 4 PM hour, 5 min otherwise
  useEffect(() => {
    let timeout;
    const checkFreshness = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/market-data-status`);
        if (res.ok) {
          const data = await res.json();
          setDataFreshness(data);
        }
      } catch {
        // Silently ignore — banner just won't show
      }
      // Schedule next poll based on current status
      const etHour = new Date(new Date().toLocaleString('en-US', { timeZone: 'America/New_York' })).getHours();
      const pollMs = dataFreshness?.status === 'processing' ? 30000 : (etHour >= 16 && etHour < 17) ? 60000 : 300000;
      timeout = setTimeout(checkFreshness, pollMs);
    };
    checkFreshness();
    return () => clearTimeout(timeout);
  }, []);

  // Handle post-checkout redirect from Stripe
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get('checkout') === 'success') {
      setCheckoutSuccess(true);
      // GA4: track purchase conversion
      if (window.gtag) {
        window.gtag('event', 'purchase', { currency: 'USD', transaction_id: params.get('session_id') || '' });
      }
      // Sync subscription status directly from Stripe, then refresh user
      api.post('/api/billing/sync', {}).catch(() => {}).finally(() => refreshUser());
      // Retry after 5s in case sync was slow
      setTimeout(() => {
        api.post('/api/billing/sync', {}).catch(() => {}).finally(() => refreshUser());
      }, 5000);
      // Clean up URL
      const url = new URL(window.location);
      url.searchParams.delete('checkout');
      url.searchParams.delete('session_id');
      window.history.replaceState({}, '', url.pathname);
      // Auto-dismiss after 8 seconds
      setTimeout(() => setCheckoutSuccess(false), 8000);
    }

    // Handle email preference links from email footer
    if (params.get('emailPrefs') === '1') {
      setShowEmailPrefsModal(true);
      const url = new URL(window.location);
      url.searchParams.delete('emailPrefs');
      url.searchParams.delete('token');
      window.history.replaceState({}, '', url.pathname);
    }

    // Handle one-click unsubscribe from email footer
    if (params.get('unsubscribe') === '1') {
      const token = params.get('token');
      if (token) {
        fetch(`${API_BASE}/api/auth/unsubscribe?token=${encodeURIComponent(token)}`, { method: 'POST' })
          .then(res => res.json())
          .then(() => {
            setEmailPrefsToast('unsubscribed');
            setEmailPrefs({ daily_digest: false, sell_alerts: false, double_signals: false, intraday_signals: false });
            setTimeout(() => setEmailPrefsToast(null), 6000);
          })
          .catch(() => {});
      }
      const url = new URL(window.location);
      url.searchParams.delete('unsubscribe');
      url.searchParams.delete('token');
      window.history.replaceState({}, '', url.pathname);
    }

    // Handle Stripe portal return — check if subscription was cancelled
    if (params.get('portal_return') === '1') {
      // Refresh subscription status, then check if they cancelled
      refreshUser().then(() => {
        // Small delay to let webhook process
        setTimeout(async () => {
          try {
            const res = await api.get('/api/billing/subscription');
            const data = res.data;
            if (data.cancel_at_period_end || data.status === 'canceled') {
              setShowCancelSurvey(true);
            }
          } catch {}
        }, 2000);
      });
      const url = new URL(window.location);
      url.searchParams.delete('portal_return');
      window.history.replaceState({}, '', url.pathname);
    }
  }, [refreshUser]);

  // Sync email preferences from user data
  useEffect(() => {
    if (user?.email_preferences) {
      setEmailPrefs(user.email_preferences);
    }
  }, [user]);

  // Live quotes polling - updates prices every 30 seconds during market hours
  useEffect(() => {
    if (timeTravelDate) { setQuotesReady(true); return; } // No live quotes in time-travel mode

    const fetchLiveQuotes = async (isInitial = false) => {
      // Skip if not authenticated (CDN data doesn't need live quotes)
      if (!localStorage.getItem('accessToken')) { if (isInitial) setQuotesReady(true); return; }

      // Get symbols from positions, signals, and recent signals
      const positionSymbols = positions.map(p => p.symbol);
      const signalSymbols = signals.slice(0, 10).map(s => s.symbol); // Top 10 signals
      const recentSignalSymbols = (dashboardData?.recent_signals || []).map(rs => rs.symbol);
      const allSymbols = [...new Set([...positionSymbols, ...signalSymbols, ...recentSignalSymbols])];

      if (allSymbols.length === 0) { if (isInitial) setQuotesReady(true); return; }

      try {
        const response = await api.get(`/api/quotes/live?symbols=${allSymbols.join(',')}`);
        if (response.quotes) {
          setLiveQuotes(response.quotes);
          setQuotesLastUpdate(new Date(response.timestamp));
        }
      } catch (err) {
        console.log('Live quotes fetch failed:', err);
      }
      if (isInitial) setQuotesReady(true);
    };

    // Initial fetch — reset quotesReady so positions show skeleton until live prices arrive
    const recentCount = (dashboardData?.recent_signals || []).length;
    if (positions.length > 0 || signals.length > 0 || recentCount > 0) {
      setQuotesReady(false);
      fetchLiveQuotes(true);
    } else {
      setQuotesReady(true);
    }

    // Poll every 30 seconds
    const interval = setInterval(() => fetchLiveQuotes(false), 30000);

    return () => clearInterval(interval);
  }, [positions.length, signals.length, dashboardData?.recent_signals?.length, timeTravelDate]);

  // Persist active tab to sessionStorage (survives refresh, clears on tab close)
  useEffect(() => {
    sessionStorage.setItem('rigacap_active_tab', activeTab);
  }, [activeTab]);

  // Persist view mode to localStorage
  useEffect(() => {
    localStorage.setItem(CACHE_KEYS.VIEW_MODE, viewMode);
  }, [viewMode]);

  // Persist sector filters to localStorage
  useEffect(() => {
    localStorage.setItem(CACHE_KEYS.SECTOR_FILTERS, JSON.stringify(excludedSectors));
  }, [excludedSectors]);
  useEffect(() => {
    localStorage.setItem(CACHE_KEYS.SECTOR_FILTER_OPEN, sectorFilterOpen);
  }, [sectorFilterOpen]);

  // Fetch unified dashboard data (regime forecast, buy signals, sell guidance, watchlist)
  // CDN-first strategy: localStorage → CDN (~200ms) → API (positions only)
  //
  // Race condition protection: AbortController cancels ALL in-flight HTTP requests
  // when timeTravelDate changes. This is bulletproof — the browser itself aborts the
  // requests, so no stale response can ever call setDashboardData.
  useEffect(() => {
    const abortController = new AbortController();
    const signal = abortController.signal;

    const buildTimeTravelPresets = (data) => {
      const presets = [];
      if (data.missed_opportunities?.length > 0) {
        const grouped = {};
        data.missed_opportunities.forEach(m => {
          const d = m.entry_date;
          if (!grouped[d]) grouped[d] = [];
          grouped[d].push(m);
        });
        Object.entries(grouped).forEach(([date, opps]) => {
          const symbols = opps.map(o => o.symbol).join(', ');
          const avgRet = Math.round(opps.reduce((s, o) => s + (o.would_be_return || 0), 0) / opps.length);
          presets.push({ date, symbols, detail: `+${avgRet}%`, source: 'missed' });
        });
      }
      if (data.buy_signals?.length > 0) {
        const grouped = {};
        data.buy_signals.filter(s => s.ensemble_entry_date && s.is_fresh).forEach(s => {
          const d = s.ensemble_entry_date;
          if (!grouped[d]) grouped[d] = [];
          grouped[d].push(s);
        });
        Object.entries(grouped).forEach(([date, sigs]) => {
          if (presets.some(p => p.date === date)) return;
          const symbols = sigs.map(s => s.symbol).join(', ');
          const topScore = Math.max(...sigs.map(s => s.ensemble_score || 0));
          presets.push({ date, symbols, detail: `Score ${Math.round(topScore)}`, source: 'signal' });
        });
      }
      presets.sort((a, b) => b.date.localeCompare(a.date));
      return presets;
    };

    const fetchDashboard = async () => {
      // Time-travel mode: always call API directly
      if (timeTravelDate) {
        setTimeTravelLoading(true);
        try {
          const res = await fetch(`${API_BASE}/api/signals/dashboard?as_of_date=${timeTravelDate}`, {
            headers: api._authHeaders(),
            signal,
          });
          if (!res.ok) throw new Error(`API error: ${res.status}`);
          const data = await res.json();
          setDashboardData(data);
          if (data.missed_opportunities?.length > 0) {
            setMissedOpportunities(data.missed_opportunities);
          }
        } catch (err) {
          if (err.name === 'AbortError') return; // Expected on cleanup
          console.error('Dashboard time-travel fetch failed:', err);
          if (err.message?.includes('503')) {
            setError('Time-travel: Price data is loading on the server. Please try again in ~30 seconds.');
          } else {
            setError(`Time-travel failed: ${err.message}`);
          }
        } finally {
          if (!signal.aborted) setTimeTravelLoading(false);
        }
        return;
      }

      // Step 1: Show localStorage cache immediately (instant)
      const cached = getCache(CACHE_KEYS.DASHBOARD);
      if (cached && !signal.aborted) {
        setDashboardData(cached);
        if (cached.missed_opportunities?.length > 0) {
          setMissedOpportunities(cached.missed_opportunities);
        }
        setTimeTravelPresets(buildTimeTravelPresets(cached));
      }

      // Step 2: Fetch from authenticated API (signals + user positions with sell guidance)
      try {
        const res = await fetch(`${API_BASE}/api/signals/dashboard`, {
          headers: api._authHeaders(),
          signal,
        });
        if (!res.ok) throw new Error(`API error: ${res.status}`);
        const data = await res.json();
        if (signal.aborted) return;
        setDashboardData(data);
        if (data.missed_opportunities?.length > 0) {
          setMissedOpportunities(data.missed_opportunities);
        }
        setCache(CACHE_KEYS.DASHBOARD, data);
        setTimeTravelPresets(buildTimeTravelPresets(data));
      } catch (err) {
        if (err.name === 'AbortError') return;
        console.log('Dashboard API fetch failed:', err);
      }
    };

    fetchDashboard();
    // Disable auto-refresh in time-travel mode (historical data doesn't change)
    if (!timeTravelDate) {
      const interval = setInterval(fetchDashboard, 60000);
      return () => { abortController.abort(); clearInterval(interval); };
    }
    return () => abortController.abort();
  }, [timeTravelDate]);

  // Live SPY/VIX polling (every 30s during market hours, no auth needed)
  useEffect(() => {
    if (!user || timeTravelDate) return;

    const fetchLiveStats = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/live-market-stats`);
        if (res.ok) {
          const data = await res.json();
          setDashboardData(prev => prev ? {
            ...prev,
            market_stats: {
              ...prev.market_stats,
              spy_price: data.spy_price ?? prev.market_stats?.spy_price,
              spy_change_pct: data.spy_change_pct ?? prev.market_stats?.spy_change_pct,
              vix_level: data.vix_level ?? prev.market_stats?.vix_level,
              live: true,
            }
          } : prev);
        }
      } catch { /* silent — non-critical */ }
    };

    fetchLiveStats();
    const interval = setInterval(fetchLiveStats, 30000);
    return () => clearInterval(interval);
  }, [user, timeTravelDate]);

  // Send time-travel email when dashboard data loads after preset click
  useEffect(() => {
    if (!timeTravelEmailPending || !timeTravelDate || !dashboardData) return;
    if (dashboardData.as_of_date !== timeTravelDate) return; // Wait for correct data

    setTimeTravelEmailPending(false);
    setTimeTravelEmailStatus('sending');
    api.post('/api/email/time-travel', {
      email: user?.email,
      as_of_date: timeTravelDate,
      buy_signals: dashboardData.buy_signals || [],
      regime_forecast: dashboardData.regime_forecast || null,
      watchlist: dashboardData.watchlist || [],
    }).then(() => {
      setTimeTravelEmailStatus('sent');
      setTimeout(() => setTimeTravelEmailStatus(null), 4000);
    }).catch(() => {
      setTimeTravelEmailStatus('failed');
      setTimeout(() => setTimeTravelEmailStatus(null), 4000);
    });
  }, [timeTravelEmailPending, dashboardData, timeTravelDate]);

  // Fetch "Your RigaCap Journey" data for subscribers
  useEffect(() => {
    if (!isAuthenticated || !user?.subscription?.is_valid) return;
    // Only show after 7 days
    const created = user?.created_at ? new Date(user.created_at) : null;
    if (!created || (Date.now() - created.getTime()) < 7 * 24 * 60 * 60 * 1000) return;

    const fetchJourney = async () => {
      try {
        const data = await api.get('/api/signals/what-if?capital=10000');
        if (!data.error) setJourneyData(data);
      } catch (err) {
        console.log('Journey fetch failed:', err);
      }
    };
    fetchJourney();
  }, [isAuthenticated, user, dashboardData?.generated_at]);

  // Merge live quotes into positions for display
  const positionsWithLiveQuotes = positions.map(p => {
    const quote = liveQuotes[p.symbol];
    if (quote) {
      const livePrice = quote.price;
      const pnlPct = ((livePrice - p.entry_price) / p.entry_price) * 100;
      const pnlDollars = (livePrice - p.entry_price) * p.shares;
      return {
        ...p,
        current_price: livePrice,
        pnl_pct: pnlPct,
        pnl_dollars: pnlDollars,
        live_change: quote.change,
        live_change_pct: quote.change_pct,
      };
    }
    return p;
  });

  // Merge live quotes into dashboard positions_with_guidance (these take render priority)
  const guidanceWithLiveQuotes = (dashboardData?.positions_with_guidance || []).map(p => {
    const quote = liveQuotes[p.symbol];
    if (quote) {
      const livePrice = quote.price;
      const pnlPct = ((livePrice - p.entry_price) / p.entry_price) * 100;

      // Recalculate trailing stop distance and action with live price
      const hwm = Math.max(p.high_water_mark || p.entry_price, livePrice);
      const stopPrice = hwm * 0.88; // 12% trailing stop, always derived from live HWM
      const distToStop = stopPrice > 0 ? ((livePrice - stopPrice) / stopPrice) * 100 : 100;
      let action = p.action || 'hold';
      let actionReason = p.action_reason || '';
      if (livePrice <= stopPrice) {
        action = 'sell';
        actionReason = `Trailing stop hit — price $${livePrice.toFixed(2)} below stop $${stopPrice.toFixed(2)}`;
      } else if (distToStop < 3) {
        action = 'warning';
        actionReason = `Within ${distToStop.toFixed(1)}% of trailing stop $${stopPrice.toFixed(2)}`;
      } else if (p.action === 'warning' && distToStop >= 5) {
        // Clear stale warning if live price moved well above stop
        action = 'hold';
        actionReason = '';
      }

      return {
        ...p,
        current_price: livePrice,
        pnl_pct: pnlPct,
        high_water_mark: hwm,
        trailing_stop_price: stopPrice,
        trailing_stop_level: stopPrice,
        distance_to_stop_pct: distToStop,
        action,
        action_reason: actionReason,
        live_change: quote.change,
        live_change_pct: quote.change_pct,
      };
    }
    return p;
  });

  // Merge live quotes into signals for display
  const signalsWithLiveQuotes = signals.map(s => {
    const quote = liveQuotes[s.symbol];
    if (quote) {
      return {
        ...s,
        live_price: quote.price,
        live_change: quote.change,
        live_change_pct: quote.change_pct,
      };
    }
    return s;
  });


  // Initial data load - HYBRID APPROACH for instant dashboard display
  // 1. Show cached data immediately (no loading state for returning users)
  // 2. Fetch signals from CDN (same for all users, instant)
  // 3. Background refresh user-specific data from API
  useEffect(() => {
    const loadData = async () => {
      // Step 1: Load cached data IMMEDIATELY (no loading spinner for returning users)
      const cachedSignals = getCache(CACHE_KEYS.SIGNALS);
      const cachedBacktest = getCache(CACHE_KEYS.BACKTEST);
      const cachedPositions = getCache(CACHE_KEYS.POSITIONS);
      const cachedMissed = getCache(CACHE_KEYS.MISSED);

      // If we have any cached data, show the dashboard immediately
      if (cachedSignals || cachedBacktest) {
        if (cachedSignals) setSignals(cachedSignals);
        if (cachedBacktest) {
          // Check if cached data is walk-forward format or simple backtest
          if (cachedBacktest.available !== undefined) {
            // Walk-forward cached format
            const wf = cachedBacktest;
            setBacktest({
              total_return_pct: wf.total_return_pct?.toFixed(1) || '0.0',
              sharpe_ratio: wf.sharpe_ratio?.toFixed(2) || '0.00',
              max_drawdown_pct: Math.abs(wf.max_drawdown_pct || 0).toFixed(1),
              win_rate: '--',
              start_date: wf.start_date?.split('T')[0],
              end_date: wf.end_date?.split('T')[0],
              strategy: 'momentum',
              benchmark_return_pct: wf.benchmark_return_pct?.toFixed(1) || '0.0',
              num_strategy_switches: wf.num_strategy_switches || 0,
              is_walk_forward: true
            });
          } else if (cachedBacktest.backtest) {
            // Simple backtest format
            setBacktest({ ...cachedBacktest.backtest, strategy: cachedBacktest.strategy || 'momentum', is_walk_forward: false });
          }
          // Don't load positions/trades from backtest cache - only from user data
        }
        // Load user positions from cache (NOT backtest positions)
        if (cachedPositions) setPositions(cachedPositions);
        // Missed opportunities removed - was simulated data
        setLoading(false); // Dashboard visible immediately!
      }

      // Step 2: Quick health check to show data status
      try {
        const health = await api.get('/health');
        setDataStatus({ loaded: health.symbols_loaded, status: 'ready' });
        setLoading(false); // Definitely show dashboard now
      } catch (err) {
        // If health check fails but we have cached data, still show dashboard
        if (cachedSignals || cachedBacktest) {
          setDataStatus({ loaded: 0, status: 'cached' });
          setLoading(false);
        } else {
          setError('Failed to connect to backend. Make sure the API is running.');
          setLoading(false);
          return;
        }
      }

      // Step 4: Background refresh - load fresh data from API (don't block UI)
      const refreshData = async () => {
        try {
          // Load all data in parallel - try cached walk-forward first, fallback to simple backtest
          const [walkForwardResult, signalsResult, marketResult, userPositionsResult, userTradesResult] = await Promise.allSettled([
            api.get('/api/backtest/walk-forward-cached').catch(() => null),
            Promise.resolve(null), // signals loaded from CDN; memory-scan is worker-only
            api.get('/api/market/regime').catch(() => null),
            api.get('/api/portfolio/positions').catch(() => null),
            api.get('/api/portfolio/trades?limit=50').catch(() => null),
          ]);

          // Process walk-forward or fallback to simple backtest (for stats display only, NOT for positions/trades)
          if (walkForwardResult.status === 'fulfilled' && walkForwardResult.value?.available) {
            // Use cached walk-forward results (more accurate)
            const wf = walkForwardResult.value;
            setBacktest({
              total_return_pct: wf.total_return_pct?.toFixed(1) || '0.0',
              sharpe_ratio: wf.sharpe_ratio?.toFixed(2) || '0.00',
              max_drawdown_pct: Math.abs(wf.max_drawdown_pct || 0).toFixed(1),
              win_rate: '--',  // Walk-forward doesn't track win rate
              start_date: wf.start_date?.split('T')[0],
              end_date: wf.end_date?.split('T')[0],
              strategy: 'momentum',
              benchmark_return_pct: wf.benchmark_return_pct?.toFixed(1) || '0.0',
              num_strategy_switches: wf.num_strategy_switches || 0,
              is_walk_forward: true
            });
            setCache(CACHE_KEYS.BACKTEST, walkForwardResult.value);
          } else {
            // Fallback to simple backtest
            try {
              const simpleBacktest = await api.get('/api/backtest/run?days=252');
              if (simpleBacktest?.success) {
                setBacktest({ ...simpleBacktest.backtest, strategy: simpleBacktest.strategy || 'momentum', is_walk_forward: false });
                setCache(CACHE_KEYS.BACKTEST, simpleBacktest);
              }
            } catch (e) {
              console.log('Simple backtest fallback failed:', e);
            }
          }

          // Process user positions ONLY - no backtest fallback
          let userPositions = [];
          if (userPositionsResult.status === 'fulfilled' && userPositionsResult.value?.positions) {
            userPositions = userPositionsResult.value.positions;
            setPositions(userPositions);
            setCache(CACHE_KEYS.POSITIONS, userPositions);
          } else {
            setPositions([]);
          }

          // Process user trades ONLY - no backtest fallback
          if (userTradesResult.status === 'fulfilled' && userTradesResult.value?.trades) {
            setTrades(userTradesResult.value.trades);
          } else {
            setTrades([]);
          }

          // Process signals result (only if CDN didn't work)
          // Filter out signals for stocks user already has positions in
          if (signalsResult.status === 'fulfilled' && signalsResult.value?.signals) {
            const positionSymbols = new Set(userPositions.map(p => p.symbol));
            const filteredSignals = signalsResult.value.signals.filter(s => !positionSymbols.has(s.symbol));
            setSignals(filteredSignals);
            setCache(CACHE_KEYS.SIGNALS, filteredSignals);
            // timestamp available in signalsResult.value.timestamp if needed
          }

          // Process market regime
          if (marketResult.status === 'fulfilled' && marketResult.value) {
            setMarketRegime(marketResult.value);
          }

          // Missed opportunities now come from /api/signals/dashboard (via fetchDashboard)
        } catch (err) {
          console.log('Background refresh failed:', err);
        }
      };

      // Run background refresh
      refreshData();
    };

    loadData();
  }, []);


  // Reload dashboard + positions after a buy/sell
  const reloadPositions = async () => {
    try {
      // Reload full dashboard (signals + positions with guidance) for accurate data
      const res = await fetch(`${API_BASE}/api/signals/dashboard`, {
        headers: api._authHeaders(),
      });
      if (res.ok) {
        const data = await res.json();
        setDashboardData(data);
        setCache(CACHE_KEYS.DASHBOARD, data);
      }

      // Also reload trades
      const tradesResult = await api.get('/api/portfolio/trades?limit=50');
      if (tradesResult.trades) {
        setTrades(tradesResult.trades);
      }
    } catch (err) {
      console.log('Could not reload after trade:', err);
    }
  };

  // Use live-quoted positions for calculations
  const totalValue = positionsWithLiveQuotes.reduce((sum, p) => sum + (p.shares || 0) * (p.current_price || 0), 0);
  const totalCost = positionsWithLiveQuotes.reduce((sum, p) => sum + (p.shares || 0) * (p.entry_price || 0), 0);
  const totalPnlPct = totalCost > 0 ? ((totalValue - totalCost) / totalCost) * 100 : 0;
  const wins = trades.filter(t => t.pnl > 0);
  const winRate = trades.length > 0 ? (wins.length / trades.length * 100) : 0;
  const totalHistoricalPnl = trades.reduce((sum, t) => sum + (t.pnl || 0), 0);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="relative mx-auto mb-4 w-16 h-16">
            <img src="/icon-halo.svg" alt="RigaCap" width="64" height="64" className="mx-auto" />
            <Loader2 className="w-5 h-5 text-amber-500 animate-spin absolute -bottom-1 -right-1" />
          </div>
          <h2 className="text-xl font-semibold text-gray-900 mb-2">Loading RigaCap</h2>
          <p className="text-gray-500">Initializing your dashboard...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center max-w-md">
          <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-gray-900 mb-2">Connection Error</h2>
          <p className="text-gray-500 mb-4">{error}</p>
          <p className="text-sm text-gray-400 mb-4">
            Backend: {API_BASE}
          </p>
          <button
            onClick={() => window.location.reload()}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  // Show data loading state only if dashboard hasn't loaded yet (not just empty portfolio)
  const noDataAvailable = !dashboardData && positions.length === 0 && signals.length === 0 && trades.length === 0;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Data Freshness Banner */}
      {dataFreshness && dataFreshness.status === 'processing' && (
        <div className="bg-blue-50 border-b border-blue-200 px-4 py-2 text-center text-sm text-blue-700">
          <Clock className="inline w-4 h-4 mr-1 -mt-0.5" />
          {dataFreshness.message || 'Market data is being updated. Signals will refresh shortly.'}
        </div>
      )}
      {dataFreshness && dataFreshness.status === 'stale' && (
        <div className="bg-amber-50 border-b border-amber-200 px-4 py-2 text-center text-sm text-amber-700">
          <AlertCircle className="inline w-4 h-4 mr-1 -mt-0.5" />
          {dataFreshness.message || "Today's market data is delayed. Signals may not reflect current prices."}
          {dataFreshness.data_date && <span className="ml-1 font-medium">(Last: {dataFreshness.data_date})</span>}
        </div>
      )}
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-3 sm:px-6 py-3 sm:py-4 flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 sm:gap-3 shrink-0">
            <img src="/icon-halo.svg" alt="RigaCap" width="32" height="32" className="shrink-0 sm:w-10 sm:h-10" />
            <div>
              <h1 className="text-base sm:text-xl font-bold text-gray-900">RigaCap</h1>
              <p className="text-xs text-gray-500 hidden sm:block">Ensemble Trading System</p>
            </div>
          </div>

          <nav className="flex items-center gap-1 bg-gray-100 p-1 rounded-xl min-w-0">
            <button onClick={() => setActiveTab('signals')} className={`px-2 sm:px-4 py-2 rounded-lg text-sm font-medium transition-all ${activeTab === 'signals' ? 'bg-white shadow text-gray-900' : 'text-gray-600 hover:text-gray-900'}`}>
              <Zap size={16} className="inline sm:mr-2" /><span className="hidden sm:inline">Signals</span>
            </button>
            <button onClick={() => setActiveTab('history')} className={`px-2 sm:px-4 py-2 rounded-lg text-sm font-medium transition-all ${activeTab === 'history' ? 'bg-white shadow text-gray-900' : 'text-gray-600 hover:text-gray-900'}`}>
              <History size={16} className="inline sm:mr-2" /><span className="hidden sm:inline">Trade History</span>
            </button>
            {isAdmin && (
              <button onClick={() => setActiveTab('admin')} className={`px-2 sm:px-4 py-2 rounded-lg text-sm font-medium transition-all ${activeTab === 'admin' ? 'bg-white shadow text-gray-900' : 'text-gray-600 hover:text-gray-900'}`}>
                <Settings size={16} className="inline sm:mr-2" /><span className="hidden sm:inline">Admin</span>
              </button>
            )}
          </nav>

          <div className="flex items-center gap-2 sm:gap-4 shrink-0">
            <button
              onClick={() => setViewMode(v => v === 'simple' ? 'advanced' : 'simple')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all border ${
                viewMode === 'simple'
                  ? 'bg-blue-50 text-blue-700 border-blue-200 hover:bg-blue-100'
                  : 'bg-gray-100 text-gray-700 border-gray-200 hover:bg-gray-200'
              }`}
              title={viewMode === 'simple' ? 'Switch to Advanced mode' : 'Switch to Simple mode'}
            >
              {viewMode === 'simple' ? <Eye size={14} /> : <Settings size={14} />}
              <span className="hidden sm:inline">{viewMode === 'simple' ? 'Simple' : 'Advanced'}</span>
            </button>
            {isAdmin && (
              <div className="relative">
                <button
                  onClick={() => setTimeTravelOpen(o => !o)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all border ${
                    timeTravelDate
                      ? 'bg-purple-100 text-purple-700 border-purple-300 hover:bg-purple-200'
                      : 'bg-gray-100 text-gray-700 border-gray-200 hover:bg-gray-200'
                  }`}
                  title="Time Travel"
                >
                  <Clock size={14} />
                  {timeTravelDate ? formatDate(timeTravelDate, { includeYear: true }) : 'Time Travel'}
                </button>
                {timeTravelOpen && (
                  <div className="absolute right-0 top-full mt-2 w-72 bg-white rounded-xl shadow-xl border border-gray-200 p-4 z-50">
                    <div className="flex items-center justify-between mb-3">
                      <h3 className="text-sm font-semibold text-gray-800">Time Travel</h3>
                      <button onClick={() => setTimeTravelOpen(false)} className="text-gray-400 hover:text-gray-600"><X size={14} /></button>
                    </div>
                    <input
                      type="date"
                      value={timeTravelDate || ''}
                      max={new Date().toISOString().split('T')[0]}
                      onChange={e => { setTimeTravelDate(e.target.value || null); setTimeTravelOpen(false); }}
                      className="w-full mb-3 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-400"
                    />
                    {timeTravelPresets.length > 0 ? (
                      <>
                        <div className="text-xs font-medium text-gray-500 mb-2">Signal Dates</div>
                        <div className="space-y-1.5 mb-3 max-h-48 overflow-y-auto">
                          {timeTravelPresets.map(({ date, symbols, detail, source }) => (
                            <button
                              key={date}
                              onClick={() => { setTimeTravelDate(date); setTimeTravelEmailPending(true); setTimeTravelOpen(false); }}
                              className={`w-full px-2.5 py-2 text-xs rounded-lg border transition-all text-left flex items-center justify-between gap-2 ${
                                timeTravelDate === date
                                  ? 'bg-purple-100 border-purple-300 text-purple-700'
                                  : 'bg-gray-50 border-gray-200 text-gray-600 hover:bg-gray-100'
                              }`}
                            >
                              <div className="flex flex-col">
                                <span className="font-medium">{formatDate(date, { includeYear: true })}</span>
                                <span className="text-gray-400 truncate max-w-[140px]">{symbols}</span>
                              </div>
                              <span className={`font-semibold whitespace-nowrap ${source === 'missed' ? 'text-green-600' : 'text-purple-600'}`}>{detail}</span>
                            </button>
                          ))}
                        </div>
                      </>
                    ) : (
                      <div className="text-xs text-gray-400 mb-3">Loading signal dates...</div>
                    )}
                    <div className="text-xs font-medium text-gray-500 mb-2">Market Events</div>
                    <div className="grid grid-cols-2 gap-1.5 mb-3">
                      {[
                        ['2025-08-05', 'VIX Spike (45+)'],
                        ['2025-04-07', 'Tariff Crash'],
                        ['2025-06-15', 'Summer Rally'],
                        ['2025-10-27', 'Q3 Earnings'],
                        ['2024-10-28', 'Election Run'],
                        ['2024-08-05', 'Yen Carry Unwind'],
                      ].map(([date, label]) => (
                        <button
                          key={date}
                          onClick={() => { setTimeTravelDate(date); setTimeTravelOpen(false); }}
                          className={`px-2 py-1.5 text-xs rounded-lg border transition-all text-left ${
                            timeTravelDate === date
                              ? 'bg-purple-100 border-purple-300 text-purple-700'
                              : 'bg-gray-50 border-gray-200 text-gray-600 hover:bg-gray-100'
                          }`}
                        >
                          {label}
                        </button>
                      ))}
                    </div>
                    {timeTravelDate && (
                      <button
                        onClick={() => { setTimeTravelDate(null); setTimeTravelOpen(false); }}
                        className="w-full px-3 py-2 text-xs font-medium text-purple-700 bg-purple-50 border border-purple-200 rounded-lg hover:bg-purple-100 transition-all"
                      >
                        Back to Live
                      </button>
                    )}
                  </div>
                )}
              </div>
            )}
            <div className="text-right text-sm hidden md:block">
              <div className="text-xs text-gray-400">{dataStatus.loaded} symbols loaded</div>
            </div>
            {user ? (
              <div className="relative">
                <button
                  onClick={() => setShowUserMenu(!showUserMenu)}
                  className="w-8 h-8 bg-blue-600 rounded-full flex items-center justify-center text-white font-medium hover:bg-blue-700 transition-colors"
                >
                  {(user.name || user.email || 'U')[0].toUpperCase()}
                </button>
                {showUserMenu && (
                  <>
                    <div className="fixed inset-0 z-40" onClick={() => setShowUserMenu(false)} />
                    <div className="absolute right-0 top-10 w-56 bg-white rounded-lg shadow-lg border z-50 py-1">
                      <div className="px-4 py-2 border-b">
                        <p className="text-sm font-medium text-gray-900 truncate">{user.name || user.email}</p>
                        <p className="text-xs text-gray-500 truncate">{user.email}</p>
                      </div>
                      {(user.subscription?.has_stripe_subscription || checkoutSuccess || ['active', 'past_due'].includes(user.subscription?.status)) && (
                        <button
                          onClick={async () => {
                            setShowUserMenu(false);
                            try {
                              const data = await api.post('/api/billing/portal', {});
                              window.location.href = data.portal_url;
                            } catch (err) {
                              console.error('Portal error:', err);
                              alert('Failed to open billing portal.');
                            }
                          }}
                          className="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-50 flex items-center gap-2"
                        >
                          <CreditCard size={14} />
                          Manage Subscription
                        </button>
                      )}
                      <button
                        onClick={() => { setShowUserMenu(false); setShowEmailPrefsModal(true); }}
                        className="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-50 flex items-center gap-2"
                      >
                        <Bell size={14} />
                        Email Preferences
                      </button>
                      <button
                        onClick={() => { setShowUserMenu(false); setShowReferralModal(true); }}
                        className="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-50 flex items-center gap-2"
                      >
                        <Gift size={14} />
                        Refer a Friend
                        {(user.referral_count > 0) && (
                          <span className="ml-auto bg-green-100 text-green-700 text-xs font-medium px-1.5 py-0.5 rounded-full">{user.referral_count}</span>
                        )}
                      </button>
                      {isAdmin && (
                        <button
                          onClick={() => { setShowUserMenu(false); setShow2FASettings(true); }}
                          className="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-50 flex items-center gap-2"
                        >
                          <Shield size={14} />
                          Two-Factor Auth
                          {user?.totp_enabled && (
                            <span className="ml-auto bg-green-100 text-green-700 text-xs font-medium px-1.5 py-0.5 rounded-full">On</span>
                          )}
                        </button>
                      )}
                      <button
                        onClick={() => { setShowUserMenu(false); logout(); }}
                        className="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-50 flex items-center gap-2"
                      >
                        <LogOut size={14} />
                        Sign Out
                      </button>
                    </div>
                  </>
                )}
              </div>
            ) : (
              <button onClick={() => setShowLoginModal(true)} className="px-4 py-2 bg-gray-900 text-white rounded-lg font-medium hover:bg-gray-800 flex items-center gap-2">
                <LogIn size={16} />Sign In
              </button>
            )}
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-3 sm:px-6 py-4 sm:py-6">
        <WelcomeTour />
        {/* Time Travel Banner */}
        {timeTravelDate && (
          <div className="mb-4 p-3 bg-purple-600 text-white rounded-xl flex items-center justify-between">
            <div className="flex items-center gap-2">
              {timeTravelLoading ? <Loader2 size={16} className="animate-spin" /> : <Clock size={16} />}
              <span className="text-sm font-medium">
                {timeTravelLoading
                  ? `Loading data for ${formatDate(timeTravelDate, { includeYear: true })}...`
                  : `Time Travel: Viewing dashboard as of ${formatDate(timeTravelDate, { includeYear: true })}`
                }
              </span>
              {timeTravelEmailStatus === 'sending' && <span className="text-xs text-purple-200 ml-2">Sending email...</span>}
              {timeTravelEmailStatus === 'sent' && <span className="text-xs text-green-300 ml-2">Email sent</span>}
              {timeTravelEmailStatus === 'failed' && <span className="text-xs text-red-300 ml-2">Email failed</span>}
            </div>
            <button
              onClick={() => setTimeTravelDate(null)}
              className="text-sm font-medium text-purple-200 hover:text-white flex items-center gap-1 transition-colors"
            >
              Back to Live <ChevronRight size={14} />
            </button>
          </div>
        )}

        {/* Subscription Banner */}
        {checkoutSuccess && (
          <div className="border border-green-200 bg-green-50 rounded-lg p-4 mb-6 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Zap className="text-green-600 flex-shrink-0" size={24} />
              <p className="font-medium text-green-800">Welcome to RigaCap! Your subscription is now active.</p>
            </div>
            <button onClick={() => setCheckoutSuccess(false)} className="p-1 text-green-400 hover:text-green-600"><X size={18} /></button>
          </div>
        )}
        {isAuthenticated && !checkoutSuccess && <SubscriptionBanner />}

        {/* Your RigaCap Journey — compact card with sparkline background */}
        {journeyData && !journeyData.error && activeTab === 'signals' && (
          <div className="mb-4 bg-gradient-to-r from-indigo-600 to-purple-600 rounded-xl text-white shadow-lg overflow-hidden">
            {/* Main body — sparkline as background, metrics overlaid */}
            <div className="relative px-5 pt-4 pb-3">
              {/* Sparkline background */}
              {journeyData.equity_curve && journeyData.equity_curve.length >= 3 && (
                <div className="absolute inset-0 top-4 opacity-30 pointer-events-none">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={journeyData.equity_curve} margin={{ top: 10, right: 0, left: 0, bottom: 0 }}>
                      <defs>
                        <linearGradient id="journeyBg" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#ffffff" stopOpacity={0.4} />
                          <stop offset="95%" stopColor="#ffffff" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <Area type="monotone" dataKey="value" stroke="#ffffff" strokeWidth={1.5}
                            fill="url(#journeyBg)" dot={false} />
                      <Area type="monotone" dataKey="spy" stroke="#fbbf24" strokeWidth={1}
                            fill="none" dot={false} strokeDasharray="4 2" />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              )}

              {/* Content overlaid on sparkline */}
              <div className="relative z-10">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="font-semibold text-sm">Your RigaCap Journey</h3>
                  <span className="text-xs text-indigo-200">Since {journeyData.start_date}</span>
                </div>

                {/* Metrics row */}
                <div className="grid grid-cols-3 gap-3">
                  <div className="text-center">
                    <p className="text-[10px] text-indigo-200 uppercase tracking-wide">Beating SPY</p>
                    <p className={`text-xl font-bold ${journeyData.alpha_pct != null ? ((journeyData.alpha_pct >= 0) ? 'text-green-300' : 'text-red-300') : ''}`}>
                      {journeyData.alpha_pct != null
                        ? `${journeyData.alpha_pct >= 0 ? '+' : ''}${journeyData.alpha_pct}%`
                        : `${journeyData.total_return_pct >= 0 ? '+' : ''}${journeyData.total_return_pct}%`}
                    </p>
                  </div>
                  <div className="text-center">
                    <p className="text-[10px] text-indigo-200 uppercase tracking-wide">Your Return</p>
                    <p className="text-lg font-semibold">
                      {journeyData.total_return_pct >= 0 ? '+' : ''}{journeyData.total_return_pct}%
                    </p>
                  </div>
                  <div className="text-center">
                    <p className="text-[10px] text-indigo-200 uppercase tracking-wide">$10K would be</p>
                    <p className="text-lg font-semibold">${journeyData.current_value?.toLocaleString()}</p>
                  </div>
                </div>
              </div>
            </div>

            {/* Footer — badges, stats, share in one row */}
            <div className="px-5 py-2 bg-black/10 flex items-center justify-between gap-2 flex-wrap">
              <div className="flex items-center gap-2 flex-wrap text-xs">
                {journeyData.best_trade && (
                  <span className="inline-flex items-center px-2 py-0.5 bg-white/15 rounded-full">
                    Best: {journeyData.best_trade.symbol} +{journeyData.best_trade.pnl_pct}%
                  </span>
                )}
                {journeyData.inception_return_pct != null && journeyData.inception_date && (
                  <span className="inline-flex items-center px-2 py-0.5 bg-white/15 rounded-full">
                    Since {journeyData.inception_date.slice(0, 4)}: +{journeyData.inception_return_pct}%
                  </span>
                )}
                <span className="text-indigo-200">
                  {journeyData.days_invested}d
                  {journeyData.trades_since_signup > 0
                    ? ` \u00B7 ${journeyData.wins_since_signup}W ${journeyData.trades_since_signup - journeyData.wins_since_signup}L`
                    : journeyData.trades_since_signup === 0 ? ' \u00B7 0 trades yet' : ''}
                </span>
              </div>
              <button
                onClick={() => {
                  let text = journeyData.alpha_pct != null
                    ? `Following @RigaCap signals, I'm beating the S&P 500 by ${journeyData.alpha_pct >= 0 ? '+' : ''}${journeyData.alpha_pct}% since ${journeyData.start_date}.`
                    : `Following @RigaCap signals: ${journeyData.total_return_pct >= 0 ? '+' : ''}${journeyData.total_return_pct}% since ${journeyData.start_date}.`;
                  if (journeyData.best_trade) text += ` Best trade: ${journeyData.best_trade.symbol} +${journeyData.best_trade.pnl_pct}%.`;
                  if (journeyData.inception_return_pct != null && journeyData.inception_date) text += ` Full track record: +${journeyData.inception_return_pct}% since ${journeyData.inception_date.slice(0, 4)}.`;
                  text += ' rigacap.com/track-record';
                  navigator.clipboard.writeText(text);
                  setJourneyCopied(true);
                  setTimeout(() => setJourneyCopied(false), 2000);
                }}
                className="flex items-center gap-1 px-2 py-1 text-xs bg-white/20 hover:bg-white/30 rounded-md transition-colors shrink-0"
              >
                {journeyCopied ? <><Check size={11} /> Copied!</> : <><Copy size={11} /> Share</>}
              </button>
            </div>
          </div>
        )}

        {/* Admin Dashboard */}
        {activeTab === 'admin' && isAdmin && (
          <AdminDashboard />
        )}

        {/* No data warning banner */}
        {noDataAvailable && (
          <div className="mb-4 bg-amber-50 border border-amber-200 rounded-xl p-4 flex items-center gap-3">
            <AlertCircle className="text-amber-500 flex-shrink-0" size={24} />
            <div>
              <h3 className="font-semibold text-amber-800">Market Data Loading</h3>
              <p className="text-sm text-amber-700">
                Historical data is being fetched. This may take a moment.
                Data refreshes automatically — check back in a few minutes.
              </p>
            </div>
          </div>
        )}

        {activeTab === 'signals' ? (
          <>
            {/* Go to Cash Banner */}
            {dashboardData?.regime_forecast?.recommended_action === 'go_to_cash' && (
              <div className="mb-4 p-4 bg-red-600 text-white rounded-xl flex items-center gap-3">
                <Shield className="w-6 h-6 flex-shrink-0" />
                <div>
                  <h3 className="font-bold text-lg">Market Conditions Deteriorating — Consider Closing Positions</h3>
                  <p className="text-red-100 text-sm">{dashboardData.regime_forecast.outlook_detail}</p>
                </div>
              </div>
            )}

            {/* Regime Forecast Bar */}
            {dashboardData?.regime_forecast && (
              viewMode === 'simple' ? (
                /* Simple mode: traffic light + one sentence, click to expand */
                <div className="mb-4">
                  <div
                    className="p-3 rounded-xl border border-gray-200 bg-white flex items-center gap-3 cursor-pointer hover:bg-gray-50 transition-colors"
                    onClick={() => setRegimeExpanded(prev => !prev)}
                  >
                    <div className={`w-4 h-4 rounded-full flex-shrink-0 ${
                      ['strong_bull', 'weak_bull', 'recovery'].includes(dashboardData.regime_forecast.current_regime) ? 'bg-emerald-500' :
                      ['rotating_bull', 'range_bound'].includes(dashboardData.regime_forecast.current_regime) ? 'bg-amber-400' :
                      'bg-red-500'
                    }`} />
                    <span className="text-sm text-gray-700 flex-1">
                      {['strong_bull', 'weak_bull'].includes(dashboardData.regime_forecast.current_regime)
                        ? 'Market looks good. Stay invested.'
                        : dashboardData.regime_forecast.current_regime === 'recovery'
                        ? 'Market is recovering. Good time to look for opportunities.'
                        : dashboardData.regime_forecast.current_regime === 'rotating_bull'
                        ? 'Market is rotating between sectors. Be selective.'
                        : dashboardData.regime_forecast.current_regime === 'range_bound'
                        ? 'Market is moving sideways. Wait for clearer direction.'
                        : dashboardData.regime_forecast.current_regime === 'weak_bear'
                        ? 'Caution: market weakening. Consider tightening stops.'
                        : 'Market under stress. Protect your positions.'}
                    </span>
                    {dashboardData.market_stats?.spy_price && (
                      <span className="text-sm font-medium text-gray-900 flex-shrink-0">
                        SPY {dashboardData.market_stats.spy_price.toFixed(2)}
                        {dashboardData.market_stats.spy_change_pct != null && (
                          <span className={`ml-1 ${dashboardData.market_stats.spy_change_pct >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                            ({dashboardData.market_stats.spy_change_pct >= 0 ? '+' : ''}{dashboardData.market_stats.spy_change_pct.toFixed(2)}%)
                          </span>
                        )}
                        {dashboardData.market_stats.live && (
                          <span className="ml-1.5 inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-700 uppercase tracking-wide">Live</span>
                        )}
                      </span>
                    )}
                    {dashboardData.data_date && (
                      <span className="text-xs text-gray-400 flex-shrink-0">as of {dashboardData.data_date}</span>
                    )}
                    <svg className={`w-4 h-4 text-gray-400 transition-transform flex-shrink-0 ${regimeExpanded ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </div>
                  {regimeExpanded && (() => {
                    const rf = dashboardData.regime_forecast;
                    const regimeColors = {
                      strong_bull: { bg: 'bg-emerald-100', text: 'text-emerald-700', bar: 'bg-emerald-500' },
                      weak_bull: { bg: 'bg-green-100', text: 'text-green-700', bar: 'bg-green-400' },
                      rotating_bull: { bg: 'bg-violet-100', text: 'text-violet-700', bar: 'bg-violet-400' },
                      range_bound: { bg: 'bg-amber-100', text: 'text-amber-700', bar: 'bg-amber-400' },
                      weak_bear: { bg: 'bg-orange-100', text: 'text-orange-700', bar: 'bg-orange-400' },
                      panic_crash: { bg: 'bg-red-100', text: 'text-red-700', bar: 'bg-red-500' },
                      recovery: { bg: 'bg-cyan-100', text: 'text-cyan-700', bar: 'bg-cyan-400' },
                    };
                    const regimeDescriptions = {
                      strong_bull: 'Broad market rally with strong breadth',
                      weak_bull: 'Advancing market, narrow leadership',
                      rotating_bull: 'Sector rotation driving gains',
                      range_bound: 'Sideways, low conviction',
                      weak_bear: 'Declining with selling pressure',
                      panic_crash: 'Sharp selloff, elevated volatility',
                      recovery: 'Rebounding from recent lows',
                    };
                    const regimeNames = {
                      strong_bull: 'Strong Bull', weak_bull: 'Weak Bull', rotating_bull: 'Rotating Bull',
                      range_bound: 'Range Bound', weak_bear: 'Weak Bear', panic_crash: 'Panic / Crash', recovery: 'Recovery',
                    };
                    const probs = rf.transition_probabilities || rf.probabilities || {};
                    const sortedProbs = Object.entries(probs).filter(([, p]) => p > 3).sort((a, b) => b[1] - a[1]);
                    const allRegimes = ['strong_bull', 'weak_bull', 'rotating_bull', 'range_bound', 'weak_bear', 'panic_crash', 'recovery'];

                    return (
                      <div className="mt-1 p-4 rounded-xl border border-gray-200 bg-white space-y-4">
                        {/* Regime name + pills */}
                        <div className="flex items-center justify-between flex-wrap gap-2">
                          <span className="font-semibold text-gray-900">{rf.current_regime_name || regimeNames[rf.current_regime]} Market</span>
                          <div className="flex gap-2 flex-wrap">
                            <span className={`text-xs px-2 py-0.5 rounded font-medium ${
                              rf.outlook === 'stable' ? 'bg-green-100 text-green-700' :
                              rf.outlook === 'improving' ? 'bg-emerald-100 text-emerald-700' :
                              'bg-orange-100 text-orange-700'
                            }`}>Outlook: {rf.outlook}</span>
                            <span className={`text-xs px-2 py-0.5 rounded font-medium ${
                              rf.risk_change === 'decreasing' ? 'bg-green-100 text-green-700' :
                              rf.risk_change === 'stable' ? 'bg-gray-100 text-gray-600' :
                              'bg-red-100 text-red-700'
                            }`}>Risk: {rf.risk_change}</span>
                            <span className={`text-xs px-2 py-0.5 rounded font-medium ${
                              rf.recommended_action === 'stay_invested' ? 'bg-green-100 text-green-700' :
                              rf.recommended_action === 'tighten_stops' ? 'bg-yellow-100 text-yellow-700' :
                              rf.recommended_action === 'reduce_exposure' ? 'bg-orange-100 text-orange-700' :
                              'bg-red-100 text-red-700'
                            }`}>{(rf.recommended_action || '').replace(/_/g, ' ')}</span>
                          </div>
                        </div>

                        {/* Outlook detail */}
                        {rf.outlook_detail && (
                          <p className="text-sm text-gray-600 leading-relaxed">{rf.outlook_detail}</p>
                        )}

                        {/* SPY + VIX */}
                        {dashboardData.market_stats && (
                          <div className="flex gap-6 text-sm">
                            <div>
                              <span className="text-gray-500">S&P 500</span>
                              <span className="ml-2 font-semibold text-gray-900">${dashboardData.market_stats.spy_price?.toFixed(0)}</span>
                              {dashboardData.market_stats.spy_change_pct != null && (
                                <span className={`ml-1 text-xs font-medium ${dashboardData.market_stats.spy_change_pct >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                                  {dashboardData.market_stats.spy_change_pct >= 0 ? '+' : ''}{dashboardData.market_stats.spy_change_pct.toFixed(2)}%
                                </span>
                              )}
                            </div>
                            <div>
                              <span className="text-gray-500">Market Fear</span>
                              <span className={`ml-2 font-semibold ${getVixLabel(dashboardData.market_stats.vix_level).color}`}>{getVixLabel(dashboardData.market_stats.vix_level).label}</span>
                              <span className="ml-1 text-xs text-gray-400">(VIX: {dashboardData.market_stats.vix_level?.toFixed(1)})</span>
                            </div>
                          </div>
                        )}

                        {/* Market Context — AI summary of signal changes */}
                        {dashboardData.market_context && (
                          <div className="bg-blue-50 border-l-4 border-blue-400 rounded-r-lg px-3 py-2">
                            <p className="text-sm text-blue-800 leading-relaxed">{dashboardData.market_context}</p>
                          </div>
                        )}

                        {/* Transition probability bar */}
                        {sortedProbs.length > 0 && (
                          <div>
                            <p className="text-xs text-gray-500 font-medium mb-1">Transition Probabilities</p>
                            <div className="flex h-2 rounded-full overflow-hidden bg-gray-100">
                              {sortedProbs.map(([r, pct]) => (
                                <div key={r} className={`h-full ${regimeColors[r]?.bar || 'bg-gray-300'}`} style={{ width: `${pct}%` }} title={`${regimeNames[r]}: ${pct.toFixed(0)}%`} />
                              ))}
                            </div>
                            <div className="flex flex-wrap gap-3 mt-1">
                              {sortedProbs.map(([r, pct]) => (
                                <div key={r} className="flex items-center gap-1">
                                  <div className={`w-2 h-2 rounded-full ${regimeColors[r]?.bar || 'bg-gray-300'}`} />
                                  <span className="text-xs text-gray-500">{regimeNames[r]} {pct.toFixed(0)}%</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* All 7 regimes */}
                        <div className="border-t border-gray-100 pt-3 space-y-1">
                          {allRegimes.map(r => {
                            const isCurrent = r === rf.current_regime;
                            const c = regimeColors[r] || { bg: 'bg-gray-100', text: 'text-gray-600', bar: 'bg-gray-300' };
                            const prob = probs[r];
                            return (
                              <div key={r} className={`flex items-center justify-between px-2 py-1.5 rounded-lg ${isCurrent ? c.bg : ''}`}>
                                <div className="flex items-center gap-2">
                                  <div className={`w-2.5 h-2.5 rounded-full ${c.bar}`} />
                                  <div>
                                    <span className={`text-sm font-medium ${isCurrent ? c.text : 'text-gray-700'}`}>
                                      {regimeNames[r]}{isCurrent ? ' \u25CF' : ''}
                                    </span>
                                    <span className="text-xs text-gray-400 ml-2">{regimeDescriptions[r]}</span>
                                  </div>
                                </div>
                                {prob != null && (
                                  <span className={`text-sm font-semibold ${isCurrent ? c.text : 'text-gray-500'}`}>{prob.toFixed(0)}%</span>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })()}
                </div>
              ) : (
                /* Advanced mode: full regime bar */
                <div onClick={() => setRegimeExpanded(v => !v)} className={`mb-4 p-4 rounded-xl border cursor-pointer ${
                  dashboardData.regime_forecast.current_regime === 'strong_bull' ? 'bg-emerald-50 border-emerald-200' :
                  dashboardData.regime_forecast.current_regime === 'weak_bull' ? 'bg-green-50 border-green-200' :
                  dashboardData.regime_forecast.current_regime === 'rotating_bull' ? 'bg-violet-50 border-violet-200' :
                  dashboardData.regime_forecast.current_regime === 'range_bound' ? 'bg-amber-50 border-amber-200' :
                  dashboardData.regime_forecast.current_regime === 'recovery' ? 'bg-cyan-50 border-cyan-200' :
                  dashboardData.regime_forecast.current_regime === 'weak_bear' ? 'bg-orange-50 border-orange-200' :
                  dashboardData.regime_forecast.current_regime === 'panic_crash' ? 'bg-red-50 border-red-200' :
                  'bg-gray-50 border-gray-200'
                }`}>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className={`p-2 rounded-full ${
                        dashboardData.regime_forecast.current_regime === 'strong_bull' ? 'bg-emerald-100' :
                        dashboardData.regime_forecast.current_regime === 'weak_bull' ? 'bg-green-100' :
                        dashboardData.regime_forecast.current_regime === 'rotating_bull' ? 'bg-violet-100' :
                        dashboardData.regime_forecast.current_regime === 'range_bound' ? 'bg-amber-100' :
                        dashboardData.regime_forecast.current_regime === 'recovery' ? 'bg-cyan-100' :
                        dashboardData.regime_forecast.current_regime === 'weak_bear' ? 'bg-orange-100' :
                        'bg-red-100'
                      }`}>
                        {['strong_bull', 'weak_bull', 'recovery'].includes(dashboardData.regime_forecast.current_regime) ? <TrendingUp className="w-5 h-5 text-emerald-600" /> :
                         dashboardData.regime_forecast.current_regime === 'rotating_bull' ? <RefreshCw className="w-5 h-5 text-violet-600" /> :
                         dashboardData.regime_forecast.current_regime === 'range_bound' ? <Activity className="w-5 h-5 text-amber-600" /> :
                         <TrendingDown className="w-5 h-5 text-red-600" />}
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-gray-900">
                            {dashboardData.regime_forecast.current_regime_name} Market
                          </span>
                          {dashboardData.market_stats?.spy_price && (
                            <>
                              <span className="text-gray-400">|</span>
                              <span className="text-gray-600 text-sm">
                                SPY ${dashboardData.market_stats.spy_price.toFixed(2)}
                                {dashboardData.market_stats.spy_change_pct != null && (
                                  <span className={`ml-1 font-medium ${dashboardData.market_stats.spy_change_pct >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                                    ({dashboardData.market_stats.spy_change_pct >= 0 ? '+' : ''}{dashboardData.market_stats.spy_change_pct.toFixed(2)}%)
                                  </span>
                                )}
                              </span>
                            </>
                          )}
                          {dashboardData.market_stats?.vix_level && (
                            <>
                              <span className="text-gray-400">|</span>
                              <span className="text-gray-600 text-sm">Market Fear: <span className={`font-medium ${getVixLabel(dashboardData.market_stats.vix_level).color}`}>{getVixLabel(dashboardData.market_stats.vix_level).label}</span></span>
                            </>
                          )}
                        </div>
                        <div className="flex items-center gap-2 mt-1">
                          <span className={`text-xs px-2 py-0.5 rounded font-medium ${
                            dashboardData.regime_forecast.outlook === 'stable' ? 'bg-green-100 text-green-700' :
                            dashboardData.regime_forecast.outlook === 'improving' ? 'bg-emerald-100 text-emerald-700' :
                            'bg-orange-100 text-orange-700'
                          }`}>
                            Outlook: {dashboardData.regime_forecast.outlook}
                          </span>
                          <span className={`text-xs px-2 py-0.5 rounded font-medium ${
                            dashboardData.regime_forecast.risk_change === 'decreasing' ? 'bg-green-100 text-green-700' :
                            dashboardData.regime_forecast.risk_change === 'stable' ? 'bg-gray-100 text-gray-600' :
                            'bg-red-100 text-red-700'
                          }`}>
                            Risk: {dashboardData.regime_forecast.risk_change}
                          </span>
                          <span className={`text-xs px-2 py-0.5 rounded font-medium ${
                            dashboardData.regime_forecast.recommended_action === 'stay_invested' ? 'bg-green-100 text-green-700' :
                            dashboardData.regime_forecast.recommended_action === 'tighten_stops' ? 'bg-yellow-100 text-yellow-700' :
                            dashboardData.regime_forecast.recommended_action === 'reduce_exposure' ? 'bg-orange-100 text-orange-700' :
                            'bg-red-100 text-red-700'
                          }`}>
                            {dashboardData.regime_forecast.recommended_action.replace(/_/g, ' ')}
                          </span>
                          {dashboardData.regime_adjustments?.changes?.length > 0 && (
                            <span className="text-xs px-2 py-0.5 rounded font-medium bg-blue-100 text-blue-700">
                              {dashboardData.regime_adjustments.changes.length} param{dashboardData.regime_adjustments.changes.length > 1 ? 's' : ''} adjusted
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="text-sm text-gray-600 max-w-sm text-right leading-tight">
                        {dashboardData.regime_forecast.outlook_detail}
                      </div>
                      <svg className={`w-4 h-4 text-gray-400 transition-transform flex-shrink-0 ${regimeExpanded ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                      </svg>
                    </div>
                  </div>

                  {/* Transition probabilities mini bar */}
                  {dashboardData.regime_forecast.transition_probabilities && (
                    <div className="mt-3 flex items-center gap-1 h-3 rounded-full overflow-hidden bg-gray-100">
                      {Object.entries(dashboardData.regime_forecast.transition_probabilities)
                        .filter(([_, pct]) => pct > 3)
                        .sort((a, b) => b[1] - a[1])
                        .map(([regime, pct]) => {
                          const colors = {
                            strong_bull: 'bg-emerald-500',
                            weak_bull: 'bg-green-400',
                            rotating_bull: 'bg-violet-400',
                            range_bound: 'bg-amber-400',
                            weak_bear: 'bg-orange-400',
                            panic_crash: 'bg-red-500',
                            recovery: 'bg-cyan-400',
                          };
                          return (
                            <div
                              key={regime}
                              className={`h-full ${colors[regime] || 'bg-gray-300'}`}
                              style={{ width: `${pct}%` }}
                              title={`${regime.replace('_', ' ')}: ${pct.toFixed(0)}%`}
                            />
                          );
                        })}
                    </div>
                  )}

                  {/* Expanded: regime detail panel */}
                  {regimeExpanded && (() => {
                    const rf = dashboardData.regime_forecast;
                    const regimeColors = {
                      strong_bull: { bg: 'bg-emerald-100', text: 'text-emerald-700', bar: 'bg-emerald-500' },
                      weak_bull: { bg: 'bg-green-100', text: 'text-green-700', bar: 'bg-green-400' },
                      rotating_bull: { bg: 'bg-violet-100', text: 'text-violet-700', bar: 'bg-violet-400' },
                      range_bound: { bg: 'bg-amber-100', text: 'text-amber-700', bar: 'bg-amber-400' },
                      weak_bear: { bg: 'bg-orange-100', text: 'text-orange-700', bar: 'bg-orange-400' },
                      panic_crash: { bg: 'bg-red-100', text: 'text-red-700', bar: 'bg-red-500' },
                      recovery: { bg: 'bg-cyan-100', text: 'text-cyan-700', bar: 'bg-cyan-400' },
                    };
                    const regimeDescriptions = {
                      strong_bull: 'Broad market rally with strong breadth',
                      weak_bull: 'Advancing market, narrow leadership',
                      rotating_bull: 'Sector rotation driving gains',
                      range_bound: 'Sideways, low conviction',
                      weak_bear: 'Declining with selling pressure',
                      panic_crash: 'Sharp selloff, elevated volatility',
                      recovery: 'Rebounding from recent lows',
                    };
                    const regimeNames = {
                      strong_bull: 'Strong Bull', weak_bull: 'Weak Bull', rotating_bull: 'Rotating Bull',
                      range_bound: 'Range Bound', weak_bear: 'Weak Bear', panic_crash: 'Panic / Crash', recovery: 'Recovery',
                    };
                    const probs = rf.transition_probabilities || rf.probabilities || {};
                    const sortedProbs = Object.entries(probs).filter(([, p]) => p > 3).sort((a, b) => b[1] - a[1]);
                    const allRegimes = ['strong_bull', 'weak_bull', 'rotating_bull', 'range_bound', 'weak_bear', 'panic_crash', 'recovery'];

                    return (
                      <div className="mt-3 pt-3 border-t border-gray-200 space-y-3">
                        {/* Probability bar with labels */}
                        {sortedProbs.length > 0 && (
                          <div>
                            <p className="text-xs text-gray-500 font-medium mb-1">Transition Probabilities</p>
                            <div className="flex h-2 rounded-full overflow-hidden bg-gray-100">
                              {sortedProbs.map(([r, pct]) => (
                                <div key={r} className={`h-full ${regimeColors[r]?.bar || 'bg-gray-300'}`} style={{ width: `${pct}%` }} />
                              ))}
                            </div>
                            <div className="flex flex-wrap gap-3 mt-1">
                              {sortedProbs.map(([r, pct]) => (
                                <div key={r} className="flex items-center gap-1">
                                  <div className={`w-2 h-2 rounded-full ${regimeColors[r]?.bar || 'bg-gray-300'}`} />
                                  <span className="text-xs text-gray-500">{regimeNames[r]} {pct.toFixed(0)}%</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* All 7 regimes */}
                        <div className="space-y-1">
                          {allRegimes.map(r => {
                            const isCurrent = r === rf.current_regime;
                            const c = regimeColors[r] || { bg: 'bg-gray-100', text: 'text-gray-600', bar: 'bg-gray-300' };
                            const prob = probs[r];
                            return (
                              <div key={r} className={`flex items-center justify-between px-2 py-1.5 rounded-lg ${isCurrent ? c.bg : ''}`}>
                                <div className="flex items-center gap-2">
                                  <div className={`w-2.5 h-2.5 rounded-full ${c.bar}`} />
                                  <div>
                                    <span className={`text-sm font-medium ${isCurrent ? c.text : 'text-gray-700'}`}>
                                      {regimeNames[r]}{isCurrent ? ' \u25CF' : ''}
                                    </span>
                                    <span className="text-xs text-gray-400 ml-2">{regimeDescriptions[r]}</span>
                                  </div>
                                </div>
                                {prob != null && (
                                  <span className={`text-sm font-semibold ${isCurrent ? c.text : 'text-gray-500'}`}>{prob.toFixed(0)}%</span>
                                )}
                              </div>
                            );
                          })}
                        </div>

                        {/* Regime-adaptive parameter adjustments */}
                        {dashboardData.regime_adjustments?.changes?.length > 0 && (
                          <div className="mt-3 pt-3 border-t border-gray-200">
                            <p className="text-xs text-gray-500 font-medium mb-2">Active Parameter Adjustments</p>
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
                              {dashboardData.regime_adjustments.changes.map(change => (
                                <div key={change.param} className="flex items-center gap-2 text-xs">
                                  <div className={`w-1.5 h-1.5 rounded-full ${change.offset > 0 ? 'bg-amber-400' : 'bg-emerald-400'}`} />
                                  <span className="text-gray-700">{change.description}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })()}
                </div>
              )
            )}

            {/* Metric Cards */}
            {viewMode === 'simple' ? (
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 mb-6">
                <MetricCard title="Portfolio Value" value={`$${totalValue.toLocaleString(undefined, {maximumFractionDigits: 0})}`} icon={Wallet} trend="up" />
                <MetricCard title="P&L" value={`${totalPnlPct >= 0 ? '+' : ''}${totalPnlPct.toFixed(1)}%`} icon={totalPnlPct >= 0 ? TrendingUp : TrendingDown} trend={totalPnlPct >= 0 ? 'up' : 'down'} />
                <MetricCard title="Buy Signals" value={dashboardData?.market_stats?.signal_count || signalsWithLiveQuotes.length} subtitle={`${dashboardData?.market_stats?.fresh_count || 0} fresh`} icon={Zap} />
              </div>
            ) : (
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4 mb-6">
                <MetricCard title="Portfolio Value" value={`$${totalValue.toLocaleString(undefined, {maximumFractionDigits: 0})}`} icon={Wallet} trend="up" />
                <MetricCard title="Open P&L" value={`${totalPnlPct >= 0 ? '+' : ''}${totalPnlPct.toFixed(1)}%`} icon={totalPnlPct >= 0 ? TrendingUp : TrendingDown} trend={totalPnlPct >= 0 ? 'up' : 'down'} />
                <MetricCard title="Positions" value={`${positions.length}/6`} icon={PieIcon} />
                <MetricCard title="Buy Signals" value={dashboardData?.market_stats?.signal_count || signalsWithLiveQuotes.length} subtitle={`${dashboardData?.market_stats?.fresh_count || 0} fresh`} icon={Zap} />
                <MetricCard title="Win Rate" value={`${winRate.toFixed(0)}%`} subtitle={`${trades.length} trades`} icon={Target} />
              </div>
            )}

            {/* Last updated timestamp */}
            {dashboardData?.generated_at && (
              <p className="text-xs text-gray-400 text-right mb-2 -mt-2">
                Last updated: {(() => {
                  const raw = dashboardData.generated_at;
                  const d = new Date(raw.endsWith('Z') ? raw : raw + 'Z');
                  if (isNaN(d.getTime())) return '';
                  const now = new Date();
                  const isToday = d.toDateString() === now.toDateString();
                  const time = d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
                  if (isToday) return `Today at ${time}`;
                  const yesterday = new Date(now); yesterday.setDate(yesterday.getDate() - 1);
                  if (d.toDateString() === yesterday.toDateString()) return `Yesterday at ${time}`;
                  return `${formatDate(dashboardData.generated_at)} at ${time}`;
                })()}
              </p>
            )}

            {/* Two column layout: Buy Signals | Open Positions */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* LEFT: Buy Signals */}
              <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
                <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Zap className="w-5 h-5 text-yellow-500" />
                    <h2 className="text-lg font-semibold text-gray-900">Buy Signals</h2>
                    <span className="text-[10px] text-gray-400 ml-1">Signals only — execute via your broker</span>
                    {dashboardData?.buy_signals?.filter(s => s.is_fresh).length > 0 && (
                      <span className="bg-green-100 text-green-800 text-xs px-2 py-0.5 rounded-full font-medium">
                        {dashboardData.buy_signals.filter(s => s.is_fresh).length} fresh
                      </span>
                    )}
                    <button
                      onClick={() => setSectorFilterOpen(prev => !prev)}
                      className="ml-1 p-1 rounded hover:bg-gray-100 transition-colors relative"
                      title="Filter by sector"
                    >
                      <Filter size={14} className="text-gray-400" />
                      {excludedSectors.length > 0 && (
                        <span className="absolute -top-0.5 -right-0.5 w-2 h-2 bg-blue-500 rounded-full" />
                      )}
                    </button>
                  </div>
                  <span className="text-xs text-gray-500">
                    {(() => {
                      // Find the most recent ensemble entry date
                      // Priority: unfiltered fresh dates (includes held positions) > current signals > persisted DB date
                      const freshDates = dashboardData?.fresh_signal_dates?.length > 0
                        ? [...dashboardData.fresh_signal_dates]
                        : (dashboardData?.buy_signals || [])
                            .filter(s => s.is_fresh)
                            .map(s => s.ensemble_entry_date)
                            .filter(Boolean);
                      const allDates = (dashboardData?.buy_signals || [])
                        .map(s => s.ensemble_entry_date)
                        .filter(Boolean);
                      // Include the persisted last_ensemble_entry_date (survives top-N churn)
                      if (dashboardData?.last_ensemble_entry_date) {
                        allDates.push(dashboardData.last_ensemble_entry_date);
                      }
                      const dates = freshDates.length > 0 ? freshDates : allDates;
                      if (dates.length === 0) return 'Ensemble: Breakout + Momentum';
                      const latest = dates.sort().reverse()[0];
                      const today = new Date(); today.setHours(0,0,0,0);
                      const signalDate = new Date(latest + 'T00:00:00');
                      const diffDays = Math.round((today - signalDate) / 86400000);
                      if (diffDays === 0) return 'Last signal: Today';
                      if (diffDays === 1) return 'Last signal: Yesterday';
                      return `Last signal: ${diffDays}d ago`;
                    })()}
                  </span>
                </div>

                {/* Collapsible sector filter pills */}
                {sectorFilterOpen && (() => {
                  const allSignals = dashboardData?.buy_signals || [];
                  const allPositions = dashboardData?.positions_with_guidance || guidanceWithLiveQuotes || [];
                  const sectorCounts = {};
                  allSignals.forEach(s => {
                    const sec = s.sector || 'Other';
                    sectorCounts[sec] = (sectorCounts[sec] || 0) + 1;
                  });
                  allPositions.forEach(p => {
                    const sec = p.sector || 'Other';
                    sectorCounts[sec] = (sectorCounts[sec] || 0) + 1;
                  });
                  const activeSectors = Object.keys(sectorCounts).sort();
                  if (activeSectors.length <= 1) return null;
                  return (
                    <div className="px-4 py-2 border-b border-gray-100 flex flex-wrap items-center gap-1.5 bg-gray-50/50">
                      <span className="text-[10px] text-gray-400 mr-1 uppercase tracking-wider">Sectors</span>
                      {activeSectors.map(sector => {
                        const isExcluded = excludedSectors.includes(sector);
                        const count = sectorCounts[sector] || 0;
                        return (
                          <button
                            key={sector}
                            onClick={() => setExcludedSectors(prev =>
                              isExcluded ? prev.filter(s => s !== sector) : [...prev, sector]
                            )}
                            className={`text-[11px] px-2 py-0.5 rounded-full border transition-all ${
                              isExcluded
                                ? 'border-gray-200 text-gray-400 bg-white'
                                : 'border-blue-200 text-blue-700 bg-blue-50'
                            }`}
                          >
                            {sector}
                            {isExcluded && count > 0 && (
                              <span className="ml-1 text-[10px] text-gray-400">({count})</span>
                            )}
                          </button>
                        );
                      })}
                      {excludedSectors.length > 0 && (
                        <button
                          onClick={() => setExcludedSectors([])}
                          className="text-[10px] text-blue-500 hover:text-blue-700 ml-1"
                        >
                          Reset
                        </button>
                      )}
                      <div className="ml-auto group relative">
                        <Info size={12} className="text-gray-300 cursor-help" />
                        <div className="absolute right-0 bottom-full mb-1 w-52 p-2 bg-gray-900 text-white text-[10px] rounded-lg shadow-lg opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-20">
                          Display filter only — the system scans the full universe every day regardless of this setting.
                        </div>
                      </div>
                    </div>
                  );
                })()}

                <div className="max-h-[500px] overflow-y-auto relative">
                  {timeTravelLoading && (
                    <div className="absolute inset-0 bg-white/80 z-10 flex items-center justify-center">
                      <div className="flex flex-col items-center gap-2">
                        <Loader2 className="w-6 h-6 text-purple-600 animate-spin" />
                        <span className="text-xs text-purple-600 font-medium">Loading signals...</span>
                      </div>
                    </div>
                  )}
                  {dashboardData?.subscription_required ? (
                    /* Upgrade prompt for users without valid subscription */
                    <div className="p-6 text-center space-y-4">
                      <div className="w-12 h-12 bg-gray-100 rounded-full flex items-center justify-center mx-auto">
                        <Lock className="w-6 h-6 text-gray-400" />
                      </div>
                      <div>
                        <h3 className="text-base font-semibold text-gray-900">Unlock Buy Signals</h3>
                        <p className="text-sm text-gray-500 mt-1">
                          Subscribe to see real-time ensemble signals, momentum rankings, and watchlist alerts.
                        </p>
                      </div>
                      {dashboardData?.regime_forecast && (
                        <div className="flex items-center justify-center gap-2 text-sm text-gray-600">
                          <div className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${
                            ['strong_bull', 'weak_bull', 'recovery'].includes(dashboardData.regime_forecast.current_regime) ? 'bg-emerald-500' :
                            ['rotating_bull', 'range_bound'].includes(dashboardData.regime_forecast.current_regime) ? 'bg-amber-400' :
                            'bg-red-500'
                          }`} />
                          <span>Current regime: <strong>{dashboardData.regime_forecast.current_regime_name}</strong></span>
                        </div>
                      )}
                      <div className="pt-2 space-y-2">
                        {user ? (
                          <>
                            <button
                              onClick={async () => {
                                setUpgradeLoading(true);
                                try {
                                  const data = await api.post('/api/billing/create-checkout', { plan: 'annual' });
                                  if (window.gtag) window.gtag('event', 'begin_checkout', { value: 349, currency: 'USD' });
                                  window.location.href = data.checkout_url;
                                } catch (err) {
                                  console.error('Checkout error:', err);
                                  alert('Failed to start checkout. Please try again.');
                                } finally {
                                  setUpgradeLoading(false);
                                }
                              }}
                              disabled={upgradeLoading}
                              className="w-full px-4 py-2.5 bg-gradient-to-r from-blue-600 to-indigo-600 text-white font-medium rounded-lg hover:from-blue-700 hover:to-indigo-700 transition-all disabled:opacity-50"
                            >
                              {upgradeLoading ? 'Loading...' : 'Subscribe — $349/year (Save $119)'}
                            </button>
                            <button
                              onClick={async () => {
                                setUpgradeLoading(true);
                                try {
                                  const data = await api.post('/api/billing/create-checkout', { plan: 'monthly' });
                                  if (window.gtag) window.gtag('event', 'begin_checkout', { value: 39, currency: 'USD' });
                                  window.location.href = data.checkout_url;
                                } catch (err) {
                                  console.error('Checkout error:', err);
                                  alert('Failed to start checkout. Please try again.');
                                } finally {
                                  setUpgradeLoading(false);
                                }
                              }}
                              disabled={upgradeLoading}
                              className="w-full px-4 py-2 text-sm text-gray-600 hover:text-gray-900 font-medium transition-colors"
                            >
                              or $39/month
                            </button>
                          </>
                        ) : (
                          <button
                            onClick={() => setShowLoginModal(true)}
                            className="w-full px-4 py-2.5 bg-gray-900 text-white font-medium rounded-lg hover:bg-gray-800 transition-all flex items-center justify-center gap-2"
                          >
                            <LogIn className="w-4 h-4" />
                            Sign in to get started
                          </button>
                        )}
                      </div>
                    </div>
                  ) : (dashboardData?.buy_signals || []).length > 0 ? (
                    (() => {
                      const sectorFilter = (s) => !excludedSectors.includes(s.sector || 'Other');
                      const freshSignals = (dashboardData?.buy_signals || []).filter(s => s.is_fresh && sectorFilter(s));
                      const monitoringSignals = (dashboardData?.buy_signals || []).filter(s => !s.is_fresh && sectorFilter(s));

                      // Days since last ensemble signal (for dynamic empty-state messaging)
                      // Use unfiltered fresh_signal_dates to include signals already held as positions
                      const daysSinceLastSignal = (() => {
                        const allDates = [
                          ...(dashboardData?.fresh_signal_dates || []),
                          ...(dashboardData?.buy_signals || []).map(s => s.ensemble_entry_date).filter(Boolean),
                        ];
                        if (dashboardData?.last_ensemble_entry_date) {
                          allDates.push(dashboardData.last_ensemble_entry_date);
                        }
                        if (allDates.length === 0) return null;
                        const latest = [...new Set(allDates)].sort().reverse()[0];
                        const today = new Date(); today.setHours(0,0,0,0);
                        const signalDate = new Date(latest + 'T00:00:00');
                        return Math.round((today - signalDate) / 86400000);
                      })();
                      const heldFreshCount = (dashboardData?.total_fresh_count || 0) - freshSignals.length;

                      const renderSimpleSignal = (s) => {
                        const label = s.signal_strength_label || (() => {
                          const score = s.ensemble_score || 0;
                          if (score >= 88) return 'Very Strong';
                          if (score >= 75) return 'Strong';
                          if (score >= 61) return 'Moderate';
                          return 'Weak';
                        })();
                        const labelColor = label === 'Very Strong' ? 'bg-emerald-600 text-white' :
                                          label === 'Strong' ? 'bg-emerald-100 text-emerald-800' :
                                          label === 'Moderate' ? 'bg-amber-100 text-amber-800' :
                                          'bg-gray-100 text-gray-600';
                        return (
                          <div
                            key={s.symbol}
                            className={`px-4 py-3 flex items-center justify-between cursor-pointer transition-colors ${
                              s.is_fresh ? 'bg-green-50 hover:bg-green-100 border-l-4 border-l-green-500' : 'hover:bg-gray-50'
                            }`}
                            onClick={() => setChartModal({ type: 'signal', data: s, symbol: s.symbol })}
                          >
                            <div className="flex items-center gap-3">
                              <span className={`font-semibold text-base ${s.is_fresh ? 'text-green-900' : 'text-gray-900'}`}>{s.symbol}</span>
                              {s.is_intraday && (
                                <span className="inline-flex items-center gap-0.5 text-[10px] bg-amber-500 text-white px-1.5 py-0.5 rounded-full font-semibold animate-pulse">
                                  <Clock className="w-3 h-3" />
                                  LIVE
                                </span>
                              )}
                              <span className="text-gray-500 text-sm">${s.price?.toFixed(2)}</span>
                              <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-semibold ${labelColor}`}>{label}</span>
                            </div>
                            <div className="flex items-center gap-2">
                              {s.is_fresh && (
                                <span className={`text-xs bg-green-600 text-white px-2.5 py-1 rounded font-medium ${((s.days_since_entry ?? s.days_since_crossover) === 0) ? 'animate-pulse' : ''}`}>BUY</span>
                              )}
                              {s.is_fresh && (s.days_since_entry ?? s.days_since_crossover) === 0 && (
                                <span className="text-xs text-green-700 font-semibold">New!</span>
                              )}
                            </div>
                          </div>
                        );
                      };

                      const renderAdvancedSignal = (s) => (
                        <tr
                          key={s.symbol}
                          className={`cursor-pointer transition-colors ${
                            s.is_fresh
                              ? 'bg-green-50 hover:bg-green-100 border-l-4 border-l-green-500'
                              : 'hover:bg-gray-50'
                          }`}
                          onClick={() => setChartModal({ type: 'signal', data: s, symbol: s.symbol })}
                        >
                          <td className="px-3 py-2.5">
                            <div className="flex items-center gap-1.5">
                              <span className={`font-semibold ${s.is_fresh ? 'text-green-900' : 'text-gray-900'}`}>
                                {s.symbol}
                              </span>
                              {s.is_strong && <ArrowUpRight className="w-3 h-3 text-green-500" />}
                              {s.is_intraday && (
                                <span className="inline-flex items-center gap-0.5 text-[10px] bg-amber-500 text-white px-1.5 py-0.5 rounded-full font-semibold animate-pulse">
                                  <Clock className="w-3 h-3" />
                                  LIVE
                                </span>
                              )}
                            </div>
                            {s.is_fresh ? (
                              <span className={`text-xs ${(s.days_since_entry ?? s.days_since_crossover) === 0 ? 'text-green-700 font-semibold' : 'text-green-600'}`}>
                                {(s.days_since_entry ?? s.days_since_crossover) === 0 ? 'New today!' : `${Math.min(s.days_since_entry ?? 999, s.days_since_crossover ?? 999)}d ago`}
                              </span>
                            ) : (
                              <span className="text-xs text-gray-400">Crossed {s.days_since_crossover}d ago</span>
                            )}
                          </td>
                          <td className="px-3 py-2.5 text-right">${s.price?.toFixed(2)}</td>
                          <td className="px-3 py-2.5 text-right text-green-600 font-medium">+{s.pct_above_dwap?.toFixed(1)}%</td>
                          <td className="px-3 py-2.5 text-right">
                            <span className={`font-medium ${s.momentum_rank <= 5 ? 'text-green-600' : 'text-gray-600'}`}>
                              #{s.momentum_rank}
                            </span>
                          </td>
                          <td className="px-3 py-2.5 text-center">
                            {(() => {
                              const label = s.signal_strength_label || (() => {
                                const score = s.ensemble_score || 0;
                                if (score >= 88) return 'Very Strong';
                                if (score >= 75) return 'Strong';
                                if (score >= 61) return 'Moderate';
                                return 'Weak';
                              })();
                              const labelColor = label === 'Very Strong' ? 'bg-emerald-600 text-white' :
                                                label === 'Strong' ? 'bg-emerald-100 text-emerald-800' :
                                                label === 'Moderate' ? 'bg-amber-100 text-amber-800' :
                                                'bg-gray-100 text-gray-600';
                              return <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-semibold ${labelColor}`}>{label}</span>;
                            })()}
                          </td>
                          {s.is_fresh && (
                            <td className="px-3 py-2.5 text-center">
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setChartModal({ type: 'signal', data: s, symbol: s.symbol });
                                }}
                                className={`text-xs bg-green-600 text-white px-2.5 py-1 rounded font-medium hover:bg-green-700 ${s.days_since_crossover === 0 ? 'animate-pulse' : ''}`}
                              >
                                {(s.days_since_entry ?? s.days_since_crossover) === 0 ? 'BUY NOW' : 'BUY'}
                              </button>
                            </td>
                          )}
                        </tr>
                      );

                      return (
                        <div>
                          {/* Buy Signals section (fresh) */}
                          {freshSignals.length > 0 ? (
                            <div>
                              <div className="px-4 py-2.5 bg-green-50 border-b border-green-100 flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                  <div className="w-1 h-5 bg-green-500 rounded-full" />
                                  <span className="text-sm font-semibold text-green-900">Buy Signals ({freshSignals.length})</span>
                                </div>
                                <span className="text-xs text-green-700">Consider adding</span>
                              </div>
                              {viewMode === 'simple' ? (
                                <div className="divide-y divide-gray-100">
                                  {freshSignals.map(renderSimpleSignal)}
                                </div>
                              ) : (
                                <div className="overflow-x-auto">
                                <table className="w-full text-sm">
                                  <thead className="bg-gray-50 text-gray-600">
                                    <tr>
                                      <th className="px-3 py-2 text-left font-medium">Symbol</th>
                                      <th className="px-3 py-2 text-right font-medium">Price</th>
                                      <th className="px-3 py-2 text-right font-medium">Breakout%</th>
                                      <th className="px-3 py-2 text-right font-medium">Rank</th>
                                      <th className="px-3 py-2 text-center font-medium">Strength</th>
                                      <th className="px-3 py-2 text-center font-medium">Action</th>
                                    </tr>
                                  </thead>
                                  <tbody className="divide-y divide-gray-100">
                                    {freshSignals.map(renderAdvancedSignal)}
                                  </tbody>
                                </table>
                                </div>
                              )}
                            </div>
                          ) : (
                            <div className="px-4 py-4 text-sm bg-gray-50 border-b border-gray-100">
                              {heldFreshCount > 0 ? (
                                <p className="text-center text-gray-500">{`Today's ${heldFreshCount} fresh signal${heldFreshCount > 1 ? 's are' : ' is'} already in your positions`}</p>
                              ) : (
                                <>
                                  {dashboardData?.market_context ? (
                                    <div>
                                      <p className="text-gray-600 italic leading-relaxed">{dashboardData.market_context}</p>
                                    </div>
                                  ) : (
                                    <p className="text-center text-gray-500">No fresh buy signals today</p>
                                  )}
                                  {heldFreshCount === 0 && daysSinceLastSignal > 14 && !dashboardData?.market_context && (
                                    <p className="text-xs text-gray-400 mt-1.5 max-w-xs mx-auto text-center">
                                      {daysSinceLastSignal <= 21
                                        ? "Two weeks of patience. Sitting out when setups aren't clean is how the ensemble protects you."
                                        : "Extended quiet stretch. The ensemble won't chase trades — when conditions are right, you'll be the first to know."}
                                    </p>
                                  )}
                                </>
                              )}
                            </div>
                          )}

                          {/* Monitoring section (non-fresh) */}
                          {monitoringSignals.length > 0 && (
                            <div>
                              <div className="px-4 py-2.5 bg-gray-50 border-b border-gray-200 flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                  <div className="w-1 h-5 bg-gray-400 rounded-full" />
                                  <span className="text-sm font-semibold text-gray-700">Monitoring ({monitoringSignals.length})</span>
                                </div>
                                <span className="text-xs text-gray-500">Strong momentum — watching for fresh entry</span>
                              </div>
                              {viewMode === 'simple' ? (
                                <div className="divide-y divide-gray-100">
                                  {monitoringSignals.map(renderSimpleSignal)}
                                </div>
                              ) : (
                                <div className="overflow-x-auto">
                                <table className="w-full text-sm">
                                  <thead className="bg-gray-50 text-gray-600">
                                    <tr>
                                      <th className="px-3 py-2 text-left font-medium">Symbol</th>
                                      <th className="px-3 py-2 text-right font-medium">Price</th>
                                      <th className="px-3 py-2 text-right font-medium">Breakout%</th>
                                      <th className="px-3 py-2 text-right font-medium">Rank</th>
                                      <th className="px-3 py-2 text-center font-medium">Strength</th>
                                    </tr>
                                  </thead>
                                  <tbody className="divide-y divide-gray-100">
                                    {monitoringSignals.map(renderAdvancedSignal)}
                                  </tbody>
                                </table>
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })()
                  ) : (
                    /* Smart empty state */
                    <div className="p-5 space-y-4">
                      {/* A. Market context message */}
                      {dashboardData?.regime_forecast && (
                        <div className="flex items-center gap-2 text-sm text-gray-600">
                          <div className={`w-3 h-3 rounded-full flex-shrink-0 ${
                            ['strong_bull', 'weak_bull', 'recovery'].includes(dashboardData.regime_forecast.current_regime) ? 'bg-emerald-500' :
                            ['rotating_bull', 'range_bound'].includes(dashboardData.regime_forecast.current_regime) ? 'bg-amber-400' :
                            'bg-red-500'
                          }`} />
                          <span>
                            <strong>{dashboardData.regime_forecast.current_regime_name}</strong> market
                            {' '}&mdash; {
                              ['weak_bear', 'panic_crash'].includes(dashboardData.regime_forecast.current_regime)
                                ? "the ensemble is protecting your capital by sitting this out."
                                : ['range_bound', 'rotating_bull'].includes(dashboardData.regime_forecast.current_regime)
                                ? "mixed conditions — the ensemble is being extra selective."
                                : "scanning for setups that meet all three criteria."
                            }
                            {(dashboardData?.watchlist || []).length > 0 && ` ${dashboardData.watchlist.length} stock${dashboardData.watchlist.length > 1 ? 's' : ''} on watchlist.`}
                          </span>
                        </div>
                      )}

                      {/* B. Promoted watchlist */}
                      {(dashboardData?.watchlist || []).length > 0 && (
                        <div>
                          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">Approaching Buy Trigger</p>
                          {viewMode === 'simple' ? (
                            <div className="space-y-1.5">
                              {dashboardData.watchlist.map(s => (
                                <div
                                  key={s.symbol}
                                  className="flex items-center justify-between px-3 py-2 bg-amber-50 rounded-lg cursor-pointer hover:bg-amber-100 transition-colors"
                                  onClick={() => setChartModal({ type: 'signal', data: { symbol: s.symbol }, symbol: s.symbol })}
                                >
                                  <span className="font-semibold text-gray-900">{s.symbol}</span>
                                  <span className="text-xs font-medium text-amber-700 bg-amber-100 px-2 py-0.5 rounded-full">
                                    {s.distance_to_trigger?.toFixed(1)}% to go
                                  </span>
                                </div>
                              ))}
                            </div>
                          ) : (
                            <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                              <thead className="text-gray-500">
                                <tr>
                                  <th className="text-left text-xs font-medium pb-1">Symbol</th>
                                  <th className="text-right text-xs font-medium pb-1">Price</th>
                                  <th className="text-right text-xs font-medium pb-1">Breakout%</th>
                                  <th className="text-right text-xs font-medium pb-1">Distance</th>
                                </tr>
                              </thead>
                              <tbody className="divide-y divide-gray-100">
                                {dashboardData.watchlist.map(s => (
                                  <tr
                                    key={s.symbol}
                                    className="cursor-pointer hover:bg-amber-50 transition-colors"
                                    onClick={() => setChartModal({ type: 'signal', data: { symbol: s.symbol }, symbol: s.symbol })}
                                  >
                                    <td className="py-1.5 font-semibold text-gray-900">{s.symbol}</td>
                                    <td className="py-1.5 text-right text-gray-600">${s.price?.toFixed(2)}</td>
                                    <td className="py-1.5 text-right text-green-600">+{s.pct_above_dwap?.toFixed(1)}%</td>
                                    <td className="py-1.5 text-right font-medium text-amber-700">+{s.distance_to_trigger?.toFixed(1)}%</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                            </div>
                          )}
                        </div>
                      )}

                      {/* C. Recent signals with outcomes */}
                      {(dashboardData?.recent_signals || []).length > 0 && (
                        <div>
                          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">Recent Signals</p>
                          <div className="flex flex-wrap gap-2">
                            {dashboardData.recent_signals.map(rs => {
                              const quote = liveQuotes[rs.symbol];
                              const livePrice = quote?.price;
                              const perfPct = livePrice && rs.signal_price > 0
                                ? Math.round((livePrice / rs.signal_price - 1) * 1000) / 10
                                : rs.performance_pct;
                              return (
                              <div key={`${rs.symbol}-${rs.signal_date}`} className="flex items-center gap-1.5 text-xs bg-gray-100 px-2.5 py-1.5 rounded-lg">
                                <span className="font-semibold text-gray-800">{rs.symbol}</span>
                                <span className="text-gray-500">{formatDate(rs.signal_date)}</span>
                                {perfPct != null && (
                                  <span className={`font-medium ${perfPct >= 0 ? 'text-emerald-600' : 'text-red-500'}`}>
                                    {perfPct >= 0 ? '+' : ''}{perfPct}%
                                  </span>
                                )}
                              </div>
                              );
                            })}
                          </div>
                        </div>
                      )}

                      {/* Fallback if nothing else rendered */}
                      {(dashboardData?.watchlist || []).length === 0 && (dashboardData?.recent_signals || []).length === 0 && !dashboardData?.regime_forecast && (
                        <div className="text-center py-6 text-gray-500">
                          <Activity className="w-12 h-12 mx-auto text-gray-300 mb-3" />
                          <p>No buy signals right now</p>
                          <p className="text-xs mt-1">We're scanning the market — check back soon</p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>

              {/* RIGHT: Open Positions with Sell Guidance */}
              {(() => {
                const positionSectorFilter = (p) => !excludedSectors.includes(p.sector || 'Other');
                const filteredGuidance = guidanceWithLiveQuotes.filter(positionSectorFilter);
                const filteredPositions = positionsWithLiveQuotes.filter(positionSectorFilter);
                const activePositions = filteredGuidance.length > 0 ? filteredGuidance : filteredPositions;
                const hasUnfilteredPositions = guidanceWithLiveQuotes.length > 0 || positionsWithLiveQuotes.length > 0;
                return (
              <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
                <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
                  <h2 className="text-lg font-semibold text-gray-900">Open Positions</h2>
                  <span className="text-xs text-gray-500">Click row for chart</span>
                </div>

                <div className="max-h-[500px] overflow-y-auto">
                  {!quotesReady && hasUnfilteredPositions ? (
                    <div className="px-5 py-8 text-center text-sm text-gray-400">
                      <div className="animate-pulse space-y-3">
                        {[1,2,3].map(i => <div key={i} className="h-10 bg-gray-100 rounded" />)}
                      </div>
                      <p className="mt-3">Loading live prices...</p>
                    </div>
                  ) : activePositions.length > 0 ? (
                    viewMode === 'simple' ? (
                      /* Simple mode: list items with friendly status */
                      <div className="divide-y divide-gray-100">
                        {activePositions.map((p) => {
                          const action = p.action || 'hold';
                          const pnl = p.pnl_pct || ((p.current_price - p.entry_price) / p.entry_price * 100) || 0;
                          const friendlyStatus = action === 'sell' ? 'Consider selling'
                            : action === 'warning' ? 'Watch closely'
                            : 'Looking good';
                          const statusColor = action === 'sell' ? 'text-red-600'
                            : action === 'warning' ? 'text-amber-600'
                            : 'text-emerald-600';

                          return (
                            <div
                              key={p.id || p.symbol}
                              className={`px-4 py-3 flex items-center justify-between cursor-pointer transition-colors ${
                                action === 'sell' ? 'bg-red-50 hover:bg-red-100 border-l-4 border-l-red-500' :
                                action === 'warning' ? 'bg-amber-50 hover:bg-amber-100 border-l-4 border-l-amber-500' :
                                'hover:bg-gray-50'
                              }`}
                              onClick={() => setChartModal({ type: 'position', data: p, symbol: p.symbol })}
                            >
                              <div>
                                <span className="font-semibold text-gray-900">{p.symbol}</span>
                                <span className={`ml-2 font-semibold ${pnl >= 0 ? 'text-emerald-600' : 'text-red-500'}`}>
                                  {pnl >= 0 ? '+' : ''}{pnl.toFixed(1)}%
                                </span>
                              </div>
                              <span className={`text-xs font-medium ${statusColor}`}>{friendlyStatus}</span>
                            </div>
                          );
                        })}
                      </div>
                    ) : (
                      /* Advanced mode: full table */
                      <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead className="bg-gray-50 text-gray-600 sticky top-0">
                          <tr>
                            <th className="px-3 py-2 text-left font-medium">Symbol</th>
                            <th className="px-3 py-2 text-right font-medium">P&L</th>
                            <th className="px-3 py-2 text-center font-medium">Status</th>
                            <th className="px-3 py-2 text-right font-medium">Stop</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100">
                          {activePositions.map((p) => {
                            const action = p.action || 'hold';
                            const pnl = p.pnl_pct || ((p.current_price - p.entry_price) / p.entry_price * 100) || 0;
                            const pnlColor = pnl >= 0 ? 'text-emerald-600' : 'text-red-500';

                            return (
                              <tr
                                key={p.id || p.symbol}
                                className={`cursor-pointer transition-colors ${
                                  action === 'sell' ? 'bg-red-50 hover:bg-red-100 border-l-4 border-l-red-500' :
                                  action === 'warning' ? 'bg-amber-50 hover:bg-amber-100 border-l-4 border-l-amber-500' :
                                  'hover:bg-gray-50'
                                }`}
                                onClick={() => setChartModal({ type: 'position', data: p, symbol: p.symbol })}
                              >
                                <td className="px-3 py-2.5">
                                  <span className="font-semibold text-gray-900">{p.symbol}</span>
                                  <div className="text-xs text-gray-400">{p.shares?.toFixed(1)} shares</div>
                                </td>
                                <td className="px-3 py-2.5 text-right">
                                  <span className={`font-semibold ${pnlColor}`}>
                                    {pnl >= 0 ? '+' : ''}{pnl.toFixed(1)}%
                                  </span>
                                  <div className="text-xs text-gray-400">${p.current_price?.toFixed(2)}</div>
                                </td>
                                <td className="px-3 py-2.5 text-center">
                                  {action === 'sell' ? (
                                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-bold bg-red-100 text-red-700">
                                      <TrendingDown size={12} /> SELL
                                    </span>
                                  ) : action === 'warning' ? (
                                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-bold bg-amber-100 text-amber-700">
                                      <AlertCircle size={12} /> WARN
                                    </span>
                                  ) : (
                                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-emerald-50 text-emerald-600">
                                      <Shield size={12} /> HOLD
                                    </span>
                                  )}
                                </td>
                                <td className="px-3 py-2.5 text-right">
                                  <span className="text-xs text-gray-600">${p.trailing_stop_level?.toFixed(2) || '--'}</span>
                                  <div className="text-xs text-gray-400">
                                    {p.distance_to_stop_pct != null ? `${p.distance_to_stop_pct.toFixed(0)}% away` : ''}
                                  </div>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                      </div>
                    )
                  ) : (
                    <div className="text-center py-12 text-gray-500">
                      <PieIcon className="w-12 h-12 mx-auto text-gray-300 mb-3" />
                      <p>No open positions</p>
                      <p className="text-xs mt-1">Click a fresh signal, then Track Position from the chart</p>
                    </div>
                  )}
                </div>

                {/* Action reasons for positions needing attention (wait for live prices) */}
                {quotesReady && viewMode !== 'simple' && activePositions.filter(p => p.action !== 'hold').length > 0 && (
                  <div className="border-t border-gray-100 px-4 py-3 space-y-1">
                    {activePositions.filter(p => p.action !== 'hold').map(p => (
                      <div key={p.symbol} className={`text-xs px-2 py-1 rounded ${
                        p.action === 'sell' ? 'bg-red-50 text-red-700' : 'bg-amber-50 text-amber-700'
                      }`}>
                        <strong>{p.symbol}:</strong> {p.action_reason}
                      </div>
                    ))}
                  </div>
                )}
              </div>
                );
              })()}
            </div>

            {/* Watchlist — Approaching Trigger (hidden when promoted into empty buy signals) */}
            {(dashboardData?.watchlist || []).length > 0 && (dashboardData?.buy_signals || []).length > 0 && (
              viewMode === 'simple' ? (
                <div className="mt-6 p-3 bg-amber-50 border border-amber-200 rounded-xl text-sm text-amber-800">
                  <Eye className="w-4 h-4 text-amber-600 inline mr-1.5" />
                  {dashboardData.watchlist.length} stock{dashboardData.watchlist.length > 1 ? 's are' : ' is'} close to triggering a buy signal: {dashboardData.watchlist.map(s => s.symbol).join(', ')}
                </div>
              ) : (
                <div className="mt-6 bg-amber-50 border border-amber-200 rounded-xl overflow-hidden">
                  <div className="px-5 py-3 border-b border-amber-200 flex items-center gap-2">
                    <Eye className="w-4 h-4 text-amber-600" />
                    <h3 className="font-medium text-amber-800">Watchlist — Approaching Trigger</h3>
                    <span className="text-xs text-amber-600 ml-2">Momentum stocks approaching breakout trigger</span>
                  </div>
                  <div className="flex flex-wrap gap-3 px-5 py-3">
                    {dashboardData.watchlist.map((s) => (
                      <div
                        key={s.symbol}
                        className="flex items-center gap-2 px-3 py-2 bg-white border border-amber-200 rounded-lg hover:bg-amber-100 cursor-pointer transition-colors"
                        onClick={() => setChartModal({ type: 'signal', data: { symbol: s.symbol }, symbol: s.symbol })}
                      >
                        <span className="font-semibold text-gray-900">{s.symbol}</span>
                        <span className="text-xs text-amber-600">#{s.momentum_rank}</span>
                        <span className="text-xs text-gray-500">+{s.pct_above_dwap?.toFixed(1)}%</span>
                        <span className="text-xs font-medium text-amber-700">+{s.distance_to_trigger?.toFixed(1)}% to go</span>
                      </div>
                    ))}
                  </div>
                </div>
              )
            )}

            {/* Missed Opportunities */}
            {missedOpportunities.length > 0 && (
              viewMode === 'simple' ? (
                /* Simple mode: summary + top 3 cards */
                <div className="mt-6 bg-gradient-to-r from-amber-50 to-orange-50 border border-amber-200 rounded-xl p-4">
                  <p className="text-sm text-amber-800 mb-3">
                    You could have made{' '}
                    <strong className="text-amber-900">
                      +${missedOpportunities.reduce((sum, m) => sum + (m.would_be_pnl || 0), 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}
                    </strong>
                    {' '}last month following our signals.
                  </p>
                  <div className="flex gap-3">
                    {missedOpportunities.slice(0, 3).map(m => (
                      <div
                        key={m.symbol}
                        className="flex-1 bg-white border border-amber-200 rounded-lg px-3 py-2 text-center cursor-pointer hover:bg-amber-50 transition-colors"
                        onClick={() => setChartModal({ type: 'missed', data: m, symbol: m.symbol })}
                      >
                        <span className="font-semibold text-gray-900">{m.symbol}</span>
                        <div className="text-emerald-600 font-bold text-sm">
                          +{m.would_be_return?.toFixed(0)}%
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                /* Advanced mode: full table */
                <div className="mt-6 bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
                  <div className="px-5 py-4 border-b border-gray-100 flex items-center gap-2">
                    <Clock className="w-5 h-5 text-amber-500" />
                    <h2 className="text-lg font-semibold text-gray-900">Missed Opportunities</h2>
                    <span className="text-xs text-gray-500 ml-2">Profitable trades using trailing stop exits</span>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="bg-gray-50 text-gray-600">
                        <tr>
                          <th className="px-3 py-2 text-left font-medium">Symbol</th>
                          <th className="px-3 py-2 text-left font-medium hidden sm:table-cell">Buy Date</th>
                          <th className="px-3 py-2 text-right font-medium hidden md:table-cell">Buy $</th>
                          <th className="px-3 py-2 text-left font-medium hidden sm:table-cell">Sell Date</th>
                          <th className="px-3 py-2 text-right font-medium hidden md:table-cell">Sell $</th>
                          <th
                            className="px-3 py-2 text-right font-medium cursor-pointer select-none hover:text-amber-600 transition-colors"
                            onClick={() => setMissedSortBy(prev => prev === 'return' ? 'date' : 'return')}
                          >
                            Return {missedSortBy === 'return' ? '↓' : ''}
                          </th>
                          <th className="px-3 py-2 text-right font-medium">P&L</th>
                          <th className="px-3 py-2 text-right font-medium hidden sm:table-cell">Days</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {[...missedOpportunities].sort((a, b) =>
                          missedSortBy === 'return'
                            ? (b.would_be_return || 0) - (a.would_be_return || 0)
                            : (b.sell_date || '').localeCompare(a.sell_date || '')
                        ).map((m) => (
                          <tr
                            key={`${m.symbol}-${m.entry_date}`}
                            className="hover:bg-amber-50 cursor-pointer transition-colors"
                            onClick={() => setChartModal({ type: 'missed', data: m, symbol: m.symbol })}
                          >
                            <td className="px-3 py-2.5 font-semibold text-gray-900">{m.symbol}</td>
                            <td className="px-3 py-2.5 text-gray-500 hidden sm:table-cell">{formatDate(m.entry_date)}</td>
                            <td className="px-3 py-2.5 text-right hidden md:table-cell">${m.entry_price?.toFixed(2)}</td>
                            <td className="px-3 py-2.5 text-gray-500 hidden sm:table-cell">{formatDate(m.sell_date)}</td>
                            <td className="px-3 py-2.5 text-right hidden md:table-cell">${m.sell_price?.toFixed(2)}</td>
                            <td className="px-3 py-2.5 text-right">
                              <span className="text-emerald-600 font-semibold">+{m.would_be_return?.toFixed(1)}%</span>
                            </td>
                            <td className="px-3 py-2.5 text-right text-emerald-600 font-medium">
                              +${m.would_be_pnl?.toFixed(0)}
                            </td>
                            <td className="px-3 py-2.5 text-right text-gray-500 hidden sm:table-cell">{m.days_held}d</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )
            )}

            {/* Backtest/Walk-Forward summary */}
            {backtest && (
              <div className={`mt-6 bg-gradient-to-r ${backtest.is_walk_forward ? 'from-purple-50 to-indigo-50 border-purple-200' : 'from-blue-50 to-indigo-50 border-blue-200'} border rounded-xl p-4`}>
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="font-semibold text-gray-900">
                      Simulated Portfolio {backtest.is_walk_forward ? '(Walk-Forward)' : '(Backtest)'}
                    </h3>
                    <p className="text-sm text-gray-500">
                      {backtest.is_walk_forward
                        ? `Ensemble strategy${backtest.num_strategy_switches > 0 ? ` with ${backtest.num_strategy_switches} switches` : ''}`
                        : `Based on ${backtest.strategy === 'momentum' ? 'Momentum' : 'Breakout'} strategy`
                      }
                      {' '}| {formatDate(backtest.start_date, { includeYear: true })} to {formatDate(backtest.end_date, { includeYear: true })}
                    </p>
                  </div>
                  <div className="flex gap-6 text-sm">
                    <div className="text-center">
                      <p className="text-gray-500">Return</p>
                      <p className={`font-bold ${parseFloat(backtest.total_return_pct) >= 0 ? 'text-emerald-600' : 'text-red-500'}`}>
                        {parseFloat(backtest.total_return_pct) >= 0 ? '+' : ''}{backtest.total_return_pct}%
                      </p>
                    </div>
                    <div className="text-center">
                      <p className="text-gray-500">Sharpe</p>
                      <p className="font-bold text-gray-900">{backtest.sharpe_ratio}</p>
                    </div>
                    <div className="text-center">
                      <p className="text-gray-500">Max DD</p>
                      <p className="font-bold text-red-500">-{backtest.max_drawdown_pct}%</p>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </>
        ) : activeTab === 'history' ? (
          <div className="space-y-6">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <MetricCard title="Total Trades" value={trades.length} icon={History} />
              <MetricCard title="Win Rate" value={`${winRate.toFixed(0)}%`} subtitle={`${wins.length}W / ${trades.length - wins.length}L`} icon={Target} trend={winRate > 50 ? 'up' : 'down'} />
              <MetricCard title="Total P&L" value={`$${totalHistoricalPnl.toLocaleString(undefined, {maximumFractionDigits: 0})}`} icon={Wallet} trend={totalHistoricalPnl >= 0 ? 'up' : 'down'} />
              <MetricCard title="Avg Return" value={`${trades.length ? (trades.reduce((s,t) => s + (t.pnl_pct || 0), 0) / trades.length).toFixed(1) : 0}%`} icon={BarChart3} />
            </div>

            <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
              <div className="px-5 py-4 border-b border-gray-100"><h2 className="text-lg font-semibold text-gray-900">Trade History (1 Year Backtest)</h2></div>
              <div className="overflow-x-auto max-h-[600px]">
                {trades.length > 0 ? (
                  <table className="w-full">
                    <thead className="bg-gray-50 border-b border-gray-100 sticky top-0">
                      <tr>{['Symbol', 'Entry', 'Exit', 'Entry $', 'Exit $', 'Return', 'P&L', 'Reason', 'Days'].map(h => <th key={h} className="py-3 px-4 text-left text-xs font-semibold text-gray-500 uppercase">{h}</th>)}</tr>
                    </thead>
                    <tbody>
                      {trades.map(t => (
                        <tr key={t.id} className="hover:bg-gray-50 border-b border-gray-50">
                          <td className="py-3 px-4 font-medium">{t.symbol}</td>
                          <td className="py-3 px-4 text-gray-500 text-sm">{formatDate(t.entry_date)}</td>
                          <td className="py-3 px-4 text-gray-500 text-sm">{formatDate(t.exit_date)}</td>
                          <td className="py-3 px-4">${t.entry_price?.toFixed(2)}</td>
                          <td className="py-3 px-4">${t.exit_price?.toFixed(2)}</td>
                          <td className="py-3 px-4"><span className={`px-2 py-1 rounded text-sm font-semibold ${t.pnl_pct >= 0 ? 'bg-emerald-50 text-emerald-600' : 'bg-red-50 text-red-500'}`}>{t.pnl_pct >= 0 ? '+' : ''}{t.pnl_pct?.toFixed(1)}%</span></td>
                          <td className={`py-3 px-4 font-medium ${t.pnl >= 0 ? 'text-emerald-600' : 'text-red-500'}`}>${t.pnl?.toFixed(0)}</td>
                          <td className="py-3 px-4"><span className={`px-2 py-1 rounded text-xs font-medium ${t.exit_reason === 'profit_target' ? 'bg-emerald-100 text-emerald-700' : t.exit_reason === 'stop_loss' ? 'bg-red-100 text-red-700' : 'bg-gray-100 text-gray-600'}`}>{({'trailing_stop':'TRAILING STOP','rebalance_exit':'REBALANCE','simulation_end':'REBALANCE','profit_target':'PROFIT TARGET','stop_loss':'STOP LOSS'}[t.exit_reason] || t.exit_reason?.toUpperCase())}</span></td>
                          <td className="py-3 px-4 text-gray-500">{t.days_held}d</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <div className="text-center py-12 text-gray-500">
                    <History className="w-12 h-12 mx-auto text-gray-300 mb-3" />
                    <p>No trades in backtest period</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        ) : null}
      </main>

      {showLoginModal && <LoginModal isOpen={showLoginModal} onClose={() => setShowLoginModal(false)} />}
      {chartModal && <StockChartModal {...chartModal} viewMode={viewMode} liveQuote={liveQuotes[chartModal.symbol]} timeTravelDate={timeTravelDate} onClose={() => setChartModal(null)} onAction={(positionData) => {
        setChartModal(null);
        if (positionData) {
          // BUY: Optimistic update — move signal to positions instantly
          const optimistic = {
            id: positionData.id,
            symbol: positionData.symbol,
            shares: positionData.shares,
            entry_price: positionData.entry_price,
            entry_date: new Date().toISOString().slice(0, 10),
            current_price: positionData.entry_price,
            pnl_pct: 0,
            days_held: 0,
            high_water_mark: positionData.entry_price,
            trailing_stop_price: positionData.stop_loss,
            trailing_stop_pct: 12,
            distance_to_stop_pct: 12,
            sell_signal: 'hold',
            action: 'hold',
          };
          setDashboardData(prev => prev ? {
            ...prev,
            buy_signals: (prev.buy_signals || []).filter(s => s.symbol !== positionData.symbol),
            positions_with_guidance: [optimistic, ...(prev.positions_with_guidance || [])],
          } : prev);
        } else {
          // SELL: Optimistic update — remove position instantly
          const sym = chartModal.symbol;
          setDashboardData(prev => prev ? {
            ...prev,
            positions_with_guidance: (prev.positions_with_guidance || []).filter(p => p.symbol !== sym),
          } : prev);
        }
        // Full reload in background for accurate data
        reloadPositions();
      }} />}

      {/* Email Preferences Modal */}
      {showEmailPrefsModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={() => setShowEmailPrefsModal(false)}>
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between p-5 border-b">
              <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2"><Bell size={18} /> Email Preferences</h3>
              <button onClick={() => setShowEmailPrefsModal(false)} className="text-gray-400 hover:text-gray-600"><X size={20} /></button>
            </div>
            <div className="p-5 space-y-4">
              {[
                { key: 'daily_digest', label: 'Daily Digest', desc: '6 PM ET summary with signals + positions' },
                { key: 'sell_alerts', label: 'Sell Alerts', desc: 'Trailing stop and regime exit alerts' },
                { key: 'double_signals', label: 'Double Signal Alerts', desc: 'Breakout + momentum confirmation alerts' },
                { key: 'intraday_signals', label: 'Intraday Signals', desc: 'Breakout crossover during market hours' },
              ].map(({ key, label, desc }) => (
                <label key={key} className="flex items-center justify-between cursor-pointer group">
                  <div>
                    <p className="text-sm font-medium text-gray-900">{label}</p>
                    <p className="text-xs text-gray-500">{desc}</p>
                  </div>
                  <button
                    type="button"
                    role="switch"
                    aria-checked={emailPrefs[key]}
                    onClick={() => setEmailPrefs(prev => ({ ...prev, [key]: !prev[key] }))}
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${emailPrefs[key] ? 'bg-blue-600' : 'bg-gray-200'}`}
                  >
                    <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${emailPrefs[key] ? 'translate-x-6' : 'translate-x-1'}`} />
                  </button>
                </label>
              ))}
            </div>
            <div className="flex items-center justify-end gap-3 p-5 border-t">
              <button onClick={() => setShowEmailPrefsModal(false)} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800">Cancel</button>
              <button
                disabled={emailPrefsSaving}
                onClick={async () => {
                  setEmailPrefsSaving(true);
                  try {
                    await api.patch('/api/auth/me/email-preferences', emailPrefs);
                    setEmailPrefsToast('saved');
                    setShowEmailPrefsModal(false);
                    setTimeout(() => setEmailPrefsToast(null), 4000);
                  } catch (err) {
                    console.error('Failed to save email preferences:', err);
                    alert('Failed to save preferences. Please try again.');
                  } finally {
                    setEmailPrefsSaving(false);
                  }
                }}
                className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50"
              >
                {emailPrefsSaving ? 'Saving...' : 'Save Preferences'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Cancel Survey Modal */}
      {showCancelSurvey && !cancelSurveySubmitted && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full" onClick={e => e.stopPropagation()}>
            <div className="p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-1">We're sorry to see you go</h3>
              <p className="text-sm text-gray-500 mb-5">Your feedback helps us improve. 30 seconds, 3 questions.</p>
              <form onSubmit={async (e) => {
                e.preventDefault();
                const form = e.target;
                const reason = form.reason.value;
                const detail = form.detail.value;
                const wouldReturn = form.would_return.value === 'yes';
                try {
                  await api.post('/api/billing/cancel-survey', { reason, detail, would_return: wouldReturn });
                } catch {}
                setCancelSurveySubmitted(true);
                setTimeout(() => setShowCancelSurvey(false), 3000);
              }}>
                <label className="block text-sm font-medium text-gray-700 mb-2">What's the main reason you're leaving?</label>
                <select name="reason" required className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm mb-4 focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
                  <option value="">Select a reason...</option>
                  <option value="not_enough_signals">Not enough signals / too quiet</option>
                  <option value="too_expensive">Too expensive for the value</option>
                  <option value="confusing">Hard to understand or use</option>
                  <option value="not_useful">Signals weren't useful to me</option>
                  <option value="using_another">Switched to another service</option>
                  <option value="not_trading">Stopped trading / investing</option>
                  <option value="other">Other</option>
                </select>
                <label className="block text-sm font-medium text-gray-700 mb-2">Anything else you'd like us to know?</label>
                <textarea name="detail" rows={2} className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm mb-4 resize-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500" placeholder="Optional — but we read every response" />
                <label className="block text-sm font-medium text-gray-700 mb-2">Would you come back if we improved?</label>
                <div className="flex gap-4 mb-5">
                  <label className="flex items-center gap-2 text-sm"><input type="radio" name="would_return" value="yes" defaultChecked className="text-blue-600" /> Yes, definitely</label>
                  <label className="flex items-center gap-2 text-sm"><input type="radio" name="would_return" value="no" className="text-blue-600" /> Probably not</label>
                </div>
                <div className="flex justify-end gap-3">
                  <button type="button" onClick={() => setShowCancelSurvey(false)} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800">Skip</button>
                  <button type="submit" className="px-4 py-2 text-sm font-medium text-white bg-blue-900 rounded-lg hover:bg-blue-800">Submit Feedback</button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
      {showCancelSurvey && cancelSurveySubmitted && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-sm w-full p-6 text-center">
            <p className="text-lg font-semibold text-gray-900 mb-2">Thank you for your feedback</p>
            <p className="text-sm text-gray-500">We'll use it to make RigaCap better. You're welcome back anytime.</p>
          </div>
        </div>
      )}

      {/* Referral Modal */}
      {showReferralModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={() => setShowReferralModal(false)}>
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between p-5 border-b">
              <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2"><Gift size={18} /> Refer a Friend</h3>
              <button onClick={() => setShowReferralModal(false)} className="text-gray-400 hover:text-gray-600"><X size={20} /></button>
            </div>
            <div className="p-5">
              <div className="bg-gradient-to-br from-blue-950 to-blue-900 rounded-xl p-6 text-center mb-5">
                <p className="text-amber-400 font-bold text-lg mb-1">Give a Month, Get a Month</p>
                <p className="text-white/80 text-sm leading-relaxed">
                  Share your link with a friend. They get their first month free,
                  and when they subscribe, you get a free month too!
                </p>
              </div>
              {user?.referral_code && (
                <div className="space-y-3">
                  <label className="text-sm font-medium text-gray-700">Your referral link</label>
                  <div className="flex gap-2">
                    <input
                      readOnly
                      value={`rigacap.com/?ref=${user.referral_code}`}
                      className="flex-1 px-3 py-2 text-sm bg-gray-50 border border-gray-200 rounded-lg font-mono text-gray-700"
                    />
                    <button
                      onClick={() => {
                        navigator.clipboard.writeText(`https://rigacap.com/?ref=${user.referral_code}`);
                        setReferralCopied(true);
                        setTimeout(() => setReferralCopied(false), 2000);
                      }}
                      className={`px-3 py-2 text-sm font-medium rounded-lg flex items-center gap-1.5 transition-colors ${
                        referralCopied
                          ? 'bg-green-100 text-green-700'
                          : 'bg-blue-600 text-white hover:bg-blue-700'
                      }`}
                    >
                      {referralCopied ? <><Check size={14} /> Copied!</> : <><Copy size={14} /> Copy</>}
                    </button>
                  </div>
                </div>
              )}
              {(user?.referral_count > 0) && (
                <div className="mt-5 bg-green-50 rounded-lg p-4 text-center">
                  <p className="text-2xl font-bold text-green-700">{user.referral_count}</p>
                  <p className="text-sm text-green-600">friend{user.referral_count !== 1 ? 's' : ''} referred</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* 2FA Settings Modal */}
      <TwoFactorSettings isOpen={show2FASettings} onClose={() => setShow2FASettings(false)} />

      {/* Email Preferences Toast */}
      {emailPrefsToast && (
        <div className="fixed bottom-6 right-6 z-50 animate-fade-in">
          <div className={`px-5 py-3 rounded-xl shadow-lg text-sm font-medium text-white ${emailPrefsToast === 'unsubscribed' ? 'bg-orange-500' : 'bg-green-600'}`}>
            {emailPrefsToast === 'unsubscribed' ? 'You have been unsubscribed from all emails.' : 'Email preferences saved.'}
          </div>
        </div>
      )}
    </div>
  );
}

// Protected Route wrapper
function ProtectedRoute({ children }) {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <Loader2 className="w-12 h-12 text-blue-600 animate-spin" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  return children;
}

function NotFoundPage() {
  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center px-4">
      <div className="text-center">
        <p className="text-6xl font-bold text-amber-400 mb-4">404</p>
        <h1 className="text-2xl font-semibold text-white mb-2">Page not found</h1>
        <p className="text-gray-400 mb-8">The page you're looking for doesn't exist or has been moved.</p>
        <a href="/" className="inline-flex items-center gap-2 px-6 py-3 bg-white text-gray-900 font-semibold rounded-xl hover:shadow-lg transition-all">
          Back to RigaCap
        </a>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/privacy" element={<PrivacyPage />} />
        <Route path="/terms" element={<TermsPage />} />
        <Route path="/contact" element={<ContactPage />} />
        <Route path="/track-record" element={<TrackRecordPage />} />
        <Route path="/track-record-10y" element={<TrackRecord10YPage />} />
        <Route path="/market-regime" element={<MarketRegimePage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route path="/app" element={
          <ProtectedRoute>
            <Dashboard />
          </ProtectedRoute>
        } />
        <Route path="/dashboard" element={
          <ProtectedRoute>
            <Dashboard />
          </ProtectedRoute>
        } />
        <Route path="/admin" element={
          <ProtectedRoute>
            <Dashboard />
          </ProtectedRoute>
        } />
        {/* Vanity redirects for social platform attribution */}
        <Route path="/x" element={<Navigate to="/?utm_source=twitter&utm_medium=social&utm_campaign=bio" replace />} />
        <Route path="/ig" element={<Navigate to="/?utm_source=instagram&utm_medium=social&utm_campaign=bio" replace />} />
        <Route path="/t" element={<Navigate to="/?utm_source=threads&utm_medium=social&utm_campaign=bio" replace />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
      <CookieConsent />
    </AuthProvider>
  );
}
