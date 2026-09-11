import React, { useState, useEffect, useLayoutEffect, useRef, useCallback, useMemo, lazy, Suspense } from 'react';
import ReactDOM from 'react-dom';
import { logEvent } from './lib/eventLogger';
import { logPublicEvent, consumeAdOrigin } from './lib/publicEvent';
import { Routes, Route, Navigate, useLocation, useParams } from 'react-router-dom';
import {
  LineChart, Line, AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ComposedChart, Bar, ReferenceLine, ReferenceDot, ReferenceArea, Legend
} from 'recharts';
import {
  TrendingUp, TrendingDown, RefreshCw, Settings, Bell, User, LogOut,
  DollarSign, Target, Shield, Activity, PieChart as PieIcon, History,
  ArrowUpRight, ArrowDownRight, Clock, Zap, X, ChevronRight, Eye,
  Calendar, BarChart3, Wallet, LogIn, AlertCircle, Loader2, CreditCard, Lock,
  Briefcase, Mail, Gift, Copy, Check, Filter, Info
} from 'lucide-react';

// Route-level code splitting. Each page becomes its own JS chunk that's
// only fetched when the user navigates to it. Drops the homepage initial
// payload from ~1.3MB to roughly the router shell + LandingPageV2 +
// shared deps. Wrapped in <Suspense> below.
const LandingPageV2 = lazy(() => import('./LandingPageV2'));
const ShouldISellPage = lazy(() => import('./ShouldISellPage'));
const MomentumPage = lazy(() => import('./MomentumPage'));
const MethodologyPageV2 = lazy(() => import('./MethodologyPageV2'));
const TrackRecordPageV2 = lazy(() => import('./TrackRecordPageV2'));
const AboutPage = lazy(() => import('./AboutPage'));
const TrackRecord10YPage = lazy(() => import('./TrackRecord10YPage'));
const MethodologyPage = lazy(() => import('./MethodologyPage'));
const MarketRegimePage = lazy(() => import('./MarketRegimePage'));
const Blog2022StoryPage = lazy(() => import('./Blog2022StoryPage'));
const BlogBacktestsPage = lazy(() => import('./BlogBacktestsPage'));
const BlogMarketCrashPage = lazy(() => import('./BlogMarketCrashPage'));
const BlogHonestBacktestPage = lazy(() => import('./BlogHonestBacktestPage'));
const BlogMarketRegimeGuidePage = lazy(() => import('./BlogMarketRegimeGuidePage'));
const BlogMomentumTradingPage = lazy(() => import('./BlogMomentumTradingPage'));
const BlogTrailingStopsPage = lazy(() => import('./BlogTrailingStopsPage'));
const BlogWalkForwardResultsPage = lazy(() => import('./BlogWalkForwardResultsPage'));
const BlogWeCalledItMRNAPage = lazy(() => import('./BlogWeCalledItMRNAPage'));
const BlogWeCalledItTGTXPage = lazy(() => import('./BlogWeCalledItTGTXPage'));
const BlogSectorObservatoryPage = lazy(() => import('./BlogSectorObservatoryPage'));
const BlogIndexPage = lazy(() => import('./BlogIndexPage'));
const ForAdvisersPage = lazy(() => import('./ForAdvisersPage'));
const NewsletterPage = lazy(() => import('./NewsletterPage'));
const NewsletterIssuePage = lazy(() => import('./NewsletterPage').then(m => ({ default: m.NewsletterIssuePage })));
const SymbolTriagePage = lazy(() => import('./SymbolTriagePage'));
const PrivacyPage = lazy(() => import('./LegalPages').then(m => ({ default: m.PrivacyPage })));
const TermsPage = lazy(() => import('./LegalPages').then(m => ({ default: m.TermsPage })));
const ContactPage = lazy(() => import('./LegalPages').then(m => ({ default: m.ContactPage })));
const ForgotPasswordPage = lazy(() => import('./components/PasswordReset').then(m => ({ default: m.ForgotPasswordPage })));
const ResetPasswordPage = lazy(() => import('./components/PasswordReset').then(m => ({ default: m.ResetPasswordPage })));
// AdminDashboard is huge (chart-heavy). Lazy-load so non-admin users
// never download it.
const AdminDashboard = lazy(() => import('./components/AdminDashboard'));

import { AuthProvider, useAuth } from './contexts/AuthContext';
import LoginModal from './components/LoginModal';
import { formatDate, formatChartDate } from './utils/formatDate';
import SubscriptionBanner from './components/SubscriptionBanner';
import FreeProofView from './components/FreeProofView';
import CookieConsent from './components/CookieConsent';
import PageViewBeacon from './components/PageViewBeacon';
import TwoFactorSettings from './components/TwoFactorSettings';
import RegimeTell from './RegimeTell';
import TierBookView from './TierBookView';
// DoubleSignals, MomentumRankings, ApproachingTrigger removed — absorbed into unified dashboard

// ============================================================================
// API Configuration
// ============================================================================

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Effective trailing stop (fraction) from the dashboard's regime-adjusted
// params. Module-level so stop-price math everywhere (trade modal, position
// guidance) tracks the LIVE strategy config instead of a hardcoded 12%.
// Updated whenever dashboard data lands; 30% = t30v default.
let EFFECTIVE_TRAIL_FRAC = 0.30;
const updateEffectiveTrail = (data) => {
  const pct = data?.regime_adjustments?.effective?.trailing_stop_pct;
  if (pct && pct > 0) EFFECTIVE_TRAIL_FRAC = pct / 100;
};

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
  if (vix == null) return { label: 'N/A', color: 'text-ink-light' };
  if (vix < 15) return { label: 'Calm', color: 'text-positive' };
  if (vix < 20) return { label: 'Normal', color: 'text-ink-mute' };
  if (vix < 25) return { label: 'Elevated', color: 'text-claret' };
  if (vix < 35) return { label: 'High Fear', color: 'text-orange-600' };
  return { label: 'Extreme Fear', color: 'text-negative' };
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
  <svg x={cx - 8} y={cy - 18} width={16} height={16} viewBox="0 0 16 16" style={{ cursor: 'pointer' }}>
    <title>Entry: {payload?.date} @ ${payload?.close?.toFixed(2)}</title>
    <polygon points="8,1 15,15 1,15" fill="#7A2430" stroke="#F5F1E8" strokeWidth="2" />
  </svg>
);

const SellMarker = ({ cx, cy, payload }) => (
  <svg x={cx - 8} y={cy + 2} width={16} height={16} viewBox="0 0 16 16" style={{ cursor: 'pointer' }}>
    <title>Exit: {payload?.date} @ ${payload?.close?.toFixed(2)}</title>
    <polygon points="8,15 15,1 1,1" fill="#141210" stroke="#F5F1E8" strokeWidth="2" />
  </svg>
);

// Loading Spinner
const LoadingSpinner = ({ message = "Loading..." }) => (
  <div className="flex flex-col items-center justify-center py-12">
    <Loader2 className="w-8 h-8 text-claret animate-spin mb-3" />
    <p className="text-ink-mute">{message}</p>
  </div>
);

// Error Display
const ErrorDisplay = ({ message, onRetry }) => (
  <div className="flex flex-col items-center justify-center py-12">
    <AlertCircle className="w-12 h-12 text-negative mb-3" />
    <p className="text-negative mb-4">{message}</p>
    {onRetry && (
      <button onClick={onRetry} className="px-4 py-2 bg-ink text-white rounded-lg hover:bg-claret">
        Retry
      </button>
    )}
  </div>
);

// LoginModal is now imported from ./components/LoginModal

// Buy Modal Component
const BuyModal = ({ symbol, price, stockInfo, onClose, onBuy, viewMode = 'advanced', timeTravelDate = null, lastPositionDollars = null, source = 'preserver' }) => {
  // Default the share count to the user's last BUY's dollar amount. New
  // users (no prior BUY) get a $10K default. Clamp to avoid 9999-share
  // nonsense when `price` falls through its fallback chain to 0.
  const targetDollars = lastPositionDollars && lastPositionDollars > 0 ? lastPositionDollars : 10000;
  const [shares, setShares] = useState(
    price > 1 ? Math.max(1, Math.floor(targetDollars / price)) : 100
  );
  const [entryPrice, setEntryPrice] = useState(price);
  const [submitting, setSubmitting] = useState(false);

  const totalCost = shares * entryPrice;
  const trailingStop = entryPrice * (1 - EFFECTIVE_TRAIL_FRAC); // trail from live effective params

  const handleBuy = async () => {
    setSubmitting(true);
    logEvent('record_entry_submit', { symbol, shares, price: entryPrice, time_travel: !!timeTravelDate });
    try {
      const result = await api.post('/api/portfolio/positions', {
        symbol,
        shares,
        price: entryPrice,
        source,  // scope the trade to the strategy that opened it (t30v | breakout)
        ...(timeTravelDate && { entry_date: timeTravelDate }),
      });
      logEvent('record_entry_success', { symbol, shares, price: entryPrice, position_id: result.position?.id });
      onBuy(result.position);
      onClose();
    } catch (err) {
      console.error('Buy failed:', err);
      logEvent('record_entry_failed', { symbol, error: String(err).slice(0, 200) });
      alert('Failed to create position. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-[60] p-4">
      <div className="bg-paper max-w-md w-full border border-ink overflow-hidden">
        <div className="px-6 py-5 border-b-2 border-ink">
          <div className="font-body text-[0.68rem] font-medium tracking-[0.22em] uppercase text-ink-mute mb-2">Record Entry</div>
          <h2 className="font-display text-2xl font-normal text-ink tracking-tight" style={{ fontVariationSettings: '"opsz" 96' }}>{symbol}</h2>
          {stockInfo?.name && <p className="text-ink-mute text-sm mt-0.5">{stockInfo.name}</p>}
          {timeTravelDate && <p className="font-mono text-[0.72rem] text-ink-light mt-1">Entry date: {timeTravelDate}</p>}
        </div>

        <div className="p-6 space-y-5">
          <div>
            <label className="block font-body text-[0.72rem] font-medium tracking-[0.15em] uppercase text-ink-mute mb-2">Number of Shares</label>
            <input
              type="number"
              value={shares}
              onChange={(e) => setShares(Math.max(1, parseInt(e.target.value) || 0))}
              className="w-full px-4 py-3 border border-rule-dark bg-paper-card font-mono text-[0.95rem] focus:outline-none focus:border-ink"
              min="1"
            />
          </div>

          <div>
            <label className="block font-body text-[0.72rem] font-medium tracking-[0.15em] uppercase text-ink-mute mb-2">Entry Price</label>
            <input
              type="number"
              step="0.01"
              value={entryPrice}
              onChange={(e) => setEntryPrice(parseFloat(e.target.value) || 0)}
              className="w-full px-4 py-3 border border-rule-dark bg-paper-card font-mono text-[0.95rem] focus:outline-none focus:border-ink"
            />
          </div>

          <div className="border-t border-b border-rule py-4 space-y-3">
            <div className="flex justify-between">
              <span className="font-body text-[0.72rem] font-medium tracking-[0.15em] uppercase text-ink-mute">Total Cost</span>
              <span className="font-mono text-[0.95rem] font-medium text-ink">${totalCost.toLocaleString(undefined, { maximumFractionDigits: 2 })}</span>
            </div>
            <div className="flex justify-between">
              <span className="font-body text-[0.72rem] font-medium tracking-[0.15em] uppercase text-ink-mute">{viewMode === 'simple' ? `${Math.round(EFFECTIVE_TRAIL_FRAC*100)}% Safety Net` : `Trailing Stop (${Math.round(EFFECTIVE_TRAIL_FRAC*100)}%)`}</span>
              <span className="font-mono text-[0.95rem] text-ink">${trailingStop.toFixed(2)}</span>
            </div>
            {viewMode !== 'simple' && (
              <div className="flex justify-between">
                <span className="font-body text-[0.72rem] font-medium tracking-[0.15em] uppercase text-ink-mute">Exit Strategy</span>
                <span className="font-mono text-[0.95rem] text-ink-mute">Let winners run</span>
              </div>
            )}
          </div>
        </div>

        <div className="px-6 py-4 border-t border-rule flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-3 text-ink-mute border border-rule-dark hover:border-ink font-body text-[0.85rem] font-medium transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleBuy}
            disabled={submitting || shares < 1 || entryPrice <= 0}
            className="flex-1 px-4 py-3 bg-ink text-paper font-body text-[0.85rem] font-medium tracking-wide hover:bg-claret transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
            {submitting ? 'Saving...' : 'Record Entry'}
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
    logEvent('close_position_submit', { symbol: position.symbol, position_id: position.id, exit_price: exitPrice, pnl_pct: pnlPct });
    try {
      await api.delete(`/api/portfolio/positions/${position.id}?exit_price=${exitPrice}`);
      logEvent('close_position_success', { symbol: position.symbol, position_id: position.id, exit_price: exitPrice, pnl_pct: pnlPct });
      onSell();
      onClose();
    } catch (err) {
      console.error('Sell failed:', err);
      logEvent('close_position_failed', { symbol: position.symbol, position_id: position.id, error: String(err).slice(0, 200) });
      alert('Failed to close position. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-[60] p-4">
      <div className="bg-paper max-w-md w-full border border-ink overflow-hidden">
        <div className="px-6 py-5 border-b-2 border-ink">
          <div className="font-body text-[0.68rem] font-medium tracking-[0.22em] uppercase text-ink-mute mb-2">Record Exit</div>
          <h2 className="font-display text-2xl font-normal text-ink tracking-tight" style={{ fontVariationSettings: '"opsz" 96' }}>{symbol}</h2>
          {stockInfo?.name && <p className="text-ink-mute text-sm mt-0.5">{stockInfo.name}</p>}
        </div>

        <div className="p-6 space-y-5">
          <div>
            <label className="block font-body text-[0.72rem] font-medium tracking-[0.15em] uppercase text-ink-mute mb-2">Number of Shares</label>
            <input
              type="number"
              value={shares}
              onChange={(e) => setShares(Math.max(0, Math.min(position?.shares || 0, parseFloat(e.target.value) || 0)))}
              className="w-full px-4 py-3 border border-rule-dark bg-paper-card font-mono text-[0.95rem] focus:outline-none focus:border-ink"
              max={position?.shares || 0}
            />
            <p className="font-mono text-[0.72rem] text-ink-light mt-1">Max: {Math.round(position?.shares || 0)} shares</p>
          </div>

          <div>
            <label className="block font-body text-[0.72rem] font-medium tracking-[0.15em] uppercase text-ink-mute mb-2">Exit Price</label>
            <input
              type="number"
              step="0.01"
              value={exitPrice}
              onChange={(e) => setExitPrice(parseFloat(e.target.value) || 0)}
              className="w-full px-4 py-3 border border-rule-dark bg-paper-card font-mono text-[0.95rem] focus:outline-none focus:border-ink"
            />
          </div>

          <div className="border-t border-b border-rule py-4 space-y-3">
            <div className="flex justify-between">
              <span className="font-body text-[0.72rem] font-medium tracking-[0.15em] uppercase text-ink-mute">Entry Price</span>
              <span className="font-mono text-[0.95rem] text-ink">${entryPrice.toFixed(2)}</span>
            </div>
            <div className="flex justify-between">
              <span className="font-body text-[0.72rem] font-medium tracking-[0.15em] uppercase text-ink-mute">Total Proceeds</span>
              <span className="font-mono text-[0.95rem] text-ink">${totalProceeds.toLocaleString(undefined, { maximumFractionDigits: 2 })}</span>
            </div>
            <div className="border-t border-rule my-2"></div>
            <div className="flex justify-between">
              <span className="font-body text-[0.72rem] font-medium tracking-[0.15em] uppercase text-ink-mute">Profit / Loss</span>
              <span className={`font-mono text-[0.95rem] font-medium ${pnl >= 0 ? 'text-positive' : 'text-negative'}`}>
                {pnl >= 0 ? '+' : ''}{pnl.toLocaleString(undefined, { maximumFractionDigits: 2 })} ({pnlPct >= 0 ? '+' : ''}{pnlPct.toFixed(1)}%)
              </span>
            </div>
          </div>
        </div>

        <div className="px-6 py-4 border-t border-rule flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-3 text-ink-mute border border-rule-dark hover:border-ink font-body text-[0.85rem] font-medium transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSell}
            disabled={submitting || shares <= 0 || exitPrice <= 0}
            className="flex-1 px-4 py-3 bg-ink text-paper font-body text-[0.85rem] font-medium tracking-wide hover:bg-claret transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
            {submitting ? 'Saving...' : 'Record Exit'}
          </button>
        </div>
      </div>
    </div>
  );
};

// "Where Your Stocks Sit" — ADMIN-ONLY PREVIEW (Aug 2026). Paste holdings → for each, summarize
// where our system has traded it (Preserver live + walk-forward + the Maximizer breakout sleeve)
// and the best result, with a click-through to the full chart + previous-holds overlay. This is
// the paid-customer direction (fed by SnapTrade/CSV import later); gated to admin while counsel
// reviews the framing. Impersonal/backward-looking track record — NOT individualized advice.
// SnapTrade connection-portal modal — lazy so it's never pulled into static prerender.
const SnapTradeReact = lazy(() => import('snaptrade-react').then(m => ({ default: m.SnapTradeReact })));

// Parse a holdings CSV — robust to broker exports (preamble rows + a Symbol/Ticker
// column) OR a plain one-ticker-per-line list. Returns a clean, de-duped ticker array.
function parseHoldingsCsv(text) {
  const lines = (text || '').split(/\r?\n/).filter(l => l.trim());
  if (!lines.length) return [];
  const splitRow = (l) => l.split(',').map(c => c.replace(/^"|"$/g, '').trim());
  const valid = (t) => /^[A-Z][A-Z.\-]{0,6}$/.test(t);
  const skip = new Set(['CASH', 'TOTAL', 'TOTALS', 'ACCOUNT', 'NA', 'N', 'USD', 'MMDA', 'SYMBOL', 'TICKER']);
  // locate a header row with a symbol/ticker column (scan the first few rows)
  let symCol = -1, startRow = 0;
  for (let i = 0; i < Math.min(lines.length, 6); i++) {
    const cells = splitRow(lines[i]).map(c => c.toLowerCase());
    const idx = cells.findIndex(c => c === 'symbol' || c === 'ticker' || c.includes('symbol'));
    if (idx >= 0) { symCol = idx; startRow = i + 1; break; }
  }
  const out = new Set();
  for (let i = startRow; i < lines.length; i++) {
    const cells = splitRow(lines[i]);
    if (symCol >= 0) {
      const t = (cells[symCol] || '').toUpperCase();
      if (valid(t) && !skip.has(t)) out.add(t);
    } else {
      for (const c of cells) {                       // headerless: first ticker-like token per row
        const t = c.toUpperCase();
        if (valid(t) && !skip.has(t)) { out.add(t); break; }
      }
    }
  }
  return [...out];
}

// Mirror Check — how closely a follower's holdings line up with the LIVE model book.
// Shared holdings source for the Mirror AND the main dashboard's "you hold this" bubbles.
// Owns the user's manual/CSV list (localStorage) + live SnapTrade holdings, so both surfaces
// read ONE held-set. Call once per page (Dashboard / MirrorCockpit) and thread down.
function useMirrorHoldings() {
  const { user, isAdmin } = useAuth();
  // Who can connect a brokerage (mirrors the server gate in signals.py): admins (test key), paid
  // subscribers, and EMAIL-VERIFIED trials. Verified trials are allowed because a verified email
  // means a real human — a bogus/gawker signup can't verify. Everyone else gets a modal instead:
  // unverified trials get a "verify to connect" prompt, free-floor gets the "subscribe" preview.
  const _sub = user?.subscription;
  const _emailVerified = !!user?.email_verified;
  const canConnectBroker = isAdmin || _sub?.status === 'active' || (_sub?.status === 'trial' && _emailVerified);
  const isUnverifiedTrial = _sub?.status === 'trial' && !_emailVerified;
  const KEY = 'rigacap_mirror_holdings';
  const SNAP_KEY = 'rigacap_mirror_snap';
  const [holdings, setHoldings] = useState(() => {
    try { return JSON.parse(localStorage.getItem(KEY) || '[]'); } catch { return []; }
  });
  useEffect(() => { try { localStorage.setItem(KEY, JSON.stringify(holdings)); } catch { /* ignore */ } }, [holdings]);

  // Cache the last SnapTrade holdings so surfaces paint complete on load (live sync is 3-5s);
  // still refresh in the background. Cache is overwritten each fetch (disconnect drops names).
  const cachedSnap = (() => { try { return JSON.parse(localStorage.getItem(SNAP_KEY) || 'null'); } catch { return null; } })();
  const [snap, setSnap] = useState(cachedSnap
    ? { connected: (cachedSnap.sources || []).length > 0, sources: cachedSnap.sources || [], loading: false }
    : { connected: false, sources: [], loading: false });
  const [snapSymbols, setSnapSymbols] = useState(cachedSnap?.symbols || []);
  const [snapReady, setSnapReady] = useState(!!cachedSnap);   // gate the alignment render until holdings are known
  const [snapOpen, setSnapOpen] = useState(false);            // connection-portal modal
  const [snapLink, setSnapLink] = useState(null);
  const [previewOpen, setPreviewOpen] = useState(false);      // free-floor "subscribe to connect" teaser
  const [verifyOpen, setVerifyOpen] = useState(false);        // unverified-trial "verify to connect" prompt
  const [csvMsg, setCsvMsg] = useState('');

  const addSymbols = (syms) => {
    const clean = [...new Set((syms || []).filter(Boolean))];
    if (!clean.length) return;
    setHoldings(h => [...new Set([...h, ...clean])].slice(0, 200));
  };
  const removeSymbol = (s) => setHoldings(h => h.filter(x => x !== s));
  const onCsv = (e) => {
    const f = e.target.files?.[0];
    e.target.value = '';                 // allow re-uploading the same file
    if (!f) return;
    const reader = new FileReader();
    reader.onload = () => {
      const syms = parseHoldingsCsv(String(reader.result || ''));
      addSymbols(syms);
      setCsvMsg(syms.length ? `Imported ${syms.length} ticker${syms.length === 1 ? '' : 's'} from ${f.name}` : `No tickers found in ${f.name}`);
      setTimeout(() => setCsvMsg(''), 6000);
    };
    reader.readAsText(f);
  };

  // SnapTrade brokerage connect — read-only, multi-brokerage. Broker holdings live in
  // snapSymbols (their own set), so disconnecting a broker just re-fetches and drops them.
  const fetchSnapHoldings = async () => {
    try {
      const r = await api.get('/api/signals/mirror/snaptrade/holdings');
      const symbols = Array.isArray(r?.symbols) ? r.symbols : [];
      const sources = r?.sources || [];
      setSnapSymbols(symbols);
      setSnap({ connected: !!r?.connected, sources, loading: false });
      try { localStorage.setItem(SNAP_KEY, JSON.stringify({ symbols, sources })); } catch { /* ignore */ }
    } catch { setSnap(s => ({ ...s, loading: false })); }
    finally { setSnapReady(true); }
  };
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const justConnected = params.get('snaptrade') === 'connected';
    fetchSnapHoldings();               // pull already-connected holdings on mount
    if (justConnected) {               // returned from the portal — clean the URL
      params.delete('snaptrade');
      const qs = params.toString();
      window.history.replaceState({}, '', window.location.pathname + (qs ? `?${qs}` : ''));
    }
  }, []);   // eslint-disable-line react-hooks/exhaustive-deps
  const connectBroker = async () => {
    if (!canConnectBroker) {                       // route to the right modal, never call the API
      if (isUnverifiedTrial) setVerifyOpen(true);  // trial but email not confirmed → verify prompt
      else setPreviewOpen(true);                   // free-floor → subscribe teaser
      return;
    }
    setSnap(s => ({ ...s, loading: true }));
    try {
      const r = await api.post('/api/signals/mirror/snaptrade/connect', {});
      if (r?.redirect_uri) { setSnapLink(r.redirect_uri); setSnapOpen(true); }   // open in-app modal
    } catch { /* ignore */ }
    setSnap(s => ({ ...s, loading: false }));
  };
  const disconnectBroker = async (authId, label) => {
    if (!authId) return;
    if (!window.confirm(`Disconnect ${label}? This removes all of its accounts from your Mirror.`)) return;
    // Optimistic: drop it from the header immediately (SnapTrade deletion is async/queued).
    setSnap(s => ({ ...s, sources: s.sources.filter(x => x.authorization_id !== authId) }));
    try { await api.post('/api/signals/mirror/snaptrade/disconnect', { authorization_id: authId }); } catch { /* ignore */ }
    setTimeout(fetchSnapHoldings, 1800);   // reconcile after the async delete completes
  };

  const effective = useMemo(() => [...new Set([...holdings, ...snapSymbols])], [holdings, snapSymbols]);
  const heldSet = useMemo(() => new Set(effective), [effective]);
  const manualSet = useMemo(() => new Set(holdings), [holdings]);   // which chips get an individual ×
  // Admin preview: ?preview=connect opens the subscribe teaser, ?preview=verify the verify prompt,
  // so we can eyeball either modal without a real free/trial account.
  useEffect(() => {
    if (!isAdmin) return;
    const p = new URLSearchParams(window.location.search).get('preview');
    if (p === 'connect') setPreviewOpen(true);
    else if (p === 'verify') setVerifyOpen(true);
  }, [isAdmin]);

  return {
    holdings, effective, heldSet, manualSet,
    snap, snapSymbols, snapReady, snapOpen, snapLink, setSnapOpen,
    canConnectBroker, previewOpen, setPreviewOpen, verifyOpen, setVerifyOpen,
    addSymbols, removeSymbol, onCsv, csvMsg,
    connectBroker, disconnectBroker, fetchSnapHoldings,
  };
}

// Non-paid preview of the brokerage-connect flow. Shows what a subscriber unlocks — link any of
// 50+ brokerages, read-only, auto-syncing Mirror — WITHOUT touching the live connect API or naming
// the underlying provider. Trials/free hit this when they click "Connect brokerage". Evokes the
// real institution picker but in brand claret/paper; broker tiles are illustrative (no live logos).
const PREVIEW_BROKERS = [
  { n: 'Charles Schwab', d: 'schwab.com', i: 'CS' },
  { n: 'Fidelity', d: 'fidelity.com', i: 'F' },
  { n: 'Vanguard', d: 'vanguard.com', i: 'V' },
  { n: 'Robinhood', d: 'robinhood.com', i: 'R' },
  { n: 'E*Trade', d: 'etrade.com', i: 'E' },
  { n: 'Merrill Edge', d: 'merrilledge.com', i: 'M' },
  { n: 'Interactive Brokers', d: 'ibkr.com', i: 'IB' },
  { n: 'Webull', d: 'webull.com', i: 'W' },
];
function BrokerConnectPreview({ onClose }) {
  const [loading, setLoading] = useState(false);
  const subscribe = async () => {
    setLoading(true);
    try {
      const d = await api.post('/api/billing/create-checkout', { plan: 'monthly' });
      if (window.gtag) window.gtag('event', 'begin_checkout', { value: 129, currency: 'USD' });
      window.location.href = d.checkout_url;
    } catch { setLoading(false); }
  };
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-ink/40 backdrop-blur-sm" onClick={onClose}>
      <div className="relative w-full max-w-md bg-paper rounded-2xl shadow-2xl border border-rule overflow-hidden" onClick={e => e.stopPropagation()}>
        <button onClick={onClose} aria-label="Close" className="absolute top-3 right-3 text-ink-light hover:text-ink text-xl leading-none">×</button>
        {/* connect motif — RigaCap ⇄ your institution */}
        <div className="pt-7 flex items-center justify-center gap-3">
          <div className="w-11 h-11 rounded-full bg-claret text-white flex items-center justify-center font-serif text-lg">R</div>
          <span className="text-ink-light text-lg">⇄</span>
          <div className="w-11 h-11 rounded-full border border-rule bg-paper-deep flex items-center justify-center text-ink-mute">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M3 21h18M5 10h14M5 10l7-5 7 5M6 10v9M18 10v9M10 10v9M14 10v9"/></svg>
          </div>
        </div>
        <div className="px-6 pt-3 pb-6 text-center">
          <h3 className="font-serif text-xl text-ink">Connect your brokerage</h3>
          <p className="text-[0.82rem] text-ink-mute mt-1.5 leading-relaxed">
            Link any of <span className="text-ink font-medium">50+ brokerages</span> — read-only — and your Mirror stays in sync with the book on its own. No manual typing.
          </p>
          <div className="mt-5 relative">
            <div className="absolute inset-x-0 -top-2.5 flex justify-center z-10">
              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-claret text-white text-[0.58rem] font-semibold tracking-[0.12em] uppercase shadow">
                <svg width="9" height="9" viewBox="0 0 24 24" fill="currentColor"><path d="M12 1a5 5 0 00-5 5v3H6a2 2 0 00-2 2v9a2 2 0 002 2h12a2 2 0 002-2v-9a2 2 0 00-2-2h-1V6a5 5 0 00-5-5zm-3 8V6a3 3 0 016 0v3H9z"/></svg>
                Preview
              </span>
            </div>
            <div className="grid grid-cols-2 gap-2 opacity-70 pointer-events-none pt-1.5">
              {PREVIEW_BROKERS.map(b => (
                <div key={b.n} className="flex items-center gap-2 px-2.5 py-2 rounded-lg border border-rule bg-paper-deep text-left">
                  <div className="w-7 h-7 rounded-full bg-ink/[0.05] border border-rule flex items-center justify-center text-[0.58rem] font-semibold text-ink-mute shrink-0">{b.i}</div>
                  <div className="min-w-0">
                    <div className="text-[0.72rem] text-ink font-medium truncate">{b.n}</div>
                    <div className="text-[0.6rem] text-ink-light truncate">{b.d}</div>
                  </div>
                </div>
              ))}
            </div>
            <div className="text-[0.64rem] text-ink-light mt-2">…and 40+ more, including your IRA custodian</div>
          </div>
          <button onClick={subscribe} disabled={loading}
            className="mt-5 w-full py-2.5 rounded-lg bg-claret text-white text-sm font-medium hover:opacity-90 disabled:opacity-50 transition-opacity">
            {loading ? 'Opening…' : 'Subscribe to connect'}
          </button>
          <button onClick={onClose} className="mt-2 w-full py-1.5 text-[0.76rem] text-ink-light hover:text-ink-mute">Maybe later</button>
          <p className="text-[0.62rem] text-ink-light mt-3 leading-relaxed">
            Read-only. We see holdings only to compare against the book — never to trade, move money, or touch your login.
          </p>
        </div>
      </div>
    </div>
  );
}

// Shown when an unverified TRIAL user tries to connect — connecting is unlocked by verifying their
// email (keeps us from paying SnapTrade for bogus signups). Lets them resend the confirmation link.
function VerifyToConnect({ onClose }) {
  const [state, setState] = useState('idle');   // idle | sending | sent | error
  const resend = async () => {
    setState('sending');
    try { await api.post('/api/auth/resend-verification', {}); setState('sent'); }
    catch { setState('error'); }
  };
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-ink/40 backdrop-blur-sm" onClick={onClose}>
      <div className="relative w-full max-w-md bg-paper rounded-2xl shadow-2xl border border-rule overflow-hidden" onClick={e => e.stopPropagation()}>
        <button onClick={onClose} aria-label="Close" className="absolute top-3 right-3 text-ink-light hover:text-ink text-xl leading-none">×</button>
        <div className="pt-8 flex items-center justify-center">
          <div className="w-12 h-12 rounded-full bg-claret/10 border border-claret/30 flex items-center justify-center">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#7A2430" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="M4 7l8 6 8-6"/></svg>
          </div>
        </div>
        <div className="px-6 pt-3 pb-6 text-center">
          <h3 className="font-serif text-xl text-ink">Confirm your email to connect</h3>
          <p className="text-[0.82rem] text-ink-mute mt-1.5 leading-relaxed">
            Linking a brokerage unlocks once your email is verified. Check your inbox for the
            confirmation link from when you signed up — click it, then come back and connect.
          </p>
          {state === 'sent' ? (
            <p className="mt-5 text-[0.84rem] text-positive font-medium">Sent — check your inbox (and spam).</p>
          ) : (
            <button onClick={resend} disabled={state === 'sending'}
              className="mt-5 w-full py-2.5 rounded-lg bg-claret text-white text-sm font-medium hover:opacity-90 disabled:opacity-50 transition-opacity">
              {state === 'sending' ? 'Sending…' : 'Resend the verification email'}
            </button>
          )}
          {state === 'error' && <p className="mt-2 text-[0.72rem] text-claret">Couldn&rsquo;t send just now — try again in a minute.</p>}
          <button onClick={onClose} className="mt-2 w-full py-1.5 text-[0.76rem] text-ink-light hover:text-ink-mute">Close</button>
        </div>
      </div>
    </div>
  );
}

// Tool-safe by design: every line is a factual set-comparison of the PUBLISHED book vs
// what the user holds — never an instruction. The user decides whether to close any gap.
// Holdings come from the shared useMirrorHoldings hook (holdingsApi); alignment recomputes off the book.
const MirrorCheck = ({ book, preserverBook, tier, regimeName, onOpenChart, onAlignment, heroMode = false, holdingsApi }) => {
  const {
    holdings, effective, heldSet, manualSet,
    snap, snapSymbols, snapReady, snapOpen, snapLink, setSnapOpen,
    previewOpen, setPreviewOpen, verifyOpen, setVerifyOpen,
    addSymbols, removeSymbol, onCsv, csvMsg,
    connectBroker, disconnectBroker, fetchSnapHoldings,
  } = holdingsApi;
  const [input, setInput] = useState('');
  const CTX_KEY = 'rigacap_mirror_ctx';
  const BEST_KEY = 'rigacap_mirror_best';
  const [ctx, setCtx] = useState(() => {        // { universe:Set, entered:Set } — hydrate from cache
    try { const c = JSON.parse(localStorage.getItem(CTX_KEY) || 'null'); return c ? { universe: new Set(c.universe || []), entered: new Set(c.entered || []) } : null; }
    catch { return null; }
  });
  const [best, setBest] = useState(() => {      // symbol -> best past pnl% (drifted flourish), cached
    try { return JSON.parse(localStorage.getItem(BEST_KEY) || '{}'); } catch { return {}; }
  });
  const [showOther, setShowOther] = useState(false);          // heroMode: reveal non-book holdings (setup detail)
  // Rolling book history (heroMode only) → "Today" delta + alignment-drift sparkline. Cached
  // for a one-shot paint like the rest.
  const [bookHist, setBookHist] = useState(() => {
    try { return JSON.parse(localStorage.getItem('rigacap_mirror_bookhist') || 'null'); } catch { return null; }
  });

  // Membership sets (universe + ever-traded), fetched once. Bucketing is set-driven, not per-ticker.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await api.get('/api/signals/mirror-context');
        if (!cancelled) {
          setCtx({ universe: new Set(r?.universe || []), entered: new Set(r?.entered || []) });
          try { localStorage.setItem(CTX_KEY, JSON.stringify({ universe: r?.universe || [], entered: r?.entered || [] })); } catch { /* ignore */ }
        }
      } catch { if (!cancelled) setCtx(c => c || { universe: new Set(), entered: new Set() }); }   // keep cache on error
    })();
    return () => { cancelled = true; };
  }, []);

  // Book history for the "Today" delta + drift sparkline (heroMode / cockpit only).
  useEffect(() => {
    if (!heroMode) return;
    let cancelled = false;
    (async () => {
      try {
        const r = await api.get('/api/signals/mirror/book-history?days=60');
        if (!cancelled && Array.isArray(r?.history)) {
          setBookHist(r.history);
          try { localStorage.setItem('rigacap_mirror_bookhist', JSON.stringify(r.history)); } catch { /* ignore */ }
        }
      } catch { /* keep cache on error */ }
    })();
    return () => { cancelled = true; };
  }, [heroMode]);

  // The book to mirror = your full ENTITLEMENT, but tracked PER BOOK so a Maximizer
  // subscriber sees which product each position belongs to (base vs breakout), not a
  // flattened "aligned". For a Maximizer: tier_book = breakout, preserver_book = base.
  // For a Preserver: tier_book IS the Preserver book (no breakout).
  const isMax = tier === 'maximizer';
  const symsOf = (b) => new Set(((b?.holdings) || []).map(h => (h.symbol || '').toUpperCase()).filter(Boolean));
  const preserverSyms = useMemo(() => symsOf(isMax ? preserverBook : book), [isMax, book, preserverBook]);
  const maximizerSyms = useMemo(() => symsOf(isMax ? book : null), [isMax, book]);
  const bookSyms = useMemo(() => [...new Set([...preserverSyms, ...maximizerSyms])], [preserverSyms, maximizerSyms]);
  const bookSet = useMemo(() => new Set(bookSyms), [bookSyms]);
  // effective / heldSet / manualSet now come from the shared useMirrorHoldings hook (above).
  const bookOf = (s) => {
    const p = preserverSyms.has(s), m = maximizerSyms.has(s);
    return m && p ? 'P·M' : m ? 'M' : p ? 'P' : null;
  };

  const aligned = effective.filter(s => bookSet.has(s));
  const alignedP = aligned.filter(s => preserverSyms.has(s));
  const alignedM = aligned.filter(s => maximizerSyms.has(s));
  const inBookNotHeld = bookSyms.filter(s => !heldSet.has(s));
  const notInBook = effective.filter(s => !bookSet.has(s));
  // Set-driven buckets: ever-traded → drifted; else in-universe → no-signal; else outside.
  const drifted = notInBook.filter(s => ctx?.entered?.has(s));
  const rest = notInBook.filter(s => !ctx?.entered?.has(s));
  const inUniverse = rest.filter(s => ctx?.universe?.has(s));
  const outside = rest.filter(s => !ctx?.universe?.has(s));
  const mirroredPct = bookSyms.length ? Math.round((aligned.length / bookSyms.length) * 100) : 0;
  const tierLabel = tier === 'maximizer' ? 'Maximizer' : 'Preserver';
  // Render the alignment as ONE unit — only once both the membership sets AND holdings are
  // known — so it never paints in two stages (page first, brokerage sync 3-5s later).
  const ready = ctx !== null && snapReady;

  // Report alignment up (the /app/next cockpit drives the eclipse off this). Carry the per-book
  // split so the caption can read "X of 20 Preserver · Y of 15 Maximizer" instead of a merged total.
  useEffect(() => { if (ready) onAlignment?.(mirroredPct, {
    aligned: aligned.length, total: bookSyms.length, isMax,
    preserver: { aligned: alignedP.length, total: preserverSyms.size },
    maximizer: { aligned: alignedM.length, total: maximizerSyms.size },
  }); },
    [ready, mirroredPct, aligned.length, bookSyms.length]);   // eslint-disable-line react-hooks/exhaustive-deps

  // Best past result for drifted names (the "we caught it" flourish) — only for the few drifted.
  useEffect(() => {
    const need = drifted.filter(s => best[s] === undefined);
    if (!need.length) return;
    let cancelled = false;
    (async () => {
      const upd = {};
      for (const s of need) {
        try {
          const r = await api.get(`/api/stock/${s}/previous-holds?t=${Date.now()}`);
          const vals = (r?.holds || []).map(h => h.pnl_pct).filter(x => x != null);
          upd[s] = vals.length ? Math.max(...vals) : null;
        } catch { upd[s] = null; }
      }
      if (!cancelled) setBest(b => {
        const nb = { ...b, ...upd };
        try { localStorage.setItem(BEST_KEY, JSON.stringify(nb)); } catch { /* ignore */ }
        return nb;
      });
    })();
    return () => { cancelled = true; };
  }, [drifted.join(',')]);   // eslint-disable-line react-hooks/exhaustive-deps

  // Add/remove delegate to the shared holdings hook; input is the only local UI state here.
  const add = (e) => {
    e?.preventDefault();
    const syms = [...new Set((input.toUpperCase().match(/[A-Z][A-Z.\-]{0,6}/g) || []))];
    if (!syms.length) return;
    addSymbols(syms);
    setInput('');
  };
  const del = (s) => removeSymbol(s);

  const Chip = ({ s, tone, sub, badge, removable = true }) => (
    <span className={`group inline-flex items-center gap-1.5 pl-2.5 ${removable ? 'pr-1' : 'pr-2.5'} py-1 rounded-full border text-[0.8rem] font-mono ${tone}`}>
      <button onClick={() => onOpenChart?.({ type: 'signal', data: { symbol: s }, symbol: s })} className="hover:underline">{s}</button>
      {badge && <span className={`text-[0.55rem] font-semibold leading-none px-1 py-0.5 rounded ${badge.includes('M') ? 'bg-claret/15 text-claret' : 'bg-ink/10 text-ink-mute'}`} title={badge === 'M' ? 'Maximizer breakout book' : badge === 'P' ? 'Preserver base book' : 'In both books'}>{badge}</span>}
      {sub && <span className="text-[0.62rem] opacity-70">{sub}</span>}
      {removable && (
        <button onClick={() => del(s)} className="opacity-30 group-hover:opacity-70 hover:!opacity-100 text-[0.85rem] leading-none px-0.5" title="remove" aria-label={`remove ${s}`}>×</button>
      )}
    </span>
  );

  const Group = ({ label, note, children, count }) => (
    count ? (
      <div className="mb-4">
        <div className="flex items-baseline gap-2 mb-1.5">
          <span className="font-body text-[0.6rem] font-medium tracking-[0.2em] uppercase text-ink-mute">{label}</span>
          <span className="font-mono text-[0.7rem] text-ink-light">{count}</span>
        </div>
        <p className="text-[0.72rem] text-ink-light mb-2">{note}</p>
        <div className="flex flex-wrap gap-2">{children}</div>
      </div>
    ) : null
  );

  // Book view (heroMode): the model book as a ledger, held first then gaps, your holdings
  // annotated onto it — instead of two flat walls of pills. Non-book names collapse below.
  // Split PER BOOK so a subscriber sees the Preserver book and the Maximizer breakout book
  // as separate, labeled sections (a user may run only one) — never a confusing merged count.
  const rowsFor = (symSet) => [...symSet]
    .map(s => ({ s, held: heldSet.has(s), manual: manualSet.has(s), badge: isMax ? bookOf(s) : null }))
    .sort((a, b) => (Number(b.held) - Number(a.held)) || a.s.localeCompare(b.s));
  const preserverRows = rowsFor(preserverSyms);
  const maximizerRows = rowsFor(maximizerSyms);
  const otherCount = drifted.length + inUniverse.length + outside.length;

  // One book's ledger — header (held/gaps) + the annotated grid. Reused per section.
  const BookLedger = ({ label, rows }) => (
    <div className="mb-5">
      <div className="flex items-baseline justify-between mb-1.5 pb-1.5 border-b border-ink/70">
        <span className="font-body text-[0.62rem] font-medium tracking-[0.2em] uppercase text-ink-mute">{label} · {rows.length} positions</span>
        <span className="font-mono text-[0.7rem] text-ink-light" style={{ fontFeatureSettings: '"tnum"' }}>{rows.filter(r => r.held).length} held · {rows.filter(r => !r.held).length} gaps</span>
      </div>
      <div className="grid gap-x-8" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))' }}>
        {rows.map(r => (
          <div key={r.s} className={`group flex items-center gap-2 py-[7px] border-b border-rule/50 ${r.held ? '' : 'opacity-90'}`}>
            <span className={r.held ? 'text-positive' : 'text-claret/45'} style={{ fontSize: 10, lineHeight: 1 }}>{r.held ? '●' : '○'}</span>
            <button onClick={() => onOpenChart?.({ type: 'signal', data: { symbol: r.s }, symbol: r.s })}
              className={`font-display text-[0.98rem] hover:underline ${r.held ? 'text-ink font-medium' : 'text-ink-mute'}`} style={{ fontVariationSettings: '"opsz" 32' }}>{r.s}</button>
            {isMax && r.badge === 'P·M' && <span className="text-[0.5rem] font-semibold leading-none px-1 py-0.5 rounded bg-claret/15 text-claret" title="Also in your other book">both</span>}
            <span className={`ml-auto text-[0.62rem] font-mono ${r.held ? 'text-positive' : 'text-ink-light'}`}>{r.held ? 'held' : 'gap'}</span>
            {r.manual && (
              <button onClick={() => del(r.s)} title={`Remove ${r.s}`} aria-label={`remove ${r.s}`}
                className="text-ink-light hover:text-claret text-[0.9rem] leading-none px-0.5 opacity-40 group-hover:opacity-100 transition-opacity">×</button>
            )}
          </div>
        ))}
      </div>
    </div>
  );

  // "Today" heartbeat + drift (heroMode). The book set for a given day mirrors the live
  // bookSet logic: Maximizer = preserver ∪ maximizer, Preserver = preserver only. Drift %
  // holds the user's CURRENT list fixed against each day's book (we don't store per-user
  // holdings history) — it reads how the BOOK moved relative to what they hold.
  const histSetFor = (day) => new Set(
    (isMax ? [...(day.preserver || []), ...(day.maximizer || [])] : (day.preserver || [])).map(s => (s || '').toUpperCase())
  );
  const driftSeries = (bookHist || []).map(day => {
    const bs = histSetFor(day);
    const al = effective.filter(s => bs.has(s)).length;
    return { date: day.date, pct: bs.size ? Math.round((al / bs.size) * 100) : 0 };
  });
  let entered = [], exited = [], alignDelta = 0;
  if (bookHist && bookHist.length >= 2) {
    const t = histSetFor(bookHist[bookHist.length - 1]);
    const y = histSetFor(bookHist[bookHist.length - 2]);
    entered = [...t].filter(s => !y.has(s)).sort();
    exited = [...y].filter(s => !t.has(s)).sort();
    alignDelta = driftSeries[driftSeries.length - 1].pct - driftSeries[driftSeries.length - 2].pct;
  }

  return (
    <div className={heroMode ? 'mb-6' : 'mb-6 border-2 border-claret/40 bg-paper-card rounded-lg overflow-hidden'}>
      {!heroMode && (
        <div className="flex items-baseline justify-between px-5 py-3 border-b border-rule bg-claret/5">
          <h2 className="font-display text-[1.1rem] font-medium text-ink tracking-tight" style={{ fontVariationSettings: '"opsz" 48' }}>
            Mirror
            <em className="font-display italic text-ink-mute text-[0.8rem] ml-2" style={{ fontVariationSettings: '"opsz" 24' }}>preview · admin only</em>
          </h2>
          <span className="text-[0.62rem] font-medium tracking-[0.18em] uppercase text-claret px-2 py-1 border border-claret/40 rounded">Direction demo</span>
        </div>
      )}
      <div className={heroMode ? '' : 'p-5'}>
        {!heroMode && (
          <>
            <p className="text-sm text-ink-mute mb-1">How closely are you mirroring the book?</p>
            <p className="text-[0.8rem] text-ink-light mb-4">Add the tickers you hold. We show how they line up with your tier&rsquo;s current model book — the facts, side by side. Whether to close the gap is your call.</p>
          </>
        )}

        {/* Alignment gauge — skeleton until holdings are known, then the whole thing at once.
            In hero mode the ECLIPSE above IS the gauge, so we drop this block entirely and
            render only a slim context caption in its place (no duplicate %/bar). */}
        {heroMode ? (
          ready && (
            <p className="text-[0.76rem] text-ink-mute text-center mb-5">
              Your tier: <span className="text-ink">{tierLabel}</span>
              {regimeName ? <> · Market regime today: <span className="text-ink">{regimeName}</span></> : null}
              {isMax ? <> · <span className="text-ink">Preserver base</span> <span className="font-mono">{alignedP.length}/{preserverSyms.size}</span> · <span className="text-claret">Maximizer breakout</span> <span className="font-mono">{alignedM.length}/{maximizerSyms.size}</span></> : null}
            </p>
          )
        ) : !ready ? (
          <div className="mb-4 p-4 bg-paper-deep border border-rule rounded-lg animate-pulse">
            <div className="h-7 w-48 bg-rule rounded mb-3" />
            <div className="h-2 bg-rule rounded-full" />
            <div className="h-3 w-56 bg-rule/60 rounded mt-3" />
          </div>
        ) : (
        <div className="mb-4 p-4 bg-paper-deep border border-rule rounded-lg">
          <div className="flex items-baseline justify-between mb-2">
            <span className="font-display text-[1.4rem] font-medium text-ink" style={{ fontVariationSettings: '"opsz" 48' }}>
              {aligned.length} <span className="text-ink-light text-[1rem]">of {bookSyms.length}</span> <span className="text-ink-mute text-[0.85rem] font-body">model positions held</span>
            </span>
            <span className="font-mono text-[1.1rem] text-claret font-medium" style={{ fontFeatureSettings: '"tnum"' }}>{mirroredPct}%</span>
          </div>
          <div className="h-2 bg-rule rounded-full overflow-hidden">
            <div className="h-full bg-claret rounded-full transition-all" style={{ width: `${mirroredPct}%` }} />
          </div>
          {isMax && (
            <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-[0.72rem]">
              <span className="text-ink-mute"><span className="inline-block w-2 h-2 rounded-sm bg-ink/25 align-middle mr-1" />Preserver base <span className="font-mono text-ink">{alignedP.length}/{preserverSyms.size}</span></span>
              <span className="text-ink-mute"><span className="inline-block w-2 h-2 rounded-sm bg-claret/60 align-middle mr-1" />Maximizer breakout <span className="font-mono text-ink">{alignedM.length}/{maximizerSyms.size}</span></span>
            </div>
          )}
          <p className="text-[0.68rem] text-ink-light mt-2">Your tier: <span className="text-ink-mute">{tierLabel}</span>{regimeName ? <> · Market regime today: <span className="text-ink-mute">{regimeName}</span></> : null}{isMax ? <> · <span className="text-ink-mute">P</span>/<span className="text-claret">M</span> badges show which book each name is in</> : null}</p>
        </div>
        )}

        {/* TODAY — the daily heartbeat: alignment change + what the book did, with a drift trend. */}
        {heroMode && ready && bookHist && bookHist.length >= 1 && (
          <div className="mb-5 py-2.5 border-y border-rule flex items-center flex-wrap gap-x-5 gap-y-1.5">
            <span className="font-body text-[0.6rem] font-medium tracking-[0.2em] uppercase text-ink-mute">Today</span>
            {bookHist.length >= 2 ? (
              <>
                <span className="text-[0.86rem] text-ink">Alignment <span className="font-medium">{mirroredPct}%</span>
                  {alignDelta !== 0 && <span className={`ml-1 font-mono text-[0.8rem] ${alignDelta > 0 ? 'text-positive' : 'text-negative'}`}>{alignDelta > 0 ? '▲' : '▼'}{Math.abs(alignDelta)}</span>}
                </span>
                {(entered.length || exited.length) ? (
                  <span className="text-[0.8rem] text-ink-mute">
                    {entered.length > 0 && <>Book entered <span className="text-claret font-medium">{entered.join(', ')}</span></>}
                    {entered.length > 0 && exited.length > 0 && <span className="text-ink-light"> · </span>}
                    {exited.length > 0 && <>exited <span className="text-ink font-medium">{exited.join(', ')}</span></>}
                  </span>
                ) : <span className="text-[0.8rem] text-ink-light">Book unchanged</span>}
              </>
            ) : (
              <span className="text-[0.8rem] text-ink-light">Tracking your alignment from today.</span>
            )}
            {driftSeries.length >= 2 && (
              <span className="ml-auto flex items-center gap-2">
                <span className="text-[0.56rem] tracking-[0.14em] uppercase text-ink-light">{driftSeries.length}-day drift</span>
                <Sparkline series={driftSeries} />
              </span>
            )}
          </div>
        )}

        <div data-tour="mirror-connect">
        <form onSubmit={add} className="flex gap-2 mb-2">
          <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="Add tickers you hold — AAPL, NVDA…"
            className="flex-1 px-3 py-2 text-sm bg-paper-deep border border-rule rounded-lg text-ink placeholder:text-ink-light focus:outline-none focus:border-claret" />
          <button type="submit" className="px-4 py-2 text-sm font-medium bg-ink text-white rounded-lg hover:opacity-90">Add</button>
        </form>
        <div className="flex flex-wrap items-center gap-2 mb-5">
          <span className="text-[0.72rem] text-ink-light">or import:</span>
          <label className="cursor-pointer text-[0.78rem] font-medium px-3 py-1.5 border border-rule rounded-lg text-ink-mute hover:border-claret hover:text-claret transition-colors">
            Upload CSV
            <input type="file" accept=".csv,text/csv,text/plain" className="hidden" onChange={onCsv} />
          </label>
          <button type="button" onClick={connectBroker} disabled={snap.loading}
            title="Connect your brokerage (read-only)"
            className="text-[0.78rem] font-medium px-3 py-1.5 border border-claret/50 rounded-lg text-claret hover:bg-claret/[0.06] transition-colors disabled:opacity-50">
            {snap.loading ? 'Opening…' : snap.connected ? 'Connect another brokerage' : 'Connect brokerage'}
          </button>
          {csvMsg && <span className="text-[0.72rem] text-positive">{csvMsg}</span>}
        </div>
        </div>
        {ready && snap.connected && snap.sources.length > 0 && (
          <div className="mb-4 -mt-1">
            <div className="flex items-center gap-2 mb-1.5">
              <span className="text-[0.6rem] font-medium tracking-[0.18em] uppercase text-positive">Connected</span>
              <button onClick={fetchSnapHoldings} className="text-[0.66rem] text-ink-light hover:text-claret underline">refresh</button>
            </div>
            <div className="flex flex-wrap gap-2">
              {snap.sources.map((b, i) => (
                <span key={i} className="group inline-flex items-center gap-2 pl-2.5 pr-1.5 py-1 rounded-lg border border-rule bg-paper-deep text-[0.72rem]">
                  <span className="text-ink font-medium">{b.institution}</span>
                  {Array.isArray(b.accounts) && b.accounts.length > 0 && (
                    <span className="text-ink-light">{b.accounts.join(' · ')}</span>
                  )}
                  {b.authorization_id && (
                    <button onClick={() => disconnectBroker(b.authorization_id, b.institution)}
                      className="opacity-40 group-hover:opacity-80 hover:!opacity-100 text-ink-mute text-[0.9rem] leading-none px-0.5"
                      title={`Disconnect ${b.institution}`} aria-label={`disconnect ${b.institution}`}>×</button>
                  )}
                </span>
              ))}
            </div>
          </div>
        )}

        {ready && ((effective.length === 0) ? (
          <p className="text-sm text-ink-light py-4 text-center">Add a ticker you hold to see how you line up with the book.</p>
        ) : heroMode ? (
          <>
            {/* THE BOOK(S) — a ledger of the model's positions, your holdings annotated onto it.
                Held names first (●), then the gaps you don't hold (○). Split into labeled
                Preserver / Maximizer sections so each product's alignment stands on its own. */}
            <BookLedger label={isMax ? 'The Preserver book' : 'The book'} rows={preserverRows} />
            {isMax && maximizerRows.length > 0 && (
              <BookLedger label="The Maximizer breakout book" rows={maximizerRows} />
            )}

            {/* Non-book holdings — the setup/diagnostic detail, collapsed by default. */}
            {otherCount > 0 && (
              <div className="mb-2 border-t border-rule">
                <button onClick={() => setShowOther(v => !v)} className="w-full flex items-baseline gap-2 py-2.5 text-left">
                  <span className="font-body text-[0.62rem] font-medium tracking-[0.2em] uppercase text-ink-mute">Also in your account</span>
                  <span className="font-mono text-[0.7rem] text-ink-light">{otherCount} not in the model</span>
                  <span className="ml-auto text-ink-light text-[0.7rem]">{showOther ? '▾ hide' : '▸ show'}</span>
                </button>
                {showOther && (
                  <div className="pt-1">
                    <Group label="No longer in the model" count={drifted.length} note="The model traded these before and has since exited.">
                      {drifted.map(s => <Chip key={s} s={s} removable={manualSet.has(s)} tone="border-rule bg-paper-deep text-ink-mute" sub={best[s] != null ? `${best[s] >= 0 ? '+' : ''}${best[s].toFixed(0)}%` : ''} />)}
                    </Group>
                    <Group label="In our universe, no signal" count={inUniverse.length} note="Liquid enough for us to track — the model has just never had a reason to buy them.">
                      {inUniverse.map(s => <Chip key={s} s={s} removable={manualSet.has(s)} tone="border-rule bg-paper-deep text-ink-mute" />)}
                    </Group>
                    <Group label="Outside our universe" count={outside.length} note="ETFs, or below our price / liquidity floor — not names the model considers.">
                      {outside.map(s => <Chip key={s} s={s} removable={manualSet.has(s)} tone="border-rule text-ink-light" />)}
                    </Group>
                  </div>
                )}
              </div>
            )}
          </>
        ) : (
          <>
            <Group label="In the model, and in your account" count={aligned.length} note="Aligned — the book holds these and so do you.">
              {aligned.map(s => <Chip key={s} s={s} badge={isMax ? bookOf(s) : null} removable={manualSet.has(s)} tone="border-positive/50 bg-positive/[0.07] text-ink" />)}
            </Group>
            <Group label="In the model book, not in your account" count={inBookNotHeld.length} note="Current book positions your list doesn't include.">
              {inBookNotHeld.map(s => <Chip key={s} s={s} badge={isMax ? bookOf(s) : null} tone="border-claret/50 bg-claret/[0.06] text-claret" removable={false} />)}
            </Group>
            <Group label="In your account, no longer in the model" count={drifted.length} note="The model traded these before and has since exited.">
              {drifted.map(s => <Chip key={s} s={s} removable={manualSet.has(s)} tone="border-rule bg-paper-deep text-ink-mute" sub={best[s] != null ? `${best[s] >= 0 ? '+' : ''}${best[s].toFixed(0)}%` : ''} />)}
            </Group>
            <Group label="In our universe, no signal" count={inUniverse.length} note="Liquid enough for us to track — the model has just never had a reason to buy them.">
              {inUniverse.map(s => <Chip key={s} s={s} removable={manualSet.has(s)} tone="border-rule bg-paper-deep text-ink-mute" />)}
            </Group>
            <Group label="Outside our universe" count={outside.length} note="ETFs, or below our price / liquidity floor — not names the model considers.">
              {outside.map(s => <Chip key={s} s={s} removable={manualSet.has(s)} tone="border-rule text-ink-light" />)}
            </Group>
          </>
        ))}

        <p className="text-[0.68rem] text-ink-light mt-4 pt-3 border-t border-rule leading-relaxed">
          This compares your holdings to RigaCap&rsquo;s published model book. It is information, <span className="text-ink-mute">not investment advice</span> and not a recommendation to buy, sell, or hold any security. RigaCap is not your investment adviser. You decide what to follow and execute it through your own broker.
        </p>
      </div>
      {snapOpen && snapLink && (
        <Suspense fallback={null}>
          <SnapTradeReact
            loginLink={snapLink}
            isOpen={snapOpen}
            close={() => setSnapOpen(false)}
            onSuccess={() => { setSnapOpen(false); fetchSnapHoldings(); }}
            onError={() => setSnapOpen(false)}
            onExit={() => setSnapOpen(false)}
          />
        </Suspense>
      )}
      {previewOpen && <BrokerConnectPreview onClose={() => setPreviewOpen(false)} />}
      {verifyOpen && <VerifyToConnect onClose={() => setVerifyOpen(false)} />}
    </div>
  );
};

// Tiny inline-SVG sparkline for the alignment-drift trend. Autoscales to the data so small
// week-to-week drift is visible; claret line + emphasized endpoint.
function Sparkline({ series, w = 104, h = 26 }) {
  if (!series || series.length < 2) return null;
  const xs = series.map(d => d.pct);
  const min = Math.min(...xs), max = Math.max(...xs), span = (max - min) || 1;
  const step = w / (series.length - 1);
  const y = v => (h - 3) - ((v - min) / span) * (h - 6);
  const pts = series.map((d, i) => [i * step, y(d.pct)]);
  const path = pts.map((p, i) => `${i ? 'L' : 'M'}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ');
  const last = pts[pts.length - 1];
  return (
    <svg width={w} height={h} style={{ display: 'block', overflow: 'visible' }} aria-hidden="true">
      <path d={path} fill="none" stroke="#7A2430" strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={last[0].toFixed(1)} cy={last[1].toFixed(1)} r="2.3" fill="#7A2430" />
    </svg>
  );
}

// Small live eclipse glyph — the Mirror's identity in the tab bar. A claret corona ring so it
// reads on both paper (inactive tab) and ink (active tab); the moon slides to total at 100%.
function EclipseGlyph({ pct = 0, size = 18 }) {
  const a = Math.max(0, Math.min(1, (pct || 0) / 100));
  // Match AlignmentEclipse: sun CENTERED, moon slides in from the right by (1-a)·R·2.16 — so 100%
  // = total (moon centered), 0% = clear (moon off the disc), and 50% reads as a true half-eclipse.
  const R = 14;
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" style={{ display: 'block', flexShrink: 0 }} aria-hidden="true">
      <defs><clipPath id="eclipse-glyph"><circle cx="20" cy="20" r="18" /></clipPath></defs>
      <g clipPath="url(#eclipse-glyph)">
        <circle cx="20" cy="20" r={R} fill="#F4E9CE" />
        <circle cx={20 + (1 - a) * R * 2.16} cy="20" r={R} fill="#201A13" />
      </g>
      <circle cx="20" cy="20" r="18" fill="none" stroke="#7A2430" strokeWidth="2.5" />
    </svg>
  );
}

// The alignment eclipse — book = sun, portfolio = moon, alignment = the eclipse (100% = total).
// Canvas port of the prototype; driven by a live `pct`, tweened on change. React overlays the number.
function AlignmentEclipse({ pct = 0, max = 440, compact = false }) {
  const ref = useRef(null);
  const curRef = useRef((pct || 0) / 100);
  const starsRef = useRef(null);
  if (!starsRef.current) {
    let seed = 7; const rnd = () => { seed = (seed * 16807) % 2147483647; return seed / 2147483647; };
    starsRef.current = Array.from({ length: 90 }, () => ({ x: rnd(), y: rnd(), r: rnd() * 1.2 + 0.2, a: rnd() * 0.5 + 0.15 }));
  }
  useEffect(() => {
    const canvas = ref.current; if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const dpr = Math.max(1, window.devicePixelRatio || 1);
    const S = 440;
    canvas.width = S * dpr; canvas.height = S * dpr; ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const stars = starsRef.current;
    function draw(a) {
      const cx = S / 2, cy = S * 0.43, R = S * 0.235;
      ctx.clearRect(0, 0, S, S);
      for (const s of stars) { ctx.globalAlpha = s.a * (0.6 + 0.4 * (1 - a)); ctx.fillStyle = '#F3ECDC'; ctx.beginPath(); ctx.arc(s.x * S, s.y * S, s.r, 0, 7); ctx.fill(); }
      ctx.globalAlpha = 1;
      const boost = 0.35 + 0.75 * a;
      const cor = ctx.createRadialGradient(cx, cy, R * 0.82, cx, cy, R * 1.85);
      cor.addColorStop(0, `rgba(197,106,70,${0.55 * boost})`); cor.addColorStop(0.35, `rgba(176,71,46,${0.34 * boost})`);
      cor.addColorStop(0.7, `rgba(122,36,48,${0.16 * boost})`); cor.addColorStop(1, 'rgba(122,36,48,0)');
      ctx.save(); ctx.globalCompositeOperation = 'lighter'; ctx.fillStyle = cor; ctx.beginPath(); ctx.arc(cx, cy, R * 1.85, 0, 7); ctx.fill(); ctx.restore();
      const core = ctx.createRadialGradient(cx - R * 0.15, cy - R * 0.15, R * 0.1, cx, cy, R);
      core.addColorStop(0, '#FFF9ED'); core.addColorStop(0.6, '#F6EBD2'); core.addColorStop(1, '#E9D6AE');
      ctx.fillStyle = core; ctx.beginPath(); ctx.arc(cx, cy, R, 0, 7); ctx.fill();
      const dx = (1 - a) * R * 2.16, mx = cx + dx, my = cy;
      const rim = ctx.createRadialGradient(mx - R, my, R * 0.2, mx, my, R * 1.06);
      rim.addColorStop(0, 'rgba(197,106,70,0)'); rim.addColorStop(0.86, 'rgba(197,106,70,0)');
      rim.addColorStop(0.97, `rgba(197,106,70,${0.5 * a + 0.15})`); rim.addColorStop(1, 'rgba(197,106,70,0)');
      ctx.save(); ctx.globalCompositeOperation = 'lighter'; ctx.fillStyle = rim; ctx.beginPath(); ctx.arc(mx, my, R * 1.06, 0, 7); ctx.fill(); ctx.restore();
      const moon = ctx.createRadialGradient(mx + R * 0.2, my + R * 0.2, R * 0.2, mx, my, R);
      moon.addColorStop(0, '#1C1712'); moon.addColorStop(1, '#0C0A08');
      ctx.fillStyle = moon; ctx.beginPath(); ctx.arc(mx, my, R, 0, 7); ctx.fill();
    }
    const target = Math.max(0, Math.min(1, (pct || 0) / 100));
    if (reduce) { curRef.current = target; draw(target); return; }
    let raf; const start = curRef.current, t0 = performance.now(), dur = 700;
    const step = (now) => { let k = Math.min(1, (now - t0) / dur); k = k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2; const a = start + (target - start) * k; curRef.current = a; draw(a); if (k < 1) raf = requestAnimationFrame(step); };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [pct]);
  const phase = pct >= 100 ? 'Total eclipse' : pct >= 86 ? 'Near-total' : pct >= 40 ? 'Deep partial' : pct > 0 ? 'Partial' : 'No overlap';
  return (
    <div style={{ position: 'relative', width: '100%', maxWidth: max, margin: '0 auto' }}>
      <canvas ref={ref} style={{ width: '100%', aspectRatio: '1', display: 'block' }} />
      {!compact && (
      <div style={{ position: 'absolute', left: 0, right: 0, bottom: '9%', textAlign: 'center', pointerEvents: 'none' }}>
        <div style={{ fontFamily: "'Iowan Old Style',Palatino,Georgia,serif", fontWeight: 600, fontSize: Math.round(max * 0.15), lineHeight: 0.9, color: '#F3ECDC', fontVariantNumeric: 'tabular-nums', textShadow: '0 2px 30px rgba(197,106,70,.35)' }}>
          {Math.round(pct)}<span style={{ fontSize: '0.3em', color: '#8A8172', fontFamily: 'system-ui,sans-serif', marginLeft: 4 }}>% mirrored</span>
        </div>
        <div style={{ fontFamily: 'ui-monospace,Menlo,monospace', fontSize: 10.5, letterSpacing: '0.16em', textTransform: 'uppercase', color: pct >= 100 ? '#E9D6AE' : '#B0472E', marginTop: 5 }}>{phase}</div>
      </div>
      )}
    </div>
  );
}

// Reusable Mirror view — night-sky eclipse hero + book ledger (MirrorCheck heroMode). Used by
// BOTH /app/next (MirrorCockpit) and the in-app "Mirror" tab. The dark hero full-bleeds to the
// viewport and dawns into paper, so it drops cleanly into a padded tab container or a bare page.
// The persistent alignment glyph lives in the Mirror TAB label (EclipseGlyph), not a scroll bar.
function MirrorView({ book, preserverBook, tier, regimeName, onOpenChart, holdingsApi, onState }) {
  const [pct, setPct] = useState(0);
  const [tally, setTally] = useState({ aligned: 0, total: 0 });
  // Full-bleed: extend to the viewport edges even inside a padded container (scrollbar-safe calc).
  const bleed = { position: 'relative', marginLeft: 'calc(50% - 50vw)', marginRight: 'calc(50% - 50vw)' };
  return (
    <>
      {/* Night-sky hero — the eclipse needs the dark to read; the sky then DAWNS into the paper
          content below (fade strip), so the drama up top flows into the editorial data. */}
      <div style={{ ...bleed, background: 'radial-gradient(125% 100% at 50% 4%, #241C12 0%, #16120D 40%, #0C0A08 78%)' }}>
        <div style={{ maxWidth: 760, margin: '0 auto', padding: '14px 20px 92px' }}>
          <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', justifyContent: 'center', gap: '4px 12px' }}>
            <h1 style={{ fontFamily: "'Iowan Old Style',Palatino,Georgia,serif", fontWeight: 600, fontSize: 'clamp(19px,3.4vw,26px)', color: '#F3ECDC', margin: 0, letterSpacing: '-0.01em' }}>How closely are you mirroring the book?</h1>
            <span style={{ fontFamily: "'Iowan Old Style',Georgia,serif", fontStyle: 'italic', color: '#B79A6E', fontSize: 13 }}>book = sun · you = moon</span>
          </div>
          <div data-tour="mirror-eclipse">
            <AlignmentEclipse pct={pct} max={360} />
          </div>
          <p style={{ textAlign: 'center', color: '#B7AE99', fontFamily: 'system-ui,sans-serif', fontSize: 13, marginTop: 2 }}>
            {tally.isMax && tally.maximizer?.total
              ? <>You hold {tally.preserver?.aligned ?? 0} of {tally.preserver?.total ?? 0} Preserver &middot; {tally.maximizer.aligned} of {tally.maximizer.total} Maximizer positions</>
              : <>You hold {tally.preserver?.aligned ?? tally.aligned} of {tally.preserver?.total ?? tally.total} model positions</>}
          </p>
        </div>
        {/* Dawn: the night sky warms at the horizon (echoing the corona) before resolving to paper. */}
        <div style={{ position: 'absolute', left: 0, right: 0, bottom: 0, height: 150, background: 'linear-gradient(180deg, rgba(122,36,48,0) 0%, rgba(150,58,50,0.22) 34%, rgba(197,106,70,0.30) 62%, rgba(230,175,120,0.35) 82%, #F5F1E8 100%)', pointerEvents: 'none' }} />
      </div>
      <div style={{ maxWidth: 760, margin: '0 auto', padding: '4px 20px 56px' }}>
        <MirrorCheck book={book} preserverBook={preserverBook} tier={tier}
          regimeName={regimeName} onOpenChart={onOpenChart || (() => {})} heroMode holdingsApi={holdingsApi}
          onAlignment={(p, t) => { setPct(p); if (t) setTally(t); onState?.({ pct: p, tally: t }); }} />
      </div>
    </>
  );
}

// Small sleeve diagram for the tour — makes "10% of YOUR money → the WHOLE book" concrete.
function SleeveDiagram() {
  return (
    <div className="w-full max-w-[260px]">
      <div className="text-[0.6rem] tracking-[0.14em] uppercase text-ink-light mb-1.5 text-center">Your portfolio</div>
      <div className="flex h-9 rounded overflow-hidden border border-rule">
        <div className="bg-claret" style={{ width: '10%' }} />
        <div className="bg-paper-card flex-1" />
      </div>
      <div className="flex justify-between mt-1.5 text-[0.6rem]">
        <span className="text-claret font-medium">10% sleeve → the whole book</span>
        <span className="text-ink-light">the rest, untouched</span>
      </div>
    </div>
  );
}

// Mirror onboarding — concept beats (centered cards) that teach the model FIRST, then a spotlight
// on the real Connect controls + the real eclipse. Prototype: mounted only on /app/next.
const MIRROR_TOUR = [
  { kind: 'modal', art: 'intro', eyebrow: 'The Mirror', title: 'One picture, honestly drawn',
    body: 'Your portfolio, side by side with our model book — as facts, not instructions. What you do about the gap is always your call.' },
  { kind: 'modal', art: 'eclipse', eyebrow: 'How to read it', title: 'Book = sun. You = moon.',
    body: 'The more your holdings overlap the book, the more the moon covers the sun. Full overlap is a total eclipse — the one number that answers "am I actually running the strategy?"' },
  { kind: 'modal', art: 'sleeve', eyebrow: 'How to run it', title: 'A sleeve — not thirty bets',
    body: 'Commit a slice of your money — say 10% — and that slice holds the whole book at our weights. A few hundred dollars a name, not thirty big decisions. Half the book isn’t half the strategy; a total eclipse is when the track record is truly yours.' },
  // Spotlights run TOP-TO-BOTTOM to match the page layout — eclipse hero (top) first, then the
  // Connect controls (below) — so the tour scrolls in one direction instead of bouncing down-then-up.
  { kind: 'spotlight', target: '[data-tour="mirror-eclipse"]', eyebrow: 'Your starting point', title: 'Further along than you think',
    body: 'This is your eclipse today. Most people start as a crescent — the gap is simply the distance to running the full book, at your pace and your size. Here’s how to draw it in.',
    // First run has no holdings yet, so the eclipse is a full sun — meet that honestly instead of
    // promising a crescent that isn't there. Picked when the live alignment is still 0%.
    emptyVariant: { eyebrow: 'Your starting point', title: 'A blank sky, waiting',
      body: 'You haven’t added anything yet, so the sun’s in full view — that’s exactly where everyone begins. Add even one name and the moon slides in; a total eclipse is when you hold the whole book, at your pace and your size. Here’s where to start.' } },
  { kind: 'spotlight', target: '[data-tour="mirror-connect"]', eyebrow: 'Your move', title: 'Show it what you hold',
    body: 'Connect your brokerage (read-only) or paste a few tickers — that’s all the mirror needs. It simply shows how your holdings line up with the book; what you do with that is always yours to decide.' },
];

function MirrorTour({ open, onClose, pct = 0 }) {
  const [step, setStep] = useState(0);
  const [rect, setRect] = useState(null);
  const [demo, setDemo] = useState(0);
  let cur = MIRROR_TOUR[step] || MIRROR_TOUR[0];
  // Empty first run (no overlap yet) → swap the eclipse step to copy that meets a full sun honestly.
  if (cur.emptyVariant && !(pct > 0)) cur = { ...cur, ...cur.emptyVariant };
  const isSpot = cur.kind === 'spotlight';
  const last = step === MIRROR_TOUR.length - 1;
  const advance = () => { if (last) onClose(); else setStep(s => s + 1); };
  const back = () => setStep(s => Math.max(0, s - 1));

  useEffect(() => { if (open) { setStep(0); setRect(null); } }, [open]);
  // Delight beat: sweep the demo eclipse 0 → 66% when the "how to read it" card shows.
  useEffect(() => { if (open && cur.art === 'eclipse') { setDemo(0); const t = setTimeout(() => setDemo(66), 140); return () => clearTimeout(t); } }, [open, step, cur.art]);
  // Scroll the spotlight target into view, then reveal the cutout ONLY once the smooth-scroll
  // has settled — otherwise the highlight snaps from the previous target's position through a
  // moving frame (the "janky" jump). rect stays null while scrolling (screen just dims), then
  // lands once the target stops moving; afterwards we track live scroll/resize.
  useEffect(() => {
    if (!open || !isSpot) { setRect(null); return; }
    const el = document.querySelector(cur.target);
    if (!el) { setRect(null); return; }
    setRect(null);                                   // drop the stale rect so nothing renders mid-scroll
    el.scrollIntoView({ block: 'center', behavior: 'smooth' });
    const measure = () => { const r = el.getBoundingClientRect(); return { top: r.top, left: r.left, width: r.width, height: r.height }; };
    let raf, settled = false, prevTop = null, still = 0;
    const t0 = performance.now();
    const settle = (now) => {
      const r = measure();
      if (prevTop !== null && Math.abs(r.top - prevTop) < 0.5) still++; else still = 0;
      prevTop = r.top;
      if (still >= 2 || now - t0 > 900) { setRect(r); settled = true; return; }   // stable or bailout
      raf = requestAnimationFrame(settle);
    };
    raf = requestAnimationFrame(settle);
    const onMove = () => { if (settled) setRect(measure()); };
    window.addEventListener('resize', onMove);
    window.addEventListener('scroll', onMove, true);
    return () => { cancelAnimationFrame(raf); window.removeEventListener('resize', onMove); window.removeEventListener('scroll', onMove, true); };
  }, [open, step, isSpot, cur.target]);
  useEffect(() => {
    if (!open) return;
    const h = (e) => { if (e.key === 'Escape') onClose(); else if (e.key === 'ArrowRight') advance(); else if (e.key === 'ArrowLeft') back(); };
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  }, [open, step, last]);   // re-register with fresh closures

  if (!open) return null;
  const showSpot = isSpot && rect;
  const vw = typeof window !== 'undefined' ? window.innerWidth : 1200;
  const vh = typeof window !== 'undefined' ? window.innerHeight : 800;
  const cardW = Math.min(vw * 0.92, 420);
  const cx = rect ? rect.left + rect.width / 2 : vw / 2;
  const cardLeft = Math.max(12, Math.min(cx - cardW / 2, vw - cardW - 12));
  const above = rect && rect.top > vh * 0.58;
  const art = cur.art === 'eclipse'
    ? <div style={{ width: 150 }}><AlignmentEclipse pct={demo} max={150} /></div>
    : cur.art === 'sleeve' ? <SleeveDiagram />
    : <EclipseGlyph pct={45} size={76} />;

  const card = (
    <div className="relative bg-paper border border-rule rounded-lg shadow-2xl overflow-hidden" style={{ width: cardW }} onClick={(e) => e.stopPropagation()}>
      <button onClick={onClose} title="Skip" aria-label="Skip tour" className="absolute top-2.5 right-2.5 text-ink-light hover:text-ink transition-colors z-10"><X size={18} /></button>
      {cur.kind === 'modal' && (
        <div className="h-40 bg-paper-deep flex items-center justify-center px-6 border-b border-rule">{art}</div>
      )}
      <div className="p-5">
        <div className="font-mono text-[0.6rem] tracking-[0.2em] uppercase text-claret mb-1.5">{cur.eyebrow}</div>
        <h3 className="font-display text-[1.35rem] font-medium text-ink tracking-tight mb-2 text-balance" style={{ fontVariationSettings: '"opsz" 48' }}>{cur.title}</h3>
        <p className="text-[0.9rem] leading-relaxed text-ink-mute">{cur.body}</p>
        <div className="flex items-center justify-between mt-5">
          <div className="flex gap-1.5 items-center">
            {MIRROR_TOUR.map((_, i) => (<span key={i} className={`h-1.5 rounded-full transition-all ${i === step ? 'w-5 bg-claret' : 'w-1.5 bg-rule'}`} />))}
          </div>
          <div className="flex items-center gap-1">
            {step > 0 && <button onClick={back} className="text-[0.8rem] text-ink-light hover:text-ink px-3 py-1.5">Back</button>}
            <button onClick={advance} className="text-[0.82rem] font-medium bg-ink text-paper px-4 py-1.5 rounded-lg hover:bg-claret transition-colors">{last ? 'Done' : 'Next'}</button>
          </div>
        </div>
      </div>
    </div>
  );

  // Spotlight step but the scroll hasn't settled yet → just dim; the cutout + card land together.
  if (isSpot && !rect) return <div className="fixed inset-0 bg-ink/70" style={{ zIndex: 60 }} />;
  if (showSpot) {
    return (
      <div className="fixed inset-0" style={{ zIndex: 60 }}>
        <div className="pointer-events-none" style={{ position: 'fixed', top: rect.top - 8, left: rect.left - 8, width: rect.width + 16, height: rect.height + 16, borderRadius: 14, boxShadow: '0 0 0 9999px rgba(20,18,16,0.74)', border: '2px solid #7A2430', transition: 'top .3s ease, left .3s ease, width .3s ease, height .3s ease' }} />
        <div style={{ position: 'fixed', left: cardLeft, top: above ? undefined : rect.top + rect.height + 14, bottom: above ? (vh - rect.top + 14) : undefined, transition: 'top .3s ease, bottom .3s ease, left .3s ease' }}>{card}</div>
      </div>
    );
  }
  return (
    <div className="fixed inset-0 bg-ink/70 flex items-center justify-center p-4" style={{ zIndex: 60 }} onClick={onClose}>{card}</div>
  );
}

// /app/next — private, admin-gated design studio for the reoriented Mirror COCKPIT.
// Thin wrapper: fetches its own dashboard (with preview-tier forwarding) and renders MirrorView.
function MirrorCockpit() {
  const { isAdmin } = useAuth();
  const [dash, setDash] = useState(null);
  const holdingsApi = useMirrorHoldings();
  useEffect(() => { (async () => {
    // Forward the tier/state preview so admin preview works here too. Accept every spelling
    // (preview_tier / preview-tier / product_tier / product-tier) → forward the canonical one.
    const qp = new URLSearchParams(window.location.search);
    const p = new URLSearchParams();
    const pt = qp.get('preview_tier') || qp.get('preview-tier') || qp.get('product_tier') || qp.get('product-tier');
    if (pt) p.set('preview_tier', pt);
    const ps = qp.get('preview_state') || qp.get('preview-state');
    if (ps) p.set('preview_state', ps);
    const q = p.toString();
    try { setDash(await api.get(`/api/signals/dashboard${q ? `?${q}` : ''}`)); } catch { setDash({}); }
  })(); }, []);
  const [tourOpen, setTourOpen] = useState(() => {
    const qp = new URLSearchParams(window.location.search);
    if (qp.has('tour')) return true;                              // force for iteration
    return localStorage.getItem('rigacap_mirror_tour_seen') !== 'true';   // auto on first visit
  });
  const closeTour = () => { setTourOpen(false); try { localStorage.setItem('rigacap_mirror_tour_seen', 'true'); } catch { /* ignore */ } };
  const [mirrorPct, setMirrorPct] = useState(0);   // live eclipse alignment → tour's final-step copy
  if (isAdmin === false) return <Navigate to="/app" replace />;
  return (
    <div style={{ minHeight: '100vh', background: '#F5F1E8' }}>
      <MirrorView book={dash?.tier_book} preserverBook={dash?.preserver_book} tier={dash?.tier}
        regimeName={dash?.regime_forecast?.current_regime_name} holdingsApi={holdingsApi}
        onState={(s) => setMirrorPct(s?.pct || 0)} />
      <MirrorTour open={tourOpen} onClose={closeTour} pct={mirrorPct} />
      <button onClick={() => setTourOpen(true)}
        className="fixed bottom-4 right-4 z-30 text-[0.75rem] font-medium px-3.5 py-2 rounded-full bg-ink text-paper shadow-lg hover:bg-claret transition-colors">
        Take the tour
      </button>
    </div>
  );
}

const WhereStocksSit = ({ onOpenChart }) => {
  const [input, setInput] = useState('NVDA, SMCI, PLTR, MSTR, IREN, AAPL');
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [ran, setRan] = useState(false);

  const run = async (e) => {
    e?.preventDefault();
    const syms = [...new Set((input.toUpperCase().match(/[A-Z][A-Z.\-]{0,6}/g) || []))].slice(0, 30);
    if (!syms.length) return;
    setLoading(true); setRan(true);
    const out = [];
    for (const s of syms) {
      try {
        const r = await api.get(`/api/stock/${s}/previous-holds?t=${Date.now()}`);
        const holds = r?.holds || [];
        const maxH = holds.filter(h => h.tier === 'maximizer');
        const presH = holds.filter(h => h.tier === 'preserver');
        const bestOf = (arr) => { const v = arr.map(h => h.pnl_pct).filter(x => x != null); return v.length ? Math.max(...v) : null; };
        out.push({
          symbol: s, count: holds.length,
          preserver: presH.length, presBest: bestOf(presH),
          maximizer: maxH.length, maxBest: bestOf(maxH),
        });
      } catch {
        out.push({ symbol: s, count: 0, error: true });
      }
    }
    setRows(out); setLoading(false);
  };

  const pct = (v) => v == null ? '—' : `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`;

  return (
    <div className="mb-6 border-2 border-claret/40 bg-paper-card rounded-lg overflow-hidden">
      <div className="flex items-baseline justify-between px-5 py-3 border-b border-rule bg-claret/5">
        <h2 className="font-display text-[1.1rem] font-medium text-ink tracking-tight" style={{ fontVariationSettings: '"opsz" 48' }}>
          Where Your Stocks Sit
          <em className="font-display italic text-ink-mute text-[0.8rem] ml-2" style={{ fontVariationSettings: '"opsz" 24' }}>preview · admin only</em>
        </h2>
        <span className="text-[0.62rem] font-medium tracking-[0.18em] uppercase text-claret px-2 py-1 border border-claret/40 rounded">Direction demo</span>
      </div>
      <div className="p-5">
        <p className="text-sm text-ink-mute mb-3">Paste a portfolio — see where our system has traded each name (live + backtested), and what the Maximizer breakout sleeve caught. Click any row for the full chart with entry/exit history.</p>
        <form onSubmit={run} className="flex gap-2 mb-4">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="AAPL, NVDA, SMCI…"
            className="flex-1 px-3 py-2 text-sm bg-paper-deep border border-rule rounded-lg text-ink placeholder:text-ink-light focus:outline-none focus:border-claret"
          />
          <button type="submit" disabled={loading} className="px-4 py-2 text-sm font-medium bg-ink text-white rounded-lg hover:opacity-90 disabled:opacity-50">
            {loading ? 'Checking…' : 'Check'}
          </button>
        </form>
        {ran && !loading && (
          rows.length ? (
            <table className="w-full border-collapse" style={{ fontFeatureSettings: '"tnum"' }}>
              <thead>
                <tr>{['Symbol', 'Our holds', 'Preserver', 'Maximizer', ''].map(h => (
                  <th key={h} className="py-2 px-3 text-left font-body text-[0.6rem] font-medium tracking-[0.2em] uppercase text-ink-mute border-b border-ink">{h}</th>
                ))}</tr>
              </thead>
              <tbody>
                {rows.map(r => (
                  <tr key={r.symbol} onClick={() => onOpenChart({ type: 'signal', data: { symbol: r.symbol }, symbol: r.symbol })} className="hover:bg-paper border-b border-rule cursor-pointer">
                    <td className="py-2.5 px-3 font-display text-[1rem] font-medium" style={{ fontVariationSettings: '"opsz" 48' }}>{r.symbol}</td>
                    <td className="py-2.5 px-3 font-mono text-[0.85rem]">{r.error ? '—' : r.count}</td>
                    {/* both tier cells = count · best% (best across that tier); M badge = upsell marker */}
                    <td className="py-2.5 px-3 font-mono text-[0.85rem]">
                      {r.preserver ? (
                        <span><span className="text-ink-mute">{r.preserver} · </span><span className={r.presBest >= 0 ? 'text-positive font-medium' : 'text-negative font-medium'}>{pct(r.presBest)}</span></span>
                      ) : <span className="text-ink-light">—</span>}
                    </td>
                    <td className="py-2.5 px-3 font-mono text-[0.85rem]">
                      {r.maximizer ? (
                        <span className="inline-flex items-center gap-1.5">
                          <span className="text-[0.6rem] font-bold text-white bg-claret rounded px-1.5 py-0.5">M</span>
                          <span className="text-ink-mute">{r.maximizer} · </span><span className={r.maxBest >= 0 ? 'text-positive font-medium' : 'text-negative font-medium'}>{pct(r.maxBest)}</span>
                        </span>
                      ) : <span className="text-ink-light">—</span>}
                    </td>
                    <td className="py-2.5 px-3 text-right text-ink-light text-sm">View →</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <p className="text-sm text-ink-light italic">No symbols recognized.</p>
        )}
        <p className="text-[0.66rem] text-ink-light italic mt-4">Information only — our system's historical signals on these names (dashed = backtested), not personalized advice.</p>
      </div>
    </div>
  );
};

// Stock Chart Modal
const StockChartModal = ({ symbol, type, data, onClose, onAction, liveQuote, viewMode = 'advanced', timeTravelDate = null, lastPositionDollars = null }) => {
  const [timeRange, setTimeRange] = useState('1Y');
  const [priceData, setPriceData] = useState([]);
  const [stockInfo, setStockInfo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showBuyModal, setShowBuyModal] = useState(false);
  const [showSellModal, setShowSellModal] = useState(false);
  const [currentLiveQuote, setCurrentLiveQuote] = useState(liveQuote);
  const [prevHolds, setPrevHolds] = useState([]);
  const [showPrevHolds, setShowPrevHolds] = useState(true);

  // Previous holds (prior entry→exit pairs incl walk-forward backtest) for the chart overlay
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const resp = await api.get(`/api/stock/${symbol}/previous-holds?t=${Date.now()}`);
        if (!cancelled) setPrevHolds(resp?.holds || []);
      } catch (err) {
        if (!cancelled) setPrevHolds([]);
      }
    })();
    return () => { cancelled = true; };
  }, [symbol]);

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
        let days = { '1M': 30, '3M': 90, '6M': 180, '1Y': 252, '2Y': 504, '5Y': 1260 }[timeRange] || 252;

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

  // Breakout hold-to-exit (Maximizer): the exit is a FUTURE time-stop (day 29), not a price
  // level. Extend the series with future business-day placeholders (null close) up to the exit
  // date so a vertical exit line can render on the categorical date axis.
  const exitDateStr = data?.exit_date_approx ? String(data.exit_date_approx).split('T')[0] : null;
  const isHoldExit = data?.exit_rule === 'hold' && !!exitDateStr;
  const chartDataForRender = (() => {
    if (!isHoldExit || chartDataWithLive.length === 0) return chartDataWithLive;
    const out = [...chartDataWithLive];
    let d = new Date(out[out.length - 1].date + 'T00:00:00');
    const end = new Date(exitDateStr + 'T00:00:00');
    let guard = 0;
    while (d < end && guard < 45) {
      d.setDate(d.getDate() + 1);
      const dow = d.getDay();
      if (dow === 0 || dow === 6) continue; // business days only
      out.push({ date: d.toISOString().split('T')[0], close: null, _future: true });
      guard++;
    }
    return out;
  })();

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-paper-card rounded shadow-2xl max-w-4xl w-full max-h-[90vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-rule relative flex-shrink-0">
          {/* Close button - top right */}
          <button onClick={onClose} className="absolute top-4 right-4 p-2 hover:bg-paper-deep rounded-lg z-10">
            <X size={24} className="text-ink-light" />
          </button>

          <div className="pr-12">
            <div className="flex items-center gap-3 flex-wrap">
              <h2 className="text-2xl font-bold text-ink">{symbol}</h2>
              {data?.is_strong && (
                <span className="px-2 py-1 bg-positive/10 text-positive text-xs font-semibold rounded-full flex items-center gap-1">
                  <Zap size={12} /> STRONG SIGNAL
                </span>
              )}
              {type === 'position' && (
                <span className="px-2 py-1 bg-claret/10 text-claret text-xs font-semibold rounded-full">
                  OPEN POSITION
                </span>
              )}
              {type === 'missed' && (
                <span className="px-2 py-1 bg-claret text-paper text-xs font-medium tracking-wide flex items-center gap-1">
                  MISSED +{data?.would_be_return?.toFixed(0) || '?'}%
                </span>
              )}
              {data?.signal_strength > 0 && (
                <span className="px-2 py-1 text-xs font-mono tracking-wide text-ink-mute border border-rule-dark">
                  Strength: {data.signal_strength.toFixed(0)}
                </span>
              )}
            </div>
            {/* Company Name & Sector */}
            {stockInfo?.name && (
              <div className="mt-1">
                <p className="text-ink-mute text-sm">{stockInfo.name}</p>
                {stockInfo?.sector && (
                  <span className="inline-block mt-1 px-2 py-0.5 bg-claret/10 text-claret text-xs font-medium rounded-full">
                    {stockInfo.sector}{stockInfo?.industry ? ` - ${stockInfo.industry}` : ''}
                  </span>
                )}
              </div>
            )}
            <div className="flex items-center gap-4 mt-2">
              <span className="text-2xl font-semibold">${currentPrice.toFixed(2)}</span>
              {currentLiveQuote && (
                <span className={`flex items-center text-sm font-medium ${currentLiveQuote.change_pct >= 0 ? 'text-positive' : 'text-negative'}`}>
                  {currentLiveQuote.change_pct >= 0 ? <ArrowUpRight size={16} /> : <ArrowDownRight size={16} />}
                  {currentLiveQuote.change_pct >= 0 ? '+' : ''}{currentLiveQuote.change_pct?.toFixed(2)}% today
                </span>
              )}
              <span className={`flex items-center text-sm font-medium ${isPositive ? 'text-positive' : 'text-negative'}`}>
                {isPositive ? <ArrowUpRight size={16} /> : <ArrowDownRight size={16} />}
                {isPositive ? '+' : ''}{changePct}% ({timeRange})
              </span>
              {currentLiveQuote && (
                <span className="flex items-center gap-1 text-xs text-claret">
                  <Activity size={12} className="animate-pulse" /> Live
                </span>
              )}
              {stockInfo?.market_cap && (
                <span className="text-sm text-ink-mute">
                  Market Cap: {formatMarketCap(stockInfo.market_cap)}
                </span>
              )}
            </div>
            {/* Company Description - scrollable */}
            {stockInfo?.description && (
              <div className="mt-2 max-h-20 overflow-y-auto">
                <p className="text-sm text-ink-mute">{stockInfo.description}</p>
              </div>
            )}
          </div>
        </div>

        {/* Scrollable content area */}
        <div className="flex-1 overflow-y-auto">
          {/* Time Range */}
          <div className="px-6 py-3 border-b border-rule flex gap-2 items-center">
          {type === 'missed' ? (
            <div className="flex items-center gap-2">
              <span className="px-3 py-1 text-[0.72rem] font-medium tracking-wide bg-claret text-paper">
                Transaction Window
              </span>
              <span className="text-sm text-ink-mute">
                {formatDate(data?.entry_date)} → {formatDate(data?.sell_date)} (±30 days)
              </span>
            </div>
          ) : (
            ['1M', '3M', '6M', '1Y', '2Y', '5Y'].map((range) => (
              <button
                key={range}
                onClick={() => setTimeRange(range)}
                className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  timeRange === range ? 'bg-ink text-white' : 'bg-paper-deep text-ink-mute hover:bg-rule'
                }`}
              >
                {range}
              </button>
            ))
          )}
          {prevHolds.length > 0 && (
            <button
              onClick={() => setShowPrevHolds(v => !v)}
              className={`ml-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                showPrevHolds ? 'bg-claret text-white' : 'bg-paper-deep text-ink-mute hover:bg-rule'
              }`}
              title="Show/hide our previous entry→exit holds (dashed = backtest)"
            >
              Prior holds ({prevHolds.length})
            </button>
          )}
          {prevHolds.length > 0 && showPrevHolds && prevHolds.some(h => h.is_walkforward) && (
            <span className="text-[0.68rem] text-ink-light italic ml-1 self-center">solid = live · dashed = backtested</span>
          )}
        </div>

        {/* Chart */}
        <div className="p-6">
          {loading ? (
            <LoadingSpinner message="Loading chart data..." />
          ) : error ? (
            <ErrorDisplay message={error} />
          ) : priceData.length === 0 ? (
            <div className="text-center py-12 text-ink-mute">
              <BarChart3 className="w-12 h-12 mx-auto text-ink-light mb-3" />
              <p>No price data available</p>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={320}>
              <ComposedChart data={chartDataForRender}>
                <defs>
                  <linearGradient id="priceGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#141210" stopOpacity={0.08}/>
                    <stop offset="100%" stopColor="#141210" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#DDD5C7" vertical={false} />
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 11, fontFamily: 'IBM Plex Mono', fill: '#8A8279' }}
                  stroke="#C9BFAC"
                  tickFormatter={(val) => formatChartDate(val)}
                  interval={Math.floor(priceData.length / 6)}
                />
                <YAxis
                  yAxisId="price"
                  tick={{ fontSize: 11, fontFamily: 'IBM Plex Mono', fill: '#8A8279' }}
                  stroke="#C9BFAC"
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
                                       isSellDay ? 'border-amber-400 border-2' : 'border-rule';
                    if (viewMode === 'simple') {
                      return (
                        <div className={`bg-paper-card p-3 rounded-lg shadow-lg border ${borderClass} text-sm`}>
                          <p className="font-medium text-ink mb-1">{formatDate(label)}</p>
                          <p className="text-claret">Price: ${d?.close?.toFixed(2)}</p>
                          {isEntryDay && <p className="text-positive font-medium">Entry Point</p>}
                          {isSellDay && <p className="text-claret font-medium">Exit Point</p>}
                          {d?.isLive && <p className="text-claret font-medium">Live Price</p>}
                        </div>
                      );
                    }
                    return (
                      <div className={`bg-paper-card p-3 rounded-lg shadow-lg border ${borderClass} text-sm`}>
                        <p className="font-mono font-medium text-ink mb-1.5 text-[0.82rem]">
                          {formatDate(label)}
                          {isEntryDay && <span className="ml-2 text-[#2D5F3F] font-medium">ENTRY</span>}
                          {isSellDay && <span className="ml-2 text-[#B8923D] font-medium">EXIT</span>}
                        </p>
                        <p className="font-mono" style={{ color: '#2A2520' }}>Price: ${d?.close?.toFixed(2)}</p>
                        {isEntryDay && data?.entry_price && (
                          <p className="font-mono" style={{ color: '#2D5F3F' }}>Entry: ${data.entry_price.toFixed(2)}</p>
                        )}
                        {isSellDay && data?.sell_price && (
                          <p className="font-mono" style={{ color: '#B8923D' }}>Exit: ${data.sell_price.toFixed(2)}</p>
                        )}
                        {d?.dwap && (
                          <>
                            <p className="font-mono" style={{ color: '#B8923D' }}>Average price: ${d.dwap.toFixed(2)}</p>
                            <p className="font-mono" style={{ color: '#2B6B8C' }}>Entry trigger: ${(d.dwap * 1.05).toFixed(2)}</p>
                          </>
                        )}
                        {d?.ma_50 && <p className="font-mono" style={{ color: '#7A2430' }}>MA50: ${d.ma_50.toFixed(2)}</p>}
                        {d?.volume > 0 && <p className="font-mono text-ink-light">Vol: {(d.volume / 1000000).toFixed(1)}M</p>}
                        {d?.isLive && <p className="font-mono text-claret font-medium">Live</p>}
                      </div>
                    );
                  }}
                />
                {viewMode !== 'simple' && <Bar yAxisId="volume" dataKey="volume" fill="#A99E87" opacity={0.35} />}

                {viewMode !== 'simple' && chartDataWithLive.some(d => d.dwap) && (
                  <>
                    <Line yAxisId="price" type="monotone" dataKey="dwap" stroke="#B8923D" strokeWidth={1.5} dot={false} strokeDasharray="6 3" name="Average price" />
                    <Line
                      yAxisId="price"
                      type="monotone"
                      dataKey={(d) => d.dwap ? d.dwap * 1.05 : null}
                      stroke="#2B6B8C"
                      strokeWidth={1.5}
                      dot={false}
                      name="Entry trigger"
                      connectNulls={false}
                    />
                  </>
                )}
                {viewMode !== 'simple' && chartDataWithLive.some(d => d.ma_50) && (
                  <Line yAxisId="price" type="monotone" dataKey="ma_50" stroke="#7A2430" strokeWidth={1.5} dot={false} strokeDasharray="5 5" name="MA50" />
                )}
                <Area yAxisId="price" type="monotone" dataKey="close" stroke="#2A2520" strokeWidth={2} fill="url(#priceGradient)" name="Price" />

                {/* Previous holds overlay — shaded entry→exit bands + edge dots (entry filled /
                    exit ring), gain/loss labels. Rendered AFTER the volume bars + price line so the
                    dots aren't painted over. WF (backtest) holds are lighter + dashed. Clamped to
                    the visible window; labels vertical-stagger to avoid nested-band collisions. */}
                {showPrevHolds && prevHolds.length > 0 && chartDataWithLive.length > 0 && (() => {
                  const dates = chartDataWithLive.map(d => d.date);
                  const first = dates[0], last = dates[dates.length - 1];
                  const snapFwd = (t) => dates.find(d => d >= t) || null;
                  const snapBack = (t) => { let r = null; for (const d of dates) { if (d <= t) r = d; else break; } return r; };
                  return prevHolds.flatMap((h, i) => {
                    const e = h.entry_date ? h.entry_date.split('T')[0] : null;
                    const x = h.exit_date ? h.exit_date.split('T')[0] : null;
                    if (!e || !x) return [];
                    const x1 = e < first ? first : snapFwd(e);
                    const x2 = x > last ? last : snapBack(x);
                    if (!x1 || !x2 || x1 > x2) return [];   // hold outside the visible window
                    const g = h.pnl_pct;
                    const col = g == null ? '#8A8172' : (g >= 0 ? '#2D5F3F' : '#8F2D3D');
                    const wf = h.is_walkforward;
                    const op = wf ? 0.7 : 0.95;
                    const lbl = g == null ? '' : `${g >= 0 ? '+' : ''}${g.toFixed(1)}%`;
                    // Vertical-stagger the gain/loss labels (offset by index) at the band bottom so
                    // heavily OVERLAPPING/nested bands don't mash labels together.
                    const bandLabel = (lp) => {
                      const vb = lp?.viewBox;
                      if (!vb || !lbl) return null;
                      const tx = vb.x + vb.width - 4;
                      const ty = vb.y + vb.height - 6 - (i * 13);
                      return <text x={tx} y={ty} textAnchor="end" fontSize={9} fontFamily="IBM Plex Mono" fill={col}>{lbl}</text>;
                    };
                    return [
                      <ReferenceArea
                        key={`ph-a-${i}`}
                        yAxisId="price"
                        x1={x1}
                        x2={x2}
                        fill={col}
                        fillOpacity={wf ? 0.05 : 0.09}
                        stroke={col}
                        strokeOpacity={wf ? 0.3 : 0.45}
                        strokeDasharray={wf ? '2 3' : undefined}
                        label={bandLabel}
                      />,
                      h.entry_price ? <ReferenceDot key={`ph-in-${i}`} yAxisId="price" x={x1} y={h.entry_price} r={4} fill={col} fillOpacity={op} stroke="#F5F1E8" strokeWidth={1} ifOverflow="extendDomain" /> : null,
                      h.exit_price ? <ReferenceDot key={`ph-out-${i}`} yAxisId="price" x={x2} y={h.exit_price} r={4} fill="none" stroke={col} strokeWidth={1.5} strokeOpacity={op} ifOverflow="extendDomain" /> : null,
                    ].filter(Boolean);
                  });
                })()}

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
                  // "Close" = within 4% of the line's price (label height zone).
                  const closenessThreshold = 0.04;

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

                  // Check if the price line crosses through the label zone
                  // Checks last close AND scans recent chart data for crossings
                  const priceCrosses = (myY, myId) => {
                    if (!myY) return false;
                    if (myId === '_price') return false;
                    // Check last N data points for any crossing near the reference line
                    const recentData = chartDataWithLive.slice(-Math.min(chartDataWithLive.length, 20));
                    return recentData.some(d => {
                      if (!d?.close) return false;
                      const diff = Math.abs(d.close - myY) / myY;
                      return diff < closenessThreshold;
                    });
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

                  // Sell (missed): scan chart for where the label has most clearance
                  const sellY = data?.sell_price;
                  const sellPos = (() => {
                    if (!sellY) return 'insideTopLeft';
                    // Check if price ends above or below the exit line
                    const endPrice = chartDataWithLive.length > 0 ? chartDataWithLive[chartDataWithLive.length - 1]?.close : null;
                    if (endPrice && endPrice > sellY * 1.05) return 'insideBottomLeft';
                    if (endPrice && endPrice < sellY * 0.95) return 'insideTopLeft';
                    // Price near exit level — put label on left where early data is likely far away
                    const startPrice = chartDataWithLive.length > 5 ? chartDataWithLive[5]?.close : null;
                    if (startPrice && startPrice < sellY) return 'insideTopLeft';
                    return 'insideBottomLeft';
                  })();

                  return (
                    <>
                      {/* Entry/Buy price */}
                      {(type === 'position' || type === 'missed') && entryPrice && (
                        <ReferenceLine
                          yAxisId="price"
                          y={entryPrice}
                          stroke="#7A2430"
                          strokeWidth={1.5}
                          strokeDasharray="5 3"
                          label={{
                            value: `Entry $${entryPrice.toFixed(2)}`,
                            fill: '#7A2430',
                            fontWeight: 500,
                            fontSize: 11,
                            fontFamily: 'IBM Plex Mono',
                            position: buyPos
                          }}
                        />
                      )}

                      {/* Exit/Sell price (missed opportunities) */}
                      {type === 'missed' && sellY && (
                        <ReferenceLine
                          yAxisId="price"
                          y={sellY}
                          stroke="#141210"
                          strokeWidth={1.5}
                          strokeDasharray="5 3"
                          label={{
                            value: `Exit $${sellY.toFixed(2)}${data?.exit_reason && data.exit_reason !== 'still_open' ? ` (${{'trailing_stop':'trailing stop','rebalance_exit':'rebalance','simulation_end':'rebalance','profit_target':'target','stop_loss':'stop loss','market_regime':'market regime'}[data.exit_reason] || data.exit_reason.replace(/_/g, ' ')})` : ''}`,
                            fill: '#141210',
                            fontWeight: 500,
                            fontSize: 11,
                            fontFamily: 'IBM Plex Mono',
                            fontStyle: 'italic',
                            position: sellPos
                          }}
                        />
                      )}

                      {/* Trailing stop */}
                      {stopY && (
                        <ReferenceLine
                          yAxisId="price"
                          y={stopY}
                          stroke="#8F2D3D"
                          strokeWidth={1.5}
                          strokeDasharray="4 4"
                          label={{
                            value: `Stop $${stopY.toFixed(2)}`,
                            fill: '#8F2D3D',
                            fontSize: 10,
                            fontFamily: 'IBM Plex Mono',
                            position: stopPos
                          }}
                        />
                      )}

                      {/* High water mark */}
                      {highY && entryPrice && highY > entryPrice * 1.01 && (
                        <ReferenceLine
                          yAxisId="price"
                          y={highY}
                          stroke="#2B6B8C"
                          strokeWidth={1}
                          strokeDasharray="3 3"
                          label={{
                            value: `High $${highY.toFixed(2)}`,
                            fill: '#2B6B8C',
                            fontSize: 10,
                            fontFamily: 'IBM Plex Mono',
                            position: highPos
                          }}
                        />
                      )}

                      {/* (removed: +20% profit-target line — vestigial from the old Ensemble/Preserver
                          strategy; the live strategy exits on the trailing stop, not a fixed target) */}
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

                {/* Breakout time-stop exit — vertical line at the projected day-29 exit date */}
                {isHoldExit && (
                  <ReferenceLine
                    yAxisId="price"
                    x={exitDateStr}
                    stroke="#7A2430"
                    strokeDasharray="4 3"
                    label={{
                      value: `Exit · day ${data?.days_held ?? '?'}/${data?.hold_days ?? 29}`,
                      position: 'insideTopRight',
                      fontSize: 10,
                      fontFamily: 'IBM Plex Mono',
                      fill: '#7A2430',
                    }}
                  />
                )}

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

                {/* Date price first crossed the entry trigger (5% above the average price) */}
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
                      label={{ value: 'Crossed trigger', fill: '#C9A54E', fontSize: 10, position: 'top' }}
                    />
                  );
                })()}

                {/* Date the name qualified as a buy signal (momentum + trigger both met) */}
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
                      label={{ value: 'Buy signal', fill: '#22C55E', fontSize: 10, position: 'top' }}
                    />
                  );
                })()}

                {/* Live price marker — claret dot with paper halo */}
                {livePrice && chartDataWithLive.length > 0 && (
                  <ReferenceDot
                    yAxisId="price"
                    x={chartDataWithLive[chartDataWithLive.length - 1]?.date}
                    y={livePrice}
                    r={5}
                    fill="#7A2430"
                    stroke="#F5F1E8"
                    strokeWidth={2}
                  />
                )}
              </ComposedChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Details */}
        <div className="px-6 py-4 bg-paper-card border-t border-rule">
          {/* Recommendation banner */}
          {data?.recommendation && (
            <div className="mb-4 p-3 bg-paper-deep border border-blue-200 rounded-lg text-sm text-ink">
              <strong>Recommendation:</strong> {data.recommendation}
            </div>
          )}

          <div className={`grid ${viewMode === 'simple' ? 'grid-cols-2' : 'grid-cols-2 sm:grid-cols-4'} gap-4`}>
            {type === 'signal' ? (
              viewMode === 'simple' ? (
                <>
                  <div className="text-center">
                    <p className="text-sm text-ink-mute">Price</p>
                    <p className="text-lg font-semibold">${data?.price?.toFixed(2)}</p>
                  </div>
                  <div className="text-center">
                    <p className="text-sm text-ink-mute">Potential</p>
                    <p className="text-lg font-semibold text-positive">Strong</p>
                  </div>
                </>
              ) : (
                <>
                  <div className="text-center">
                    <p className="font-body text-[0.72rem] font-medium tracking-[0.15em] uppercase text-ink-mute mb-1">Breakout</p>
                    <p className="font-mono text-lg text-ink">+{Number(data?.pct_above_dwap ?? 0).toFixed(1)}%</p>
                  </div>
                  <div className="text-center">
                    <p className="font-body text-[0.72rem] font-medium tracking-[0.15em] uppercase text-ink-mute mb-1">Mom Rank</p>
                    <p className="font-mono text-lg text-ink">#{data?.momentum_rank || '-'}</p>
                  </div>
                  {/* Live trailing stop (t30v=30%), not the old hardcoded 12%. */}
                  <div className="text-center">
                    <p className="font-body text-[0.72rem] font-medium tracking-[0.15em] uppercase text-ink-mute mb-1">Trailing Stop</p>
                    <p className="font-mono text-lg text-ink">{Math.round(data?.trailing_stop_pct ?? 30)}%</p>
                  </div>
                  {/* t30v has NO fixed profit target — show the stop price level
                      instead of a misleading "+20% target" (which would tell
                      subscribers to sell winners the strategy lets run). */}
                  <div className="text-center">
                    <p className="font-body text-[0.72rem] font-medium tracking-[0.15em] uppercase text-ink-mute mb-1">Stop Price</p>
                    <p className="font-mono text-lg text-ink">${data?.price ? (data.price * (1 - (data.trailing_stop_pct ?? 30) / 100)).toFixed(2) : '-'}</p>
                  </div>
                </>
              )
            ) : type === 'missed' ? (
              viewMode === 'simple' ? (
                <>
                  <div className="text-center">
                    <p className="text-sm text-ink-mute">Return</p>
                    <p className="text-lg font-semibold text-positive">
                      +{data?.would_be_return?.toFixed(1)}%
                    </p>
                  </div>
                  <div className="text-center">
                    <p className="text-sm text-ink-mute">Days Held</p>
                    <p className="text-lg font-semibold">{data?.days_held || '-'}</p>
                  </div>
                </>
              ) : (
                <>
                  <div className="text-center">
                    <p className="text-sm text-ink-mute">Buy Date</p>
                    <p className="text-lg font-semibold">{formatDate(data?.entry_date)}</p>
                    <p className="text-xs text-positive">${data?.entry_price?.toFixed(2)}</p>
                  </div>
                  <div className="text-center">
                    <p className="text-sm text-ink-mute">Sell Date</p>
                    <p className="text-lg font-semibold">{formatDate(data?.sell_date)}</p>
                    <p className="text-xs text-positive">${data?.sell_price?.toFixed(2)}</p>
                  </div>
                  <div className="text-center">
                    <p className="text-sm text-ink-mute">Return</p>
                    <p className="text-lg font-semibold text-positive">
                      +{data?.would_be_return?.toFixed(1)}%
                    </p>
                  </div>
                  <div className="text-center">
                    <p className="text-sm text-ink-mute">Days Held</p>
                    <p className="text-lg font-semibold">{data?.days_held || '-'}</p>
                  </div>
                </>
              )
            ) : (
              viewMode === 'simple' ? (
                <>
                  <div className="text-center">
                    <p className="text-sm text-ink-mute">Price</p>
                    <p className="text-lg font-semibold">${data?.current_price?.toFixed(2) || data?.entry_price?.toFixed(2)}</p>
                  </div>
                  <div className="text-center">
                    <p className="text-sm text-ink-mute">P&L</p>
                    <p className={`text-lg font-semibold ${data?.pnl_pct >= 0 ? 'text-positive' : 'text-negative'}`}>
                      {data?.pnl_pct >= 0 ? '+' : ''}{data?.pnl_pct?.toFixed(1)}%
                    </p>
                  </div>
                </>
              ) : (
                <>
                  <div className="text-center">
                    <p className="text-sm text-ink-mute">Entry Price</p>
                    <p className="text-lg font-semibold">${data?.entry_price?.toFixed(2)}</p>
                    <p className="text-xs text-ink-light">{formatDate(data?.entry_date)}</p>
                  </div>
                  <div className="text-center">
                    <p className="text-sm text-ink-mute">Current P&L</p>
                    {(() => {
                      // NaN-safe: tier-book holdings use `price`/`implied_shares` (no
                      // current_price/pnl_dollars). Derive from the modal's currentPrice +
                      // implied_shares/shares; render "—" rather than ever showing NaN.
                      const entry = data?.entry_price;
                      const sh = data?.implied_shares ?? data?.shares ?? 0;
                      const pctVal = (data?.pnl_pct != null && isFinite(data.pnl_pct))
                        ? data.pnl_pct
                        : ((isFinite(currentPrice) && entry) ? ((currentPrice - entry) / entry) * 100 : null);
                      const dollarVal = (data?.pnl_dollars != null && isFinite(data.pnl_dollars))
                        ? data.pnl_dollars
                        : ((isFinite(currentPrice) && isFinite(entry) && sh) ? (currentPrice - entry) * sh : null);
                      return (
                        <>
                          <p className={`text-lg font-semibold ${(pctVal ?? 0) >= 0 ? 'text-positive' : 'text-negative'}`}>
                            {pctVal == null ? '—' : `${pctVal >= 0 ? '+' : ''}${pctVal.toFixed(1)}%`}
                          </p>
                          {dollarVal != null && (
                            <p className={`text-xs ${dollarVal >= 0 ? 'text-positive' : 'text-negative'}`}>
                              {dollarVal >= 0 ? '+' : '-'}${Math.abs(Math.round(dollarVal)).toLocaleString()}
                            </p>
                          )}
                        </>
                      );
                    })()}
                  </div>
                  <div className="text-center">
                    <p className="text-sm text-ink-mute">Trailing Stop</p>
                    <p className="text-lg font-semibold text-negative">
                      {data?.trailing_stop_level ? `$${data.trailing_stop_level.toFixed(2)}` : '-'}
                    </p>
                    {data?.distance_to_stop_pct != null && (
                      <p className={`text-xs ${data.distance_to_stop_pct < 5 ? 'text-negative' : 'text-ink-light'}`}>
                        {data.distance_to_stop_pct.toFixed(1)}% away
                      </p>
                    )}
                  </div>
                  <div className="text-center">
                    <p className="text-sm text-ink-mute">High Water</p>
                    <p className="text-lg font-semibold text-claret">
                      {data?.high_water_mark ? `$${data.high_water_mark.toFixed(2)}` : '-'}
                    </p>
                  </div>
                </>
              )
            )}
          </div>

          {/* Technical Indicators - Signal only, Advanced mode only */}
          {viewMode !== 'simple' && type === 'signal' && (data?.ma_50 || stockInfo?.ma_50) && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-4 pt-4 border-t border-rule">
              <div className="text-center">
                <p className="text-sm text-ink-mute">50-Day MA</p>
                <p className="text-lg font-semibold">${(data?.ma_50 || stockInfo?.ma_50)?.toFixed(2)}</p>
              </div>
              <div className="text-center">
                <p className="text-sm text-ink-mute">200-Day MA</p>
                <p className="text-lg font-semibold">${(data?.ma_200 || stockInfo?.ma_200)?.toFixed(2)}</p>
              </div>
              <div className="text-center">
                <p className="text-sm text-ink-mute">52-Week High</p>
                <p className="text-lg font-semibold">${(data?.high_52w || stockInfo?.high_52w)?.toFixed(2)}</p>
              </div>
              <div className="text-center">
                <p className="text-sm text-ink-mute">Weighted Avg</p>
                <p className="text-lg font-semibold">${data?.dwap?.toFixed(2)}</p>
              </div>
            </div>
          )}
        </div>
        </div>

        {/* Actions - fixed footer */}
        <div className="px-6 py-4 border-t border-rule flex justify-end gap-3 flex-shrink-0 bg-paper-card">
          <button onClick={onClose} className="px-6 py-2.5 text-ink-mute hover:bg-paper-deep rounded font-medium">
            Close
          </button>
          {/* Record Entry retired — the manual per-user portfolio workflow was replaced by the
              auto-mirror book model, so signals no longer offer a "record entry" action. */}
          {type === 'position' && (
            <button
              onClick={() => setShowSellModal(true)}
              className="px-6 py-2.5 bg-negative text-white rounded font-medium hover:bg-negative flex items-center gap-2"
            >
              <DollarSign size={18} />
              Record Exit
            </button>
          )}
          {type === 'missed' && (
            <div className="px-4 py-2 bg-paper-deep text-ink-mute text-sm font-display italic" style={{ fontVariationSettings: '"opsz" 24' }}>
              This window has closed.
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
          lastPositionDollars={lastPositionDollars}
          source={data?.source || 'preserver'}
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
const MetricCard = ({ title, value, subtitle, trend }) => (
  <div className="px-4 first:pl-0 border-r border-rule last:border-r-0">
    <div className="font-body text-[0.64rem] font-medium tracking-[0.22em] uppercase text-ink-mute mb-1">{title}</div>
    <div className={`font-display text-[1.7rem] font-normal leading-none tracking-tight ${trend === 'up' ? 'text-positive' : trend === 'down' ? 'text-negative' : 'text-ink'}`} style={{ fontVariationSettings: '"opsz" 72' }}>{value}</div>
    {subtitle && <div className="font-mono text-[0.7rem] text-ink-light mt-1 tracking-wide">{subtitle}</div>}
  </div>
);

// Inline popover that explains the Strong / Moderate / Very Strong labels in
// 3-4 lines. Click ⓘ to open, click outside or "Got it" to close, "Read more"
// jumps to /methodology#signal-strength for the full explanation.
// Rendered into a portal (document.body) so it escapes overflow:hidden
// scroll containers — the trigger sits inside the Monitoring scroller
// which was clipping the absolutely-positioned popover.
const StrengthInfoPopover = () => {
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState({ top: 0, left: 0 });
  const triggerRef = useRef(null);
  const popoverRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    const handle = (e) => {
      if (popoverRef.current && popoverRef.current.contains(e.target)) return;
      if (triggerRef.current && triggerRef.current.contains(e.target)) return;
      setOpen(false);
    };
    document.addEventListener('mousedown', handle);
    return () => document.removeEventListener('mousedown', handle);
  }, [open]);

  const handleClick = (e) => {
    e.stopPropagation();
    if (!open && triggerRef.current) {
      const r = triggerRef.current.getBoundingClientRect();
      // Position popover below the icon, aligned left, with viewport-edge guard
      const POP_WIDTH = 320;
      let left = r.left;
      if (left + POP_WIDTH > window.innerWidth - 12) {
        left = Math.max(12, window.innerWidth - POP_WIDTH - 12);
      }
      setPosition({ top: r.bottom + window.scrollY + 6, left: left + window.scrollX });
    }
    setOpen((v) => !v);
  };

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        onClick={handleClick}
        className="text-ink-light hover:text-claret no-underline align-baseline cursor-pointer bg-transparent border-0 p-0 leading-none"
        title="What do these labels mean?"
      >
        ⓘ
      </button>
      {open && ReactDOM.createPortal(
        <div
          ref={popoverRef}
          style={{ position: 'absolute', top: position.top, left: position.left, width: 320 }}
          className="z-[9999] bg-paper border border-rule-dark shadow-lg p-4 text-left normal-case tracking-normal"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="font-display text-[0.98rem] font-medium text-ink mb-2" style={{ fontVariationSettings: '"opsz" 24' }}>
            What Strong means
          </div>
          <p className="text-[0.85rem] leading-[1.55] text-ink-mute mb-3">
            A composite of five validated factors: timing setup, momentum quality, volume confirmation, volatility profile, and regime fit. Higher = more factors aligning.
          </p>
          <p className="text-[0.82rem] leading-[1.5] text-ink-mute mb-3 italic">
            Read as context, not a verdict — a Moderate signal in a strong-bull regime can outperform a Very Strong signal in a range-bound one.
          </p>
          <div className="flex items-center justify-between pt-2 border-t border-rule">
            <a
              href="/methodology#signal-strength"
              target="_blank"
              rel="noopener noreferrer"
              className="text-[0.78rem] text-claret hover:underline no-underline"
            >
              Read full methodology →
            </a>
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="text-[0.78rem] text-ink-mute hover:text-ink bg-transparent border-0 cursor-pointer"
            >
              Got it
            </button>
          </div>
        </div>,
        document.body,
      )}
    </>
  );
};

// Signal Strength indicator
const SignalStrengthBar = ({ strength }) => {
  const numStrength = typeof strength === 'string' ? parseFloat(strength) : (strength || 0);
  const color = numStrength >= 70 ? 'bg-positive/100' : numStrength >= 50 ? 'bg-claret' : numStrength >= 30 ? 'bg-rule-dark' : 'bg-rule';
  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-2 bg-rule rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full transition-all`} style={{ width: `${numStrength}%` }} />
      </div>
      <span className="text-xs font-semibold text-ink-mute">{Math.round(numStrength)}</span>
    </div>
  );
};

// Signal Card
const SignalCard = ({ signal, onClick }) => {
  const displayPrice = signal.live_price || signal.price;
  const hasLiveData = !!signal.live_price;

  return (
    <div onClick={() => onClick(signal)} className={`bg-paper-card rounded-lg border-l-4 ${signal.is_strong ? 'border-claret' : 'border-rule-dark'} shadow-sm p-4 hover:shadow-md transition-all cursor-pointer group`}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-lg font-bold text-ink">{signal.symbol}</span>
          {signal.is_strong && <span className="px-2 py-0.5 bg-positive/10 text-positive text-xs font-semibold rounded-full flex items-center gap-1"><Zap size={12} /> STRONG</span>}
        </div>
        <div className="flex items-center gap-2">
          <div className="text-right">
            <span className="text-lg font-semibold text-ink">${displayPrice?.toFixed(2)}</span>
            {hasLiveData && signal.live_change_pct !== undefined && (
              <span className={`ml-2 text-sm ${signal.live_change_pct >= 0 ? 'text-positive' : 'text-negative'}`}>
                {signal.live_change_pct >= 0 ? '+' : ''}{signal.live_change_pct?.toFixed(2)}%
              </span>
            )}
          </div>
          <ChevronRight size={18} className="text-ink-light group-hover:text-claret transition-colors" />
        </div>
      </div>
      <div className="grid grid-cols-3 gap-2 text-sm">
        <div className="flex items-center gap-1">
          <TrendingUp size={14} className="text-positive" />
          <span className="text-ink-mute">Breakout:</span>
          <span className="font-medium text-positive">+{signal.pct_above_dwap}%</span>
        </div>
        <div className="flex items-center gap-1">
          <Activity size={14} className="text-claret" />
          <span className="text-ink-mute">Vol:</span>
          <span className="font-medium">{signal.volume_ratio}x</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="text-ink-mute">Str:</span>
          <SignalStrengthBar strength={signal.signal_strength || 0} />
        </div>
      </div>
      {signal.recommendation && (
        <div className="mt-2 text-xs text-ink-mute italic truncate">{signal.recommendation}</div>
      )}
      {hasLiveData && (
        <div className="mt-1 text-xs text-claret flex items-center gap-1">
          <Activity size={10} className="animate-pulse" /> Live
        </div>
      )}
    </div>
  );
};

// Maximizer breakout-book card — the breakout book shown beside the Preserver base
// (additive serving). Fields come from build_maximizer_breakout_view: status ('new'|
// 'holding'), day X/29 countdown (days_held/hold_days/days_left), price, pnl_pct.
// Position Row
const PositionRow = ({ position, onClick }) => {
  const pnlColor = position.pnl_pct >= 0 ? 'text-positive' : 'text-negative';
  const pnlBg = position.pnl_pct >= 0 ? 'bg-positive/10' : 'bg-negative/10';
  const hasLiveData = position.live_change !== undefined;
  const dayChangeColor = (position.live_change_pct || 0) >= 0 ? 'text-positive' : 'text-negative';

  // Sell signal indicator
  const sellSignal = position.sell_signal || 'hold';
  const trailingStopPrice = position.trailing_stop_price;
  const distanceToStop = position.distance_to_stop_pct || 0;

  const getSellIndicator = () => {
    if (sellSignal === 'sell') {
      return {
        color: 'text-negative',
        bg: 'bg-negative/10',
        icon: <TrendingDown size={14} className="text-negative" />,
        label: 'SELL',
        sublabel: `Stop: $${trailingStopPrice?.toFixed(2)}`
      };
    } else if (sellSignal === 'warning') {
      return {
        color: 'text-claret',
        bg: 'bg-claret/10',
        icon: <AlertCircle size={14} className="text-claret" />,
        label: `${distanceToStop?.toFixed(0)}%`,
        sublabel: `Stop: $${trailingStopPrice?.toFixed(2)}`
      };
    } else {
      return {
        color: 'text-positive',
        bg: 'bg-positive/10',
        icon: <Shield size={14} className="text-positive" />,
        label: `${distanceToStop?.toFixed(0)}%`,
        sublabel: `Stop: $${trailingStopPrice?.toFixed(2)}`
      };
    }
  };

  const indicator = getSellIndicator();

  return (
    <tr onClick={() => onClick(position)} className="hover:bg-paper-deep transition-colors cursor-pointer group">
      <td className="py-3 px-4">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-ink">{position.symbol}</span>
          {hasLiveData && <Activity size={10} className="text-claret animate-pulse" />}
          <Eye size={14} className="text-ink-light group-hover:text-claret" />
        </div>
      </td>
      <td className="py-3 px-4 text-ink-mute">{position.shares?.toFixed(2)}</td>
      <td className="py-3 px-4 text-ink-mute">${position.entry_price?.toFixed(2)}</td>
      <td className="py-3 px-4">
        <div className="flex flex-col">
          <span className="font-medium text-ink">${position.current_price?.toFixed(2)}</span>
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
          <span className="text-xs text-ink-light mt-0.5">{indicator.sublabel}</span>
        </div>
      </td>
      <td className="py-3 px-4 text-ink-mute"><Clock size={14} className="inline mr-1" />{position.days_held}d</td>
    </tr>
  );
};

// ============================================================================
// Welcome Tour
// ============================================================================

const TOUR_STEPS = [
  {
    title: 'Your Signals',
    description: 'When the system spots a strong setup, it appears here. Fresh signals are marked for action. You decide when and how to trade — through your own broker, on your schedule.',
    renderIllustration: () => (
      <div className="flex flex-col items-center gap-3">
        <Zap size={28} className="text-claret" />
        <div className="w-full max-w-xs space-y-2">
          <div className="flex items-center justify-between border-b border-rule px-1 py-2.5">
            <div className="flex items-center gap-2">
              <span className="font-display text-sm text-ink" style={{ fontVariationSettings: '"opsz" 14' }}>NVDA</span>
              <span className="text-xs font-mono text-ink-mute">$142.50</span>
            </div>
            <span className="text-[10px] font-medium tracking-wide text-positive uppercase">Fresh</span>
          </div>
          <div className="flex items-center justify-between border-b border-rule px-1 py-2.5">
            <div className="flex items-center gap-2">
              <span className="font-display text-sm text-ink" style={{ fontVariationSettings: '"opsz" 14' }}>AVGO</span>
              <span className="text-xs font-mono text-ink-mute">$198.30</span>
            </div>
            <span className="text-[10px] font-medium tracking-wide text-claret uppercase">Entry</span>
          </div>
        </div>
      </div>
    ),
  },
  {
    title: 'Open Positions',
    description: 'Track every position in one place. Live P&L, trailing stop levels, days held. When the system says sell, you\'ll see it here and in your evening email.',
    renderIllustration: () => (
      <div className="flex flex-col items-center gap-3">
        <Briefcase size={28} className="text-claret" />
        <div className="w-full max-w-xs border-b border-rule px-1 py-3">
          <div className="flex items-center justify-between">
            <div>
              <span className="font-display text-sm text-ink" style={{ fontVariationSettings: '"opsz" 14' }}>AAPL</span>
              <span className="text-xs text-ink-mute ml-2">50 shares</span>
            </div>
            <div className="text-right">
              <span className="text-sm font-mono text-positive">+$1,240</span>
              <span className="text-xs font-mono text-positive ml-1">+8.2%</span>
            </div>
          </div>
          <div className="flex justify-between mt-2">
            <span className="text-[10px] text-ink-light">Entry $151.20</span>
            <span className="text-[10px] text-ink-light">Stop $140.10</span>
          </div>
        </div>
      </div>
    ),
  },
  {
    title: 'Missed Opportunities',
    description: 'Didn\'t catch a signal? This section tracks what it would have returned. Proof the system works, even when life gets in the way.',
    renderIllustration: () => (
      <div className="flex flex-col items-center gap-3">
        <TrendingUp size={28} className="text-claret" />
        <div className="w-full max-w-xs space-y-0">
          <div className="flex items-center justify-between border-b border-rule px-1 py-2.5 opacity-60">
            <div className="flex items-center gap-2">
              <span className="font-display text-sm text-ink" style={{ fontVariationSettings: '"opsz" 14' }}>META</span>
              <span className="text-[10px] text-ink-light">Jan 28</span>
            </div>
            <span className="text-sm font-mono text-positive">+14.3%</span>
          </div>
          <div className="flex items-center justify-between border-b border-rule px-1 py-2.5 opacity-60">
            <div className="flex items-center gap-2">
              <span className="font-display text-sm text-ink" style={{ fontVariationSettings: '"opsz" 14' }}>AMZN</span>
              <span className="text-[10px] text-ink-light">Jan 22</span>
            </div>
            <span className="text-sm font-mono text-positive">+9.7%</span>
          </div>
        </div>
      </div>
    ),
  },
  {
    title: 'Simple & Advanced',
    description: 'Start with the clean view — just signals and positions. When you want the full picture (momentum scores, breakout strength, regime data), switch to Advanced in the top corner.',
    renderIllustration: () => (
      <div className="flex flex-col items-center gap-3">
        <div className="flex items-center gap-6">
          <div className="flex flex-col items-center gap-1.5">
            <div className="w-11 h-11 border border-rule rounded flex items-center justify-center">
              <Eye size={22} className="text-ink" />
            </div>
            <span className="text-[10px] font-medium text-ink-mute tracking-wide uppercase">Simple</span>
          </div>
          <ChevronRight size={18} className="text-ink-light" />
          <div className="flex flex-col items-center gap-1.5">
            <div className="w-11 h-11 border border-claret rounded flex items-center justify-center">
              <Settings size={22} className="text-claret" />
            </div>
            <span className="text-[10px] font-medium text-claret tracking-wide uppercase">Advanced</span>
          </div>
        </div>
        <div className="w-full max-w-xs border-t border-rule pt-2 mt-1 space-y-1.5">
          <div className="flex items-center justify-between px-1">
            <span className="text-[11px] text-ink-mute">Momentum Score</span>
            <span className="text-[11px] font-mono text-ink">87.4</span>
          </div>
          <div className="flex items-center justify-between px-1">
            <span className="text-[11px] text-ink-mute">Breakout Strength</span>
            <span className="text-[11px] font-mono text-ink">+5.8%</span>
          </div>
          <div className="flex items-center justify-between px-1">
            <span className="text-[11px] text-ink-mute">Sharpe Ratio</span>
            <span className="text-[11px] font-mono text-ink">1.42</span>
          </div>
        </div>
      </div>
    ),
  },
  {
    title: 'Evening Briefing',
    description: 'Every weeknight at 6 PM ET, a briefing lands in your inbox: today\'s signals, open positions, market regime, and a fresh market summary written that afternoon. Expect 3-4 signals per month in healthy markets — and silence when there\'s nothing worth buying.',
    renderIllustration: () => (
      <div className="flex items-center justify-center">
        <div className="relative w-64 h-32">
          {[
            { rotate: '-rotate-6', offset: 'left-2 top-2', subject: '2 Fresh Signals — Strong Bull' },
            { rotate: 'rotate-0', offset: 'left-6 top-1', subject: 'Market Update — NVDA Entry' },
            { rotate: 'rotate-6', offset: 'left-10 top-2', subject: 'RigaCap Daily — 6 Monitoring' },
          ].map((card, i) => (
            <div
              key={i}
              className={`absolute ${card.offset} ${card.rotate} w-44 bg-paper-card rounded shadow-md overflow-hidden`}
              style={{ zIndex: i }}
            >
              <div className="bg-ink px-3 py-1.5 flex items-center gap-1.5">
                <Mail size={10} className="text-paper" />
                <span className="text-[9px] font-display text-paper" style={{ fontVariationSettings: '"opsz" 9' }}>RigaCap</span>
              </div>
              <div className="px-3 py-2">
                <p className="text-[10px] font-medium text-ink truncate">{card.subject}</p>
                <p className="text-[9px] text-ink-light mt-0.5">Today at 6:00 PM ET</p>
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
    <div className="fixed inset-0 bg-ink/60 z-40 flex items-center justify-center p-4" onClick={dismiss}>
      <div
        className="bg-paper rounded max-w-lg w-full mx-4 overflow-hidden border border-rule"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Illustration area */}
        <div className="relative h-48 bg-paper-deep flex items-center justify-center px-6">
          <button
            onClick={dismiss}
            className="absolute top-3 right-3 text-ink-light hover:text-ink transition-colors"
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
            <h3 className="font-display text-xl text-ink" style={{ fontVariationSettings: '"opsz" 24' }}>{current.title}</h3>
            <p className="mt-2 text-sm text-ink-mute leading-relaxed">{current.description}</p>
          </div>

          {/* Footer: dots + buttons */}
          <div className="flex items-center justify-between mt-6">
            <div className="flex gap-1.5">
              {TOUR_STEPS.map((_, i) => (
                <div
                  key={i}
                  className={`w-1.5 h-1.5 rounded-full transition-colors ${
                    i === step ? 'bg-claret' : 'bg-rule'
                  }`}
                />
              ))}
            </div>
            <div className="flex items-center gap-3">
              {!isLast && (
                <button onClick={dismiss} className="text-sm text-ink-light hover:text-ink-mute transition-colors">
                  Skip
                </button>
              )}
              <button
                onClick={next}
                className="px-4 py-2 bg-ink hover:bg-claret text-paper text-sm font-medium rounded transition-colors"
              >
                {isLast ? 'Get Started' : 'Continue'}
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
  const { user, logout, isAdmin, isAuthenticated, loading: authLoading, refreshUser, hasValidSubscription } = useAuth();
  // Shared holdings — drives the Mirror tab AND the "you hold this" bubbles on the main book.
  const holdingsApi = useMirrorHoldings();
  const heldSet = useMemo(() => new Set([...holdingsApi.heldSet].map(s => (s || '').toUpperCase())), [holdingsApi.heldSet]);
  const isHeld = (sym) => heldSet.has((sym || '').toUpperCase());
  const [checkoutSuccess, setCheckoutSuccess] = useState(false);
  const [signals, setSignals] = useState([]);
  const [positions, setPositions] = useState([]);
  const [trades, setTrades] = useState([]);
  const [missedOpportunities, setMissedOpportunities] = useState([]);
  const [missedSortBy, setMissedSortBy] = useState('date'); // 'date' or 'return'
  const [backtest, setBacktest] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  // Captured on first render (before the persist effect overwrites sessionStorage) so we can tell a
  // fresh session (no saved tab) apart from a returning one.
  const hadSavedTabRef = useRef(sessionStorage.getItem('rigacap_active_tab'));
  const [activeTab, setActiveTab] = useState(() => {
    const saved = hadSavedTabRef.current;
    if (saved && !(saved === 'admin' && !isAdmin)) return saved;
    // Pre-entitlement default = Signals (safe: never briefly flashes the paid Mirror to a free user).
    // Upgraded to Mirror for paid/admin once auth resolves, in the effect below.
    return 'signals';
  });
  // Once auth entitlement resolves on a fresh session, land PAID/admin users on the Mirror (the
  // flagship default) and leave FREE / proof-floor users on Signals. Runs once.
  const tabDefaultedRef = useRef(false);
  useEffect(() => {
    if (authLoading || tabDefaultedRef.current) return;
    tabDefaultedRef.current = true;
    if (!hadSavedTabRef.current) {
      setActiveTab((isAdmin || hasValidSubscription) ? 'mirror' : 'signals');
    }
  }, [authLoading, isAdmin, hasValidSubscription]);
  // Mirror onboarding tour — now that the Mirror is the live default tab, run it the first time a
  // user lands on the tab (seen-flag in localStorage). mirrorLivePct is the post-holdings-sync
  // alignment that drives the tour's final-step copy. (Also relaunchable via the "Take the tour" btn.)
  const [mirrorTourOpen, setMirrorTourOpen] = useState(false);
  const [mirrorLivePct, setMirrorLivePct] = useState(0);
  const closeMirrorTour = () => { setMirrorTourOpen(false); try { localStorage.setItem('rigacap_mirror_tour_seen', 'true'); } catch { /* ignore */ } };
  useEffect(() => {
    if (activeTab !== 'mirror') return;
    if (localStorage.getItem('rigacap_mirror_tour_seen') === 'true') return;
    const t = setTimeout(() => setMirrorTourOpen(true), 400);   // let MirrorView paint its spotlight targets first
    return () => clearTimeout(t);
  }, [activeTab]);
  const [dashboardData, setDashboardData] = useState(null); // Unified dashboard data
  // FREE/proof-floor vs full layout decision. For real users it's driven PURELY by the stable auth
  // entitlement (hasValidSubscription, resolved from /me before the dashboard fetch) — so the correct
  // layout renders from the first frame regardless of what's in the (possibly stale, cross-account)
  // dashboard cache. That kills the flash where a stale PAID payload painted the 2-column layout for
  // a beat before the fresh free payload arrived. Admins are never "free" except via the explicit
  // ?preview_state=free QA path (payload subscription_required). (project_free_first_spec)
  const freeTier = isAdmin
    ? (dashboardData?.subscription_required === true)
    : (isAuthenticated && !hasValidSubscription);
  // Rotation-watch row count — measured so the card fills to the bottom of the (taller) Preserver
  // book with no wasted space. Default until measured.
  const [rotRows, setRotRows] = useState(6);

  // Two side-by-side book measurements (two-book view), md+ only:
  //  1. Market Read blocks pinned to the taller so the Your Capital ribbons align pixel-perfect.
  //  2. Rotation watch row count set so its list reaches the Preserver column's bottom (fill, no gap).
  // Direct DOM writes for (1) → no re-render; (2) setStates only when the count changes → converges
  // (Preserver height is independent of rotRows, so the target is stable). No dep array: re-syncs
  // after every render (data fetch, tab/view switch); resize listener handles width changes.
  useLayoutEffect(() => {
    const sync = () => {
      const wide = window.matchMedia('(min-width: 768px)').matches;
      // (1) equal-height Market Read
      const reads = document.querySelectorAll('[data-market-read]');
      reads.forEach(n => { n.style.height = 'auto'; });
      if (reads.length >= 2 && wide) {
        const max = Math.max(...[...reads].map(n => n.offsetHeight));
        reads.forEach(n => { n.style.height = `${max}px`; });
      }
      // (2) Rotation-watch fill — rows to reach the Preserver column bottom
      const left = document.querySelector('[data-books-left]');
      const list = document.querySelector('[data-rot-list]');
      if (left && list && wide) {
        const maxRows = parseInt(list.getAttribute('data-rot-max') || '5', 10);
        const rowEls = list.querySelectorAll('[data-rot-row]');
        const rowH = rowEls.length ? rowEls[0].getBoundingClientRect().height : 49;
        const avail = left.getBoundingClientRect().bottom - list.getBoundingClientRect().top;
        // floor → the most rows that fit WITHOUT extending past the Preserver book (near, not past).
        const target = Math.min(maxRows, Math.max(3, Math.floor(avail / rowH)));
        if (target !== rotRows) setRotRows(target);
      }
    };
    sync();
    window.addEventListener('resize', sync);
    return () => window.removeEventListener('resize', sync);
  });
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
  const [emailPrefs, setEmailPrefs] = useState({ daily_digest: true, sell_alerts: true, intraday_signals: true, market_measured: true });
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

  // Free-first (project_free_first_spec §7): auto-launching Stripe checkout after signup is
  // RETIRED. New users land in the FREE view and upgrade ONLY via an explicit action (the free
  // view's Upgrade button → create-checkout directly). This effect now just clears any stale
  // plan intent left in localStorage so a leftover value can't trigger a surprise checkout a few
  // seconds after landing on the dashboard.
  useEffect(() => {
    localStorage.removeItem('rigacap_selected_plan');
    localStorage.removeItem('rigacap_want_maximizer');
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

    // Handle deep link from daily digest email — open chart popup for a symbol
    const chartSymbol = params.get('chart');
    if (chartSymbol) {
      const sym = chartSymbol.toUpperCase();
      setTimeout(() => setChartModal({ type: 'signal', data: { symbol: sym }, symbol: sym }), 500);
      const url = new URL(window.location);
      url.searchParams.delete('chart');
      window.history.replaceState({}, '', url.pathname);
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
            setEmailPrefs({ daily_digest: false, sell_alerts: false, intraday_signals: false, market_measured: false });
            setTimeout(() => setEmailPrefsToast(null), 6000);
          })
          .catch(() => {});
      }
      const url = new URL(window.location);
      url.searchParams.delete('unsubscribe');
      url.searchParams.delete('token');
      window.history.replaceState({}, '', url.pathname);
    }

    // Handle email-verification return (from the confirmation-link redirect)
    const verified = params.get('verified');
    if (verified) {
      if (verified === '1') {
        refreshUser();                       // pick up email_verified → unlocks connect
        setEmailPrefsToast('verified');
      } else {
        setEmailPrefsToast('verify_failed');
      }
      setTimeout(() => setEmailPrefsToast(null), 6000);
      const url = new URL(window.location);
      url.searchParams.delete('verified');
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
    logEvent('tab_change', { tab: activeTab });
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
          updateEffectiveTrail(data);
          setDashboardData(data);
          // Always reflect the payload (incl. empty) so switching tier/date CLEARS a prior
          // tier's list instead of leaving it stuck (e.g. Maximizer has no missed-opps yet).
          setMissedOpportunities(data.missed_opportunities || []);
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
        updateEffectiveTrail(cached);
        setDashboardData(cached);
        setMissedOpportunities(cached.missed_opportunities || []);
        setTimeTravelPresets(buildTimeTravelPresets(cached));
      }

      // Step 2: Fetch from authenticated API (signals + user positions with sell guidance).
      // Forward ?preview_tier= and ?preview_state= from the URL so admins can preview any tier
      // and any account state (free/active/expired/…) — backend restricts both to admins.
      const _qp = new URLSearchParams(window.location.search);
      const _dashParams = new URLSearchParams();
      if (_qp.get('preview_tier')) _dashParams.set('preview_tier', _qp.get('preview_tier'));
      if (_qp.get('preview_state')) _dashParams.set('preview_state', _qp.get('preview_state'));
      const _dashUrl = _dashParams.toString()
        ? `${API_BASE}/api/signals/dashboard?${_dashParams.toString()}`
        : `${API_BASE}/api/signals/dashboard`;
      try {
        const res = await fetch(_dashUrl, {
          headers: api._authHeaders(),
          signal,
        });
        if (!res.ok) throw new Error(`API error: ${res.status}`);
        const data = await res.json();
        if (signal.aborted) return;
        updateEffectiveTrail(data);
        setDashboardData(data);
        setMissedOpportunities(data.missed_opportunities || []);
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

  // Fetch "This Week" panel data — replaces the old Your Journey strip.
  // Surfaces what the system has done this calendar week (Sun → Sat) so a
  // brand new subscriber lands on real recent activity instead of zeros.
  const [thisWeek, setThisWeek] = useState(null);
  useEffect(() => {
    if (!isAuthenticated || !user?.subscription?.is_valid) return;
    const fetchThisWeek = async () => {
      try {
        // Forward ?preview_tier= so admin tier-preview shows the SERVED tier's book here too
        // (backend is tier-scoped; without this the panel always resolves to the real tier).
        const _pt = new URLSearchParams(window.location.search).get('preview_tier');
        const data = await api.get(`/api/signals/this-week${_pt ? `?preview_tier=${encodeURIComponent(_pt)}` : ''}`);
        if (!data?.error) setThisWeek(data);
      } catch (err) {
        console.log('This-week fetch failed:', err);
      }
    };
    fetchThisWeek();
  }, [isAuthenticated, user?.id, dashboardData?.generated_at]);

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

  // Intraday-live tier book: reprice the mirror-book holdings with live quotes (the backend
  // marks them at the EOD close). Scales each holding's implied value by live/EOD price and
  // recomputes P&L + the invested total; cash is unchanged.
  const tierBookLive = (() => {
    const tb = dashboardData?.tier_book;
    if (!tb || !Array.isArray(tb.holdings)) return tb;
    let invested = 0;
    let anyLive = false;
    const holdings = tb.holdings.map(h => {
      const q = liveQuotes[h.symbol];
      if (q && q.price && h.entry_price && h.price) {
        anyLive = true;
        const price = q.price;
        const iv = h.implied_value * (price / h.price);
        invested += iv;
        return {
          ...h,
          price: +price.toFixed(2),
          pnl_pct: +(((price / h.entry_price) - 1) * 100).toFixed(1),
          implied_value: Math.round(iv),
          live_change_pct: q.change_pct,
          _live: true,
        };
      }
      invested += (h.implied_value || 0);
      return h;
    });
    return anyLive ? { ...tb, holdings, invested_value: Math.round(invested), _intraday: true } : tb;
  })();

  // Live alignment % for the Mirror tab glyph — mirrors MirrorCheck's book logic (Maximizer =
  // preserver base ∪ breakout; Preserver = tier book) against the shared held-set. Null = no book.
  const mirrorPct = (() => {
    const symsOf = (b) => ((b?.holdings) || []).map(h => (h.symbol || '').toUpperCase()).filter(Boolean);
    const isMax = dashboardData?.tier === 'maximizer';
    const bookSet = new Set([...symsOf(isMax ? dashboardData?.preserver_book : tierBookLive), ...(isMax ? symsOf(tierBookLive) : [])]);
    if (!bookSet.size) return null;
    let held = 0; bookSet.forEach(s => { if (heldSet.has(s)) held++; });
    return Math.round((held / bookSet.size) * 100);
  })();

  // Merge live quotes into dashboard positions_with_guidance (these take render priority)
  const guidanceWithLiveQuotes = (dashboardData?.positions_with_guidance || []).map(p => {
    const quote = liveQuotes[p.symbol];
    if (quote) {
      const livePrice = quote.price;
      const pnlPct = ((livePrice - p.entry_price) / p.entry_price) * 100;

      // Recalculate trailing stop distance and action with live price
      const hwm = Math.max(p.high_water_mark || p.entry_price, livePrice);
      const stopPrice = hwm * (1 - EFFECTIVE_TRAIL_FRAC); // effective trail, always derived from live HWM
      const distToStop = livePrice > 0 ? ((livePrice - stopPrice) / livePrice) * 100 : 100; // cushion as % of CURRENT price (not the stop)
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
      // Reload full dashboard (signals + positions with guidance) for accurate data.
      // Forward ?preview_tier= so an admin previewing a tier stays on it after a buy/sell.
      const _pt = new URLSearchParams(window.location.search).get('preview_tier');
      const res = await fetch(`${API_BASE}/api/signals/dashboard${_pt ? `?preview_tier=${encodeURIComponent(_pt)}` : ''}`, {
        headers: api._authHeaders(),
      });
      if (res.ok) {
        const data = await res.json();
        setDashboardData(data);
        setCache(CACHE_KEYS.DASHBOARD, data);
      }

      // Reload user positions so metric cards update (Portfolio Value, P&L, Positions)
      const posResult = await api.get('/api/portfolio/positions');
      if (posResult.positions) {
        setPositions(posResult.positions);
        setCache(CACHE_KEYS.POSITIONS, posResult.positions);
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
      <div className="min-h-screen bg-paper font-body flex items-center justify-center">
        <div className="text-center">
          <div className="relative mx-auto mb-4 w-16 h-16">
            <div className="text-center font-display text-3xl font-semibold text-ink tracking-tight" style={{ fontVariationSettings: '"opsz" 144' }}>RigaCap<span className="text-claret">.</span></div>
            <Loader2 className="w-5 h-5 text-claret animate-spin absolute -bottom-1 -right-1" />
          </div>
          <h2 className="text-xl font-semibold text-ink mb-2">Loading RigaCap</h2>
          <p className="text-ink-mute">Initializing your dashboard...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-paper font-body flex items-center justify-center">
        <div className="text-center max-w-md">
          <AlertCircle className="w-12 h-12 text-negative mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-ink mb-2">Connection Error</h2>
          <p className="text-ink-mute mb-4">{error}</p>
          <p className="text-sm text-ink-light mb-4">
            Backend: {API_BASE}
          </p>
          <button
            onClick={() => window.location.reload()}
            className="px-6 py-2 bg-ink text-white rounded-lg hover:bg-claret"
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
    <div className="min-h-screen bg-paper font-body">
      {/* Data Freshness Banner */}
      {dataFreshness && dataFreshness.status === 'processing' && (
        <div className="bg-paper-deep border-b border-blue-200 px-4 py-2 text-center text-sm text-claret">
          <Clock className="inline w-4 h-4 mr-1 -mt-0.5" />
          {dataFreshness.message || 'Market data is being updated. Signals will refresh shortly.'}
        </div>
      )}
      {dataFreshness && dataFreshness.status === 'stale' && (
        <div className="bg-paper-deep border-b border-amber-200 px-4 py-2 text-center text-sm text-claret">
          <AlertCircle className="inline w-4 h-4 mr-1 -mt-0.5" />
          {dataFreshness.message || "Today's market data is delayed. Signals may not reflect current prices."}
          {dataFreshness.data_date && <span className="ml-1 font-medium">(Last: {dataFreshness.data_date})</span>}
        </div>
      )}
      {/* Header */}
      <header className="bg-paper-card border-b border-rule sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-3 sm:px-6 py-3 sm:py-4 flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 sm:gap-3 shrink-0">
            <svg className="w-9 h-9 sm:w-10 sm:h-10 shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 1024">
              <g transform="matrix(5.266369152845155 0 0 5.266369152845155 639.7474324688749 511.4611892669334)">
                <g>
                  <g transform="matrix(0.447842401165958 0 0 0.447842401165958 -22.37905439059665 -28.76675371508702)"><path fill="#7A2430" transform="translate(-300.0291900499999, -285.76590730000004)" d="M 215.49 348.13 C 215.49 341.43 220.55 335.98 227.05 335.22 L 241.64 278.36 C 238.32 275.99 236.13 272.12 236.13 267.73 C 236.13 260.51 241.98 254.66 249.2 254.66 C 255.89 254.66 261.34 259.71 262.11 266.19 L 309.18 278.16 C 311.55 274.82 315.42 272.63 319.83 272.63 C 324 272.63 327.67 274.62 330.06 277.66 L 391.39 258.85 C 391.87 252.06 397.46 246.69 404.37 246.69 C 405.09 246.69 405.78 246.79 406.47 246.91 L 420.4 223.13 C 395.44 205.2 364.84 194.62 331.76 194.62 C 247.75 194.62 179.66 262.72 179.66 346.72 C 179.66 357.06 180.71 367.15 182.69 376.91 L 216.05 351.72 C 215.72 350.57 215.49 349.38 215.49 348.13 z"/></g>
                  <g transform="matrix(0.447842401165958 0 0 0.447842401165958 -11.05489640960161 -8.986830154000359)"><path fill="#7A2430" transform="translate(-325.3152236000001, -329.93305964999996)" d="M 427.89 228.86 L 414.54 251.65 C 416.32 253.88 417.43 256.68 417.43 259.76 C 417.43 266.98 411.58 272.83 404.37 272.83 C 400.19 272.83 396.52 270.84 394.13 267.79 L 332.8 286.61 C 332.33 293.39 326.73 298.76 319.83 298.76 C 313.14 298.76 307.69 293.72 306.92 287.24 L 259.84 275.26 C 257.76 278.21 254.48 280.2 250.71 280.64 L 236.12 337.5 C 239.44 339.87 241.63 343.74 241.63 348.13 C 241.63 355.35 235.78 361.2 228.56 361.2 C 226.02 361.2 223.68 360.45 221.67 359.19 L 185.04 386.86 C 189.39 402.76 196.25 417.63 205.17 431 L 343.51 312.12 L 408.04 312.12 L 465.59 274.41 C 456.09 256.86 443.23 241.4 427.89 228.86 z"/></g>
                  <g transform="matrix(0.447842401165958 0 0 0.447842401165958 73.82936460708436 -37.11089695025285)"><polygon fill="#7A2430" points="-45.31,-14.33 45.31,-39.44 -12.75,39.44 -17.06,3.28 "/></g>
                  <g transform="matrix(0.447842401165958 0 0 0.447842401165958 -48.16632626991975 25.662112400608095)"><path fill="#141210" transform="translate(-242.44805925, -407.30166625000004)" d="M 297.69 513.38 C 291.85 512.18 286.13 510.68 280.53 508.91 L 280.53 405.3 L 233.16 446.01 L 233.16 485.18 C 189.93 454.31 161.67 403.77 161.67 346.72 C 161.67 321.48 167.23 297.53 177.14 275.97 L 153.41 275.97 C 144.69 297.88 139.84 321.74 139.84 346.72 C 139.84 452.54 225.93 538.63 331.76 538.63 C 336.23 538.63 340.66 538.42 345.06 538.12 L 345.06 349.85 L 297.69 390.55 L 297.69 513.38 z"/></g>
                  <g transform="matrix(0.447842401165958 0 0 0.447842401165958 41.62493388227972 31.445543033824293)"><path fill="#141210" transform="translate(-442.94551085, -420.21565254999996)" d="M 523.16 333.38 L 501.27 333.38 C 501.62 337.79 501.85 342.23 501.85 346.72 C 501.85 381 491.63 412.92 474.11 439.65 L 474.11 304.24 L 426.75 335.28 L 426.75 487.65 C 421.24 491.37 415.52 494.78 409.58 497.85 L 409.58 341.74 L 362.22 341.74 L 362.22 536.19 C 453.61 521.55 523.67 442.17 523.67 346.72 C 523.67 342.23 523.46 337.79 523.16 333.38 z"/></g>
                  <g transform="matrix(0.447842401165958 0 0 0.447842401165958 -11.758155759779243 -60.819370702594256)"><path fill="#141210" transform="translate(-323.7448958499999, -214.1947097)" d="M 331.75 169.32 C 390.45 169.32 442.58 197.98 474.89 242.04 L 483.06 239.78 C 449.46 192.37 394.16 161.37 331.75 161.37 C 258.06 161.37 194.28 204.6 164.43 267.02 L 173.29 267.02 C 202.53 209.12 262.58 169.32 331.75 169.32 z"/></g>
                </g>
              </g>
            </svg>
            <div>
              <h1 className="font-display text-lg sm:text-xl font-semibold text-ink tracking-tight" style={{ fontVariationSettings: '"opsz" 144' }}>RigaCap<span className="text-claret">.</span></h1>
              <p className="text-[0.65rem] font-medium tracking-[0.2em] uppercase text-ink-mute hidden sm:block">Ensemble Signals</p>
            </div>
            {/* Tier badge — reflects the SERVED tier (dashboardData.tier, so admin ?preview_tier
                flips it too), falling back to the subscription. Maximizer = premium filled
                claret pill w/ mark; Preserver = subtle outline. */}
            {(() => {
              // No tier badge for free/proof-only users — they haven't chosen a tier yet.
              if (freeTier) return null;
              const servedTier = dashboardData?.tier
                || (user?.subscription ? (user.subscription.has_maximizer ? 'maximizer' : 'preserver') : null);
              if (!servedTier) return null;
              if (servedTier === 'maximizer') {
                return (
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-[0.15em] bg-claret text-paper shadow-sm">
                    <span className="text-[8px] leading-none">◆</span> Maximizer
                  </span>
                );
              }
              return (
                <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold uppercase tracking-[0.12em] border border-rule-dark text-ink-mute">
                  Preserver
                </span>
              );
            })()}
          </div>

          <nav className="flex items-center border border-rule-dark bg-paper-card">
            <button onClick={() => setActiveTab('mirror')} title={mirrorPct != null ? `${mirrorPct}% mirrored` : 'Mirror'} className={`px-4 sm:px-5 py-2 text-[0.85rem] font-medium border-r border-rule-dark transition-colors inline-flex items-center gap-2 ${activeTab === 'mirror' ? 'bg-ink text-paper' : 'text-ink-mute hover:bg-paper hover:text-ink'}`}>
              <EclipseGlyph pct={mirrorPct || 0} size={16} />
              Mirror
            </button>
            <button onClick={() => setActiveTab('signals')} className={`px-4 sm:px-5 py-2 text-[0.85rem] font-medium border-r border-rule-dark transition-colors ${activeTab === 'signals' ? 'bg-ink text-paper' : 'text-ink-mute hover:bg-paper hover:text-ink'}`}>
              Signals
            </button>
            <button onClick={() => setActiveTab('history')} className={`px-4 sm:px-5 py-2 text-[0.85rem] font-medium border-r border-rule-dark transition-colors ${activeTab === 'history' ? 'bg-ink text-paper' : 'text-ink-mute hover:bg-paper hover:text-ink'}`}>
              Trade History
            </button>
            {isAdmin && (
              <button onClick={() => setActiveTab('admin')} className={`px-4 sm:px-5 py-2 text-[0.85rem] font-medium transition-colors ${activeTab === 'admin' ? 'bg-ink text-paper' : 'text-ink-mute hover:bg-paper hover:text-ink'}`}>
                Admin
              </button>
            )}
          </nav>

          <div className="flex items-center gap-2 sm:gap-4 shrink-0">
            <button
              onClick={() => setViewMode(v => v === 'simple' ? 'advanced' : 'simple')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all border ${
                viewMode === 'simple'
                  ? 'bg-paper-deep text-claret border-blue-200 hover:bg-claret/10'
                  : 'bg-paper-deep text-ink border-rule hover:bg-rule'
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
                      ? 'bg-claret/10 text-claret border-claret/30 hover:bg-claret/20'
                      : 'bg-paper-deep text-ink border-rule hover:bg-rule'
                  }`}
                  title="Time Travel"
                >
                  <Clock size={14} />
                  {timeTravelDate ? formatDate(timeTravelDate, { includeYear: true }) : 'Time Travel'}
                </button>
                {timeTravelOpen && (
                  <div className="absolute right-0 top-full mt-2 w-72 bg-paper-card rounded shadow-xl border border-rule p-4 z-50">
                    <div className="flex items-center justify-between mb-3">
                      <h3 className="text-sm font-semibold text-ink">Time Travel</h3>
                      <button onClick={() => setTimeTravelOpen(false)} className="text-ink-light hover:text-ink-mute"><X size={14} /></button>
                    </div>
                    <input
                      type="date"
                      value={timeTravelDate || ''}
                      max={new Date().toISOString().split('T')[0]}
                      onChange={e => { setTimeTravelDate(e.target.value || null); setTimeTravelOpen(false); }}
                      className="w-full mb-3 px-3 py-2 border border-rule rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-claret"
                    />
                    {timeTravelPresets.length > 0 ? (
                      <>
                        <div className="text-xs font-medium text-ink-mute mb-2">Signal Dates</div>
                        <div className="space-y-1.5 mb-3 max-h-48 overflow-y-auto">
                          {timeTravelPresets.map(({ date, symbols, detail, source }) => (
                            <button
                              key={date}
                              onClick={() => { setTimeTravelDate(date); setTimeTravelEmailPending(true); setTimeTravelOpen(false); }}
                              className={`w-full px-2.5 py-2 text-xs rounded-lg border transition-all text-left flex items-center justify-between gap-2 ${
                                timeTravelDate === date
                                  ? 'bg-claret/10 border-claret/30 text-claret'
                                  : 'bg-paper-card border-rule text-ink-mute hover:bg-paper-deep'
                              }`}
                            >
                              <div className="flex flex-col">
                                <span className="font-medium">{formatDate(date, { includeYear: true })}</span>
                                <span className="text-ink-light truncate max-w-[140px]">{symbols}</span>
                              </div>
                              <span className={`font-semibold whitespace-nowrap ${source === 'missed' ? 'text-positive' : 'text-claret'}`}>{detail}</span>
                            </button>
                          ))}
                        </div>
                      </>
                    ) : (
                      <div className="text-xs text-ink-light mb-3">Loading signal dates...</div>
                    )}
                    <div className="text-xs font-medium text-ink-mute mb-2">Market Events</div>
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
                              ? 'bg-claret/10 border-claret/30 text-claret'
                              : 'bg-paper-card border-rule text-ink-mute hover:bg-paper-deep'
                          }`}
                        >
                          {label}
                        </button>
                      ))}
                    </div>
                    {timeTravelDate && (
                      <button
                        onClick={() => { setTimeTravelDate(null); setTimeTravelOpen(false); }}
                        className="w-full px-3 py-2 text-xs font-medium text-claret bg-claret/5 border border-claret/20 rounded-lg hover:bg-claret/10 transition-all"
                      >
                        Back to Live
                      </button>
                    )}
                  </div>
                )}
              </div>
            )}
            <div className="text-right text-sm hidden md:block">
              {/* Was "{N} symbols loaded" — an internal cache count that read 603
                  under the parquet scoped load and undercut the "4,000+ scanned"
                  pitch. Replaced with the accurate coverage line. (Jun 23 2026) */}
              <div className="text-xs text-ink-light">Scanning 4,000+ US stocks daily</div>
            </div>
            {user ? (
              <div className="relative">
                <button
                  onClick={() => setShowUserMenu(!showUserMenu)}
                  className="w-8 h-8 bg-ink rounded-full flex items-center justify-center text-white font-medium hover:bg-claret transition-colors"
                >
                  {(user.name || user.email || 'U')[0].toUpperCase()}
                </button>
                {showUserMenu && (
                  <>
                    <div className="fixed inset-0 z-40" onClick={() => setShowUserMenu(false)} />
                    <div className="absolute right-0 top-10 w-56 bg-paper-card rounded-lg shadow-lg border z-50 py-1">
                      <div className="px-4 py-2 border-b">
                        <p className="text-sm font-medium text-ink truncate">{user.name || user.email}</p>
                        <p className="text-xs text-ink-mute truncate">{user.email}</p>
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
                          className="w-full px-4 py-2 text-left text-sm text-ink hover:bg-paper-card flex items-center gap-2"
                        >
                          <CreditCard size={14} />
                          Manage Subscription
                        </button>
                      )}
                      <button
                        onClick={() => { setShowUserMenu(false); setShowEmailPrefsModal(true); }}
                        className="w-full px-4 py-2 text-left text-sm text-ink hover:bg-paper-card flex items-center gap-2"
                      >
                        <Bell size={14} />
                        Email Preferences
                      </button>
                      <button
                        onClick={() => { setShowUserMenu(false); setShowReferralModal(true); }}
                        className="w-full px-4 py-2 text-left text-sm text-ink hover:bg-paper-card flex items-center gap-2"
                      >
                        <Gift size={14} />
                        Refer a Friend
                        {(user.referral_count > 0) && (
                          <span className="ml-auto bg-positive/10 text-positive text-xs font-medium px-1.5 py-0.5 rounded-full">{user.referral_count}</span>
                        )}
                      </button>
                      {isAdmin && (
                        <button
                          onClick={() => { setShowUserMenu(false); setShow2FASettings(true); }}
                          className="w-full px-4 py-2 text-left text-sm text-ink hover:bg-paper-card flex items-center gap-2"
                        >
                          <Shield size={14} />
                          Two-Factor Auth
                          {user?.totp_enabled && (
                            <span className="ml-auto bg-positive/10 text-positive text-xs font-medium px-1.5 py-0.5 rounded-full">On</span>
                          )}
                        </button>
                      )}
                      <button
                        onClick={() => { setShowUserMenu(false); logout(); }}
                        className="w-full px-4 py-2 text-left text-sm text-ink hover:bg-paper-card flex items-center gap-2"
                      >
                        <LogOut size={14} />
                        Sign Out
                      </button>
                    </div>
                  </>
                )}
              </div>
            ) : (
              <button onClick={() => setShowLoginModal(true)} className="px-4 py-2 bg-ink text-white rounded-lg font-medium hover:bg-claret flex items-center gap-2">
                <LogIn size={16} />Sign In
              </button>
            )}
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-3 sm:px-6 pt-4 sm:pt-6 pb-28 sm:pb-28">
        <WelcomeTour />
        {/* Time Travel Banner */}
        {timeTravelDate && (
          <div className="mb-4 p-3 bg-ink text-white rounded flex items-center justify-between">
            <div className="flex items-center gap-2">
              {timeTravelLoading ? <Loader2 size={16} className="animate-spin" /> : <Clock size={16} />}
              <span className="text-sm font-medium">
                {timeTravelLoading
                  ? `Loading data for ${formatDate(timeTravelDate, { includeYear: true })}...`
                  : `Time Travel: Viewing dashboard as of ${formatDate(timeTravelDate, { includeYear: true })}`
                }
              </span>
              {timeTravelEmailStatus === 'sending' && <span className="text-xs text-ink-light ml-2">Sending email...</span>}
              {timeTravelEmailStatus === 'sent' && <span className="text-xs text-positive ml-2">Email sent</span>}
              {timeTravelEmailStatus === 'failed' && <span className="text-xs text-negative ml-2">Email failed</span>}
            </div>
            <button
              onClick={() => setTimeTravelDate(null)}
              className="text-sm font-medium text-ink-light hover:text-white flex items-center gap-1 transition-colors"
            >
              Back to Live <ChevronRight size={14} />
            </button>
          </div>
        )}

        {/* Subscription Banner */}
        {checkoutSuccess && (
          <div className="border border-rule-dark bg-paper-card p-5 mb-6 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <p className="font-body text-ink font-medium">Welcome to RigaCap. Your subscription is now active.</p>
            </div>
            <button onClick={() => setCheckoutSuccess(false)} className="p-1 text-ink-light hover:text-ink"><X size={18} /></button>
          </div>
        )}
        {isAuthenticated && !checkoutSuccess && <SubscriptionBanner />}

        {/* This Week — prose-led editorial briefing. Pulled for served tiers (books-first
            redesign: too much preamble before the books). Kept for legacy/unserved (!tier_book).
            Reversible — drop the `!tier_book` guard to bring it back. */}
        {thisWeek && activeTab === 'signals' && !dashboardData?.tier_book && (() => {
          const c = thisWeek.closed_count;
          const w = thisWeek.winning_count;
          const o = thisWeek.still_running_count;
          const avg = thisWeek.average_pnl_pct;
          // Backend computes leader/tail across the full open set
          const openAvg = thisWeek.open_avg_pnl_pct;
          const leader = thisWeek.leader;
          const tail = thisWeek.tail;
          const longestHold = thisWeek.longest_hold;
          const allOpenPositive = leader && tail && tail.pnl_pct > 0;

          const fmtPct = (v) => `${v >= 0 ? '+' : ''}${v}%`;
          const heldClause = (days) => days != null ? ` (held ${days} ${days === 1 ? 'day' : 'days'})` : '';

          // Build the headline + rotating accent line based on what kind of week it was.
          // Priority order — first match wins:
          //   1. Closes happened: lead with the closed picks (always honest)
          //   2. All open positions positive: sweetener flex
          //   3. Leader is up, tail is also up: show both with "still up" framing
          //   4. Leader is up, tail is down: show both honestly
          //   5. Leader is flat-or-negative: pivot to longest-hold discipline flex
          //      (this is the "both red" failure mode — never read as defeat)
          //   6. No open positions: quiet week
          const buildHeadlineParts = () => {
            // Closes this week — lead with what closed
            if (c > 0) {
              const pick = c === 1 ? 'one pick' : `${c} picks`;
              const wlClause = c > 1
                ? ` (${w} ${w === 1 ? 'win' : 'wins'}, ${c - w} ${c - w === 1 ? 'loss' : 'losses'})`
                : '';
              const avgClause = avg >= 0 ? `averaging +${avg}%` : `averaging ${avg}%`;
              const openClause = o > 0 ? ` ${o} still ${o === 1 ? 'runs' : 'run'}.` : '';
              return {
                lead: `The system closed ${pick} this week${wlClause}, ${avgClause}.${openClause}`,
                accent: null,
              };
            }
            // No open positions
            if (o === 0) {
              return { lead: 'A quiet week — no closes, no open positions.', accent: null };
            }
            // Open positions exist but no closes this week
            const baseLead = `A holding week. ${o} ${o === 1 ? 'position' : 'positions'} running, no closes.`;
            // Branch 2: all open positions positive
            if (allOpenPositive && o >= 2) {
              return {
                lead: baseLead,
                accent: `All ${o} positions positive. ${leader.symbol} leads at ${fmtPct(leader.pnl_pct)}, tail ${tail.symbol} at ${fmtPct(tail.pnl_pct)}, average ${fmtPct(openAvg)}.`,
              };
            }
            // Branch 3: leader up, tail up (but not "all" — covers o=1 and edge cases)
            if (leader && leader.pnl_pct > 0 && tail && tail.pnl_pct > 0) {
              return {
                lead: baseLead,
                accent: `${leader.symbol} leads at ${fmtPct(leader.pnl_pct)}${heldClause(leader.days_held)}. Tail ${tail.symbol} still up at ${fmtPct(tail.pnl_pct)}.`,
              };
            }
            // Branch 4: leader up, tail down — show honestly
            if (leader && leader.pnl_pct > 0) {
              return {
                lead: baseLead,
                accent: `${leader.symbol} leads at ${fmtPct(leader.pnl_pct)}${heldClause(leader.days_held)}. Tail: ${tail.symbol} ${fmtPct(tail.pnl_pct)}${heldClause(tail.days_held)}. Average ${fmtPct(openAvg)}.`,
              };
            }
            // Branch 5: leader is flat/negative — pivot to discipline flex (longest hold)
            if (longestHold && longestHold.days_held != null) {
              return {
                lead: baseLead,
                accent: `Longest hold: ${longestHold.symbol}, ${longestHold.days_held} days. The system isn't trading — it's waiting.`,
              };
            }
            // No leader/longest data at all
            return { lead: baseLead, accent: null };
          };

          const { lead: headlineLead, accent: headlineAccent } = buildHeadlineParts();

          return (
            <section className="mb-6 border-y border-rule py-5">
              <div className="flex items-baseline justify-between mb-3">
                <h2
                  className="font-display italic text-ink"
                  style={{ fontVariationSettings: '"opsz" 48', fontSize: 'clamp(1.25rem, 2vw, 1.55rem)', fontWeight: 400 }}
                >
                  This Week
                </h2>
                <span className="font-body text-[0.66rem] tracking-[0.22em] uppercase text-ink-light">
                  {new Date(thisWeek.as_of_date + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                </span>
              </div>

              {/* Lead paragraph + rotating accent line — branch chosen by buildHeadlineParts() above */}
              <p
                className="font-display text-ink mb-1"
                style={{ fontVariationSettings: '"opsz" 24', fontSize: 'clamp(1rem, 1.6vw, 1.15rem)', lineHeight: 1.45, fontWeight: 400 }}
              >
                {headlineLead}
              </p>
              {headlineAccent && (
                <p
                  className="font-display text-ink-mute mb-4"
                  style={{ fontVariationSettings: '"opsz" 24', fontSize: 'clamp(0.95rem, 1.4vw, 1.05rem)', lineHeight: 1.55, fontWeight: 400 }}
                >
                  {headlineAccent}
                </p>
              )}

              {/* Closed picks — single-row tape with dotted leaders */}
              {thisWeek.closed_this_week && thisWeek.closed_this_week.length > 0 && (
                <div className="flex flex-wrap items-baseline gap-x-6 gap-y-2 pt-3 border-t border-rule">
                  {thisWeek.closed_this_week.map((p, idx) => (
                    <span key={`${p.symbol}-${p.exit_date}`} className="inline-flex items-baseline gap-1.5">
                      <span
                        className="font-display text-ink"
                        style={{ letterSpacing: '0.1em', fontSize: '0.95rem', fontWeight: 500 }}
                      >
                        {p.symbol}
                      </span>
                      <span
                        className={`font-mono ${p.pnl_pct >= 0 ? 'text-positive' : 'text-negative'}`}
                        style={{ fontSize: '0.95rem', fontWeight: 500 }}
                      >
                        {p.pnl_pct >= 0 ? '+' : ''}{p.pnl_pct}%
                      </span>
                      {idx < thisWeek.closed_this_week.length - 1 && (
                        <span aria-hidden className="text-ink-light/40 ml-3">·</span>
                      )}
                    </span>
                  ))}
                </div>
              )}
            </section>
          );
        })()}

        {/* Admin Dashboard */}
        {activeTab === 'admin' && isAdmin && (
          <Suspense fallback={<div className="py-12 text-center text-ink-mute">Loading admin…</div>}>
            <AdminDashboard />
          </Suspense>
        )}

        {/* No data warning banner */}
        {noDataAvailable && (
          <div className="mb-4 bg-paper-deep border border-amber-200 rounded p-4 flex items-center gap-3">
            <AlertCircle className="text-claret flex-shrink-0" size={24} />
            <div>
              <h3 className="font-semibold text-ink">Market Data Loading</h3>
              <p className="text-sm text-claret">
                Historical data is being fetched. This may take a moment.
                Data refreshes automatically — check back in a few minutes.
              </p>
            </div>
          </div>
        )}

        {activeTab === 'mirror' ? (
          <>
            <MirrorView book={tierBookLive} preserverBook={dashboardData?.preserver_book} tier={dashboardData?.tier}
              regimeName={dashboardData?.regime_forecast?.current_regime_name} onOpenChart={setChartModal} holdingsApi={holdingsApi}
              onState={(s) => setMirrorLivePct(s?.pct || 0)} />
            <MirrorTour open={mirrorTourOpen} onClose={closeMirrorTour} pct={mirrorLivePct} />
            <button onClick={() => setMirrorTourOpen(true)}
              className="fixed bottom-4 right-4 z-30 text-[0.75rem] font-medium px-3.5 py-2 rounded-full bg-ink text-paper shadow-lg hover:bg-claret transition-colors">
              Take the tour
            </button>
          </>
        ) : activeTab === 'signals' ? (
          <>
            {/* Go to Cash Banner */}
            {dashboardData?.regime_forecast?.recommended_action === 'go_to_cash' && !freeTier && (
              <div className="mb-4 p-4 bg-negative text-white rounded flex items-center gap-3">
                <Shield className="w-6 h-6 flex-shrink-0" />
                <div>
                  <h3 className="font-bold text-lg">Market Conditions Deteriorating — Consider Closing Positions</h3>
                  <p className="text-ink-mute text-sm">{dashboardData.regime_forecast.outlook_detail}</p>
                </div>
              </div>
            )}

            {/* "Where we are right now" — honest book-phase readout, shown in the trial/paid
                dashboard too (the proof floor shows it via FreeProofView). project_free_first_spec. */}
            {dashboardData?.current_phase?.text && !freeTier && (
              <div className={`mb-4 rounded-[2px] border p-4 ${dashboardData.current_phase.phase === 'soft_patch' ? 'border-ink/15 bg-paper-deep' : 'border-positive/30 bg-positive/5'}`}>
                <div className="flex items-center gap-2 mb-1">
                  <TrendingUp className={`w-4 h-4 ${dashboardData.current_phase.phase === 'soft_patch' ? 'text-ink-mute' : 'text-positive'}`} />
                  <span className="text-xs font-medium uppercase tracking-wide text-ink-mute">Where we are right now</span>
                </div>
                <p className="text-sm text-ink leading-relaxed">{dashboardData.current_phase.text}</p>
              </div>
            )}

            {/* Regime Forecast Bar — shown for everyone incl. the proof floor (regime is market
                context, not an actionable signal; Erik wants the regime control visible to free). */}
            {dashboardData?.regime_forecast && (
              viewMode === 'simple' ? (
                /* Simple mode: traffic light + one sentence, click to expand */
                <div className="mb-4">
                  <div
                    className="p-3 rounded border border-rule bg-paper-card flex items-center gap-3 cursor-pointer hover:bg-paper-card transition-colors"
                    onClick={() => setRegimeExpanded(prev => !prev)}
                  >
                    <div className={`w-4 h-4 rounded-full flex-shrink-0 ${
                      ['strong_bull', 'weak_bull', 'recovery'].includes(dashboardData.regime_forecast.current_regime) ? 'bg-rule-dark' :
                      ['rotating_bull', 'range_bound'].includes(dashboardData.regime_forecast.current_regime) ? 'bg-ink-light' :
                      'bg-negative/100'
                    }`} />
                    <span className="text-sm text-ink flex-1">
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
                      <span className="text-sm font-medium text-ink flex-shrink-0">
                        SPY {dashboardData.market_stats.spy_price.toFixed(2)}
                        {dashboardData.market_stats.spy_change_pct != null && (
                          <span className={`ml-1 ${dashboardData.market_stats.spy_change_pct >= 0 ? 'text-positive' : 'text-negative'}`}>
                            ({dashboardData.market_stats.spy_change_pct >= 0 ? '+' : ''}{dashboardData.market_stats.spy_change_pct.toFixed(2)}%)
                          </span>
                        )}
                        {dashboardData.market_stats.live && (
                          <span className="ml-1.5 inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold bg-positive/10 text-positive uppercase tracking-wide">Live</span>
                        )}
                      </span>
                    )}
                    {dashboardData.data_date && (
                      <span className="text-xs text-ink-light flex-shrink-0">as of {dashboardData.data_date}</span>
                    )}
                    <svg className={`w-4 h-4 text-ink-light transition-transform flex-shrink-0 ${regimeExpanded ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </div>
                  {/* Regime TELL — expectation-setter (not a trade signal). Tier from the
                      SERVED tier (dashboardData.tier, so admin ?preview_tier flips it), else sub. */}
                  <RegimeTell regime={dashboardData.regime_forecast.current_regime}
                              tier={dashboardData?.tier || (user?.subscription?.has_maximizer ? 'maximizer' : 'preserver')} />
                  {regimeExpanded && (() => {
                    const rf = dashboardData.regime_forecast;
                    const regimeColors = {
                      strong_bull: { bg: 'bg-paper-card', text: 'text-ink', bar: 'bg-paper' },
                      weak_bull: { bg: 'bg-paper-card', text: 'text-ink', bar: 'bg-paper-deep' },
                      rotating_bull: { bg: 'bg-paper-card', text: 'text-ink-mute', bar: 'bg-rule-dark' },
                      range_bound: { bg: 'bg-paper-deep', text: 'text-ink-mute', bar: 'bg-ink-light' },
                      weak_bear: { bg: 'bg-paper-deep', text: 'text-ink', bar: 'bg-ink-mute' },
                      panic_crash: { bg: 'bg-paper-deep', text: 'text-ink', bar: 'bg-ink' },
                      recovery: { bg: 'bg-paper-card', text: 'text-ink-mute', bar: 'bg-rule' },
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
                      <div className="mt-1 p-4 rounded border border-rule bg-paper-card space-y-4">
                        {/* Regime name + pills */}
                        <div className="flex items-center justify-between flex-wrap gap-2">
                          <span className="font-semibold text-ink">{rf.current_regime_name || regimeNames[rf.current_regime]} Market</span>
                          <div className="flex items-center gap-4">
                            <span className="font-mono text-[0.7rem] tracking-[0.1em] uppercase text-ink-mute">Outlook: <strong className="text-ink font-medium">{rf.outlook}</strong></span>
                            <span className="w-px h-4 bg-rule" />
                            <span className="font-mono text-[0.7rem] tracking-[0.1em] uppercase text-ink-mute">Risk: <strong className="text-ink font-medium">{rf.risk_change}</strong></span>
                            <span className="w-px h-4 bg-rule" />
                            <span className="font-mono text-[0.7rem] tracking-[0.1em] uppercase text-ink-mute"><strong className="text-ink font-medium">{(rf.recommended_action || '').replace(/_/g, ' ')}</strong></span>
                          </div>
                        </div>

                        {/* Outlook detail */}
                        {rf.outlook_detail && (
                          <p className="text-sm text-ink-mute leading-relaxed">{rf.outlook_detail}</p>
                        )}

                        {/* SPY + VIX */}
                        {dashboardData.market_stats && (
                          <div className="flex gap-6 text-sm">
                            <div>
                              <span className="text-ink-mute">S&P 500</span>
                              <span className="ml-2 font-semibold text-ink">${dashboardData.market_stats.spy_price?.toFixed(0)}</span>
                              {dashboardData.market_stats.spy_change_pct != null && (
                                <span className={`ml-1 text-xs font-medium ${dashboardData.market_stats.spy_change_pct >= 0 ? 'text-positive' : 'text-negative'}`}>
                                  {dashboardData.market_stats.spy_change_pct >= 0 ? '+' : ''}{dashboardData.market_stats.spy_change_pct.toFixed(2)}%
                                </span>
                              )}
                            </div>
                            <div>
                              <span className="text-ink-mute">Market Fear</span>
                              <span className={`ml-2 font-semibold ${getVixLabel(dashboardData.market_stats.vix_level).color}`}>{getVixLabel(dashboardData.market_stats.vix_level).label}</span>
                              <span className="ml-1 text-xs text-ink-light">(VIX: {dashboardData.market_stats.vix_level?.toFixed(1)})</span>
                            </div>
                          </div>
                        )}

                        {/* Market Context — shown in the editorial lede above signals, not here */}

                        {/* Transition probability bar — editorial density visualization */}
                        {sortedProbs.length > 0 && (
                          <div>
                            <div className="flex justify-between items-baseline mb-2">
                              <p className="font-body text-[0.66rem] font-medium tracking-[0.22em] uppercase text-ink-mute">Transition Probabilities · Next Period</p>
                              <span className="font-mono text-[0.72rem] text-ink-light tracking-wide">
                                {rf.outlook_detail ? rf.outlook_detail.split('.')[0] : `${(probs[rf.current_regime] || 0).toFixed(0)}% chance regime holds`}
                              </span>
                            </div>
                            <div className="flex h-8 border border-ink bg-paper">
                              {sortedProbs.map(([r, pct]) => {
                                const isCurrent = r === rf.current_regime;
                                const regimeDensity = {
                                  strong_bull: 'bg-paper text-ink',
                                  weak_bull: 'bg-paper-deep text-ink',
                                  recovery: 'bg-rule text-ink',
                                  rotating_bull: 'bg-rule-dark text-ink',
                                  range_bound: 'bg-ink-light text-paper',
                                  weak_bear: 'bg-ink-mute text-paper',
                                  panic_crash: 'bg-ink text-paper',
                                };
                                const densityClass = isCurrent
                                  ? 'bg-claret text-paper'
                                  : (regimeDensity[r] || 'bg-rule text-ink');
                                return (
                                  <div
                                    key={r}
                                    className={`flex items-center justify-center border-r border-ink last:border-r-0 ${densityClass} ${isCurrent ? 'shadow-[inset_0_-3px_0_#141210]' : ''}`}
                                    style={{ flex: Math.max(pct, 0.5) }}
                                    title={`${regimeNames[r]}: ${pct.toFixed(0)}%`}
                                  >
                                    {pct >= 8 && <span className="font-mono text-[0.78rem] font-medium">{pct.toFixed(0)}%</span>}
                                  </div>
                                );
                              })}
                            </div>
                            <div className="flex justify-between font-mono text-[0.68rem] text-ink-light tracking-wide mt-1.5">
                              {sortedProbs.map(([r]) => (
                                <span key={r}>{({'strong_bull':'Str.Bull','weak_bull':'Wk.Bull','rotating_bull':'Rot.Bull','range_bound':'Range','weak_bear':'Wk.Bear','panic_crash':'Panic','recovery':'Recov.'}[r] || r)}{r === rf.current_regime ? ' ●' : ''}</span>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* All 7 regimes */}
                        <div className="border-t border-rule pt-3 space-y-0">
                          {allRegimes.map(r => {
                            const isCurrent = r === rf.current_regime;
                            const c = regimeColors[r] || { bg: 'bg-paper-deep', text: 'text-ink-mute', bar: 'bg-rule' };
                            const prob = probs[r];
                            return (
                              <div key={r} className={`flex items-center justify-between px-2 py-2 border-b border-rule last:border-b-0 ${isCurrent ? 'bg-claret/5' : ''}`}>
                                <div className="flex items-center gap-3">
                                  <div className={`w-2.5 h-2.5 ${isCurrent ? 'bg-claret' : c.bar}`} />
                                  <div>
                                    <span className={`text-sm font-medium ${isCurrent ? 'text-ink' : 'text-ink-mute'}`}>
                                      {regimeNames[r]}
                                    </span>
                                    <span className="text-xs text-ink-light ml-2">{regimeDescriptions[r]}</span>
                                  </div>
                                </div>
                                <span className={`font-mono text-sm ${isCurrent ? 'text-claret font-medium' : 'text-ink-light'}`}>
                                  {prob != null ? `${prob.toFixed(0)}%` : '—'}
                                </span>
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
                <div onClick={() => setRegimeExpanded(v => !v)} className={`mb-4 p-4 rounded border cursor-pointer ${
                  dashboardData.regime_forecast.current_regime === 'strong_bull' ? 'bg-paper-card border-rule' :
                  dashboardData.regime_forecast.current_regime === 'weak_bull' ? 'bg-paper-card border-rule' :
                  dashboardData.regime_forecast.current_regime === 'rotating_bull' ? 'bg-paper-card border-rule-dark' :
                  dashboardData.regime_forecast.current_regime === 'range_bound' ? 'bg-paper-deep border-rule-dark' :
                  dashboardData.regime_forecast.current_regime === 'recovery' ? 'bg-paper-card border-rule' :
                  dashboardData.regime_forecast.current_regime === 'weak_bear' ? 'bg-paper-deep border-rule-dark' :
                  dashboardData.regime_forecast.current_regime === 'panic_crash' ? 'bg-paper-deep border-ink-light' :
                  'bg-paper-card border-rule'
                }`}>
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <div className={`p-2 rounded-full ${
                        dashboardData.regime_forecast.current_regime === 'strong_bull' ? 'bg-paper-card' :
                        dashboardData.regime_forecast.current_regime === 'weak_bull' ? 'bg-paper-card' :
                        dashboardData.regime_forecast.current_regime === 'rotating_bull' ? 'bg-paper-card' :
                        dashboardData.regime_forecast.current_regime === 'range_bound' ? 'bg-paper-deep' :
                        dashboardData.regime_forecast.current_regime === 'recovery' ? 'bg-paper-card' :
                        dashboardData.regime_forecast.current_regime === 'weak_bear' ? 'bg-paper-deep' :
                        'bg-negative/10'
                      }`}>
                        {['strong_bull', 'weak_bull', 'recovery'].includes(dashboardData.regime_forecast.current_regime) ? <TrendingUp className="w-5 h-5 text-positive" /> :
                         dashboardData.regime_forecast.current_regime === 'rotating_bull' ? <RefreshCw className="w-5 h-5 text-ink-mute" /> :
                         dashboardData.regime_forecast.current_regime === 'range_bound' ? <Activity className="w-5 h-5 text-claret" /> :
                         <TrendingDown className="w-5 h-5 text-negative" />}
                      </div>
                      <div>
                        <div className="flex items-center flex-wrap gap-x-2 gap-y-1">
                          <span className="font-semibold text-ink">
                            {dashboardData.regime_forecast.current_regime_name} Market
                          </span>
                          {dashboardData.market_stats?.spy_price && (
                            <>
                              <span className="text-ink-light">|</span>
                              <span className="text-ink-mute text-sm">
                                SPY ${dashboardData.market_stats.spy_price.toFixed(2)}
                                {dashboardData.market_stats.spy_change_pct != null && (
                                  <span className={`ml-1 font-medium ${dashboardData.market_stats.spy_change_pct >= 0 ? 'text-positive' : 'text-negative'}`}>
                                    ({dashboardData.market_stats.spy_change_pct >= 0 ? '+' : ''}{dashboardData.market_stats.spy_change_pct.toFixed(2)}%)
                                  </span>
                                )}
                              </span>
                            </>
                          )}
                          {dashboardData.market_stats?.vix_level && (
                            <>
                              <span className="text-ink-light">|</span>
                              <span className="text-ink-mute text-sm">Market Fear: <span className={`font-medium ${getVixLabel(dashboardData.market_stats.vix_level).color}`}>{getVixLabel(dashboardData.market_stats.vix_level).label}</span></span>
                            </>
                          )}
                        </div>
                        <div className="flex items-center flex-wrap gap-2 mt-1">
                          <span className={`text-xs px-2 py-0.5 rounded font-medium ${
                            dashboardData.regime_forecast.outlook === 'stable' ? 'bg-positive/10 text-positive' :
                            dashboardData.regime_forecast.outlook === 'improving' ? 'bg-positive/10 text-positive' :
                            'bg-orange-100 text-orange-700'
                          }`}>
                            Outlook: {dashboardData.regime_forecast.outlook}
                          </span>
                          <span className={`text-xs px-2 py-0.5 rounded font-medium ${
                            dashboardData.regime_forecast.risk_change === 'decreasing' ? 'bg-positive/10 text-positive' :
                            dashboardData.regime_forecast.risk_change === 'stable' ? 'bg-paper-deep text-ink-mute' :
                            'bg-negative/10 text-negative'
                          }`}>
                            Risk: {dashboardData.regime_forecast.risk_change}
                          </span>
                          <span className={`text-xs px-2 py-0.5 rounded font-medium ${
                            dashboardData.regime_forecast.recommended_action === 'stay_invested' ? 'bg-positive/10 text-positive' :
                            dashboardData.regime_forecast.recommended_action === 'tighten_stops' ? 'bg-yellow-100 text-yellow-700' :
                            dashboardData.regime_forecast.recommended_action === 'reduce_exposure' ? 'bg-orange-100 text-orange-700' :
                            'bg-negative/10 text-negative'
                          }`}>
                            {dashboardData.regime_forecast.recommended_action.replace(/_/g, ' ')}
                          </span>
                          {dashboardData.regime_adjustments?.changes?.length > 0 && (
                            <span className="text-xs px-2 py-0.5 rounded font-medium bg-claret/10 text-claret">
                              {dashboardData.regime_adjustments.changes.length} param{dashboardData.regime_adjustments.changes.length > 1 ? 's' : ''} adjusted
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-start sm:items-center gap-2 w-full sm:w-auto">
                      <div className="text-sm text-ink-mute w-full sm:max-w-sm text-left sm:text-right leading-snug">
                        {dashboardData.regime_forecast.outlook_detail}
                      </div>
                      <svg className={`w-4 h-4 text-ink-light transition-transform flex-shrink-0 mt-0.5 sm:mt-0 ${regimeExpanded ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                      </svg>
                    </div>
                  </div>

                  {/* Transition probabilities mini bar — hidden when expanded */}
                  {!regimeExpanded && dashboardData.regime_forecast.transition_probabilities && (() => {
                    const currentRegime = dashboardData.regime_forecast.current_regime;
                    const probs = dashboardData.regime_forecast.transition_probabilities;
                    const sorted = Object.entries(probs)
                      .filter(([_, pct]) => pct > 0.5)
                      .sort((a, b) => b[1] - a[1]);
                    return (
                      <div className="mt-3 flex h-4 border border-ink overflow-hidden bg-paper">
                        {sorted.map(([regime, pct]) => {
                          const isCurrent = regime === currentRegime;
                          const regimeDensity = {
                            strong_bull: 'bg-paper',
                            weak_bull: 'bg-paper-deep',
                            recovery: 'bg-rule',
                            rotating_bull: 'bg-rule-dark',
                            range_bound: 'bg-ink-light',
                            weak_bear: 'bg-ink-mute',
                            panic_crash: 'bg-ink',
                          };
                          const densityClass = isCurrent ? 'bg-claret' : (regimeDensity[regime] || 'bg-rule');
                          return (
                            <div
                              key={regime}
                              className={`h-full border-r border-ink last:border-r-0 ${densityClass}`}
                              style={{ flex: Math.max(pct, 0.5) }}
                              title={`${regime.replace(/_/g, ' ')}: ${pct.toFixed(0)}%`}
                            />
                          );
                        })}
                      </div>
                    );
                  })()}

                  {/* Expanded: regime detail panel */}
                  {regimeExpanded && (() => {
                    const rf = dashboardData.regime_forecast;
                    const regimeColors = {
                      strong_bull: { bg: 'bg-paper-card', text: 'text-ink', bar: 'bg-paper' },
                      weak_bull: { bg: 'bg-paper-card', text: 'text-ink', bar: 'bg-paper-deep' },
                      rotating_bull: { bg: 'bg-paper-card', text: 'text-ink-mute', bar: 'bg-rule-dark' },
                      range_bound: { bg: 'bg-paper-deep', text: 'text-ink-mute', bar: 'bg-ink-light' },
                      weak_bear: { bg: 'bg-paper-deep', text: 'text-ink', bar: 'bg-ink-mute' },
                      panic_crash: { bg: 'bg-paper-deep', text: 'text-ink', bar: 'bg-ink' },
                      recovery: { bg: 'bg-paper-card', text: 'text-ink-mute', bar: 'bg-rule' },
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
                      <div className="mt-3 pt-3 border-t border-rule space-y-4">
                        {/* Transition probability bar — editorial density */}
                        {sortedProbs.length > 0 && (
                          <div>
                            <div className="flex justify-between items-baseline mb-2">
                              <p className="font-body text-[0.66rem] font-medium tracking-[0.22em] uppercase text-ink-mute">Transition Probabilities · Next Period</p>
                              <span className="font-mono text-[0.72rem] text-ink-light tracking-wide">
                                {(probs[rf.current_regime] || 0).toFixed(0)}% chance regime holds
                              </span>
                            </div>
                            <div className="flex h-8 border border-ink bg-paper">
                              {sortedProbs.map(([r, pct]) => {
                                const isCurrent = r === rf.current_regime;
                                const regimeDensity = {
                                  strong_bull: 'bg-paper text-ink',
                                  weak_bull: 'bg-paper-deep text-ink',
                                  recovery: 'bg-rule text-ink',
                                  rotating_bull: 'bg-rule-dark text-ink',
                                  range_bound: 'bg-ink-light text-paper',
                                  weak_bear: 'bg-ink-mute text-paper',
                                  panic_crash: 'bg-ink text-paper',
                                };
                                const densityClass = isCurrent
                                  ? 'bg-claret text-paper'
                                  : (regimeDensity[r] || 'bg-rule text-ink');
                                return (
                                  <div
                                    key={r}
                                    className={`flex items-center justify-center border-r border-ink last:border-r-0 ${densityClass} ${isCurrent ? 'shadow-[inset_0_-3px_0_#141210]' : ''}`}
                                    style={{ flex: Math.max(pct, 0.5) }}
                                    title={`${regimeNames[r]}: ${pct.toFixed(0)}%`}
                                  >
                                    {pct >= 8 && <span className="font-mono text-[0.78rem] font-medium">{pct.toFixed(0)}%</span>}
                                  </div>
                                );
                              })}
                            </div>
                            <div className="flex justify-between font-mono text-[0.68rem] text-ink-light tracking-wide mt-1.5">
                              {sortedProbs.map(([r]) => (
                                <span key={r}>{({'strong_bull':'Str.Bull','weak_bull':'Wk.Bull','rotating_bull':'Rot.Bull','range_bound':'Range','weak_bear':'Wk.Bear','panic_crash':'Panic','recovery':'Recov.'}[r] || r)}{r === rf.current_regime ? ' ●' : ''}</span>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* All 7 regimes */}
                        <div className="border-t border-rule pt-3 space-y-0">
                          {allRegimes.map(r => {
                            const isCurrent = r === rf.current_regime;
                            const c = regimeColors[r] || { bg: 'bg-paper-deep', text: 'text-ink-mute', bar: 'bg-rule' };
                            const prob = probs[r];
                            return (
                              <div key={r} className={`flex items-center justify-between px-2 py-2 border-b border-rule last:border-b-0 ${isCurrent ? 'bg-claret/5' : ''}`}>
                                <div className="flex items-center gap-3">
                                  <div className={`w-2.5 h-2.5 ${isCurrent ? 'bg-claret' : c.bar}`} />
                                  <div>
                                    <span className={`text-sm font-medium ${isCurrent ? 'text-ink' : 'text-ink-mute'}`}>
                                      {regimeNames[r]}
                                    </span>
                                    <span className="text-xs text-ink-light ml-2">{regimeDescriptions[r]}</span>
                                  </div>
                                </div>
                                <span className={`font-mono text-sm ${isCurrent ? 'text-claret font-medium' : 'text-ink-light'}`}>
                                  {prob != null ? `${prob.toFixed(0)}%` : '—'}
                                </span>
                              </div>
                            );
                          })}
                        </div>

                        {/* Regime-adaptive parameter adjustments */}
                        {dashboardData.regime_adjustments?.changes?.length > 0 && (
                          <div className="mt-3 pt-3 border-t border-rule">
                            <p className="text-xs text-ink-mute font-medium mb-2">Active Parameter Adjustments</p>
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
                              {dashboardData.regime_adjustments.changes.map(change => (
                                <div key={change.param} className="flex items-center gap-2 text-xs">
                                  <div className={`w-1.5 h-1.5 rounded-full ${change.offset > 0 ? 'bg-ink-light' : 'bg-rule'}`} />
                                  <span className="text-ink">{change.description}</span>
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
            {/* Stats strip — hidden for served tiers (capital-scaled mirror): Portfolio Value /
                P&L / Positions / Win Rate are all manual-portfolio-derived and have no data
                under the mirror model. The book view carries capital/invested/cash instead. */}
            {!dashboardData?.tier_book && !freeTier && (
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 border-t border-b border-ink py-4 mb-6">
                <MetricCard title="Portfolio Value" value={`$${totalValue.toLocaleString(undefined, {maximumFractionDigits: 0})}`} subtitle={`Cost basis $${totalCost.toLocaleString(undefined, {maximumFractionDigits: 0})}`} />
                <MetricCard title="Open P&L" value={`${totalPnlPct >= 0 ? '+' : ''}${totalPnlPct.toFixed(1)}%`} trend={totalPnlPct >= 0 ? 'up' : 'down'} subtitle={`${totalPnlPct >= 0 ? '+' : ''}$${Math.abs(totalValue - totalCost).toLocaleString(undefined, {maximumFractionDigits: 0})} unrealized`} />
                <MetricCard title="Positions" value={<>{positions.length}<span className="text-[0.95rem] text-ink-light">&thinsp;/&thinsp;{dashboardData?.regime_adjustments?.effective?.max_positions ?? 20}</span></>} subtitle={positions.length >= (dashboardData?.regime_adjustments?.effective?.max_positions ?? 20) ? 'Max filled' : `${(dashboardData?.regime_adjustments?.effective?.max_positions ?? 20) - positions.length} open slots`} />
                <MetricCard title="Buy Signals" value={dashboardData?.market_stats?.signal_count || signalsWithLiveQuotes.length} subtitle={`${dashboardData?.market_stats?.fresh_count || 0} fresh`} />
                <MetricCard title="Win Rate" value={trades.length > 0 ? `${winRate.toFixed(0)}%` : '—'} subtitle={trades.length > 0 ? `${trades.length} trades` : '0 closed trades'} />
              </div>
            )}

            {/* Last updated timestamp. For the two-book view it's merged onto the date line
                below (saves a row); render standalone only otherwise. */}
            {dashboardData?.generated_at && dashboardData?.signal_source !== 'both' && (
              <p className="font-mono text-[0.72rem] text-ink-light text-right mb-4 -mt-2 tracking-wide">
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

            {/* Two column layout: Buy Signals | Open Positions. Served tiers (capital-scaled
                mirror) collapse to a single column — the book view IS the portfolio. */}
            <div className={`grid grid-cols-1 gap-6 ${dashboardData?.tier_book || freeTier ? '' : 'lg:grid-cols-2'}`}>
              {/* LEFT: Buy Signals (for free/proof-only users this column holds FreeProofView) */}
              <div className="overflow-hidden">
                {!dashboardData?.tier_book && !freeTier && (<div className="pb-3 border-b-2 border-ink mb-5">
                  <div className="flex items-baseline justify-between gap-3">
                    <div className="flex items-baseline gap-2 min-w-0">
                      <h2 className="font-display text-[1.25rem] font-medium text-ink tracking-tight whitespace-nowrap" style={{ fontVariationSettings: '"opsz" 48' }}>Buy Signals</h2>
                      <StrengthInfoPopover />
                      {dashboardData?.buy_signals?.filter(s => s.is_fresh).length > 0 && (
                        <span className="font-body text-[0.65rem] font-medium tracking-[0.15em] uppercase text-claret whitespace-nowrap">
                          {dashboardData.buy_signals.filter(s => s.is_fresh).length} Fresh
                        </span>
                      )}
                      <button
                        onClick={() => setSectorFilterOpen(prev => !prev)}
                        className="p-1 rounded hover:bg-paper-deep transition-colors relative"
                        title="Filter by sector"
                      >
                        <Filter size={14} className="text-ink-light" />
                        {excludedSectors.length > 0 && (
                          <span className="absolute -top-0.5 -right-0.5 w-2 h-2 bg-claret rounded-full" />
                        )}
                      </button>
                    </div>
                  <span className="font-mono text-[0.72rem] text-ink-light tracking-wide">
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
                  <em className="block font-display italic text-ink-mute text-[0.78rem] mt-1.5" style={{ fontVariationSettings: '"opsz" 24' }}>Signals only — execute via your broker</em>
                </div>)}

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
                    <div className="px-4 py-2 border-b border-rule flex flex-wrap items-center gap-1.5 bg-paper-card/50">
                      <span className="text-[10px] text-ink-light mr-1 uppercase tracking-wider">Sectors</span>
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
                                ? 'border-rule text-ink-light bg-paper-card'
                                : 'border-blue-200 text-claret bg-paper-deep'
                            }`}
                          >
                            {sector}
                            {isExcluded && count > 0 && (
                              <span className="ml-1 text-[10px] text-ink-light">({count})</span>
                            )}
                          </button>
                        );
                      })}
                      {excludedSectors.length > 0 && (
                        <button
                          onClick={() => setExcludedSectors([])}
                          className="text-[10px] text-claret hover:text-claret ml-1"
                        >
                          Reset
                        </button>
                      )}
                      <div className="ml-auto group relative">
                        <Info size={12} className="text-ink-light cursor-help" />
                        <div className="absolute right-0 bottom-full mb-1 w-52 p-2 bg-ink text-white text-[10px] rounded-lg shadow-lg opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-20">
                          Display filter only — the system scans the full universe every day regardless of this setting.
                        </div>
                      </div>
                    </div>
                  );
                })()}

                <div className={`relative ${dashboardData?.tier_book || freeTier ? '' : 'max-h-[500px] overflow-y-auto'}`}>
                  {timeTravelLoading && (
                    <div className="absolute inset-0 bg-paper-card/80 z-10 flex items-center justify-center">
                      <div className="flex flex-col items-center gap-2">
                        <Loader2 className="w-6 h-6 text-claret animate-spin" />
                        <span className="text-xs text-claret font-medium">Loading signals...</span>
                      </div>
                    </div>
                  )}
                  {freeTier ? (
                    /* FREE tier proof-only view (project_free_first_spec §2) */
                    <FreeProofView
                      data={dashboardData}
                      user={user}
                      upgradeLoading={upgradeLoading}
                      onSignIn={() => setShowLoginModal(true)}
                      onSubscribe={async (plan) => {
                        setUpgradeLoading(true);
                        try {
                          const d = await api.post('/api/billing/create-checkout', { plan });
                          if (window.gtag) window.gtag('event', 'begin_checkout', { value: plan === 'annual' ? 1099 : 129, currency: 'USD' });
                          window.location.href = d.checkout_url;
                        } catch (err) {
                          console.error('Checkout error:', err);
                          alert('Failed to start checkout. Please try again.');
                        } finally {
                          setUpgradeLoading(false);
                        }
                      }}
                    />
                  ) : (dashboardData?.tier_book || (dashboardData?.buy_signals || []).length > 0) ? (
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

                      // Continuity badge: NEW TODAY / DAY N / RE-SIGNAL.
                      // Only renders here in the signals view; monitoring intentionally skips it.
                      // whitespace-nowrap on every variant so the badge never wraps in
                      // narrow table cells (Advanced mode) — that was making the row
                      // stack 3-deep and pushing the right-side action button onto a
                      // second line. Keep badge text short for the same reason; gap-
                      // days detail stays in the data + chart modal, not the badge.
                      // "NEW today" lies when viewing the dashboard between
                      // scans (e.g. Monday morning, dashboard is from Friday).
                      // Replace "today" with the day-of-week the signal actually
                      // fired when data_date != real today. Surfaced May 18
                      // 2026 (WULF, XOM) — both showed "NEW today" on Monday
                      // but the scan that flagged them ran the prior Friday.
                      const dashDate = dashboardData?.data_date;
                      const todayStr = (() => {
                        const t = new Date();
                        const y = t.getFullYear();
                        const m = String(t.getMonth() + 1).padStart(2, '0');
                        const d = String(t.getDate()).padStart(2, '0');
                        return `${y}-${m}-${d}`;
                      })();
                      const newLabelWhen = (dashDate && dashDate !== todayStr)
                        ? (() => {
                            const [yy, mm, dd] = dashDate.split('-').map(Number);
                            const day = new Date(yy, mm - 1, dd)
                              .toLocaleDateString('en-US', { weekday: 'short' });
                            return day.toUpperCase();  // MON, TUE, ...
                          })()
                        : 'TODAY';

                      const renderContinuityBadge = (s) => {
                        const c = s.continuity;
                        if (!c) return null;
                        const base = "font-mono text-[0.62rem] tracking-[0.18em] uppercase ml-2 whitespace-nowrap";
                        // 'Re-signal' fires only on Day 1 of the return — the day the
                        // name actually came back to the list. After that it's a
                        // continuing run (Day 2, Day 3…) even though is_resignal
                        // stays true for the whole run's lifetime.
                        if (c.is_resignal && c.is_new_today) {
                          // "Re-sig" shortened from "Re-signal" — same meaning,
                          // fewer chars; otherwise the badge + a 3-digit price
                          // (e.g. XOM at $160) overflows the Advanced-mode
                          // table beyond viewport, clipping + Entry on the right.
                          return <span className={`${base} text-claret-light`}>Re-sig {newLabelWhen === 'TODAY' ? '' : newLabelWhen}</span>;
                        }
                        if (c.is_new_today) {
                          return <span className={`${base} text-claret font-medium`}>NEW {newLabelWhen}</span>;
                        }
                        if ((c.consecutive_days || 0) >= 2) {
                          return <span className={`${base} text-ink-mute`}>Day {c.consecutive_days}</span>;
                        }
                        return null;
                      };

                      // Actionability ("did I miss the window?"). Only flag the case that
                      // matters — a name that's run too far to mirror cleanly. Preserver
                      // (trailing stop): extended = chased past its signal. Maximizer
                      // (29-day time-stop): 'late' = too few hold days left to initiate.
                      // Fresh/actionable names get no chip — absence means clean to enter.
                      const renderActionBadge = (s) => {
                        if (s.entry_status !== 'extended') return null;
                        const base = "font-mono text-[0.58rem] tracking-[0.16em] uppercase ml-2 whitespace-nowrap text-claret border border-claret/40 px-1.5 py-0.5";
                        const isBreakout = s.source === 'breakout';
                        const txt = isBreakout ? 'Late' : 'Extended';
                        const title = isBreakout
                          ? `Only ${s.days_left}d left in the hold — late to initiate a fresh mirror`
                          : (s.move_since_signal_pct != null
                              ? `Run +${Math.round(s.move_since_signal_pct)}% past its signal — the trade isn't broken, but don't chase; wait for a pullback or size down`
                              : `Run well past its signal — don't chase`);
                        return <span className={base} title={title}>{txt}</span>;
                      };

                      const renderSimpleSignal = (s) => {
                        const isBreakout = s.source === 'breakout';
                        const label = s.signal_strength_label || (() => {
                          const score = s.ensemble_score || 0;
                          if (score >= 88) return 'Very Strong';
                          if (score >= 75) return 'Strong';
                          if (score >= 61) return 'Moderate';
                          return 'Weak';
                        })();
                        return (
                          <div
                            key={s.symbol}
                            className={`px-4 py-3 cursor-pointer transition-colors border-b border-rule ${
                              s.is_fresh ? 'border-l-4 border-l-claret' : 'hover:bg-paper-card'
                            }`}
                            style={{
                              display: 'grid',
                              gridTemplateColumns: 'minmax(0, 1fr) 80px 140px 110px',
                              alignItems: 'center',
                              gap: '0.75rem',
                            }}
                            onClick={() => {
                              logEvent('signal_click', { symbol: s.symbol, mode: 'simple', is_fresh: s.is_fresh, label });
                              setChartModal({ type: 'signal', data: s, symbol: s.symbol });
                            }}
                          >
                            <div className="flex items-baseline gap-2 min-w-0">
                              {isHeld(s.symbol) && <span title="In your portfolio" className="text-positive text-[0.62rem] self-center shrink-0" aria-label="You hold this">●</span>}
                              <span className="font-display text-[1.1rem] font-medium tracking-tight truncate" style={{ fontVariationSettings: '"opsz" 48' }}>{s.symbol}</span>
                              {isBreakout && <span className="font-mono text-[0.58rem] tracking-[0.16em] uppercase text-claret border border-claret/40 px-1.5 py-0.5 whitespace-nowrap">Breakout</span>}
                              {!isBreakout && renderContinuityBadge(s)}
                              {renderActionBadge(s)}
                            </div>
                            <span className="font-mono text-[0.88rem] text-ink-mute text-right">${s.price?.toFixed(2)}</span>
                            {isBreakout ? (
                              /* Breakout: show the 29-day hold countdown, not a momentum score */
                              <span className="font-mono text-[0.7rem] tracking-[0.1em] uppercase text-ink-mute text-right whitespace-nowrap">
                                {s.status === 'holding'
                                  ? <><span className="text-ink">Day {s.days_held}/{s.hold_days}</span> · {s.days_left}d left</>
                                  : <>New · hold {s.hold_days}d</>}
                              </span>
                            ) : (
                              <span className="font-mono text-[0.7rem] tracking-[0.1em] uppercase text-claret text-right whitespace-nowrap">
                                <span className="text-ink">{Math.round(s.ensemble_score || 0)}</span> · {label}
                              </span>
                            )}
                            <div className="text-right">
                              {s.in_user_position ? (
                                <span className="font-body text-[0.7rem] font-medium tracking-[0.12em] uppercase px-2.5 py-1 bg-paper-card text-ink-mute border border-rule whitespace-nowrap inline-block">Held</span>
                              ) : isBreakout && s.status === 'holding' ? (
                                <span className="font-body text-[0.7rem] font-medium tracking-[0.12em] uppercase px-2.5 py-1 bg-paper-card text-ink-mute border border-rule whitespace-nowrap inline-block">Mirror</span>
                              ) : dashboardData?.tier_book ? (
                                /* Served tiers ("just mirror the book"): signals are informational —
                                   no manual +Entry. Row stays click-to-chart. */
                                s.is_fresh ? <span className="font-body text-[0.62rem] font-medium tracking-[0.14em] uppercase text-ink-light whitespace-nowrap inline-block">Signal</span> : null
                              ) : s.is_fresh && (
                                <span className="font-body text-[0.7rem] font-medium tracking-[0.12em] uppercase px-2.5 py-1 bg-ink text-paper border border-ink hover:bg-claret hover:border-claret transition-colors whitespace-nowrap inline-block">+ Entry</span>
                              )}
                            </div>
                          </div>
                        );
                      };

                      const renderAdvancedSignal = (s) => {
                        const isBreakout = s.source === 'breakout';
                        return (
                        <tr
                          key={s.symbol}
                          className={`cursor-pointer transition-colors ${
                            s.is_fresh
                              ? 'border-l-4 border-l-claret'
                              : 'hover:bg-paper-card'
                          }`}
                          onClick={() => {
                            logEvent('signal_click', { symbol: s.symbol, mode: 'advanced', is_fresh: s.is_fresh });
                            setChartModal({ type: 'signal', data: s, symbol: s.symbol });
                          }}
                        >
                          <td className="px-3 py-3">
                            {isHeld(s.symbol) && <span title="In your portfolio" className="text-positive text-[0.62rem] mr-1.5" aria-label="You hold this">●</span>}
                            <span className="font-display text-[1.05rem] font-medium tracking-tight" style={{ fontVariationSettings: '"opsz" 48' }}>
                              {s.symbol}
                            </span>
                            {isBreakout
                              ? <span className="font-mono text-[0.58rem] tracking-[0.16em] uppercase text-claret border border-claret/40 px-1.5 py-0.5 ml-2 whitespace-nowrap">Breakout</span>
                              : renderContinuityBadge(s)}
                            {renderActionBadge(s)}
                          </td>
                          <td className="px-3 py-3 text-right font-mono text-[0.88rem]">${s.price?.toFixed(2)}</td>
                          <td className="px-3 py-3 text-right font-mono text-[0.88rem] text-positive">
                            {isBreakout ? <span className="text-ink-mute">—</span> : <>+{s.pct_above_dwap?.toFixed(1)}%</>}
                          </td>
                          <td className="px-3 py-3 text-center font-mono text-[0.95rem] text-ink">
                            {isBreakout
                              ? (s.status === 'holding' ? `${s.days_held}/${s.hold_days}` : <span className="text-ink-mute">—</span>)
                              : Math.round(s.ensemble_score || 0)}
                          </td>
                          <td className="px-3 py-2.5 text-center">
                            {isBreakout ? (
                              <span className="font-mono text-[0.7rem] tracking-[0.12em] uppercase text-claret whitespace-nowrap">
                                {s.status === 'holding' ? `${s.days_left}d to exit` : `Hold ${s.hold_days}d`}
                              </span>
                            ) : (() => {
                              const label = s.signal_strength_label || (() => {
                                const score = s.ensemble_score || 0;
                                if (score >= 88) return 'Very Strong';
                                if (score >= 75) return 'Strong';
                                if (score >= 61) return 'Moderate';
                                return 'Weak';
                              })();
                              return <span className="font-mono text-[0.7rem] tracking-[0.12em] uppercase text-claret">{label}</span>;
                            })()}
                          </td>
                          {/* Trailing action column — RETIRED for mirror/served-tier users: no
                              manual record-entry workflow, so the "Signal"/"+Entry" column is dropped. */}
                          {!dashboardData?.tier_book && (
                          <td className="px-3 py-3 text-center">
                            {s.in_user_position ? (
                              <span className="font-body text-[0.7rem] font-medium tracking-[0.1em] uppercase px-2.5 py-1 bg-paper-card text-ink-mute border border-rule whitespace-nowrap inline-block">
                                Held
                              </span>
                            ) : isBreakout && s.status === 'holding' ? (
                              <span className="font-body text-[0.7rem] font-medium tracking-[0.1em] uppercase px-2.5 py-1 bg-paper-card text-ink-mute border border-rule whitespace-nowrap inline-block">
                                Mirror
                              </span>
                            ) : dashboardData?.tier_book ? (
                              /* Served tiers ("just mirror the book"): informational, no manual +Entry. */
                              s.is_fresh ? <span className="font-body text-[0.62rem] font-medium tracking-[0.12em] uppercase text-ink-light whitespace-nowrap inline-block">Signal</span> : null
                            ) : s.is_fresh && (
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setChartModal({ type: 'signal', data: s, symbol: s.symbol });
                                }}
                                className="font-body text-[0.7rem] font-medium tracking-[0.1em] uppercase px-2.5 py-1 bg-ink text-paper border border-ink hover:bg-claret hover:border-claret transition-colors whitespace-nowrap"
                              >
                                + Entry
                              </button>
                            )}
                          </td>
                          )}
                        </tr>
                        );
                      };

                      return (
                        <div>
                          {/* AI Market Briefing — sticky at the top of the signals
                              scroll area so the system's editorial voice stays
                              visible while subscribers scan the list. z-10 to
                              sit above the rows but well below the popover
                              portal (z-9999). bg-paper-card matches its block
                              treatment; an outer wrapper carries the paper
                              background so the briefing doesn't show row content
                              bleeding through when scrolled. */}
                          {/* Daily market read. For a served Maximizer (signal_source==='both')
                              the read lives per-book (each TierBookView has its own), so up top we
                              keep ONLY a slim date line — the redundant briefing box is dropped.
                              Preserver keeps the full briefing (date + prose). */}
                          {(() => {
                            const dashDate = dashboardData?.data_date;
                            const todayStr = (() => {
                              const t = new Date();
                              return `${t.getFullYear()}-${String(t.getMonth() + 1).padStart(2, '0')}-${String(t.getDate()).padStart(2, '0')}`;
                            })();
                            const dateLabel = (() => {
                              if (!dashDate) {
                                return `${new Date().toLocaleDateString('en-US', { weekday: 'long' })} · ${new Date().toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}`;
                              }
                              const [yy, mm, dd] = dashDate.split('-').map(Number);
                              const date = new Date(yy, mm - 1, dd);
                              const dayName = date.toLocaleDateString('en-US', { weekday: 'long' });
                              const monthDay = date.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' });
                              return dashDate !== todayStr ? `${dayName} · ${monthDay} (from ${dayName}'s close)` : `${dayName} · ${monthDay}`;
                            })();
                            if (dashboardData?.signal_source === 'both') {
                              // Date tag (left) + Last updated (right) on ONE row — no wasted vertical space.
                              const lu = (() => {
                                const raw = dashboardData?.generated_at;
                                if (!raw) return '';
                                const d = new Date(raw.endsWith('Z') ? raw : raw + 'Z');
                                if (isNaN(d.getTime())) return '';
                                const now = new Date();
                                const time = d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
                                if (d.toDateString() === now.toDateString()) return `Today at ${time}`;
                                const y = new Date(now); y.setDate(y.getDate() - 1);
                                if (d.toDateString() === y.toDateString()) return `Yesterday at ${time}`;
                                return `${formatDate(raw)} at ${time}`;
                              })();
                              return (
                                <div className="pt-3 pb-1 flex items-baseline justify-between gap-3">
                                  <span className="font-body text-[0.64rem] font-medium tracking-[0.22em] uppercase text-ink-mute">{dateLabel}</span>
                                  {lu && <span className="font-mono text-[0.72rem] text-ink-light tracking-wide whitespace-nowrap">Last updated: {lu}</span>}
                                </div>
                              );
                            }
                            if (!dashboardData?.market_context) return null;
                            return (
                              <div className="sticky top-0 z-10 bg-paper px-4 pt-4 pb-2 border-b border-rule">
                                <div className="py-4 px-5 bg-paper-card border-l-2 border-claret" style={{ fontVariationSettings: '"opsz" 24' }}>
                                  <span className="block font-body text-[0.64rem] font-medium tracking-[0.22em] uppercase text-ink-mute mb-2 not-italic">{dateLabel}</span>
                                  <p className="font-display italic text-[1rem] text-ink leading-[1.6]">{dashboardData.market_context}</p>
                                </div>
                              </div>
                            );
                          })()}

                          {/* ADDITIVE MAXIMIZER (signal_source === 'both'): "YOUR BOOKS" — both
                              capital-scaled MIRROR books side-by-side (stacks on mobile). Preserver
                              base book LEFT, Maximizer breakout book RIGHT — both are HOLDINGS, so
                              they're symmetric. One shared capital control (on the left book) drives
                              both. This is the canonical "just mirror the book" view; the Signals
                              feed below is the optional deviation layer. */}
                          {dashboardData?.signal_source === 'both' && dashboardData?.tier_book && (() => {
                            // One capital control → rescale BOTH books client-side (linear in capital)
                            // for instant preview; the next fetch confirms server-side.
                            const setSharedCapital = async (val) => {
                              try {
                                await api.patch('/api/auth/me/portfolio-size', { portfolio_size: val });
                                await refreshUser();
                                setDashboardData(prev => {
                                  if (!prev) return prev;
                                  const rescale = (bk) => {
                                    if (!bk) return bk;
                                    const f = val / (bk.capital || val);
                                    return {
                                      ...bk, capital: val,
                                      invested_value: Math.round((bk.invested_value || 0) * f),
                                      cash_value: Math.round((bk.cash_value || 0) * f),
                                      holdings: (bk.holdings || []).map(h => ({
                                        ...h,
                                        implied_shares: +((h.implied_shares || 0) * f).toFixed(2),
                                        implied_value: Math.round((h.implied_value || 0) * f),
                                      })),
                                    };
                                  };
                                  return { ...prev, preserver_book: rescale(prev.preserver_book), tier_book: rescale(prev.tier_book) };
                                });
                              } catch (e) { console.error('set capital failed', e); }
                            };
                            // Each book's candidate list now lives IN its own column under the book
                            // (fills the empty gap under the shorter Maximizer column + makes "which
                            // book" unambiguous). Preserver = momentum names not held; Maximizer =
                            // breakout radar (approaching a trigger). The old full-width Signals
                            // section is suppressed for 'both' (below) so these don't duplicate.
                            // Rotation watch — Maximizer holdings nearest their 29-day time-stop,
                            // re-sorted by URGENCY (the book table is sorted by weight, so the
                            // soonest-to-exit name is otherwise buried). 100% live data from the
                            // book's own hold-clocks — no walk-forward. Once tier_fills logs real
                            // sells (~mid-Aug, when the Jul-15 buys hit day 29) this block splits:
                            // Rotation watch (upcoming) | Recently closed (realized).
                            // Full urgency-sorted list; the visible count (rotRows) is measured so
                            // the card fills to the Preserver column's bottom with no wasted space.
                            const rotationAll = [...(dashboardData.tier_book?.holdings || [])]
                              .filter(h => h.days_left != null)
                              .sort((a, b) => a.days_left - b.days_left);
                            const rotation = rotationAll.slice(0, rotRows);
                            const recentlyClosed = dashboardData.maximizer_recent_exits || []; // populated once real sells exist
                            return (
                              <div className="pt-4">
                                <div className="flex items-baseline justify-between mb-3">
                                  <h2 className="font-display text-[1.15rem] font-medium tracking-tight text-ink" style={{ fontVariationSettings: '"opsz" 48' }}>Your Books</h2>
                                  <span className="font-display italic text-[0.82rem] text-ink-mute" style={{ fontVariationSettings: '"opsz" 24' }}>auto-mirrored to your capital</span>
                                </div>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-start">
                                  {/* LEFT — Preserver book (candidate signals are full-width BELOW,
                                      not in-column: an in-column list made the left run far longer
                                      than the right and opened a canyon under Maximizer).
                                      data-books-left: the measured reference height Rotation watch fills to. */}
                                  <div data-books-left>
                                    <TierBookView
                                      book={dashboardData.preserver_book}
                                      isHeld={isHeld}
                                      compact
                                      marketNote={dashboardData.preserver_market_context}
                                      onRowClick={(h) => setChartModal({ type: 'position', data: h, symbol: h.symbol })}
                                      onSetCapital={setSharedCapital}
                                    />
                                  </div>
                                  {/* RIGHT — Maximizer book + Rotation watch (stays in this column).
                                      Rotation watch shows a MEASURED number of rows (rotRows) so it
                                      reaches the Preserver column's bottom — no wasted space. */}
                                  <div>
                                    <TierBookView
                                      book={dashboardData.tier_book}
                                      isHeld={isHeld}
                                      actions={dashboardData.todays_actions}
                                      marketNote={dashboardData.maximizer_market_context}
                                      hideCapitalEditor
                                      onRowClick={(h) => setChartModal({ type: 'position', data: h, symbol: h.symbol })}
                                    />
                                    {/* Rotation watch — nearest time-stops (live hold-clocks). Tight top
                                        margin; row count measured to fill. Splits into a 2-up grid once
                                        Recently closed has real sells. */}
                                    {rotation.length > 0 && (
                                      <div className={`mt-2 grid grid-cols-1 ${recentlyClosed.length > 0 ? 'sm:grid-cols-2' : ''} gap-3`}>
                                        <div className="border border-rule rounded bg-paper-card overflow-hidden">
                                          <div className="px-4 py-2.5 border-b border-rule">
                                            <span className="font-display text-[0.9rem] font-medium tracking-tight">Rotation watch</span>
                                            <p className="font-display italic text-[0.78rem] text-ink-mute mt-0.5" style={{ fontVariationSettings: '"opsz" 24' }}>Nearest the 29-day time-stop &mdash; the book rotates these next.</p>
                                          </div>
                                          <div className="divide-y divide-rule" data-rot-list data-rot-max={rotationAll.length}>
                                            {rotation.map((h) => {
                                              const soon = h.days_left <= 5;
                                              return (
                                                <div key={h.symbol} data-rot-row
                                                     onClick={() => setChartModal({ type: 'position', data: h, symbol: h.symbol })}
                                                     className="px-4 py-3 flex items-center justify-between cursor-pointer hover:bg-paper-deep transition-colors">
                                                  <span className="font-display text-[1rem] font-medium text-ink" style={{ fontVariationSettings: '"opsz" 32' }}>{h.symbol}</span>
                                                  <span className={`font-mono text-[0.72rem] ${soon ? 'text-claret' : 'text-ink-mute'}`}>day {h.days_held}/{h.hold_days} &middot; ~{h.days_left}d</span>
                                                </div>
                                              );
                                            })}
                                          </div>
                                        </div>
                                        {recentlyClosed.length > 0 && (
                                          <div className="border border-rule rounded bg-paper-card overflow-hidden">
                                            <div className="px-4 py-2.5 border-b border-rule">
                                              <span className="font-display text-[0.9rem] font-medium tracking-tight">Recently closed</span>
                                              <p className="font-display italic text-[0.78rem] text-ink-mute mt-0.5" style={{ fontVariationSettings: '"opsz" 24' }}>Last rotations &mdash; realized result.</p>
                                            </div>
                                            <div className="divide-y divide-rule">
                                              {recentlyClosed.slice(0, 5).map((c) => (
                                                <div key={`${c.symbol}-${c.fill_date}`}
                                                     className="px-4 py-3 flex items-center justify-between">
                                                  <span className="font-display text-[1rem] font-medium text-ink" style={{ fontVariationSettings: '"opsz" 32' }}>{c.symbol}</span>
                                                  <span className="font-mono text-[0.72rem] text-ink-mute">
                                                    {c.reason === 'stop' ? 'stopped out' : `day ${c.days_held}`} &middot;{' '}
                                                    <span className={c.pnl_pct >= 0 ? 'text-positive' : 'text-negative'}>{c.pnl_pct >= 0 ? '+' : ''}{c.pnl_pct}%</span>
                                                  </span>
                                                </div>
                                              ))}
                                            </div>
                                          </div>
                                        )}
                                      </div>
                                    )}
                                  </div>
                                </div>
                              </div>
                            );
                          })()}

                          {/* Capital-scaled MIRROR book — the primary portfolio view for a
                              served tier (implied holdings scaled to portfolio_size). Renders
                              above the signal list; when present it IS the portfolio.
                              Suppressed in additive 'both' mode (the 2-col section above shows
                              the breakout book instead). */}
                          {dashboardData?.tier_book && dashboardData?.signal_source !== 'both' && (
                            <div className="px-4 pt-4">
                              <TierBookView
                                book={tierBookLive || dashboardData.tier_book}
                                isHeld={isHeld}
                                radar={dashboardData.breakout_radar}
                                actions={dashboardData.todays_actions}
                                onRowClick={(h) => setChartModal({ type: 'position', data: h, symbol: h.symbol })}
                                onSetCapital={async (val) => {
                                  try {
                                    await api.patch('/api/auth/me/portfolio-size', { portfolio_size: val });
                                    await refreshUser();
                                    // Rescale the book client-side (everything is linear in capital)
                                    // so the preview updates instantly; the next fetch confirms it.
                                    setDashboardData(prev => {
                                      const tb = prev?.tier_book;
                                      if (!tb) return prev;
                                      const f = val / (tb.capital || val);
                                      return { ...prev, tier_book: {
                                        ...tb, capital: val,
                                        invested_value: Math.round((tb.invested_value || 0) * f),
                                        cash_value: Math.round((tb.cash_value || 0) * f),
                                        holdings: (tb.holdings || []).map(h => ({
                                          ...h,
                                          implied_shares: +(h.implied_shares * f).toFixed(2),
                                          implied_value: Math.round(h.implied_value * f),
                                        })),
                                      } };
                                    });
                                  } catch (e) { console.error('set capital failed', e); }
                                }}
                              />
                            </div>
                          )}

                          {/* Tier note — expectation-setter for the active regime/tier
                              (e.g. "your Maximizer book is hunting breakouts, held ~29
                              trading days" or the Preserver capitulation posture). Served
                              by the tier-aware dashboard path; absent => nothing renders. */}
                          {dashboardData?.tier_note && (
                            <div className="px-3 pt-3">
                              <div className="py-3 px-4 bg-claret/5 border-l-2 border-claret font-display italic text-[0.9rem] text-ink leading-[1.55]" style={{ fontVariationSettings: '"opsz" 24' }}>
                                {dashboardData.tier_note}
                              </div>
                            </div>
                          )}

                          {/* Winding Down — positions still held from a PREVIOUS tier setting
                              (e.g. breakout names after toggling Maximizer off). Kept visible with
                              their own source-scoped exit guidance until they siphon off; new entries
                              follow the mirror book above. Without this, served tiers hide the user's
                              real positions and these would vanish (Erik requirement Aug 6). */}
                          {dashboardData?.tier_book && (() => {
                            const servedSource = dashboardData?.signal_source || 'preserver';
                            const posBook = (p) => (p.source === 'breakout' || p.exit_rule === 'hold' || p.days_left != null || p.hold_days != null) ? 'breakout' : 'preserver';
                            const windingDown = (guidanceWithLiveQuotes || []).filter(p => posBook(p) !== servedSource);
                            if (windingDown.length === 0) return null;
                            const otherLabel = servedSource === 'preserver' ? 'their 29-day breakout exit' : 'the 30% trailing stop';
                            return (
                              <div className="px-4 pt-4">
                                <div className="border border-claret/30 rounded bg-paper-card">
                                  <div className="px-4 sm:px-5 py-3 border-b border-rule">
                                    <h3 className="font-display text-[1.05rem] font-medium text-ink" style={{ fontVariationSettings: '"opsz" 48' }}>
                                      Winding Down <span className="font-mono text-[0.6rem] tracking-[0.16em] uppercase text-ink-mute align-middle ml-1">from your previous setting</span>
                                    </h3>
                                    <p className="font-display italic text-[0.82rem] text-ink-mute mt-1 leading-snug" style={{ fontVariationSettings: '"opsz" 24' }}>
                                      {windingDown.length} position{windingDown.length !== 1 ? 's' : ''} you still hold from before &mdash; keep {windingDown.length !== 1 ? 'them' : 'it'} to {otherLabel}. Not in your current book; new entries follow the book above.
                                    </p>
                                  </div>
                                  <div className="divide-y divide-rule">
                                    {windingDown.map((p) => {
                                      const pnl = (p.pnl_pct ?? ((p.current_price - p.entry_price) / p.entry_price * 100)) || 0;
                                      const isBreakout = posBook(p) === 'breakout';
                                      const exitTxt = isBreakout
                                        ? `day ${p.days_held ?? '—'}/${p.hold_days ?? 29}${p.days_left != null ? ` · ${p.days_left}d left` : ''}`
                                        : `30% trail${p.trailing_stop_level != null ? ` · $${Number(p.trailing_stop_level).toFixed(2)}` : ''}`;
                                      return (
                                        <div
                                          key={p.id || p.symbol}
                                          onClick={() => setChartModal({ type: 'position', data: p, symbol: p.symbol })}
                                          className="px-4 sm:px-5 py-3 flex items-center justify-between cursor-pointer hover:bg-paper-deep transition-colors"
                                        >
                                          <div className="flex items-baseline gap-2 min-w-0">
                                            <span className="font-display text-[1.05rem] font-medium text-ink" style={{ fontVariationSettings: '"opsz" 32' }}>{p.symbol}</span>
                                            <span className="font-mono text-[0.6rem] tracking-[0.14em] uppercase text-claret border border-claret/40 px-1.5 py-0.5 whitespace-nowrap">{isBreakout ? 'Breakout' : 'Preserver'}</span>
                                          </div>
                                          <div className="flex items-center gap-4 whitespace-nowrap">
                                            <span className="font-mono text-[0.7rem] text-ink-mute">{exitTxt}</span>
                                            <span className={`font-mono text-[0.9rem] ${pnl >= 0 ? 'text-positive' : 'text-negative'}`}>{pnl >= 0 ? '+' : ''}{pnl.toFixed(1)}%</span>
                                          </div>
                                        </div>
                                      );
                                    })}
                                  </div>
                                </div>
                              </div>
                            );
                          })()}

                          {/* Other Signals — served tiers: ensemble names that pass our
                              screen but are NOT in our book. Kept (not discarded) so a
                              subscriber running their OWN book off our signals — different
                              entries = their own diversification, a hedge on our timing —
                              still gets them. Framed so it never reads as a book holding.
                              Breakout-tier signals ARE the book, so they're excluded here. */}
                          {dashboardData?.tier_book && (() => {
                            const other = [...freshSignals, ...monitoringSignals].filter(s => s.source !== 'breakout');
                            if (other.length === 0) return null;
                            return (
                              <div className="mt-2">
                                <div className="px-3 py-2.5 border-t border-rule flex items-center justify-between">
                                  <span className="font-display text-[0.95rem] font-medium tracking-tight">Preserver signals <em className="font-display italic text-ink-light font-normal">({other.length})</em></span>
                                  <span className="font-display italic text-[0.85rem] text-ink-mute" style={{ fontVariationSettings: '"opsz" 24' }}>Not in the Preserver book &mdash; but could be in yours.</span>
                                </div>
                                {viewMode === 'simple' ? (
                                  <div className="divide-y divide-rule">
                                    {other.map(renderSimpleSignal)}
                                  </div>
                                ) : (
                                  <div className="overflow-x-auto">
                                    <table className="w-full border-collapse" style={{ fontFeatureSettings: '"tnum"' }}>
                                      <thead>
                                        <tr>
                                          <th className="px-3 py-2 text-left font-body text-[0.62rem] font-medium tracking-[0.2em] uppercase text-ink-mute border-b border-ink">Symbol</th>
                                          <th className="px-3 py-2 text-right font-body text-[0.62rem] font-medium tracking-[0.2em] uppercase text-ink-mute border-b border-ink">Price</th>
                                          <th className="px-3 py-2 text-right font-body text-[0.62rem] font-medium tracking-[0.2em] uppercase text-ink-mute border-b border-ink">Breakout</th>
                                          <th className="px-3 py-2 text-center font-body text-[0.62rem] font-medium tracking-[0.2em] uppercase text-ink-mute border-b border-ink">Score</th>
                                          <th className="px-3 py-2 text-center font-body text-[0.62rem] font-medium tracking-[0.2em] uppercase text-ink-mute border-b border-ink whitespace-nowrap">Strength</th>
                                          {!dashboardData?.tier_book && <th className="px-3 py-2 text-center font-body text-[0.62rem] font-medium tracking-[0.2em] uppercase text-ink-mute border-b border-ink"></th>}
                                        </tr>
                                      </thead>
                                      <tbody>
                                        {other.map(renderAdvancedSignal)}
                                      </tbody>
                                    </table>
                                  </div>
                                )}
                              </div>
                            );
                          })()}

                          {/* Maximizer breakout candidates — names approaching a 50-day-high
                              breakout (the radar). Not yet in the Maximizer book; the second book's
                              opportunity layer, so the Signals area shows BOTH books' deviations. */}
                          {dashboardData?.tier_book && (dashboardData?.breakout_radar || []).length > 0 && (
                            <div className="mt-2">
                              <div className="px-3 py-2.5 border-t border-rule flex items-center justify-between">
                                <span className="font-display text-[0.95rem] font-medium tracking-tight text-claret">&#9670; Maximizer breakout candidates <em className="font-display italic text-ink-light font-normal">({dashboardData.breakout_radar.length})</em></span>
                                <span className="font-display italic text-[0.85rem] text-ink-mute" style={{ fontVariationSettings: '"opsz" 24' }}>Approaching a breakout trigger.</span>
                              </div>
                              {viewMode === 'simple' ? (
                                <div className="divide-y divide-rule">
                                  {dashboardData.breakout_radar.map((r) => (
                                    <div key={r.symbol}
                                         onClick={() => setChartModal({ type: 'signal', data: { symbol: r.symbol, price: r.price, source: 'breakout' }, symbol: r.symbol })}
                                         className="px-3 py-3 flex items-center justify-between cursor-pointer hover:bg-paper-deep transition-colors">
                                      <span className="font-display text-[1rem] font-medium text-ink" style={{ fontVariationSettings: '"opsz" 32' }}>{r.symbol}</span>
                                      <span className="font-mono text-[0.72rem] text-ink-mute">{r.trigger != null ? `buy > $${r.trigger}` : `${r.pct_below_50d_high}% below high`}{r.pct_to_trigger != null ? ` · ${r.pct_to_trigger}% to go` : ''}</span>
                                    </div>
                                  ))}
                                </div>
                              ) : (
                                <div className="overflow-x-auto">
                                  <table className="w-full border-collapse" style={{ fontFeatureSettings: '"tnum"' }}>
                                    <thead>
                                      <tr>
                                        <th className="px-3 py-2 text-left font-body text-[0.62rem] font-medium tracking-[0.2em] uppercase text-ink-mute border-b border-ink">Symbol</th>
                                        <th className="px-3 py-2 text-right font-body text-[0.62rem] font-medium tracking-[0.2em] uppercase text-ink-mute border-b border-ink">Price</th>
                                        <th className="px-3 py-2 text-right font-body text-[0.62rem] font-medium tracking-[0.2em] uppercase text-ink-mute border-b border-ink">Trigger</th>
                                        <th className="px-3 py-2 text-right font-body text-[0.62rem] font-medium tracking-[0.2em] uppercase text-ink-mute border-b border-ink whitespace-nowrap">% to go</th>
                                        <th className="px-3 py-2 text-center font-body text-[0.62rem] font-medium tracking-[0.2em] uppercase text-ink-mute border-b border-ink whitespace-nowrap">6-mo mom</th>
                                        <th className="px-3 py-2 text-center font-body text-[0.62rem] font-medium tracking-[0.2em] uppercase text-ink-mute border-b border-ink">Vol</th>
                                      </tr>
                                    </thead>
                                    <tbody>
                                      {dashboardData.breakout_radar.map((r) => (
                                        <tr key={r.symbol}
                                            onClick={() => setChartModal({ type: 'signal', data: { symbol: r.symbol, price: r.price, source: 'breakout' }, symbol: r.symbol })}
                                            className="cursor-pointer hover:bg-paper-deep transition-colors border-b border-rule">
                                          <td className="px-3 py-3 font-display text-[1rem] font-medium text-ink" style={{ fontVariationSettings: '"opsz" 32' }}>{r.symbol}</td>
                                          <td className="px-3 py-3 text-right font-mono text-[0.8rem] text-ink">${r.price}</td>
                                          <td className="px-3 py-3 text-right font-mono text-[0.8rem] text-claret">{r.trigger != null ? `$${r.trigger}` : '—'}</td>
                                          <td className="px-3 py-3 text-right font-mono text-[0.8rem] text-ink-mute">{r.pct_to_trigger != null ? `${r.pct_to_trigger}%` : '—'}</td>
                                          <td className="px-3 py-3 text-center font-mono text-[0.8rem] text-ink">{r.mom_6mo_pct != null ? `${r.mom_6mo_pct >= 0 ? '+' : ''}${r.mom_6mo_pct}%` : '—'}</td>
                                          <td className="px-3 py-3 text-center font-mono text-[0.8rem] text-ink-mute">{r.vol_ratio}&times;</td>
                                        </tr>
                                      ))}
                                    </tbody>
                                  </table>
                                </div>
                              )}
                            </div>
                          )}

                          {/* Served tiers: calm signals empty-state on a quiet day. The books
                              above always render now (redesign: books-on-top, unconditional for a
                              served user), so when BOTH deviation groups are empty we say so here
                              instead of leaving a blank gap. */}
                          {dashboardData?.tier_book
                            && [...freshSignals, ...monitoringSignals].filter(s => s.source !== 'breakout').length === 0
                            && (dashboardData?.breakout_radar || []).length === 0 && (
                            <div className="px-4 py-6 mt-2 border-t border-rule text-center font-display italic text-ink-mute text-sm" style={{ fontVariationSettings: '"opsz" 24' }}>
                              No new signals today &mdash; the system is watching.
                            </div>
                          )}

                          {/* Buy Signals section (fresh) — hidden for served tiers; the
                              capital-scaled mirror book replaces the pick-and-add flow. */}
                          {!dashboardData?.tier_book && (freshSignals.length > 0 ? (
                            <div>
                              <div className="px-4 py-2.5 border-b border-rule flex items-center justify-between">
                                <span className="font-display text-[0.95rem] font-medium tracking-tight">Buy Signals <em className="font-display italic text-ink-light font-normal">({freshSignals.length})</em></span>
                                <span className="font-display italic text-[0.85rem] text-claret" style={{ fontVariationSettings: '"opsz" 24' }}>Consider adding</span>
                              </div>
                              {viewMode === 'simple' ? (
                                <div className="divide-y divide-rule">
                                  {freshSignals.map(renderSimpleSignal)}
                                </div>
                              ) : (
                                <div className="overflow-x-auto">
                                <table className="w-full border-collapse" style={{ fontFeatureSettings: '"tnum"' }}>
                                  <thead>
                                    <tr>
                                      <th className="px-3 py-2 text-left font-body text-[0.62rem] font-medium tracking-[0.2em] uppercase text-ink-mute border-b border-ink">Symbol</th>
                                      <th className="px-3 py-2 text-right font-body text-[0.62rem] font-medium tracking-[0.2em] uppercase text-ink-mute border-b border-ink">Price</th>
                                      <th className="px-3 py-2 text-right font-body text-[0.62rem] font-medium tracking-[0.2em] uppercase text-ink-mute border-b border-ink">Breakout</th>
                                      <th className="px-3 py-2 text-center font-body text-[0.62rem] font-medium tracking-[0.2em] uppercase text-ink-mute border-b border-ink">Score</th>
                                      <th className="px-3 py-2 text-center font-body text-[0.62rem] font-medium tracking-[0.2em] uppercase text-ink-mute border-b border-ink whitespace-nowrap">
                                        Strength
                                        <span className="ml-1.5"><StrengthInfoPopover /></span>
                                      </th>
                                      <th className="px-3 py-2 text-center font-body text-[0.62rem] font-medium tracking-[0.2em] uppercase text-ink-mute border-b border-ink"></th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {freshSignals.map(renderAdvancedSignal)}
                                  </tbody>
                                </table>
                                </div>
                              )}
                            </div>
                          ) : (
                            <div className="px-4 py-4 text-sm bg-paper-card border-b border-rule">
                              {heldFreshCount > 0 ? (
                                <p className="text-center text-ink-mute">{`Today's ${heldFreshCount} fresh signal${heldFreshCount > 1 ? 's are' : ' is'} already in your positions`}</p>
                              ) : (
                                <>
                                  {(() => {
                                    const day = new Date().getDay();
                                    const isWeekend = day === 0 || day === 6;
                                    const dayName = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'][day];
                                    if (isWeekend) {
                                      return <p className="text-center text-ink-mute">Have a nice {dayName}! Markets reopen {day === 6 ? 'Monday' : 'tomorrow'}.</p>;
                                    }
                                    return <p className="text-center text-ink-mute font-display italic" style={{ fontVariationSettings: '"opsz" 24' }}>No fresh signals today. The system is watching.</p>;
                                  })()}
                                  {heldFreshCount === 0 && daysSinceLastSignal > 14 && !dashboardData?.market_context && (
                                    <p className="text-xs text-ink-light mt-1.5 max-w-xs mx-auto text-center">
                                      {daysSinceLastSignal <= 21
                                        ? "Two weeks of patience. Sitting out when setups aren't clean is how the ensemble protects you."
                                        : "Extended quiet stretch. The ensemble won't chase trades — when conditions are right, you'll be the first to know."}
                                    </p>
                                  )}
                                </>
                              )}
                            </div>
                          ))}

                          {/* Monitoring section (non-fresh) — hidden for served tiers (mirror book) */}
                          {!dashboardData?.tier_book && monitoringSignals.length > 0 && (
                            <div>
                              <div className="px-4 py-2.5 border-b border-rule flex items-center justify-between">
                                <span className="font-display text-[0.95rem] font-medium tracking-tight">Monitoring <em className="font-display italic text-ink-light font-normal">({monitoringSignals.length})</em></span>
                                <span className="font-display italic text-[0.85rem] text-ink-mute" style={{ fontVariationSettings: '"opsz" 24' }}>Watching for entry</span>
                              </div>
                              {viewMode === 'simple' ? (
                                <div className="divide-y divide-rule">
                                  {monitoringSignals.map(renderSimpleSignal)}
                                </div>
                              ) : (
                                <div className="overflow-x-auto">
                                <table className="w-full text-sm">
                                  <thead className="bg-paper-card text-ink-mute">
                                    <tr>
                                      <th className="px-3 py-2 text-left font-medium">Symbol</th>
                                      <th className="px-3 py-2 text-right font-medium">Price</th>
                                      <th className="px-3 py-2 text-right font-medium">Breakout%</th>
                                      <th className="px-3 py-2 text-center font-medium">Score</th>
                                      <th className="px-3 py-2 text-center font-medium whitespace-nowrap">
                                        Strength
                                        <span className="ml-1"><StrengthInfoPopover /></span>
                                      </th>
                                    </tr>
                                  </thead>
                                  <tbody className="divide-y divide-rule">
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
                      {/* AI Market Briefing — was only mounted in the signals>0
                          branch, so on all-cash days (when it matters most:
                          "all 25 signals cleared overnight") it never rendered. */}
                      {dashboardData?.market_context && (
                        <div className="py-4 px-5 bg-paper-card border-l-2 border-claret">
                          <span className="block font-body text-[0.64rem] font-medium tracking-[0.22em] uppercase text-ink-mute mb-2">
                            Market Briefing
                          </span>
                          <p className="font-display italic text-[1rem] text-ink leading-[1.6]">{dashboardData.market_context}</p>
                        </div>
                      )}
                      {/* A. Market context message */}
                      {dashboardData?.regime_forecast && (
                        <div className="flex items-center gap-2 text-sm text-ink-mute">
                          <div className={`w-3 h-3 rounded-full flex-shrink-0 ${
                            ['strong_bull', 'weak_bull', 'recovery'].includes(dashboardData.regime_forecast.current_regime) ? 'bg-positive/100' :
                            ['rotating_bull', 'range_bound'].includes(dashboardData.regime_forecast.current_regime) ? 'bg-ink-light' :
                            'bg-negative/100'
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

                      {/* Market context shown in editorial lede above */}

                      {/* B. Promoted watchlist */}
                      {(dashboardData?.watchlist || []).length > 0 && (
                        <div>
                          <p className="text-xs font-medium text-ink-mute uppercase tracking-wide mb-2">Approaching Buy Trigger</p>
                          {viewMode === 'simple' ? (
                            <div className="space-y-1.5">
                              {dashboardData.watchlist.map(s => (
                                <div
                                  key={s.symbol}
                                  className="flex items-center justify-between px-3 py-2 bg-paper-deep rounded-lg cursor-pointer hover:bg-claret/10 transition-colors"
                                  onClick={() => setChartModal({ type: 'signal', data: { symbol: s.symbol }, symbol: s.symbol })}
                                >
                                  <span className="font-semibold text-ink">{s.symbol}</span>
                                  <span className="text-xs font-medium text-claret bg-claret/10 px-2 py-0.5 rounded-full">
                                    {s.distance_to_trigger?.toFixed(1)}% to go
                                  </span>
                                </div>
                              ))}
                            </div>
                          ) : (
                            <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                              <thead className="text-ink-mute">
                                <tr>
                                  <th className="text-left text-xs font-medium pb-1">Symbol</th>
                                  <th className="text-right text-xs font-medium pb-1">Price</th>
                                  <th className="text-right text-xs font-medium pb-1">Breakout%</th>
                                  <th className="text-right text-xs font-medium pb-1">Distance</th>
                                </tr>
                              </thead>
                              <tbody className="divide-y divide-rule">
                                {dashboardData.watchlist.map(s => (
                                  <tr
                                    key={s.symbol}
                                    className="cursor-pointer hover:bg-paper-deep transition-colors"
                                    onClick={() => setChartModal({ type: 'signal', data: { symbol: s.symbol }, symbol: s.symbol })}
                                  >
                                    <td className="py-1.5 font-semibold text-ink">{s.symbol}</td>
                                    <td className="py-1.5 text-right text-ink-mute">${s.price?.toFixed(2)}</td>
                                    <td className="py-1.5 text-right text-positive">+{s.pct_above_dwap?.toFixed(1)}%</td>
                                    <td className="py-1.5 text-right font-medium text-claret">+{s.distance_to_trigger?.toFixed(1)}%</td>
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
                          <p className="text-xs font-medium text-ink-mute uppercase tracking-wide mb-2">Recent Signals</p>
                          <div className="flex flex-wrap gap-2">
                            {dashboardData.recent_signals.map(rs => {
                              const quote = liveQuotes[rs.symbol];
                              const livePrice = quote?.price;
                              const perfPct = livePrice && rs.signal_price > 0
                                ? Math.round((livePrice / rs.signal_price - 1) * 1000) / 10
                                : rs.performance_pct;
                              return (
                              <div key={`${rs.symbol}-${rs.signal_date}`} className="flex items-center gap-1.5 text-xs bg-paper-deep px-2.5 py-1.5 rounded-lg">
                                <span className="font-semibold text-ink">{rs.symbol}</span>
                                <span className="text-ink-mute">{formatDate(rs.signal_date)}</span>
                                {perfPct != null && (
                                  <span className={`font-medium ${perfPct >= 0 ? 'text-positive' : 'text-negative'}`}>
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
                        <div className="text-center py-6 text-ink-mute">
                          <Activity className="w-12 h-12 mx-auto text-ink-light mb-3" />
                          <p>No buy signals right now</p>
                          <p className="text-xs mt-1">We're scanning the market — check back soon</p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>

              {/* RIGHT: Open Positions with Sell Guidance — hidden for served tiers (mirror book)
                  and for free/proof-only users (the free view owns the single column). */}
              {!dashboardData?.tier_book && !freeTier && (() => {
                const positionSectorFilter = (p) => !excludedSectors.includes(p.sector || 'Other');
                const filteredGuidance = guidanceWithLiveQuotes.filter(positionSectorFilter);
                const filteredPositions = positionsWithLiveQuotes.filter(positionSectorFilter);
                const activePositions = filteredGuidance.length > 0 ? filteredGuidance : filteredPositions;
                const hasUnfilteredPositions = guidanceWithLiveQuotes.length > 0 || positionsWithLiveQuotes.length > 0;
                return (
              <div className="overflow-hidden">
                <div className="pb-3 border-b-2 border-ink mb-5">
                  <div className="flex items-baseline justify-between">
                    <h2 className="font-display text-[1.25rem] font-medium text-ink tracking-tight" style={{ fontVariationSettings: '"opsz" 48' }}>Open Positions</h2>
                    <span className="font-mono text-[0.72rem] text-ink-light tracking-wide">Click row for chart</span>
                  </div>
                  {/* invisible spacer matching Buy Signals' subtitle line so both
                      headers' bottom borders align across the two columns */}
                  <em className="block invisible font-display italic text-[0.78rem] mt-1.5" style={{ fontVariationSettings: '"opsz" 24' }}>spacer</em>
                </div>

                <div className="max-h-[500px] overflow-y-auto">
                  {!quotesReady && hasUnfilteredPositions ? (
                    <div className="px-5 py-8 text-center text-sm text-ink-light">
                      <div className="animate-pulse space-y-3">
                        {[1,2,3].map(i => <div key={i} className="h-10 bg-paper-deep rounded" />)}
                      </div>
                      <p className="mt-3">Loading live prices...</p>
                    </div>
                  ) : activePositions.length > 0 ? (
                    viewMode === 'simple' ? (
                      /* Simple mode: list items with friendly status */
                      <div className="divide-y divide-rule">
                        {activePositions.map((p) => {
                          const action = p.action || 'hold';
                          const pnl = p.pnl_pct || ((p.current_price - p.entry_price) / p.entry_price * 100) || 0;
                          const statusLabel = action === 'sell' ? 'SELL'
                            : action === 'warning' ? 'WATCH'
                            : 'HOLD';
                          const statusColor = action === 'sell' ? 'text-negative'
                            : action === 'warning' ? 'text-claret'
                            : 'text-ink-mute';

                          return (
                            <div
                              key={p.id || p.symbol}
                              className={`px-4 py-3 flex items-center justify-between cursor-pointer transition-colors hover:bg-paper-card ${
                                action === 'sell' ? 'border-l-4 border-l-negative' :
                                action === 'warning' ? 'border-l-4 border-l-claret' : ''
                              }`}
                              onClick={() => setChartModal({ type: 'position', data: p, symbol: p.symbol })}
                            >
                              <div className="flex items-center gap-3">
                                <div>
                                  <span className="font-display text-[1.05rem] font-medium tracking-tight" style={{ fontVariationSettings: '"opsz" 48' }}>{p.symbol}</span>
                                  <span className="block font-mono text-[0.72rem] text-ink-light">{Math.round(p.shares || 0)} shares</span>
                                </div>
                                <span className={`font-mono text-[0.88rem] ${pnl >= 0 ? 'text-positive' : 'text-negative'}`}>
                                  {pnl >= 0 ? '+' : ''}{pnl.toFixed(1)}%
                                </span>
                              </div>
                              <span className={`font-mono text-[0.68rem] tracking-[0.2em] uppercase ${statusColor} px-2 py-1 border border-rule-dark`}>{statusLabel}</span>
                            </div>
                          );
                        })}
                      </div>
                    ) : (
                      /* Advanced mode: full table */
                      <div className="overflow-x-auto">
                      <table className="w-full border-collapse" style={{ fontFeatureSettings: '"tnum"' }}>
                        <thead>
                          <tr>
                            <th className="px-3 py-2 text-left font-body text-[0.62rem] font-medium tracking-[0.2em] uppercase text-ink-mute border-b border-ink">Symbol</th>
                            <th className="px-3 py-2 text-right font-body text-[0.62rem] font-medium tracking-[0.2em] uppercase text-ink-mute border-b border-ink">P&L</th>
                            <th className="px-3 py-2 text-center font-body text-[0.62rem] font-medium tracking-[0.2em] uppercase text-ink-mute border-b border-ink">Status</th>
                            <th className="px-3 py-2 text-right font-body text-[0.62rem] font-medium tracking-[0.2em] uppercase text-ink-mute border-b border-ink">Stop</th>
                          </tr>
                        </thead>
                        <tbody>
                          {activePositions.map((p) => {
                            const action = p.action || 'hold';
                            const pnl = p.pnl_pct || ((p.current_price - p.entry_price) / p.entry_price * 100) || 0;
                            const pnlColor = pnl >= 0 ? 'text-positive' : 'text-negative';

                            return (
                              <tr
                                key={p.id || p.symbol}
                                className={`cursor-pointer transition-colors border-b border-rule hover:bg-paper-card ${
                                  action === 'sell' ? 'border-l-4 border-l-negative' :
                                  action === 'warning' ? 'border-l-4 border-l-claret' : ''
                                }`}
                                onClick={() => setChartModal({ type: 'position', data: p, symbol: p.symbol })}
                              >
                                <td className="px-3 py-3">
                                  <span className="font-display text-[1.05rem] font-medium tracking-tight" style={{ fontVariationSettings: '"opsz" 48' }}>{p.symbol}</span>
                                  <div className="font-mono text-[0.72rem] text-ink-light mt-0.5">{Math.round(p.shares || 0)} shares</div>
                                </td>
                                <td className="px-3 py-3 text-right">
                                  <span className={`font-mono text-[0.88rem] ${pnlColor}`}>
                                    {pnl >= 0 ? '+' : ''}{pnl.toFixed(1)}%
                                  </span>
                                  <div className="font-mono text-[0.72rem] text-ink-light mt-0.5">${p.current_price?.toFixed(2)}</div>
                                </td>
                                <td className="px-3 py-3 text-center">
                                  <span className={`font-mono text-[0.68rem] tracking-[0.2em] uppercase px-2 py-1 border ${
                                    action === 'sell' ? 'text-negative border-negative/30' :
                                    action === 'warning' ? 'text-claret border-claret/30' :
                                    'text-ink-mute border-rule-dark'
                                  }`}>
                                    {action === 'sell' ? 'SELL' : action === 'warning' ? 'WATCH' : 'HOLD'}
                                  </span>
                                </td>
                                <td className="px-3 py-3 text-right">
                                  <span className="font-mono text-[0.88rem] text-ink-mute">${p.trailing_stop_level?.toFixed(2) || '--'}</span>
                                  <div className="font-mono text-[0.72rem] text-ink-light mt-0.5">
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
                    <div className="text-center py-12 text-ink-mute">
                      <PieIcon className="w-12 h-12 mx-auto text-ink-light mb-3" />
                      <p>No open positions</p>
                      <p className="text-xs mt-1">Click a fresh signal, then Record Entry from the chart</p>
                    </div>
                  )}
                </div>

                {/* Action reasons for positions needing attention (wait for live prices) */}
                {quotesReady && viewMode !== 'simple' && activePositions.filter(p => p.action !== 'hold').length > 0 && (
                  <div className="border-t border-rule px-4 py-3 space-y-1">
                    {activePositions.filter(p => p.action !== 'hold').map(p => (
                      <div key={p.symbol} className={`text-xs px-2 py-1 rounded ${
                        p.action === 'sell' ? 'bg-negative/10 text-negative' : 'bg-paper-deep text-claret'
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

            {/* Watchlist — Approaching Trigger. Hidden for Maximizer: the mirror book auto-enters
                breakouts, so a manual t30v "approaching" list doesn't apply. Preserver keeps it. */}
            {dashboardData?.tier !== 'maximizer' && (dashboardData?.watchlist || []).length > 0 && (dashboardData?.buy_signals || []).length > 0 && (
              viewMode === 'simple' ? (
                <div className="mt-6 p-3 bg-paper-deep border border-amber-200 rounded text-sm text-ink">
                  <Eye className="w-4 h-4 text-claret inline mr-1.5" />
                  {dashboardData.watchlist.length} stock{dashboardData.watchlist.length > 1 ? 's are' : ' is'} close to triggering a buy signal: {dashboardData.watchlist.map(s => s.symbol).join(', ')}
                </div>
              ) : (
                <div className="mt-6 bg-paper-deep border border-amber-200 rounded overflow-hidden">
                  <div className="px-5 py-3 border-b border-amber-200 flex items-center gap-2">
                    <Eye className="w-4 h-4 text-claret" />
                    <h3 className="font-medium text-ink">Watchlist — Approaching Trigger</h3>
                    <span className="text-xs text-claret ml-2">Momentum stocks approaching breakout trigger</span>
                  </div>
                  <div className="flex flex-wrap gap-3 px-5 py-3">
                    {dashboardData.watchlist.map((s) => (
                      <div
                        key={s.symbol}
                        className="flex items-center gap-2 px-3 py-2 bg-paper-card border border-amber-200 rounded-lg hover:bg-claret/10 cursor-pointer transition-colors"
                        onClick={() => setChartModal({ type: 'signal', data: { symbol: s.symbol }, symbol: s.symbol })}
                      >
                        <span className="font-semibold text-ink">{s.symbol}</span>
                        <span className="text-xs text-ink-mute">+{s.pct_above_dwap?.toFixed(1)}%</span>
                        <span className="text-xs font-medium text-claret">+{s.distance_to_trigger?.toFixed(1)}% to go</span>
                      </div>
                    ))}
                  </div>
                </div>
              )
            )}

            {/* Missed Opportunities — the walk-forward "you could have made $X following our
                signals" upsell. Only meaningful for users NOT following the book; a mirror/paid
                user (tier_book) DID take these trades, so it's shown their real "Recently closed"
                instead (in the Maximizer book column). Free users get this framing via
                FreeProofView's "Recent catches". (project_free_first_spec — split by tier) */}
            {!dashboardData?.tier_book && missedOpportunities.length > 0 && (
              viewMode === 'simple' ? (
                /* Simple mode: summary + top 3 cards */
                <div className="mt-6 bg-paper-deep border border-rule-dark rounded p-4">
                  <p className="text-sm text-ink mb-3">
                    You could have made{' '}
                    <strong className="text-ink">
                      +${missedOpportunities.reduce((sum, m) => sum + (m.would_be_pnl || 0), 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}
                    </strong>
                    {' '}last month following our signals.
                  </p>
                  <div className="flex gap-3">
                    {missedOpportunities.slice(0, 3).map(m => (
                      <div
                        key={m.symbol}
                        className="flex-1 bg-paper-card border border-amber-200 rounded-lg px-3 py-2 text-center cursor-pointer hover:bg-paper-deep transition-colors"
                        onClick={() => setChartModal({ type: 'missed', data: m, symbol: m.symbol })}
                      >
                        <span className="font-semibold text-ink">{m.symbol}</span>
                        <div className="text-positive font-bold text-sm">
                          +{m.would_be_return?.toFixed(0)}%
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                /* Advanced mode: full table */
                <div className="mt-6 overflow-hidden">
                  <div className="flex items-baseline justify-between pb-3 border-b-2 border-ink mb-5">
                    <h2 className="font-display text-[1.25rem] font-medium text-ink tracking-tight" style={{ fontVariationSettings: '"opsz" 48' }}>Missed Opportunities</h2>
                    <span className="font-mono text-[0.72rem] text-ink-light tracking-wide">Trailing stop exits</span>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full border-collapse" style={{ fontFeatureSettings: '"tnum"' }}>
                      <thead>
                        <tr>
                          <th className="px-3 py-2 text-left font-body text-[0.62rem] font-medium tracking-[0.2em] uppercase text-ink-mute border-b border-ink">Symbol</th>
                          <th className="px-3 py-2 text-left font-body text-[0.62rem] font-medium tracking-[0.2em] uppercase text-ink-mute border-b border-ink hidden sm:table-cell">Buy</th>
                          <th className="px-3 py-2 text-right font-body text-[0.62rem] font-medium tracking-[0.2em] uppercase text-ink-mute border-b border-ink hidden md:table-cell">Buy $</th>
                          <th className="px-3 py-2 text-left font-body text-[0.62rem] font-medium tracking-[0.2em] uppercase text-ink-mute border-b border-ink hidden sm:table-cell">Sell</th>
                          <th className="px-3 py-2 text-right font-body text-[0.62rem] font-medium tracking-[0.2em] uppercase text-ink-mute border-b border-ink hidden md:table-cell">Sell $</th>
                          <th
                            className="px-3 py-2 text-right font-body text-[0.62rem] font-medium tracking-[0.2em] uppercase text-ink-mute border-b border-ink cursor-pointer hover:text-claret transition-colors"
                            onClick={() => setMissedSortBy(prev => prev === 'return' ? 'date' : 'return')}
                          >
                            Return {missedSortBy === 'return' ? '↓' : ''}
                          </th>
                          <th className="px-3 py-2 text-right font-body text-[0.62rem] font-medium tracking-[0.2em] uppercase text-ink-mute border-b border-ink">P&L</th>
                          <th className="px-3 py-2 text-right font-body text-[0.62rem] font-medium tracking-[0.2em] uppercase text-ink-mute border-b border-ink hidden sm:table-cell">Days</th>
                        </tr>
                      </thead>
                      <tbody>
                        {[...missedOpportunities].sort((a, b) =>
                          missedSortBy === 'return'
                            ? (b.would_be_return || 0) - (a.would_be_return || 0)
                            : (b.sell_date || '').localeCompare(a.sell_date || '')
                        ).map((m) => (
                          <tr
                            key={`${m.symbol}-${m.entry_date}`}
                            className="hover:bg-paper-card cursor-pointer transition-colors border-b border-rule"
                            onClick={() => setChartModal({ type: 'missed', data: m, symbol: m.symbol })}
                          >
                            <td className="px-3 py-3"><span className="font-display text-[1.05rem] font-medium" style={{ fontVariationSettings: '"opsz" 48' }}>{m.symbol}</span></td>
                            <td className="px-3 py-3 font-mono text-[0.85rem] text-ink-mute hidden sm:table-cell">{formatDate(m.entry_date)}</td>
                            <td className="px-3 py-3 text-right font-mono text-[0.88rem] hidden md:table-cell">${m.entry_price?.toFixed(2)}</td>
                            <td className="px-3 py-3 font-mono text-[0.85rem] text-ink-mute hidden sm:table-cell">{formatDate(m.sell_date)}</td>
                            <td className="px-3 py-3 text-right font-mono text-[0.88rem] hidden md:table-cell">${m.sell_price?.toFixed(2)}</td>
                            <td className="px-3 py-3 text-right font-mono text-[0.88rem] text-positive font-medium">+{m.would_be_return?.toFixed(1)}%</td>
                            <td className="px-3 py-3 text-right font-mono text-[0.88rem] text-positive">+${m.would_be_pnl?.toFixed(0)}</td>
                            <td className="px-3 py-3 text-right font-mono text-[0.85rem] text-ink-mute hidden sm:table-cell">{m.days_held}d</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )
            )}

            {/* Maximizer upsell — breakout winners the Maximizer book caught (real closed
                trades), shown to Preserver users only (backend populates upsell_missed just
                for them). "What the aggressive tier would have added." */}
            {(dashboardData?.upsell_missed?.length > 0) && (
              <div className="mt-6 border border-claret/30 bg-claret/5 rounded p-4">
                <div className="flex items-baseline justify-between mb-3">
                  <h3 className="font-display text-[1.05rem] font-medium text-ink tracking-tight" style={{ fontVariationSettings: '"opsz" 32' }}>
                    What Maximizer caught
                  </h3>
                  <span className="font-mono text-[0.62rem] tracking-[0.16em] uppercase text-claret">Upgrade</span>
                </div>
                <p className="font-display italic text-[0.88rem] text-ink-mute mb-3 leading-[1.5]" style={{ fontVariationSettings: '"opsz" 24' }}>
                  Breakout trades the Maximizer tier closed for a gain in rotating-bull regimes — a 29-day hold, no trailing stop. Add Maximizer to mirror these.
                </p>
                <div className="flex flex-wrap gap-2">
                  {dashboardData.upsell_missed.slice(0, 6).map((m) => (
                    <div
                      key={m.symbol}
                      className="bg-paper-card border border-claret/30 rounded px-3 py-2 text-center cursor-pointer hover:bg-paper-deep transition-colors"
                      onClick={() => setChartModal({ type: 'missed', data: m, symbol: m.symbol })}
                    >
                      <span className="font-display text-[0.95rem] font-medium text-ink" style={{ fontVariationSettings: '"opsz" 32' }}>{m.symbol}</span>
                      <div className="text-positive font-mono font-bold text-[0.82rem]">+{m.would_be_return?.toFixed(0)}%</div>
                      <div className="font-mono text-[0.6rem] text-ink-mute">{m.days_held}d hold</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Backtest/Walk-Forward summary. For a served tier, source the CERTIFIED tier
                walk-forward numbers (tier_backtest) instead of the ensemble/0% cache. */}
            {(() => {
              const tb = dashboardData?.tier_backtest;
              const bt = tb ? {
                total_return_pct: tb.total_return_pct?.toFixed ? tb.total_return_pct.toFixed(1) : tb.total_return_pct,
                sharpe_ratio: tb.sharpe_ratio, max_drawdown_pct: tb.max_drawdown_pct,
                start_date: tb.start_date, end_date: tb.end_date, is_walk_forward: true,
                return_label: tb.annualized ? 'Annualized' : 'Return',  // overlay card is per-year, not cumulative
                subtitle: `${tb.label} · ${tb.rolling ? 'trailing 365d (rolling)' : (tb.window || 'walk-forward')}`,
                hide_dates: !tb.rolling,  // full-cycle label already states the window
              } : backtest;
              if (!bt) return null;
              const subtitle = bt.subtitle || (bt.is_walk_forward
                ? `Ensemble strategy${bt.num_strategy_switches > 0 ? ` · ${bt.num_strategy_switches} switches` : ''}`
                : `${bt.strategy === 'momentum' ? 'Momentum' : 'Breakout'} strategy`);
              return (
              <div className="mt-6 bg-gradient-to-r from-paper-deep to-paper-card border-rule-dark border rounded p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="font-display text-[1.1rem] font-medium text-ink tracking-tight" style={{ fontVariationSettings: '"opsz" 48' }}>
                      Simulated Portfolio (Walk-Forward)
                    </h3>
                    <p className="font-mono text-[0.78rem] text-ink-mute tracking-wide mt-1">
                      {subtitle}
                      {!bt.hide_dates && <>{' · '}{formatDate(bt.start_date, { includeYear: true })} to {formatDate(bt.end_date, { includeYear: true })}</>}
                    </p>
                  </div>
                  <div className="flex gap-8">
                    <div>
                      <div className="font-body text-[0.64rem] font-medium tracking-[0.22em] uppercase text-ink-mute mb-1">{bt.return_label || 'Return'}</div>
                      <div className={`font-display text-[1.5rem] font-normal leading-none tracking-tight ${parseFloat(bt.total_return_pct) >= 0 ? 'text-positive' : 'text-negative'}`} style={{ fontVariationSettings: '"opsz" 72' }}>
                        {parseFloat(bt.total_return_pct) >= 0 ? '+' : ''}{bt.total_return_pct}%{bt.return_label === 'Annualized' ? <span className="text-[0.8rem] text-ink-mute">/yr</span> : ''}
                      </div>
                    </div>
                    <div>
                      <div className="font-body text-[0.64rem] font-medium tracking-[0.22em] uppercase text-ink-mute mb-1">Sharpe</div>
                      <div className="font-display text-[1.5rem] font-normal leading-none tracking-tight text-ink" style={{ fontVariationSettings: '"opsz" 72' }}>{bt.sharpe_ratio}</div>
                    </div>
                    <div>
                      <div className="font-body text-[0.64rem] font-medium tracking-[0.22em] uppercase text-ink-mute mb-1">Max DD</div>
                      <div className="font-display text-[1.5rem] font-normal leading-none tracking-tight text-ink" style={{ fontVariationSettings: '"opsz" 72' }}>{bt.max_drawdown_pct}%</div>
                    </div>
                  </div>
                </div>
                {/* Foundations — the 5-year + 21-year overlay track record beneath the real
                    trailing-365 rolling headline, so the live recent number sits on the long-term base. */}
                {Array.isArray(tb?.foundations) && tb.foundations.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-rule space-y-1.5">
                    {tb.foundations.map((f, idx) => (
                      <div key={idx} className="flex items-baseline justify-between font-mono text-[0.78rem] text-ink-mute tracking-wide">
                        <span>{f.window}</span>
                        <span>
                          <span className={parseFloat(f.total_return_pct) >= 0 ? 'text-positive' : 'text-negative'}>
                            {parseFloat(f.total_return_pct) >= 0 ? '+' : ''}{f.total_return_pct}%{f.annualized ? '/yr' : ''}
                          </span>
                          <span className="text-ink-light"> · Sharpe {f.sharpe_ratio} · MaxDD {f.max_drawdown_pct}%</span>
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
              );
            })()}
          </>
        ) : activeTab === 'history' ? (
          <div className="space-y-6">
            <div className="grid grid-cols-2 sm:grid-cols-4 border-t border-b border-ink py-4 mb-6">
              <MetricCard title="Total Trades" value={trades.length} />
              <MetricCard title="Win Rate" value={`${winRate.toFixed(0)}%`} subtitle={`${wins.length}W / ${trades.length - wins.length}L`} trend={winRate > 50 ? 'up' : 'down'} />
              <MetricCard title="Total P&L" value={`$${totalHistoricalPnl.toLocaleString(undefined, {maximumFractionDigits: 0})}`} trend={totalHistoricalPnl >= 0 ? 'up' : 'down'} />
              <MetricCard title="Avg Return" value={`${trades.length ? (trades.reduce((s,t) => s + (t.pnl_pct || 0), 0) / trades.length).toFixed(1) : 0}%`} />
            </div>

            <div className="overflow-hidden">
              <div className="flex items-baseline justify-between pb-3 border-b-2 border-ink mb-5">
                <h2 className="font-display text-[1.25rem] font-medium text-ink tracking-tight" style={{ fontVariationSettings: '"opsz" 48' }}>Trade History <em className="font-display italic text-ink-mute text-[0.85rem]" style={{ fontVariationSettings: '"opsz" 24' }}>Your recorded entries &amp; exits</em></h2>
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    const v = (e.currentTarget.ticker.value || '').trim().toUpperCase();
                    if (v) setChartModal({ type: 'signal', data: { symbol: v }, symbol: v });
                  }}
                  className="flex items-center gap-2"
                >
                  <input
                    name="ticker"
                    placeholder="Look up ticker…"
                    autoComplete="off"
                    className="w-32 px-3 py-1.5 text-sm bg-paper-deep border border-rule rounded-lg text-ink placeholder:text-ink-light focus:outline-none focus:border-claret"
                  />
                  <button type="submit" className="px-3 py-1.5 text-sm font-medium bg-ink text-white rounded-lg hover:opacity-90">Chart</button>
                </form>
              </div>
              <div className="overflow-x-auto max-h-[600px]">
                {trades.length > 0 ? (
                  <table className="w-full border-collapse" style={{ fontFeatureSettings: '"tnum"' }}>
                    <thead>
                      <tr>{['Symbol', 'Entry', 'Exit', 'Entry $', 'Exit $', 'Return', 'P&L', 'Reason', 'Days'].map(h => <th key={h} className="py-2 px-3 text-left font-body text-[0.62rem] font-medium tracking-[0.2em] uppercase text-ink-mute border-b border-ink">{h}</th>)}</tr>
                    </thead>
                    <tbody>
                      {trades.map(t => (
                        <tr
                          key={t.id}
                          onClick={() => setChartModal({ type: 'position', data: { ...t, sell_date: t.exit_date, sell_price: t.exit_price }, symbol: t.symbol })}
                          className="hover:bg-paper-card border-b border-rule cursor-pointer"
                        >
                          <td className="py-3 px-3 font-display text-[1.05rem] font-medium" style={{ fontVariationSettings: '"opsz" 48' }}>{t.symbol}</td>
                          <td className="py-3 px-3 font-mono text-[0.85rem] text-ink-mute">{formatDate(t.entry_date)}</td>
                          <td className="py-3 px-3 font-mono text-[0.85rem] text-ink-mute">{formatDate(t.exit_date)}</td>
                          <td className="py-3 px-3 font-mono text-[0.88rem]">${t.entry_price?.toFixed(2)}</td>
                          <td className="py-3 px-3 font-mono text-[0.88rem]">${t.exit_price?.toFixed(2)}</td>
                          <td className="py-3 px-3 font-mono text-[0.88rem]"><span className={`font-medium ${t.pnl_pct >= 0 ? 'text-positive' : 'text-negative'}`}>{t.pnl_pct >= 0 ? '+' : ''}{t.pnl_pct?.toFixed(1)}%</span></td>
                          <td className={`py-3 px-3 font-mono text-[0.88rem] font-medium ${t.pnl >= 0 ? 'text-positive' : 'text-negative'}`}>${t.pnl?.toFixed(0)}</td>
                          <td className="py-3 px-3"><span className="font-mono text-[0.68rem] tracking-[0.15em] uppercase text-ink-mute px-2 py-1 border border-rule-dark">{({'trailing_stop':'TRAIL STOP','rebalance_exit':'REBALANCE','simulation_end':'REBALANCE','profit_target':'TARGET','stop_loss':'STOP LOSS'}[t.exit_reason] || t.exit_reason?.toUpperCase())}</span></td>
                          <td className="py-3 px-3 font-mono text-[0.85rem] text-ink-mute">{(() => {
                            const d = t.days_held ?? ((t.entry_date && t.exit_date) ? Math.max(0, Math.round((new Date(t.exit_date) - new Date(t.entry_date)) / 86400000)) : null);
                            return d == null ? '—' : `${d}d`;
                          })()}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <div className="text-center py-12 text-ink-mute">
                    <p className="font-display italic text-ink-mute" style={{ fontVariationSettings: '"opsz" 24' }}>No recorded trades yet.</p>
                    <p className="text-sm text-ink-light mt-1">Use "Record Entry" on a signal, then "Record Exit" when you close.</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        ) : null}
      </main>

      {showLoginModal && <LoginModal isOpen={showLoginModal} onClose={() => setShowLoginModal(false)} />}
      {chartModal && <StockChartModal {...chartModal} viewMode={viewMode} liveQuote={liveQuotes[chartModal.symbol]} timeTravelDate={timeTravelDate} lastPositionDollars={user?.last_position_dollars} onClose={() => setChartModal(null)} onAction={(positionData) => {
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
            trailing_stop_level: positionData.stop_loss ?? positionData.entry_price * (1 - EFFECTIVE_TRAIL_FRAC),
            trailing_stop_pct: Math.round(EFFECTIVE_TRAIL_FRAC * 100),
            distance_to_stop_pct: Math.round(EFFECTIVE_TRAIL_FRAC * 100),
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
        // Pick up updated last_position_dollars so the next BuyModal pre-fills
        // shares from this BUY's dollar amount.
        if (positionData) refreshUser();
      }} />}

      {/* Email Preferences Modal */}
      {showEmailPrefsModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={() => setShowEmailPrefsModal(false)}>
          <div className="bg-paper-card rounded shadow-xl max-w-md w-full" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between p-5 border-b">
              <h3 className="text-lg font-semibold text-ink flex items-center gap-2"><Bell size={18} /> Email Preferences</h3>
              <button onClick={() => setShowEmailPrefsModal(false)} className="text-ink-light hover:text-ink-mute"><X size={20} /></button>
            </div>
            <div className="p-5 space-y-4">
              {[
                { key: 'daily_digest', label: 'Daily Digest', desc: '6 PM ET summary with signals + positions' },
                { key: 'sell_alerts', label: 'Sell Alerts', desc: 'Trailing stop and regime exit alerts' },
                { key: 'intraday_signals', label: 'Intraday Signals', desc: 'Breakout crossover during market hours' },
                { key: 'market_measured', label: 'Market, Measured.', desc: 'Sunday morning weekly newsletter' },
              ].map(({ key, label, desc }) => (
                <label key={key} className="flex items-center justify-between cursor-pointer group">
                  <div>
                    <p className="text-sm font-medium text-ink">{label}</p>
                    <p className="text-xs text-ink-mute">{desc}</p>
                  </div>
                  <button
                    type="button"
                    role="switch"
                    aria-checked={emailPrefs[key]}
                    onClick={() => setEmailPrefs(prev => ({ ...prev, [key]: !prev[key] }))}
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${emailPrefs[key] ? 'bg-ink' : 'bg-rule'}`}
                  >
                    <span className={`inline-block h-4 w-4 transform rounded-full bg-paper-card transition-transform ${emailPrefs[key] ? 'translate-x-6' : 'translate-x-1'}`} />
                  </button>
                </label>
              ))}
            </div>
            <div className="flex items-center justify-end gap-3 p-5 border-t">
              <button onClick={() => setShowEmailPrefsModal(false)} className="px-4 py-2 text-sm text-ink-mute hover:text-ink">Cancel</button>
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
                className="px-4 py-2 text-sm font-medium text-white bg-ink rounded-lg hover:bg-claret disabled:opacity-50"
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
          <div className="bg-paper-card rounded shadow-xl max-w-md w-full" onClick={e => e.stopPropagation()}>
            <div className="p-6">
              <h3 className="text-lg font-semibold text-ink mb-1">We're sorry to see you go</h3>
              <p className="text-sm text-ink-mute mb-5">Your feedback helps us improve. 30 seconds, 3 questions.</p>
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
                <label className="block text-sm font-medium text-ink mb-2">What's the main reason you're leaving?</label>
                <select name="reason" required className="w-full border border-rule-dark rounded-lg px-3 py-2 text-sm mb-4 focus:ring-2 focus:ring-blue-500 focus:border-rule-dark">
                  <option value="">Select a reason...</option>
                  <option value="not_enough_signals">Not enough signals / too quiet</option>
                  <option value="too_expensive">Too expensive for the value</option>
                  <option value="confusing">Hard to understand or use</option>
                  <option value="not_useful">Signals weren't useful to me</option>
                  <option value="using_another">Switched to another service</option>
                  <option value="not_trading">Stopped trading / investing</option>
                  <option value="other">Other</option>
                </select>
                <label className="block text-sm font-medium text-ink mb-2">Anything else you'd like us to know?</label>
                <textarea name="detail" rows={2} className="w-full border border-rule-dark rounded-lg px-3 py-2 text-sm mb-4 resize-none focus:ring-2 focus:ring-blue-500 focus:border-rule-dark" placeholder="Optional — but we read every response" />
                <label className="block text-sm font-medium text-ink mb-2">Would you come back if we improved?</label>
                <div className="flex gap-4 mb-5">
                  <label className="flex items-center gap-2 text-sm"><input type="radio" name="would_return" value="yes" defaultChecked className="text-claret" /> Yes, definitely</label>
                  <label className="flex items-center gap-2 text-sm"><input type="radio" name="would_return" value="no" className="text-claret" /> Probably not</label>
                </div>
                <div className="flex justify-end gap-3">
                  <button type="button" onClick={() => setShowCancelSurvey(false)} className="px-4 py-2 text-sm text-ink-mute hover:text-ink">Skip</button>
                  <button type="submit" className="px-4 py-2 text-sm font-medium text-white bg-ink rounded-lg hover:bg-claret">Submit Feedback</button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
      {showCancelSurvey && cancelSurveySubmitted && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-paper-card rounded shadow-xl max-w-sm w-full p-6 text-center">
            <p className="text-lg font-semibold text-ink mb-2">Thank you for your feedback</p>
            <p className="text-sm text-ink-mute">We'll use it to make RigaCap better. You're welcome back anytime.</p>
          </div>
        </div>
      )}

      {/* Referral Modal */}
      {showReferralModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={() => setShowReferralModal(false)}>
          <div className="bg-paper-card rounded shadow-xl max-w-md w-full" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between p-5 border-b">
              <h3 className="text-lg font-semibold text-ink flex items-center gap-2"><Gift size={18} /> Refer a Friend</h3>
              <button onClick={() => setShowReferralModal(false)} className="text-ink-light hover:text-ink-mute"><X size={20} /></button>
            </div>
            <div className="p-5">
              <div className="bg-ink rounded p-6 text-center mb-5">
                <p className="text-claret font-bold text-lg mb-1">Give a Month, Get a Month</p>
                <p className="text-white/80 text-sm leading-relaxed">
                  Share your link with a friend. They get their first month free,
                  and when they subscribe, you get a free month too!
                </p>
              </div>
              {user?.referral_code && (
                <div className="space-y-3">
                  <label className="text-sm font-medium text-ink">Your referral link</label>
                  <div className="flex gap-2">
                    <input
                      readOnly
                      value={`rigacap.com/?ref=${user.referral_code}`}
                      className="flex-1 px-3 py-2 text-sm bg-paper-card border border-rule rounded-lg font-mono text-ink"
                    />
                    <button
                      onClick={() => {
                        navigator.clipboard.writeText(`https://rigacap.com/?ref=${user.referral_code}`);
                        setReferralCopied(true);
                        setTimeout(() => setReferralCopied(false), 2000);
                      }}
                      className={`px-3 py-2 text-sm font-medium rounded-lg flex items-center gap-1.5 transition-colors ${
                        referralCopied
                          ? 'bg-positive/10 text-positive'
                          : 'bg-ink text-white hover:bg-claret'
                      }`}
                    >
                      {referralCopied ? <><Check size={14} /> Copied!</> : <><Copy size={14} /> Copy</>}
                    </button>
                  </div>
                </div>
              )}
              {(user?.referral_count > 0) && (
                <div className="mt-5 bg-positive/10 rounded-lg p-4 text-center">
                  <p className="text-2xl font-bold text-positive">{user.referral_count}</p>
                  <p className="text-sm text-positive">friend{user.referral_count !== 1 ? 's' : ''} referred</p>
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
          <div className={`px-5 py-3 rounded shadow-lg text-sm font-medium text-white ${emailPrefsToast === 'unsubscribed' || emailPrefsToast === 'verify_failed' ? 'bg-orange-500' : 'bg-positive'}`}>
            {emailPrefsToast === 'unsubscribed' ? 'You have been unsubscribed from all emails.'
              : emailPrefsToast === 'verified' ? 'Email verified — you can now connect a brokerage.'
              : emailPrefsToast === 'verify_failed' ? 'That verification link is invalid or expired. Try resending it.'
              : 'Email preferences saved.'}
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
      <div className="min-h-screen bg-paper font-body flex items-center justify-center">
        <Loader2 className="w-12 h-12 text-claret animate-spin" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  return children;
}

function NotFoundPage() {
  // Tell Google not to index typo / nonexistent URLs (soft-404 signal). The
  // server still returns 200 for these because the SPA shell needs to load
  // for routing to work — but the rendered content + noindex meta is what
  // Google's classifier reads to decide whether to drop it from the index.
  // The canonical is also pointed back at the homepage so any link equity
  // accumulated by a typo URL flows to / instead of the typo URL itself.
  useEffect(() => {
    const robots = document.createElement('meta');
    robots.setAttribute('name', 'robots');
    robots.setAttribute('content', 'noindex, nofollow');
    document.head.appendChild(robots);

    const canonical = document.querySelector('link[rel="canonical"]');
    const prevCanonical = canonical?.getAttribute('href');
    if (canonical) canonical.setAttribute('href', 'https://rigacap.com/');

    document.title = '404 — Page not found · RigaCap';

    return () => {
      // Clean up so subsequent navigation doesn't inherit noindex
      robots.remove();
      if (canonical && prevCanonical) canonical.setAttribute('href', prevCanonical);
    };
  }, []);

  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center px-4">
      <div className="text-center">
        <p className="text-6xl font-bold text-claret mb-4">404</p>
        <h1 className="text-2xl font-semibold text-white mb-2">Page not found</h1>
        <p className="text-ink-light mb-8">The page you're looking for doesn't exist or has been moved.</p>
        <a href="/" className="inline-flex items-center gap-2 px-6 py-3 bg-paper-card text-ink font-semibold rounded hover:shadow-lg transition-all">
          Back to RigaCap
        </a>
      </div>
    </div>
  );
}

function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo(0, 0);
    // Dynamic canonical — prevents Google from seeing all pages as duplicates of /
    const canonical = document.querySelector('link[rel="canonical"]');
    if (canonical) canonical.setAttribute('href', `https://rigacap.com${pathname}`);
  }, [pathname]);
  return null;
}

// Suspense fallback for lazy route loading. Minimal — paper background
// flash without an explicit spinner, since chunks are typically <100KB
// and arrive in <100ms on any reasonable connection. A spinner would
// flicker more than help. Visible only on slow networks or first-time
// chunk fetches.
function RouteFallback() {
  return <div className="min-h-screen bg-paper" aria-hidden />;
}

// Destination-aware social vanity redirect: /ig/track-record ->
// /track-record?utm_source=instagram&utm_medium=social&utm_campaign=post.
// Social posts link to the clean /<code>/<page>; attribution is stamped here on
// redirect, so the posted URL stays short + brand-safe (no UTM funnel string).
function VanityRedirect({ platform }) {
  const { dest } = useParams();
  const to = dest
    ? `/${dest}?utm_source=${platform}&utm_medium=social&utm_campaign=post`
    : `/?utm_source=${platform}&utm_medium=social&utm_campaign=post`;
  return <Navigate to={to} replace />;
}

export default function App() {
  return (
    <AuthProvider>
      <ScrollToTop />
      <PageViewBeacon />
      <Suspense fallback={<RouteFallback />}>
      <Routes>
        <Route path="/" element={<LandingPageV2 />} />
        <Route path="/privacy" element={<PrivacyPage />} />
        <Route path="/terms" element={<TermsPage />} />
        <Route path="/contact" element={<ContactPage />} />
        <Route path="/track-record" element={<TrackRecordPageV2 />} />
        <Route path="/should-i-sell" element={<ShouldISellPage />} />
        <Route path="/momentum" element={<MomentumPage />} />
        <Route path="/for-advisers" element={<ForAdvisersPage />} />
        <Route path="/track-record-10y" element={<TrackRecord10YPage />} />
        <Route path="/methodology" element={<MethodologyPageV2 />} />
        <Route path="/methodology-v1" element={<MethodologyPage />} />
        <Route path="/about" element={<AboutPage />} />
        <Route path="/newsletter" element={<NewsletterPage />} />
        <Route path="/newsletter/:date" element={<NewsletterIssuePage />} />
        <Route path="/admin/symbol/:symbol/triage" element={<SymbolTriagePage />} />
        <Route path="/market-regime" element={<MarketRegimePage />} />
        <Route path="/blog" element={<BlogIndexPage />} />
        <Route path="/blog/2022-story" element={<Blog2022StoryPage />} />
        <Route path="/blog/backtests" element={<BlogBacktestsPage />} />
        <Route path="/blog/market-crash" element={<BlogMarketCrashPage />} />
        <Route path="/blog/honest-backtest" element={<BlogHonestBacktestPage />} />
        <Route path="/blog/trailing-stops" element={<BlogTrailingStopsPage />} />
        <Route path="/blog/momentum-trading" element={<BlogMomentumTradingPage />} />
        <Route path="/blog/walk-forward-results" element={<BlogWalkForwardResultsPage />} />
        <Route path="/blog/market-regime-guide" element={<BlogMarketRegimeGuidePage />} />
        <Route path="/blog/we-called-it-mrna" element={<BlogWeCalledItMRNAPage />} />
        <Route path="/blog/we-called-it-tgtx" element={<BlogWeCalledItTGTXPage />} />
        <Route path="/blog/sector-observatory" element={<BlogSectorObservatoryPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route path="/app/next" element={
          <ProtectedRoute>
            <MirrorCockpit />
          </ProtectedRoute>
        } />
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
        {/* Destination-aware (posts): /ig/track-record -> /track-record?utm_source=instagram... */}
        <Route path="/x/:dest" element={<VanityRedirect platform="twitter" />} />
        <Route path="/ig/:dest" element={<VanityRedirect platform="instagram" />} />
        <Route path="/t/:dest" element={<VanityRedirect platform="threads" />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
      </Suspense>
      <CookieConsent />
    </AuthProvider>
  );
}
