import React, { useState, useEffect, useMemo } from 'react';
import { Users, Activity, DollarSign, Clock, Search, ChevronLeft, ChevronRight, ToggleLeft, ToggleRight, Plus, Zap, TrendingUp, AlertCircle, CheckCircle, PlayCircle, RefreshCw, Beaker, Bot, Settings, Share2, Server, Briefcase, Sparkles, Calculator, Shield, Mail, Lock, Loader2, Edit3 } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { useAuth } from '../contexts/AuthContext';
import StrategyGenerator from './StrategyGenerator';
import { formatDate } from '../utils/formatDate';
import WalkForwardSimulator from './WalkForwardSimulator';
import AutoSwitchConfig from './AutoSwitchConfig';
import StrategyEditor from './StrategyEditor';
import FlexibleBacktest from './FlexibleBacktest';
import SocialTab from './SocialTab';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const TABS = [
  { id: 'overview', label: 'Overview', icon: Activity },
  { id: 'portfolio', label: 'Portfolio', icon: Briefcase },
  { id: 'strategies', label: 'Strategies', icon: TrendingUp },
  { id: 'lab', label: 'Strategy Lab', icon: Beaker },
  { id: 'autopilot', label: 'Auto-Pilot', icon: Bot },
  { id: 'social', label: 'Social', icon: Share2 },
  { id: 'newsletter', label: 'Newsletter', icon: Mail },
  { id: 'users', label: 'Users', icon: Users },
];

export default function AdminDashboard() {
  const { fetchWithAuth, isAdmin } = useAuth();
  const [activeTab, setActiveTab] = useState(() => sessionStorage.getItem('rigacap_admin_tab') || 'overview');
  const [stats, setStats] = useState(null);
  const [serviceStatus, setServiceStatus] = useState(null);
  const [users, setUsers] = useState([]);
  const [usersPagination, setUsersPagination] = useState({ page: 1, total: 0, per_page: 20 });
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Strategy management state
  const [strategies, setStrategies] = useState([]);
  const [activeStrategy, setActiveStrategy] = useState(null);
  const [analysisResults, setAnalysisResults] = useState(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [strategiesLoading, setStrategiesLoading] = useState(false);

  // AWS Health state
  const [awsHealth, setAwsHealth] = useState(null);

  // Pipeline log state
  const [pipelineLog, setPipelineLog] = useState(null);

  // Strategy Lab state
  const [showStrategyEditor, setShowStrategyEditor] = useState(false);
  const [editingStrategy, setEditingStrategy] = useState(null);

  // Fetch admin stats
  const fetchStats = async () => {
    try {
      const response = await fetchWithAuth(`${API_URL}/api/admin/stats`);
      if (response.ok) {
        const data = await response.json();
        setStats(data);
      }
    } catch (err) {
      console.error('Failed to fetch stats:', err);
    }
  };

  // Fetch service status
  const fetchServiceStatus = async () => {
    try {
      const response = await fetchWithAuth(`${API_URL}/api/admin/service-status`);
      if (response.ok) {
        const data = await response.json();
        setServiceStatus(data);
      }
    } catch (err) {
      console.error('Failed to fetch service status:', err);
    }
  };

  // Fetch AWS health
  const fetchAwsHealth = async () => {
    try {
      const response = await fetchWithAuth(`${API_URL}/api/admin/aws-health`);
      if (response.ok) {
        const data = await response.json();
        setAwsHealth(data);
      }
    } catch (err) {
      console.error('Failed to fetch AWS health:', err);
    }
  };

  // Fetch pipeline log
  const fetchPipelineLog = async () => {
    try {
      const response = await fetchWithAuth(`${API_URL}/api/admin/pipeline-log`);
      if (response.ok) setPipelineLog(await response.json());
    } catch (err) {
      console.error('Failed to fetch pipeline log:', err);
    }
  };

  // Fetch users
  const fetchUsers = async (page = 1, search = '') => {
    try {
      let url = `${API_URL}/api/admin/users?page=${page}&per_page=20`;
      if (search) {
        url += `&search=${encodeURIComponent(search)}`;
      }
      const response = await fetchWithAuth(url);
      if (response.ok) {
        const data = await response.json();
        setUsers(data.users);
        setUsersPagination({
          page: data.page,
          total: data.total,
          per_page: data.per_page,
        });
      }
    } catch (err) {
      console.error('Failed to fetch users:', err);
    }
  };

  // Toggle user status
  const toggleUserStatus = async (userId, isActive) => {
    try {
      const endpoint = isActive ? 'disable' : 'enable';
      const response = await fetchWithAuth(`${API_URL}/api/admin/users/${userId}/${endpoint}`, {
        method: 'POST',
      });
      if (response.ok) {
        fetchUsers(usersPagination.page, searchQuery);
      }
    } catch (err) {
      console.error('Failed to toggle user status:', err);
    }
  };

  // Extend trial
  const extendTrial = async (userId, days = 7) => {
    try {
      const response = await fetchWithAuth(`${API_URL}/api/admin/users/${userId}/extend-trial?days=${days}`, {
        method: 'POST',
      });
      if (response.ok) {
        fetchUsers(usersPagination.page, searchQuery);
        alert(`Trial extended by ${days} days`);
      }
    } catch (err) {
      console.error('Failed to extend trial:', err);
    }
  };

  // Comp subscription
  const compUser = async (userId) => {
    const days = prompt('Comp subscription for how many days?', '90');
    if (!days) return;
    try {
      const response = await fetchWithAuth(`${API_URL}/api/admin/users/${userId}/comp?days=${days}`, {
        method: 'POST',
      });
      if (response.ok) {
        const data = await response.json();
        alert(data.message);
        fetchUsers(usersPagination.page, searchQuery);
      } else {
        const err = await response.json();
        alert(`Failed: ${err.detail}`);
      }
    } catch (err) {
      console.error('Failed to comp user:', err);
    }
  };

  // Revoke comp
  const revokeComp = async (userId) => {
    if (!confirm('Revoke this comp subscription?')) return;
    try {
      const response = await fetchWithAuth(`${API_URL}/api/admin/users/${userId}/revoke-comp`, {
        method: 'POST',
      });
      if (response.ok) {
        alert('Comp revoked');
        fetchUsers(usersPagination.page, searchQuery);
      } else {
        const err = await response.json();
        alert(`Failed: ${err.detail}`);
      }
    } catch (err) {
      console.error('Failed to revoke comp:', err);
    }
  };

  // Fetch strategies
  const fetchStrategies = async () => {
    setStrategiesLoading(true);
    try {
      const response = await fetchWithAuth(`${API_URL}/api/admin/strategies`);
      if (response.ok) {
        const data = await response.json();
        setStrategies(data);
        const active = data.find(s => s.is_active);
        if (active) setActiveStrategy(active);
      }
    } catch (err) {
      console.error('Failed to fetch strategies:', err);
    } finally {
      setStrategiesLoading(false);
    }
  };

  // Fetch latest analysis
  const fetchLatestAnalysis = async () => {
    try {
      const response = await fetchWithAuth(`${API_URL}/api/admin/strategies/analysis`);
      if (response.ok) {
        const data = await response.json();
        setAnalysisResults(data);
      }
    } catch (err) {
      // 404 is expected if no analysis has been run yet
      if (err.message?.includes('404')) {
        console.log('No analysis results yet');
      } else {
        console.error('Failed to fetch analysis:', err);
      }
    }
  };

  // Run strategy analysis
  const runAnalysis = async (lookbackDays = 90) => {
    setAnalysisLoading(true);
    try {
      const response = await fetchWithAuth(`${API_URL}/api/admin/strategies/analyze?lookback_days=${lookbackDays}`, {
        method: 'POST',
      });
      if (response.ok) {
        const data = await response.json();
        setAnalysisResults(data);
        await fetchStrategies(); // Refresh strategies to get updated evaluations
      } else {
        try {
          const error = await response.json();
          alert(`Analysis failed: ${error.detail || JSON.stringify(error)}`);
        } catch {
          const text = await response.text();
          alert(`Analysis failed (${response.status}): ${text.slice(0, 200)}`);
        }
      }
    } catch (err) {
      console.error('Failed to run analysis:', err);
      alert(`Failed to run analysis: ${err.message}`);
    } finally {
      setAnalysisLoading(false);
    }
  };

  // Activate a strategy
  const activateStrategy = async (strategyId) => {
    try {
      const response = await fetchWithAuth(`${API_URL}/api/admin/strategies/${strategyId}/activate`, {
        method: 'POST',
      });
      if (response.ok) {
        const data = await response.json();
        setActiveStrategy(data);
        await fetchStrategies(); // Refresh all strategies
        alert(`Strategy "${data.name}" is now active`);
      }
    } catch (err) {
      console.error('Failed to activate strategy:', err);
      alert('Failed to activate strategy');
    }
  };

  // Persist admin sub-tab to sessionStorage
  useEffect(() => {
    sessionStorage.setItem('rigacap_admin_tab', activeTab);
  }, [activeTab]);

  // Initial load
  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      await Promise.all([
        fetchStats(),
        fetchServiceStatus(),
        fetchAwsHealth(),
        fetchPipelineLog(),
        fetchUsers(),
        fetchStrategies(),
        fetchLatestAnalysis(),
      ]);
      setLoading(false);
    };
    loadData();

    // Refresh every 30 seconds
    const interval = setInterval(() => {
      fetchStats();
      fetchServiceStatus();
      fetchAwsHealth();
    }, 30000);

    return () => clearInterval(interval);
  }, []);

  // Handle search
  const handleSearch = (e) => {
    e.preventDefault();
    fetchUsers(1, searchQuery);
  };

  // Handle strategy created/updated
  const handleStrategyChange = () => {
    fetchStrategies();
    setShowStrategyEditor(false);
    setEditingStrategy(null);
  };

  if (!isAdmin) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
        <h3 className="text-lg font-semibold text-red-800">Access Denied</h3>
        <p className="text-red-600 mt-2">You don't have permission to view this page.</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold text-gray-900">Admin Dashboard</h2>
        <button
          onClick={() => { fetchStats(); fetchServiceStatus(); fetchUsers(usersPagination.page, searchQuery); fetchStrategies(); }}
          className="px-4 py-2 text-sm bg-blue-100 text-blue-700 rounded-lg hover:bg-blue-200 transition-colors"
        >
          Refresh
        </button>
      </div>

      {/* Tab Navigation */}
      <div className="border-b border-gray-200">
        <nav className="flex gap-4 -mb-px">
          {TABS.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === tab.id
                    ? 'border-blue-600 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <Icon size={18} />
                {tab.label}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Tab Content */}
      {activeTab === 'overview' && (
        <OverviewTab
          stats={stats}
          serviceStatus={serviceStatus}
          activeStrategy={activeStrategy}
          awsHealth={awsHealth}
          pipelineLog={pipelineLog}
        />
      )}

      {activeTab === 'portfolio' && (
        <ModelPortfolioTab fetchWithAuth={fetchWithAuth} />
      )}

      {activeTab === 'strategies' && (
        <StrategiesTab
          strategies={strategies}
          activeStrategy={activeStrategy}
          analysisResults={analysisResults}
          analysisLoading={analysisLoading}
          runAnalysis={runAnalysis}
          activateStrategy={activateStrategy}
          onEditStrategy={(strategy) => {
            setEditingStrategy(strategy);
            setShowStrategyEditor(true);
            setActiveTab('lab');
          }}
        />
      )}

      {activeTab === 'lab' && (
        <StrategyLabTab
          fetchWithAuth={fetchWithAuth}
          strategies={strategies}
          onStrategyCreated={handleStrategyChange}
          showStrategyEditor={showStrategyEditor}
          setShowStrategyEditor={setShowStrategyEditor}
          editingStrategy={editingStrategy}
          setEditingStrategy={setEditingStrategy}
        />
      )}

      {activeTab === 'autopilot' && (
        <AutoPilotTab fetchWithAuth={fetchWithAuth} />
      )}

      {activeTab === 'social' && (
        <SocialTab fetchWithAuth={fetchWithAuth} />
      )}

      {activeTab === 'newsletter' && (
        <NewsletterTab fetchWithAuth={fetchWithAuth} />
      )}

      {activeTab === 'users' && (
        <UsersTab
          users={users}
          usersPagination={usersPagination}
          searchQuery={searchQuery}
          setSearchQuery={setSearchQuery}
          handleSearch={handleSearch}
          toggleUserStatus={toggleUserStatus}
          extendTrial={extendTrial}
          compUser={compUser}
          revokeComp={revokeComp}
          fetchUsers={fetchUsers}
        />
      )}
    </div>
  );
}

// Overview Tab Component
function OverviewTab({ stats, serviceStatus, activeStrategy, awsHealth, pipelineLog }) {
  return (
    <div className="space-y-6">
      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={<Users className="text-blue-600" />}
          label="Total Users"
          value={stats?.total_users || 0}
          subtext={`${stats?.new_users_week || 0} this week`}
        />
        <StatCard
          icon={<Clock className="text-yellow-600" />}
          label="Active Trials"
          value={stats?.active_trials || 0}
          subtext={`${stats?.expired_trials || 0} expired`}
        />
        <StatCard
          icon={<DollarSign className="text-green-600" />}
          label="Paid Subscribers"
          value={stats?.paid_subscribers || 0}
          subtext={`$${stats?.mrr?.toFixed(0) || 0} MRR`}
        />
        <StatCard
          icon={<Activity className="text-purple-600" />}
          label="System Status"
          value={serviceStatus?.overall_status === 'healthy' ? 'Healthy' : 'Degraded'}
          subtext={`${Object.keys(serviceStatus?.services || {}).length} services`}
          valueColor={serviceStatus?.overall_status === 'healthy' ? 'text-green-600' : 'text-yellow-600'}
        />
      </div>

      {/* Service Status */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Service Status</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {serviceStatus?.services && Object.entries(serviceStatus.services).map(([name, service]) => {
            // Combined Market Data card
            if (name === 'market_data') {
              const statusBadge = service.status === 'ok' ? 'bg-green-100 text-green-800' :
                service.status === 'degraded' ? 'bg-yellow-100 text-yellow-800' :
                'bg-red-100 text-red-800';
              const sourceDot = (s) => s === 'green' ? 'bg-green-500' : s === 'yellow' ? 'bg-yellow-500' : s === 'red' ? 'bg-red-500' : 'bg-gray-400';
              return (
                <div key={name} className="p-4 bg-gray-50 rounded-lg">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-medium text-gray-700">Market Data</span>
                    <span className={`px-2 py-1 rounded text-xs font-medium ${statusBadge}`}>
                      {service.status}
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5 mb-2">
                    <span className="text-xs text-gray-500">Primary:</span>
                    <span className="text-xs font-semibold text-gray-800 uppercase">{service.primary || '—'}</span>
                  </div>
                  <div className="space-y-1.5">
                    {['alpaca', 'yfinance'].map((src) => {
                      const s = service[src];
                      if (!s) return null;
                      return (
                        <div key={src} className="flex items-center justify-between">
                          <div className="flex items-center gap-1.5">
                            <div className={`w-2 h-2 rounded-full ${sourceDot(s.status)}`} />
                            <span className="text-xs text-gray-600 capitalize">{src}</span>
                            {service.primary === src && (
                              <span className="text-[9px] px-1 py-0.5 bg-blue-100 text-blue-700 rounded font-medium leading-none">PRIMARY</span>
                            )}
                          </div>
                          <div className="flex items-center gap-2 text-xs text-gray-500">
                            {s.total_requests > 0 && (
                              <span>{s.total_requests - s.total_failures}/{s.total_requests}</span>
                            )}
                            {s.consecutive_failures > 0 && (
                              <span className="text-red-500">{s.consecutive_failures}x fail</span>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                  {service.symbols_loaded !== undefined && (
                    <p className="text-xs text-gray-500 mt-2">{service.symbols_loaded} symbols cached</p>
                  )}
                  {service.error && (
                    <p className="text-xs text-red-500 truncate mt-1">{service.error}</p>
                  )}
                </div>
              );
            }

            // Generic service card (database, stripe, scanner)
            return (
              <div key={name} className="p-4 bg-gray-50 rounded-lg">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-medium text-gray-700 capitalize">{name}</span>
                  <span className={`px-2 py-1 rounded text-xs font-medium ${
                    service.status === 'ok' ? 'bg-green-100 text-green-800' :
                    service.status === 'not_configured' ? 'bg-gray-100 text-gray-600' :
                    'bg-red-100 text-red-800'
                  }`}>
                    {service.status}
                  </span>
                </div>
                {service.latency_ms && (
                  <p className="text-sm text-gray-500">{service.latency_ms}ms latency</p>
                )}
                {service.symbols_loaded !== undefined && (
                  <p className="text-sm text-gray-500">{service.symbols_loaded} symbols</p>
                )}
                {service.signals_today !== undefined && (
                  <p className="text-sm text-gray-500">{service.signals_today} signals today</p>
                )}
                {service.error && (
                  <p className="text-sm text-red-500 truncate">{service.error}</p>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Infrastructure Health */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <div className="flex items-center gap-2 mb-4">
          <Server size={20} className="text-gray-700" />
          <h3 className="text-lg font-semibold text-gray-900">Infrastructure</h3>
        </div>

        {!awsHealth || awsHealth.local_dev || awsHealth.error ? (
          <div className="p-4 bg-gray-50 rounded-lg text-sm text-gray-500">
            {awsHealth?.error
              ? `Infrastructure metrics error: ${awsHealth.error}`
              : 'Infrastructure metrics unavailable (local dev)'}
          </div>
        ) : (
          <>
            {/* Alarm Status */}
            {awsHealth.alarms.length > 0 && (
              <div className="mb-4">
                <p className="text-sm font-medium text-gray-600 mb-2">Alarm Status</p>
                <div className="flex flex-wrap gap-2">
                  {awsHealth.alarms.map((alarm) => (
                    <span
                      key={alarm.name}
                      className={`px-2.5 py-1 rounded-full text-xs font-medium ${
                        alarm.state === 'OK'
                          ? 'bg-green-100 text-green-800'
                          : alarm.state === 'ALARM'
                          ? 'bg-red-100 text-red-800'
                          : 'bg-gray-100 text-gray-600'
                      }`}
                    >
                      {alarm.name.replace('rigacap-prod-', '')}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Metrics Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* Lambda */}
              <div className="p-4 bg-gray-50 rounded-lg">
                <p className="text-sm font-medium text-gray-700 mb-2">Lambda</p>
                <div className="space-y-1 text-sm text-gray-600">
                  <p>Invocations (24h): <span className="font-medium text-gray-900">{awsHealth.metrics.lambda?.invocations_24h?.toLocaleString() ?? '—'}</span></p>
                  <p>Errors (24h): <span className={`font-medium ${(awsHealth.metrics.lambda?.errors_24h || 0) > 0 ? 'text-red-600' : 'text-gray-900'}`}>{awsHealth.metrics.lambda?.errors_24h ?? '—'}</span></p>
                  <p>Avg Duration: <span className="font-medium text-gray-900">{awsHealth.metrics.lambda?.avg_duration_ms != null ? `${awsHealth.metrics.lambda.avg_duration_ms}ms` : '—'}</span></p>
                </div>
              </div>

              {/* API Gateway */}
              <div className="p-4 bg-gray-50 rounded-lg">
                <p className="text-sm font-medium text-gray-700 mb-2">API Gateway</p>
                <div className="space-y-1 text-sm text-gray-600">
                  <p>Requests (24h): <span className="font-medium text-gray-900">{awsHealth.metrics.api_gateway?.requests_24h?.toLocaleString() ?? '—'}</span></p>
                </div>
              </div>

              {/* RDS */}
              <div className="p-4 bg-gray-50 rounded-lg">
                <p className="text-sm font-medium text-gray-700 mb-2">RDS</p>
                <div className="space-y-1 text-sm text-gray-600">
                  <p>CPU: <span className={`font-medium ${(awsHealth.metrics.rds?.cpu_percent || 0) > 80 ? 'text-red-600' : 'text-gray-900'}`}>{awsHealth.metrics.rds?.cpu_percent != null ? `${awsHealth.metrics.rds.cpu_percent}%` : '—'}</span></p>
                  <p>Free Storage: <span className="font-medium text-gray-900">{awsHealth.metrics.rds?.free_storage_gb != null ? `${awsHealth.metrics.rds.free_storage_gb} GB` : '—'}</span></p>
                  <p>Connections: <span className="font-medium text-gray-900">{awsHealth.metrics.rds?.connections ?? '—'}</span></p>
                </div>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Pipeline Log */}
      {pipelineLog && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Activity size={20} className="text-gray-700" />
              <h3 className="text-lg font-semibold text-gray-900">Last Pipeline Run</h3>
            </div>
            <div className="flex items-center gap-2">
              <span className={`px-2.5 py-1 rounded-full text-xs font-medium ${
                pipelineLog.status === 'success' ? 'bg-green-100 text-green-800' :
                pipelineLog.status === 'aborted' ? 'bg-yellow-100 text-yellow-800' :
                'bg-red-100 text-red-800'
              }`}>
                {pipelineLog.status}
              </span>
              {pipelineLog.completed_at && (
                <span className="text-xs text-gray-500">
                  {(() => {
                    const diff = Date.now() - new Date(pipelineLog.completed_at).getTime();
                    const mins = Math.floor(diff / 60000);
                    if (mins < 60) return `${mins}m ago`;
                    const hrs = Math.floor(mins / 60);
                    if (hrs < 24) return `${hrs}h ago`;
                    return `${Math.floor(hrs / 24)}d ago`;
                  })()}
                </span>
              )}
              <span className="text-xs text-gray-400">{pipelineLog.duration_seconds}s</span>
            </div>
          </div>

          {/* Market Summary */}
          {pipelineLog.market && (
            <div className="flex flex-wrap gap-3 mb-4 text-sm">
              {pipelineLog.market.regime && (
                <span className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded text-xs font-medium">
                  {pipelineLog.market.regime.replace(/_/g, ' ')}
                </span>
              )}
              {pipelineLog.market.spy_price && (
                <span className="text-gray-600">SPY ${Number(pipelineLog.market.spy_price).toFixed(2)}</span>
              )}
              {pipelineLog.market.vix_level && (
                <span className="text-gray-600">VIX {Number(pipelineLog.market.vix_level).toFixed(1)}</span>
              )}
              <span className="text-gray-600">{pipelineLog.market.signals} signals</span>
            </div>
          )}

          {/* Portfolio Summary */}
          {pipelineLog.portfolio && (pipelineLog.portfolio.live_value || pipelineLog.portfolio.entries > 0 || pipelineLog.portfolio.exits > 0) && (
            <div className="flex flex-wrap gap-3 mb-4 text-sm">
              {pipelineLog.portfolio.live_value && (
                <span className="text-gray-600">Portfolio ${Number(pipelineLog.portfolio.live_value).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</span>
              )}
              {pipelineLog.portfolio.positions != null && (
                <span className="text-gray-600">{pipelineLog.portfolio.positions} positions</span>
              )}
              {pipelineLog.portfolio.entries > 0 && (
                <span className="text-green-600 font-medium">+{pipelineLog.portfolio.entries} entries</span>
              )}
              {pipelineLog.portfolio.exits > 0 && (
                <span className="text-red-600 font-medium">{pipelineLog.portfolio.exits} exits</span>
              )}
              {pipelineLog.portfolio.regime_stop_pct && (
                <span className="text-gray-500">stop {pipelineLog.portfolio.regime_stop_pct}%</span>
              )}
            </div>
          )}

          {/* Steps */}
          {pipelineLog.steps && pipelineLog.steps.length > 0 && (
            <div className="space-y-1">
              {pipelineLog.steps.map((step, i) => (
                <div key={i} className="flex items-center gap-2 text-sm py-0.5">
                  <div className={`w-2 h-2 rounded-full flex-shrink-0 ${
                    step.status === 'ok' ? 'bg-green-500' :
                    step.status === 'warning' ? 'bg-yellow-500' :
                    step.status === 'error' ? 'bg-red-500' :
                    'bg-gray-400'
                  }`} />
                  <span className="text-gray-700 font-medium w-36 flex-shrink-0">{step.name}</span>
                  <span className="text-gray-400 w-12 text-right flex-shrink-0">{step.duration_s}s</span>
                  <span className="text-gray-500 truncate">{step.detail}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Active Strategy Summary */}
      {activeStrategy && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Active Strategy</h3>
          <div className="p-4 bg-gradient-to-r from-emerald-50 to-green-50 border border-emerald-200 rounded-xl">
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <Zap size={18} className="text-emerald-600" />
                  <span className="text-sm font-medium text-emerald-700">Currently Active</span>
                </div>
                <h4 className="text-xl font-bold text-gray-900">{activeStrategy.name}</h4>
                <p className="text-sm text-gray-600 mt-1">{activeStrategy.description}</p>
              </div>
              <span className={`px-3 py-1 rounded-full text-xs font-medium ${
                activeStrategy.strategy_type === 'momentum'
                  ? 'bg-purple-100 text-purple-800'
                  : 'bg-blue-100 text-blue-800'
              }`}>
                {activeStrategy.strategy_type.toUpperCase()}
              </span>
            </div>
            {activeStrategy.latest_evaluation && (
              <div className="mt-4 pt-4 border-t border-emerald-200 grid grid-cols-4 gap-4">
                <div>
                  <p className="text-xs text-gray-500">Sharpe</p>
                  <p className="font-semibold text-emerald-700">{activeStrategy.latest_evaluation.sharpe_ratio?.toFixed(2) || '-'}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Return</p>
                  <p className={`font-semibold ${(activeStrategy.latest_evaluation.total_return_pct || 0) >= 0 ? 'text-emerald-700' : 'text-red-600'}`}>
                    {(activeStrategy.latest_evaluation.total_return_pct || 0) >= 0 ? '+' : ''}{activeStrategy.latest_evaluation.total_return_pct?.toFixed(1) || '-'}%
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Max DD</p>
                  <p className="font-semibold text-red-600">-{activeStrategy.latest_evaluation.max_drawdown_pct?.toFixed(1) || '-'}%</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Score</p>
                  <p className="font-semibold">{activeStrategy.latest_evaluation.recommendation_score?.toFixed(0) || '-'}</p>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// Strategies Tab Component
function StrategiesTab({ strategies, activeStrategy, analysisResults, analysisLoading, runAnalysis, activateStrategy, onEditStrategy }) {
  return (
    <div className="space-y-6">
      {/* Header with Run Analysis button */}
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-semibold text-gray-900">Strategy Library</h3>
        <button
          onClick={() => runAnalysis(90)}
          disabled={analysisLoading}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
        >
          {analysisLoading ? (
            <>
              <RefreshCw size={16} className="animate-spin" />
              Analyzing...
            </>
          ) : (
            <>
              <PlayCircle size={16} />
              Run Analysis
            </>
          )}
        </button>
      </div>

      {/* Active Strategy Card */}
      {activeStrategy && (
        <div className="p-4 bg-gradient-to-r from-emerald-50 to-green-50 border border-emerald-200 rounded-xl">
          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <Zap size={18} className="text-emerald-600" />
                <span className="text-sm font-medium text-emerald-700">Active Strategy</span>
              </div>
              <h4 className="text-xl font-bold text-gray-900">{activeStrategy.name}</h4>
              <p className="text-sm text-gray-600 mt-1">{activeStrategy.description}</p>
            </div>
            <span className={`px-3 py-1 rounded-full text-xs font-medium ${
              activeStrategy.strategy_type === 'momentum'
                ? 'bg-purple-100 text-purple-800'
                : 'bg-blue-100 text-blue-800'
            }`}>
              {activeStrategy.strategy_type.toUpperCase()}
            </span>
          </div>
          <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div>
              <p className="text-xs text-gray-500">Max Positions</p>
              <p className="font-semibold">{activeStrategy.parameters?.max_positions || '-'}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">Position Size</p>
              <p className="font-semibold">{activeStrategy.parameters?.position_size_pct || '-'}%</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">Stop Type</p>
              <p className="font-semibold">
                {activeStrategy.parameters?.trailing_stop_pct
                  ? `${activeStrategy.parameters.trailing_stop_pct}% Trailing`
                  : `${activeStrategy.parameters?.stop_loss_pct || '-'}% Fixed`}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500">Activated</p>
              <p className="font-semibold">
                {activeStrategy.activated_at
                  ? formatDate(activeStrategy.activated_at)
                  : '-'}
              </p>
            </div>
          </div>
          {activeStrategy.latest_evaluation && (
            <div className="mt-4 pt-4 border-t border-emerald-200 grid grid-cols-4 gap-4">
              <div>
                <p className="text-xs text-gray-500">Sharpe</p>
                <p className="font-semibold text-emerald-700">{activeStrategy.latest_evaluation.sharpe_ratio?.toFixed(2) || '-'}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500">Return</p>
                <p className={`font-semibold ${(activeStrategy.latest_evaluation.total_return_pct || 0) >= 0 ? 'text-emerald-700' : 'text-red-600'}`}>
                  {(activeStrategy.latest_evaluation.total_return_pct || 0) >= 0 ? '+' : ''}{activeStrategy.latest_evaluation.total_return_pct?.toFixed(1) || '-'}%
                </p>
              </div>
              <div>
                <p className="text-xs text-gray-500">Max DD</p>
                <p className="font-semibold text-red-600">-{activeStrategy.latest_evaluation.max_drawdown_pct?.toFixed(1) || '-'}%</p>
              </div>
              <div>
                <p className="text-xs text-gray-500">Score</p>
                <p className="font-semibold">{activeStrategy.latest_evaluation.recommendation_score?.toFixed(0) || '-'}</p>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Strategy Library Table */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Strategy</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Sharpe</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Return</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Max DD</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Score</th>
                <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">Status</th>
                <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {strategies.map((strategy) => (
                <tr key={strategy.id} className={strategy.is_active ? 'bg-emerald-50' : 'hover:bg-gray-50'}>
                  <td className="px-4 py-3">
                    <div className="font-medium text-gray-900">{strategy.name}</div>
                    <div className="text-xs text-gray-500 truncate max-w-[200px]">{strategy.description}</div>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-1 rounded text-xs font-medium ${
                      strategy.strategy_type === 'momentum'
                        ? 'bg-purple-100 text-purple-800'
                        : 'bg-blue-100 text-blue-800'
                    }`}>
                      {strategy.strategy_type}
                    </span>
                    {strategy.source === 'ai_generated' && (
                      <span className="ml-1 px-1.5 py-0.5 rounded text-xs bg-amber-100 text-amber-700">AI</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right font-medium">
                    {strategy.latest_evaluation?.sharpe_ratio?.toFixed(2) || '-'}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <span className={`font-medium ${(strategy.latest_evaluation?.total_return_pct || 0) >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                      {strategy.latest_evaluation?.total_return_pct != null
                        ? `${strategy.latest_evaluation.total_return_pct >= 0 ? '+' : ''}${strategy.latest_evaluation.total_return_pct.toFixed(1)}%`
                        : '-'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right text-red-600 font-medium">
                    {strategy.latest_evaluation?.max_drawdown_pct != null
                      ? `-${strategy.latest_evaluation.max_drawdown_pct.toFixed(1)}%`
                      : '-'}
                  </td>
                  <td className="px-4 py-3 text-right font-bold">
                    {strategy.latest_evaluation?.recommendation_score?.toFixed(0) || '-'}
                  </td>
                  <td className="px-4 py-3 text-center">
                    {strategy.is_active ? (
                      <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800">
                        <CheckCircle size={12} /> Active
                      </span>
                    ) : (
                      <span className="text-xs text-gray-500">Inactive</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <div className="flex items-center justify-center gap-2">
                      {strategy.is_custom && (
                        <button
                          onClick={() => onEditStrategy(strategy)}
                          className="px-2 py-1 text-xs font-medium text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded"
                        >
                          Edit
                        </button>
                      )}
                      {!strategy.is_active && (
                        <button
                          onClick={() => activateStrategy(strategy.id)}
                          className="px-3 py-1 text-xs font-medium text-blue-600 hover:text-blue-800 hover:bg-blue-50 rounded"
                        >
                          Activate
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Analysis Results Panel */}
      {analysisResults && (
        <div className="p-4 bg-gray-50 rounded-xl border border-gray-200">
          <div className="flex items-center justify-between mb-3">
            <h4 className="font-semibold text-gray-900">Latest Analysis</h4>
            <span className="text-xs text-gray-500">
              {analysisResults.analysis_date
                ? new Date(analysisResults.analysis_date).toLocaleString()
                : '-'}
              {' '}&bull;{' '}{analysisResults.lookback_days} day lookback
            </span>
          </div>
          <div className="p-3 bg-white rounded-lg border border-gray-200">
            <div className="flex items-start gap-3">
              {analysisResults.recommended_strategy_id === analysisResults.current_active_strategy_id ? (
                <CheckCircle size={20} className="text-emerald-600 mt-0.5" />
              ) : (
                <AlertCircle size={20} className="text-amber-500 mt-0.5" />
              )}
              <div>
                <p className="text-sm text-gray-700 whitespace-pre-line">
                  {analysisResults.recommendation_notes}
                </p>
                {analysisResults.recommended_strategy_id !== analysisResults.current_active_strategy_id && (
                  <button
                    onClick={() => activateStrategy(analysisResults.recommended_strategy_id)}
                    className="mt-3 px-4 py-2 bg-amber-500 text-white text-sm font-medium rounded-lg hover:bg-amber-600 transition-colors"
                  >
                    Accept Recommendation
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// Strategy Lab Tab Component
function StrategyLabTab({ fetchWithAuth, strategies, onStrategyCreated, showStrategyEditor, setShowStrategyEditor, editingStrategy, setEditingStrategy }) {
  return (
    <div className="space-y-6">
      {/* Create Strategy Button */}
      <div className="flex justify-end">
        <button
          onClick={() => {
            setEditingStrategy(null);
            setShowStrategyEditor(true);
          }}
          className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors"
        >
          <Plus size={16} />
          Create Custom Strategy
        </button>
      </div>

      {/* Strategy Editor */}
      {showStrategyEditor && (
        <StrategyEditor
          fetchWithAuth={fetchWithAuth}
          strategy={editingStrategy}
          strategies={strategies}
          onSave={onStrategyCreated}
          onCancel={() => {
            setShowStrategyEditor(false);
            setEditingStrategy(null);
          }}
        />
      )}

      {/* AI Strategy Generator */}
      <StrategyGenerator
        fetchWithAuth={fetchWithAuth}
        onStrategyCreated={onStrategyCreated}
      />

      {/* Flexible Backtest */}
      <FlexibleBacktest
        fetchWithAuth={fetchWithAuth}
        strategies={strategies}
      />
    </div>
  );
}

// Auto-Pilot Tab Component
function AutoPilotTab({ fetchWithAuth }) {
  return (
    <div className="space-y-6">
      {/* Walk-Forward Simulator */}
      <WalkForwardSimulator fetchWithAuth={fetchWithAuth} />

      {/* Auto-Switch Configuration */}
      <AutoSwitchConfig fetchWithAuth={fetchWithAuth} />
    </div>
  );
}

// Users Tab Component
function UsersTab({ users, usersPagination, searchQuery, setSearchQuery, handleSearch, toggleUserStatus, extendTrial, compUser, revokeComp, fetchUsers }) {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200">
      <div className="p-6 border-b border-gray-200">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
          <h3 className="text-lg font-semibold text-gray-900">Users</h3>
          <form onSubmit={handleSearch} className="flex gap-2">
            <div className="relative">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search users..."
                className="pl-10 pr-4 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
            <button
              type="submit"
              className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 transition-colors"
            >
              Search
            </button>
          </form>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">User</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Subscription</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Created</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Last Login</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {users.map((user) => (
              <tr key={user.id} className="hover:bg-gray-50">
                <td className="px-6 py-4 whitespace-nowrap">
                  <div>
                    <div className="text-sm font-medium text-gray-900">{user.name || 'No name'}</div>
                    <div className="text-sm text-gray-500">{user.email}</div>
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span className={`px-2 py-1 rounded text-xs font-medium ${
                    user.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                  }`}>
                    {user.is_active ? 'Active' : 'Disabled'}
                  </span>
                  {user.role === 'admin' && (
                    <span className="ml-2 px-2 py-1 rounded text-xs font-medium bg-purple-100 text-purple-800">
                      Admin
                    </span>
                  )}
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="text-sm text-gray-900 capitalize">{user.subscription_status || 'None'}</div>
                  {user.subscription_status === 'trial' && user.trial_days_remaining !== null && (
                    <div className="text-xs text-gray-500">
                      {user.trial_days_remaining} days left
                    </div>
                  )}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {user.created_at ? formatDate(user.created_at) : '-'}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {user.last_login ? formatDate(user.last_login) : 'Never'}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm">
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => toggleUserStatus(user.id, user.is_active)}
                      className={`p-1 rounded ${user.is_active ? 'text-red-600 hover:bg-red-50' : 'text-green-600 hover:bg-green-50'}`}
                      title={user.is_active ? 'Disable user' : 'Enable user'}
                    >
                      {user.is_active ? <ToggleRight size={20} /> : <ToggleLeft size={20} />}
                    </button>
                    {user.subscription_status === 'trial' && (
                      <button
                        onClick={() => extendTrial(user.id)}
                        className="p-1 rounded text-blue-600 hover:bg-blue-50"
                        title="Extend trial by 7 days"
                      >
                        <Plus size={20} />
                      </button>
                    )}
                    {user.subscription_status !== 'active' ? (
                      <button
                        onClick={() => compUser(user.id)}
                        className="px-2 py-1 rounded text-xs font-medium text-emerald-700 bg-emerald-50 hover:bg-emerald-100"
                        title="Grant comp subscription"
                      >
                        Comp
                      </button>
                    ) : (
                      <button
                        onClick={() => revokeComp(user.id)}
                        className="px-2 py-1 rounded text-xs font-medium text-orange-700 bg-orange-50 hover:bg-orange-100"
                        title="Revoke comp subscription"
                      >
                        Revoke
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="px-6 py-4 border-t border-gray-200 flex justify-between items-center">
        <p className="text-sm text-gray-500">
          Showing {((usersPagination.page - 1) * usersPagination.per_page) + 1} to{' '}
          {Math.min(usersPagination.page * usersPagination.per_page, usersPagination.total)} of{' '}
          {usersPagination.total} users
        </p>
        <div className="flex gap-2">
          <button
            onClick={() => fetchUsers(usersPagination.page - 1, searchQuery)}
            disabled={usersPagination.page <= 1}
            className="p-2 rounded border border-gray-300 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <ChevronLeft size={16} />
          </button>
          <button
            onClick={() => fetchUsers(usersPagination.page + 1, searchQuery)}
            disabled={usersPagination.page * usersPagination.per_page >= usersPagination.total}
            className="p-2 rounded border border-gray-300 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <ChevronRight size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}

// Model Portfolio Tab Component
function ModelPortfolioTab({ fetchWithAuth }) {
  const [data, setData] = useState(null);
  const [equityCurve, setEquityCurve] = useState([]);
  const [trades, setTrades] = useState([]);
  const [expandedTrade, setExpandedTrade] = useState(null);
  const [tradeDetail, setTradeDetail] = useState(null);
  const [subscriberPreview, setSubscriberPreview] = useState(null);
  const [regimeHistory, setRegimeHistory] = useState([]);
  const [regimeAccuracy, setRegimeAccuracy] = useState(null);
  const [whatIfResult, setWhatIfResult] = useState(null);
  const [whatIfDate, setWhatIfDate] = useState('2026-02-01');
  const [whatIfCapital, setWhatIfCapital] = useState(10000);
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState(false);
  const [liveQuotes, setLiveQuotes] = useState({});
  const [signalTrackStats, setSignalTrackStats] = useState(null);
  const [chartSymbol, setChartSymbol] = useState(null);
  const [chartData, setChartData] = useState([]);
  const [chartLoading, setChartLoading] = useState(false);
  const [chartTrade, setChartTrade] = useState(null); // { entry_date, entry_price, exit_date?, exit_price? }

  const fetchPortfolio = async () => {
    try {
      const response = await fetchWithAuth(`${API_URL}/api/admin/model-portfolio`);
      if (response.ok) {
        setData(await response.json());
      }
    } catch (err) {
      console.error('Failed to fetch model portfolio:', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchEquityCurve = async () => {
    try {
      const response = await fetchWithAuth(`${API_URL}/api/admin/model-portfolio/equity-curve`);
      if (response.ok) setEquityCurve(await response.json());
    } catch (err) {
      console.error('Failed to fetch equity curve:', err);
    }
  };

  const fetchTrades = async () => {
    try {
      const response = await fetchWithAuth(`${API_URL}/api/admin/model-portfolio/trades?limit=100`);
      if (response.ok) setTrades(await response.json());
    } catch (err) {
      console.error('Failed to fetch trades:', err);
    }
  };

  const fetchSignalTrackStats = async () => {
    try {
      const response = await fetchWithAuth(`${API_URL}/api/signals/signal-track-record`);
      if (response.ok) setSignalTrackStats(await response.json());
    } catch (err) {
      console.error('Failed to fetch signal track stats:', err);
    }
  };

  const fetchSubscriberPreview = async () => {
    try {
      const response = await fetchWithAuth(`${API_URL}/api/admin/model-portfolio/subscriber-preview`);
      if (response.ok) setSubscriberPreview(await response.json());
    } catch (err) {
      console.error('Failed to fetch subscriber preview:', err);
    }
  };

  const fetchRegimeData = async () => {
    try {
      const [histResp, accResp] = await Promise.all([
        fetchWithAuth(`${API_URL}/api/admin/regime-forecast/history?days=90`),
        fetchWithAuth(`${API_URL}/api/admin/regime-forecast/accuracy?days=90`),
      ]);
      if (histResp.ok) setRegimeHistory(await histResp.json());
      if (accResp.ok) setRegimeAccuracy(await accResp.json());
    } catch (err) {
      console.error('Failed to fetch regime data:', err);
    }
  };

  const fetchWhatIf = async () => {
    try {
      const response = await fetchWithAuth(
        `${API_URL}/api/admin/model-portfolio/what-if?start_date=${whatIfDate}&capital=${whatIfCapital}`
      );
      if (response.ok) setWhatIfResult(await response.json());
    } catch (err) {
      console.error('Failed to calculate what-if:', err);
    }
  };

  const fetchTradeDetail = async (tradeId) => {
    if (expandedTrade === tradeId) {
      setExpandedTrade(null);
      setTradeDetail(null);
      return;
    }
    setExpandedTrade(tradeId);
    try {
      const response = await fetchWithAuth(`${API_URL}/api/admin/model-portfolio/trades/${tradeId}`);
      if (response.ok) setTradeDetail(await response.json());
    } catch (err) {
      console.error('Failed to fetch trade detail:', err);
    }
  };

  const generateAutopsy = async (tradeId) => {
    try {
      const response = await fetchWithAuth(`${API_URL}/api/admin/model-portfolio/trades/${tradeId}/autopsy`, {
        method: 'POST',
      });
      if (response.ok) {
        // Refresh trade detail to show autopsy
        const detailResp = await fetchWithAuth(`${API_URL}/api/admin/model-portfolio/trades/${tradeId}`);
        if (detailResp.ok) setTradeDetail(await detailResp.json());
      }
    } catch (err) {
      console.error('Failed to generate autopsy:', err);
    }
  };

  const fetchLiveQuotes = async (positions) => {
    const symbols = positions || [
      ...(data?.live?.open_positions || []),
      ...(data?.walkforward?.open_positions || []),
    ].map(p => p.symbol);
    if (symbols.length === 0) return;
    try {
      const response = await fetchWithAuth(`${API_URL}/api/quotes/live?symbols=${[...new Set(symbols)].join(',')}`);
      if (response.ok) {
        const result = await response.json();
        if (result.quotes) setLiveQuotes(result.quotes);
      }
    } catch (err) {
      console.log('Live quotes fetch failed:', err);
    }
  };

  // Merge live quotes into portfolio positions
  const mergeQuotes = (positions) => {
    if (!positions || Object.keys(liveQuotes).length === 0) return positions;
    return positions.map(pos => {
      const quote = liveQuotes[pos.symbol];
      if (quote) {
        const livePrice = quote.price;
        const pnlPct = pos.entry_price > 0 ? ((livePrice - pos.entry_price) / pos.entry_price) * 100 : 0;
        const pnlDollars = (livePrice - pos.entry_price) * (pos.shares || 0);
        const hwm = Math.max(pos.highest_price || pos.entry_price, livePrice);
        return { ...pos, current_price: livePrice, pnl_pct: pnlPct, pnl_dollars: pnlDollars, highest_price: hwm };
      }
      return pos;
    });
  };

  // Recompute portfolio summaries when live quotes arrive
  const liveData = useMemo(() => {
    if (!data || Object.keys(liveQuotes).length === 0) return data;
    const adjusted = {};
    for (const key of Object.keys(data)) {
      const p = data[key];
      if (!p?.open_positions) { adjusted[key] = p; continue; }
      const positions = mergeQuotes(p.open_positions);
      const positionsValue = positions.reduce((sum, pos) => sum + (pos.current_price || 0) * (pos.shares || 0), 0);
      const totalValue = (p.current_cash || 0) + positionsValue;
      const unrealizedPnl = positions.reduce((sum, pos) => sum + (pos.pnl_dollars || 0), 0);
      const totalReturnPct = p.starting_capital > 0 ? ((totalValue / p.starting_capital) - 1) * 100 : 0;
      adjusted[key] = { ...p, total_value: totalValue, total_return_pct: totalReturnPct, unrealized_pnl: unrealizedPnl, open_positions: positions };
    }
    return adjusted;
  }, [data, liveQuotes]);

  const openChart = async (symbol, trade = null) => {
    setChartSymbol(symbol);
    setChartTrade(trade);
    setChartLoading(true);
    setChartData([]);
    try {
      // Fetch enough data to show trade context
      let days = 252;
      if (trade?.entry_date) {
        const entryDate = new Date(trade.entry_date);
        const daysSince = Math.ceil((Date.now() - entryDate.getTime()) / 86400000);
        days = Math.max(days, daysSince + 30);
      }
      const response = await fetchWithAuth(`${API_URL}/api/stock/${symbol}/history?days=${days}`);
      const res = await response.json();
      let prices = res?.data || [];
      if (!Array.isArray(prices)) prices = [];

      // Annotate chart data with buy/sell markers
      if (trade && prices.length > 0) {
        const entryStr = trade.entry_date?.slice(0, 10);
        const exitStr = trade.exit_date?.slice(0, 10);
        prices = prices.map(p => ({
          ...p,
          buyMarker: p.date === entryStr ? trade.entry_price : null,
          sellMarker: p.date === exitStr ? trade.exit_price : null,
        }));
      }
      setChartData(prices);
    } catch (err) {
      console.error('Chart fetch failed:', err);
    } finally {
      setChartLoading(false);
    }
  };

  useEffect(() => {
    fetchPortfolio();
    fetchEquityCurve();
    fetchTrades();
    fetchSignalTrackStats();
    fetchSubscriberPreview();
    fetchRegimeData();
    const interval = setInterval(fetchPortfolio, 30000);
    return () => clearInterval(interval);
  }, []);

  // Poll live quotes every 30 seconds
  useEffect(() => {
    if (!data) return;
    fetchLiveQuotes();
    const interval = setInterval(fetchLiveQuotes, 30000);
    return () => clearInterval(interval);
  }, [data]);

  const runAction = async (action, extra = {}) => {
    setProcessing(true);
    try {
      const response = await fetchWithAuth(`${API_URL}/api/admin/model-portfolio/action`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, ...extra }),
      });
      if (response.ok) {
        await fetchPortfolio();
        await fetchEquityCurve();
        await fetchTrades();
        await fetchSubscriberPreview();
      }
    } catch (err) {
      console.error('Action failed:', err);
    } finally {
      setProcessing(false);
    }
  };

  if (loading) {
    return <div className="text-center py-12 text-gray-500">Loading portfolios...</div>;
  }

  if (!data) {
    return <div className="text-center py-12 text-gray-500">Portfolio is in cash — waiting for signals</div>;
  }

  const portfolios = [
    { key: 'live', label: 'Live Portfolio', desc: 'Intraday monitoring, trailing stop & regime exits' },
  ];

  const exitReasonBadge = (reason) => {
    const colors = {
      trailing_stop: 'bg-red-100 text-red-700',
      rebalance_exit: 'bg-blue-100 text-blue-700',
      regime_exit: 'bg-amber-100 text-amber-700',
    };
    return (
      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${colors[reason] || 'bg-gray-100 text-gray-600'}`}>
        {(reason || 'unknown').replace('_', ' ')}
      </span>
    );
  };

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {portfolios.map(({ key, label, desc }) => {
          const p = liveData[key];
          if (!p) return null;
          const returnPct = p.total_return_pct || 0;
          const returnColor = returnPct > 0 ? 'text-green-600' : returnPct < 0 ? 'text-red-600' : 'text-gray-600';
          return (
            <div key={key} className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
              <div className="flex items-center justify-between mb-1">
                <h3 className="text-lg font-semibold text-gray-900">{label}</h3>
                <span className={`text-xs px-2 py-1 rounded-full font-medium ${
                  key === 'live' ? 'bg-green-100 text-green-700' : 'bg-blue-100 text-blue-700'
                }`}>
                  {key === 'live' ? 'LIVE' : 'WF'}
                </span>
              </div>
              <p className="text-xs text-gray-400 mb-4">{desc}</p>

              <div className="grid grid-cols-3 gap-4 mb-4">
                <div>
                  <p className="text-xs text-gray-500">Total Value</p>
                  <p className="text-lg font-bold text-gray-900">${p.total_value?.toLocaleString(undefined, {minimumFractionDigits: 0, maximumFractionDigits: 0})}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Return</p>
                  <p className={`text-lg font-bold ${returnColor}`}>{returnPct >= 0 ? '+' : ''}{returnPct.toFixed(1)}%</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Cash</p>
                  <p className="text-lg font-bold text-gray-900">${p.current_cash?.toLocaleString(undefined, {minimumFractionDigits: 0, maximumFractionDigits: 0})}</p>
                </div>
              </div>

              <div className="grid grid-cols-4 gap-3 text-center">
                <div className="bg-gray-50 rounded-lg p-2">
                  <p className="text-xs text-gray-400">Trades</p>
                  <p className="font-semibold text-gray-900">{p.total_trades}</p>
                </div>
                <div className="bg-gray-50 rounded-lg p-2">
                  <p className="text-xs text-gray-400">Win Rate</p>
                  <p className="font-semibold text-gray-900">{p.win_rate}%</p>
                </div>
                <div className="bg-gray-50 rounded-lg p-2">
                  <p className="text-xs text-gray-400">Realized</p>
                  <p className={`font-semibold ${p.realized_pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                    ${p.realized_pnl?.toLocaleString(undefined, {minimumFractionDigits: 0, maximumFractionDigits: 0})}
                  </p>
                </div>
                <div className="bg-gray-50 rounded-lg p-2">
                  <p className="text-xs text-gray-400">Unrealized</p>
                  <p className={`font-semibold ${p.unrealized_pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                    ${p.unrealized_pnl?.toLocaleString(undefined, {minimumFractionDigits: 0, maximumFractionDigits: 0})}
                  </p>
                </div>
              </div>

              {/* Open Positions */}
              {p.open_positions?.length > 0 && (
                <div className="mt-4">
                  <h4 className="text-sm font-medium text-gray-700 mb-2">Open Positions ({p.open_positions.length})</h4>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-left text-xs text-gray-400 border-b border-gray-100">
                          <th className="pb-2 pr-3">Symbol</th>
                          <th className="pb-2 pr-3">Entry Date</th>
                          <th className="pb-2 pr-3">Entry</th>
                          <th className="pb-2 pr-3">Current</th>
                          <th className="pb-2 pr-3">P&L</th>
                          <th className="pb-2 pr-3">Days</th>
                          <th className="pb-2">Shares</th>
                        </tr>
                      </thead>
                      <tbody>
                        {p.open_positions.map((pos) => {
                          const pnlColor = pos.pnl_pct > 0 ? 'text-green-600' : pos.pnl_pct < 0 ? 'text-red-600' : 'text-gray-600';
                          const daysHeld = pos.entry_date ? Math.floor((Date.now() - new Date(pos.entry_date).getTime()) / 86400000) : null;
                          return (
                            <tr key={pos.symbol} className="border-b border-gray-50">
                              <td className="py-2 pr-3 font-medium text-indigo-600 cursor-pointer hover:text-indigo-800 hover:underline" onClick={() => openChart(pos.symbol, { entry_date: pos.entry_date, entry_price: pos.entry_price })}>{pos.symbol}</td>
                              <td className="py-2 pr-3 text-gray-500 text-xs">{formatDate(pos.entry_date) || '—'}</td>
                              <td className="py-2 pr-3 text-gray-600">${pos.entry_price?.toFixed(2)}</td>
                              <td className="py-2 pr-3 text-gray-600">${pos.current_price?.toFixed(2)}</td>
                              <td className={`py-2 pr-3 font-medium ${pnlColor}`}>
                                {pos.pnl_pct >= 0 ? '+' : ''}{pos.pnl_pct?.toFixed(1)}%
                                <span className="text-xs text-gray-400 ml-1">
                                  (${pos.pnl_dollars >= 0 ? '+' : ''}{pos.pnl_dollars?.toLocaleString(undefined, {minimumFractionDigits: 0, maximumFractionDigits: 0})})
                                </span>
                              </td>
                              <td className="py-2 pr-3 text-gray-500 text-xs">{daysHeld != null ? `${daysHeld}d` : '—'}</td>
                              <td className="py-2 text-gray-600">{pos.shares?.toFixed(1)}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
              {p.open_positions?.length === 0 && (
                <p className="mt-4 text-sm text-gray-400 italic">No open positions</p>
              )}

              {/* Recent Closed Trades */}
              {p.recent_trades?.length > 0 && (
                <div className="mt-4">
                  <h4 className="text-sm font-medium text-gray-700 mb-2">Recent Trades</h4>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-left text-xs text-gray-400 border-b border-gray-100">
                          <th className="pb-2 pr-3">Symbol</th>
                          <th className="pb-2 pr-3">Entry</th>
                          <th className="pb-2 pr-3">Exit</th>
                          <th className="pb-2 pr-3">P&L</th>
                          <th className="pb-2">Reason</th>
                        </tr>
                      </thead>
                      <tbody>
                        {p.recent_trades.map((t) => {
                          const tPnlColor = (t.pnl_pct || 0) > 0 ? 'text-green-600' : (t.pnl_pct || 0) < 0 ? 'text-red-600' : 'text-gray-600';
                          return (
                            <tr key={t.id} className="border-b border-gray-50">
                              <td className="py-1.5 pr-3 font-medium text-indigo-600 cursor-pointer hover:text-indigo-800 hover:underline" onClick={() => openChart(t.symbol, { entry_date: t.entry_date, entry_price: t.entry_price, exit_date: t.exit_date, exit_price: t.exit_price })}>{t.symbol}</td>
                              <td className="py-1.5 pr-3 text-gray-500 text-xs">
                                {formatDate(t.entry_date) || '—'}
                                <span className="text-gray-400 ml-1">${t.entry_price?.toFixed(2)}</span>
                              </td>
                              <td className="py-1.5 pr-3 text-gray-500 text-xs">
                                {formatDate(t.exit_date) || '—'}
                                <span className="text-gray-400 ml-1">${t.exit_price?.toFixed(2)}</span>
                              </td>
                              <td className={`py-1.5 pr-3 font-medium ${tPnlColor}`}>
                                {t.pnl_pct != null ? `${t.pnl_pct >= 0 ? '+' : ''}${t.pnl_pct?.toFixed(1)}%` : '—'}
                              </td>
                              <td className="py-1.5">{t.exit_reason ? exitReasonBadge(t.exit_reason) : '—'}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Signal Track Record */}
      {signalTrackStats && signalTrackStats.total_picks > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <div className="flex items-center gap-3 mb-1">
            <h3 className="text-lg font-semibold text-gray-900">Signal Track Record</h3>
            <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-purple-100 text-purple-700">EVERY PICK</span>
          </div>
          <p className="text-xs text-gray-400 mb-4">Tracks every fresh signal — no position limit, $10K flat sizing</p>

          {/* Stats row 1 */}
          <div className="grid grid-cols-3 md:grid-cols-6 gap-3 mb-4">
            <div className="bg-gray-50 rounded-lg p-2">
              <p className="text-xs text-gray-400">Total Picks</p>
              <p className="font-semibold text-gray-900">{signalTrackStats.total_picks}</p>
            </div>
            <div className="bg-gray-50 rounded-lg p-2">
              <p className="text-xs text-gray-400">Open</p>
              <p className="font-semibold text-blue-600">{signalTrackStats.open_count}</p>
            </div>
            <div className="bg-gray-50 rounded-lg p-2">
              <p className="text-xs text-gray-400">Closed</p>
              <p className="font-semibold text-gray-900">{signalTrackStats.closed_count}</p>
            </div>
            <div className="bg-gray-50 rounded-lg p-2">
              <p className="text-xs text-gray-400">Win Rate</p>
              <p className="font-semibold text-gray-900">{signalTrackStats.win_rate}%</p>
            </div>
            <div className="bg-gray-50 rounded-lg p-2">
              <p className="text-xs text-gray-400">Avg Gain</p>
              <p className="font-semibold text-green-600">+{signalTrackStats.avg_gain_pct?.toFixed(1)}%</p>
            </div>
            <div className="bg-gray-50 rounded-lg p-2">
              <p className="text-xs text-gray-400">Avg Loss</p>
              <p className="font-semibold text-red-600">{signalTrackStats.avg_loss_pct?.toFixed(1)}%</p>
            </div>
          </div>

          {/* Stats row 2 */}
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-4">
            <div className="bg-gray-50 rounded-lg p-2">
              <p className="text-xs text-gray-400">Avg P&L</p>
              <p className={`font-semibold ${signalTrackStats.avg_pnl_pct >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {signalTrackStats.avg_pnl_pct >= 0 ? '+' : ''}{signalTrackStats.avg_pnl_pct?.toFixed(2)}%
              </p>
            </div>
            <div className="bg-gray-50 rounded-lg p-2">
              <p className="text-xs text-gray-400">Avg Holding</p>
              <p className="font-semibold text-gray-900">{signalTrackStats.avg_holding_days} days</p>
            </div>
            <div className="bg-gray-50 rounded-lg p-2 col-span-2 md:col-span-1">
              <p className="text-xs text-gray-400">Best / Worst</p>
              <p className="font-semibold">
                {signalTrackStats.best_pick ? (
                  <span className="text-green-600">{signalTrackStats.best_pick.symbol} +{signalTrackStats.best_pick.pnl_pct}%</span>
                ) : '—'}
                {' / '}
                {signalTrackStats.worst_pick ? (
                  <span className="text-red-600">{signalTrackStats.worst_pick.symbol} {signalTrackStats.worst_pick.pnl_pct}%</span>
                ) : '—'}
              </p>
            </div>
          </div>

          {/* Open Positions */}
          {signalTrackStats.open_positions?.length > 0 && (
            <div className="mt-4">
              <h4 className="text-sm font-medium text-gray-700 mb-2">Open Positions ({signalTrackStats.open_positions.length})</h4>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-gray-400 border-b border-gray-100">
                      <th className="pb-2 pr-3">Symbol</th>
                      <th className="pb-2 pr-3">Entry Date</th>
                      <th className="pb-2 pr-3">Entry</th>
                      <th className="pb-2 pr-3">Current</th>
                      <th className="pb-2 pr-3">P&L</th>
                      <th className="pb-2">HWM</th>
                    </tr>
                  </thead>
                  <tbody>
                    {signalTrackStats.open_positions.map((pos) => {
                      const pnlColor = pos.pnl_pct > 0 ? 'text-green-600' : pos.pnl_pct < 0 ? 'text-red-600' : 'text-gray-600';
                      return (
                        <tr key={pos.symbol} className="border-b border-gray-50">
                          <td className="py-2 pr-3 font-medium text-indigo-600 cursor-pointer hover:text-indigo-800 hover:underline" onClick={() => openChart(pos.symbol)}>{pos.symbol}</td>
                          <td className="py-2 pr-3 text-gray-500 text-xs">{formatDate(pos.entry_date) || '—'}</td>
                          <td className="py-2 pr-3 text-gray-600">${pos.entry_price?.toFixed(2)}</td>
                          <td className="py-2 pr-3 text-gray-600">${pos.current_price?.toFixed(2)}</td>
                          <td className={`py-2 pr-3 font-medium ${pnlColor}`}>
                            {pos.pnl_pct >= 0 ? '+' : ''}{pos.pnl_pct?.toFixed(1)}%
                          </td>
                          <td className="py-2 text-gray-600">${pos.highest_price?.toFixed(2)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Recent Closed Trades */}
          {signalTrackStats.recent_closed?.length > 0 && (
            <div className="mt-4">
              <h4 className="text-sm font-medium text-gray-700 mb-2">Recent Closed ({signalTrackStats.recent_closed.length})</h4>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-gray-400 border-b border-gray-100">
                      <th className="pb-2 pr-3">Symbol</th>
                      <th className="pb-2 pr-3">Entry</th>
                      <th className="pb-2 pr-3">Exit</th>
                      <th className="pb-2 pr-3">P&L</th>
                      <th className="pb-2">Reason</th>
                    </tr>
                  </thead>
                  <tbody>
                    {signalTrackStats.recent_closed.map((t, i) => {
                      const tPnlColor = (t.pnl_pct || 0) > 0 ? 'text-green-600' : (t.pnl_pct || 0) < 0 ? 'text-red-600' : 'text-gray-600';
                      return (
                        <tr key={`${t.symbol}-${i}`} className="border-b border-gray-50">
                          <td className="py-1.5 pr-3 font-medium text-gray-900">{t.symbol}</td>
                          <td className="py-1.5 pr-3 text-gray-500 text-xs">
                            {formatDate(t.entry_date) || '—'}
                            <span className="text-gray-400 ml-1">${t.entry_price?.toFixed(2)}</span>
                          </td>
                          <td className="py-1.5 pr-3 text-gray-500 text-xs">
                            {formatDate(t.exit_date) || '—'}
                            <span className="text-gray-400 ml-1">${t.exit_price?.toFixed(2)}</span>
                          </td>
                          <td className={`py-1.5 pr-3 font-medium ${tPnlColor}`}>
                            {t.pnl_pct != null ? `${t.pnl_pct >= 0 ? '+' : ''}${t.pnl_pct?.toFixed(1)}%` : '—'}
                          </td>
                          <td className="py-1.5">{t.exit_reason ? exitReasonBadge(t.exit_reason) : '—'}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Equity Curve Chart */}
      {equityCurve.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Equity Curve</h3>
          <EquityCurveChart data={equityCurve} />
        </div>
      )}

      {/* Regime Intelligence */}
      {regimeHistory.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <div className="flex items-center gap-2 mb-4">
            <Shield size={18} className="text-blue-600" />
            <h3 className="text-lg font-semibold text-gray-900">Regime Intelligence</h3>
          </div>

          {/* Current Forecast */}
          {regimeHistory.length > 0 && (() => {
            const latest = regimeHistory[regimeHistory.length - 1];
            const regimeColors = {
              strong_bull: 'bg-green-100 text-green-700',
              weak_bull: 'bg-emerald-100 text-emerald-700',
              rotating_bull: 'bg-lime-100 text-lime-700',
              range_bound: 'bg-amber-100 text-amber-700',
              weak_bear: 'bg-orange-100 text-orange-700',
              panic_crash: 'bg-red-100 text-red-700',
              recovery: 'bg-blue-100 text-blue-700',
            };
            const outlookColors = {
              stable: 'text-green-600',
              improving: 'text-blue-600',
              deteriorating: 'text-red-600',
            };
            return (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                <div>
                  <p className="text-xs text-gray-400 mb-1">Current Regime</p>
                  <span className={`text-xs px-2.5 py-1 rounded-full font-semibold ${regimeColors[latest.regime] || 'bg-gray-100 text-gray-600'}`}>
                    {latest.regime?.replace('_', ' ')}
                  </span>
                </div>
                <div>
                  <p className="text-xs text-gray-400 mb-1">Outlook</p>
                  <span className={`text-sm font-semibold ${outlookColors[latest.outlook] || 'text-gray-600'}`}>
                    {latest.outlook}
                  </span>
                </div>
                <div>
                  <p className="text-xs text-gray-400 mb-1">Recommended</p>
                  <span className="text-sm font-medium text-gray-700">
                    {latest.recommended_action?.replace(/_/g, ' ')}
                  </span>
                </div>
                <div>
                  <p className="text-xs text-gray-400 mb-1">Risk</p>
                  <span className={`text-sm font-semibold ${
                    latest.risk_change === 'increasing' ? 'text-red-600' :
                    latest.risk_change === 'decreasing' ? 'text-green-600' : 'text-gray-600'
                  }`}>
                    {latest.risk_change}
                  </span>
                </div>
              </div>
            );
          })()}

          {/* Regime Timeline */}
          <div className="mb-4">
            <p className="text-xs text-gray-400 mb-2">Regime Timeline (last {regimeHistory.length} days)</p>
            <div className="flex h-6 rounded-md overflow-hidden">
              {regimeHistory.map((s, i) => {
                const colors = {
                  strong_bull: '#22c55e', weak_bull: '#10b981', rotating_bull: '#84cc16',
                  range_bound: '#f59e0b', weak_bear: '#f97316', panic_crash: '#ef4444', recovery: '#3b82f6',
                };
                return (
                  <div
                    key={i}
                    className="flex-1"
                    style={{ backgroundColor: colors[s.regime] || '#d1d5db' }}
                    title={`${s.date}: ${s.regime}`}
                  />
                );
              })}
            </div>
            <div className="flex justify-between text-xs text-gray-400 mt-1">
              <span>{formatDate(regimeHistory[0]?.date)}</span>
              <span>{formatDate(regimeHistory[regimeHistory.length - 1]?.date)}</span>
            </div>
          </div>

          {/* Accuracy */}
          {regimeAccuracy && regimeAccuracy.accuracy_pct != null && (
            <div className="bg-gray-50 rounded-lg p-3">
              <p className="text-sm text-gray-600">
                Forecast accuracy: <span className="font-bold text-gray-900">{regimeAccuracy.accuracy_pct}%</span>
                <span className="text-xs text-gray-400 ml-2">
                  ({regimeAccuracy.correct}/{regimeAccuracy.total_forecasts} correct predictions)
                </span>
              </p>
            </div>
          )}
        </div>
      )}

      {/* What-If Calculator */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <div className="flex items-center gap-2 mb-4">
          <Calculator size={18} className="text-indigo-600" />
          <h3 className="text-lg font-semibold text-gray-900">What If Calculator</h3>
        </div>
        <div className="flex items-end gap-3 mb-4">
          <div>
            <label className="text-xs text-gray-400 block mb-1">Start Date</label>
            <input
              type="date"
              value={whatIfDate}
              onChange={(e) => setWhatIfDate(e.target.value)}
              className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm"
            />
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-1">Capital ($)</label>
            <input
              type="number"
              value={whatIfCapital}
              onChange={(e) => setWhatIfCapital(Number(e.target.value))}
              className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm w-32"
              min={100}
            />
          </div>
          <button
            onClick={fetchWhatIf}
            className="px-4 py-1.5 text-sm bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
          >
            Calculate
          </button>
        </div>
        {whatIfResult && !whatIfResult.error && (
          <div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
              <div>
                <p className="text-xs text-gray-400">Final Value</p>
                <p className="text-xl font-bold text-gray-900">
                  ${whatIfResult.current_value?.toLocaleString(undefined, {minimumFractionDigits: 2})}
                </p>
              </div>
              <div>
                <p className="text-xs text-gray-400">Your Return</p>
                <p className={`text-xl font-bold ${whatIfResult.total_return_pct >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {whatIfResult.total_return_pct >= 0 ? '+' : ''}{whatIfResult.total_return_pct}%
                </p>
              </div>
              <div>
                <p className="text-xs text-gray-400">SPY Return</p>
                <p className="text-xl font-bold text-gray-600">
                  {whatIfResult.spy_return_pct != null ? `${whatIfResult.spy_return_pct >= 0 ? '+' : ''}${whatIfResult.spy_return_pct}%` : 'N/A'}
                </p>
              </div>
              <div>
                <p className="text-xs text-gray-400">Alpha vs SPY</p>
                <p className={`text-xl font-bold ${(whatIfResult.alpha_pct || 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {whatIfResult.alpha_pct != null ? `${whatIfResult.alpha_pct >= 0 ? '+' : ''}${whatIfResult.alpha_pct}%` : 'N/A'}
                </p>
              </div>
            </div>
            {whatIfResult.equity_curve?.length > 2 && (
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={whatIfResult.equity_curve} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd" tickFormatter={(d) => formatDate(d, { compact: true })} />
                  <YAxis tick={{ fontSize: 10 }} tickFormatter={(v) => `$${(v/1000).toFixed(0)}k`} />
                  <Tooltip formatter={(value) => [`$${value?.toLocaleString()}`, '']} />
                  <Line type="monotone" dataKey="value" name="Your Portfolio" stroke="#4f46e5" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="spy" name="SPY" stroke="#f59e0b" strokeWidth={1.5} strokeDasharray="5 5" dot={false} />
                </LineChart>
              </ResponsiveContainer>
            )}
            <p className="text-xs text-gray-400 mt-2 italic">
              "If you'd invested ${whatIfCapital.toLocaleString()} on {whatIfResult.start_date} and followed our signals, you'd have ${whatIfResult.current_value?.toLocaleString(undefined, {minimumFractionDigits: 2})} today."
            </p>
          </div>
        )}
        {whatIfResult?.error && (
          <p className="text-sm text-red-500">{whatIfResult.error}</p>
        )}
      </div>

      {/* Trade Journal */}
      {trades.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Trade Journal ({trades.length})</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-gray-400 border-b border-gray-100">
                  <th className="pb-2 pr-3">Symbol</th>
                  <th className="pb-2 pr-3">Type</th>
                  <th className="pb-2 pr-3">Entry</th>
                  <th className="pb-2 pr-3">Exit</th>
                  <th className="pb-2 pr-3">P&L</th>
                  <th className="pb-2 pr-3">Days</th>
                  <th className="pb-2">Reason</th>
                </tr>
              </thead>
              <tbody>
                {trades.map((t) => {
                  const pnlColor = (t.pnl_pct || 0) > 0 ? 'text-green-600' : (t.pnl_pct || 0) < 0 ? 'text-red-600' : 'text-gray-600';
                  const isOpen = t.status === 'open';
                  const isExpanded = expandedTrade === t.id;
                  return (
                    <React.Fragment key={t.id}>
                      <tr
                        className={`border-b border-gray-50 cursor-pointer hover:bg-gray-50 ${isExpanded ? 'bg-gray-50' : ''}`}
                        onClick={() => fetchTradeDetail(t.id)}
                      >
                        <td className="py-2 pr-3 font-medium text-gray-900">{t.symbol}</td>
                        <td className="py-2 pr-3">
                          <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${
                            t.portfolio_type === 'live' ? 'bg-green-50 text-green-600' : 'bg-blue-50 text-blue-600'
                          }`}>
                            {t.portfolio_type === 'live' ? 'L' : 'WF'}
                          </span>
                        </td>
                        <td className="py-2 pr-3 text-gray-600">${t.entry_price?.toFixed(2)}</td>
                        <td className="py-2 pr-3 text-gray-600">
                          {isOpen ? <span className="text-xs text-green-500 font-medium">OPEN</span> : `$${t.exit_price?.toFixed(2)}`}
                        </td>
                        <td className={`py-2 pr-3 font-medium ${pnlColor}`}>
                          {t.pnl_pct != null ? `${t.pnl_pct >= 0 ? '+' : ''}${t.pnl_pct?.toFixed(1)}%` : '-'}
                        </td>
                        <td className="py-2 pr-3 text-gray-500 text-xs">{t.days_held ?? '-'}d</td>
                        <td className="py-2">{t.exit_reason ? exitReasonBadge(t.exit_reason) : '-'}</td>
                      </tr>
                      {isExpanded && tradeDetail && (
                        <tr>
                          <td colSpan="7" className="p-0">
                            <TradeDetailCard detail={tradeDetail} onGenerateAutopsy={generateAutopsy} />
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Subscriber Preview Card */}
      {subscriberPreview && (
        <div className="bg-gradient-to-br from-slate-900 to-slate-800 rounded-xl shadow-lg p-6 text-white">
          <div className="flex items-center gap-2 mb-4">
            <span className="text-amber-400 text-xs font-semibold uppercase tracking-wider">Preview: Subscriber View</span>
          </div>

          {/* Performance banner */}
          <div className="grid grid-cols-3 gap-4 mb-5">
            <div className="text-center">
              <p className="text-xs text-slate-400">Portfolio Return</p>
              <p className={`text-2xl font-bold ${subscriberPreview.portfolio_return_pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {subscriberPreview.portfolio_return_pct >= 0 ? '+' : ''}{subscriberPreview.portfolio_return_pct}%
              </p>
            </div>
            <div className="text-center">
              <p className="text-xs text-slate-400">Win Rate</p>
              <p className="text-2xl font-bold text-amber-400">{subscriberPreview.win_rate}%</p>
            </div>
            <div className="text-center">
              <p className="text-xs text-slate-400">Active Since</p>
              <p className="text-2xl font-bold text-slate-200">{subscriberPreview.active_since_days}d</p>
            </div>
          </div>

          {/* Current positions */}
          {subscriberPreview.open_positions?.length > 0 && (
            <div className="mb-4">
              <h4 className="text-sm font-medium text-slate-300 mb-2">Current Positions</h4>
              <div className="flex flex-wrap gap-2">
                {mergeQuotes(subscriberPreview.open_positions).map((pos) => (
                  <div key={pos.symbol} className="flex items-center gap-2 bg-slate-700/50 rounded-lg px-3 py-1.5 cursor-pointer hover:bg-slate-600/50" onClick={() => openChart(pos.symbol)}>
                    <span className="font-semibold text-sm text-slate-100">{pos.symbol}</span>
                    <span className={`text-sm font-medium ${pos.pnl_pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {pos.pnl_pct >= 0 ? '+' : ''}{pos.pnl_pct?.toFixed(1)}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Recent winners */}
          {subscriberPreview.recent_winners?.length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-slate-300 mb-2">Recent Winners</h4>
              <div className="flex flex-wrap gap-2">
                {subscriberPreview.recent_winners.map((w, i) => (
                  <div key={i} className="flex items-center gap-2 bg-green-900/30 border border-green-800/30 rounded-lg px-3 py-1.5">
                    <span className="font-semibold text-sm text-slate-100">{w.symbol}</span>
                    <span className="text-sm font-medium text-green-400">+{w.pnl_pct?.toFixed(1)}%</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <p className="text-xs text-slate-500 mt-4">
            {subscriberPreview.total_trades} trades since {subscriberPreview.inception_date || 'launch'}
          </p>
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-3 flex-wrap">
        <button
          onClick={fetchPortfolio}
          className="flex items-center gap-2 px-4 py-2 text-sm text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50"
        >
          <RefreshCw size={14} />
          Refresh
        </button>
        <button
          onClick={() => runAction('backfill', { as_of_date: '2026-02-01', force: true })}
          disabled={processing}
          className="flex items-center gap-2 px-4 py-2 text-sm text-blue-600 border border-blue-300 rounded-lg hover:bg-blue-50 disabled:opacity-50"
        >
          {processing ? 'Running...' : 'Backfill WF from Feb 1'}
        </button>
      </div>

      {/* Chart Modal Overlay */}
      {chartSymbol && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={() => setChartSymbol(null)}>
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-3xl max-h-[80vh] overflow-auto" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between p-4 border-b">
              <h3 className="text-lg font-bold text-gray-900">{chartSymbol}</h3>
              <button onClick={() => setChartSymbol(null)} className="text-gray-400 hover:text-gray-600 text-xl">&times;</button>
            </div>
            <div className="p-4">
              {chartTrade && (
                <div className="flex gap-4 mb-3 text-sm">
                  {chartTrade.entry_date && (
                    <span className="flex items-center gap-1">
                      <span className="inline-block w-3 h-3 rounded-full bg-green-500" />
                      Buy {formatDate(chartTrade.entry_date)} @ ${chartTrade.entry_price?.toFixed(2)}
                    </span>
                  )}
                  {chartTrade.exit_date && (
                    <span className="flex items-center gap-1">
                      <span className="inline-block w-3 h-3 rounded-full bg-red-500" />
                      Sell {formatDate(chartTrade.exit_date)} @ ${chartTrade.exit_price?.toFixed(2)}
                    </span>
                  )}
                </div>
              )}
              {chartLoading ? (
                <div className="flex items-center justify-center h-64 text-gray-400">Loading chart...</div>
              ) : chartData.length > 0 ? (
                <ResponsiveContainer width="100%" height={350}>
                  <LineChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                    <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={d => d?.slice(5)} interval={Math.floor(chartData.length / 8)} />
                    <YAxis tick={{ fontSize: 11 }} domain={['auto', 'auto']} tickFormatter={v => `$${v?.toFixed(0)}`} />
                    <Tooltip formatter={(v, name) => {
                      if (name === 'buyMarker') return [`$${Number(v).toFixed(2)}`, 'BUY'];
                      if (name === 'sellMarker') return [`$${Number(v).toFixed(2)}`, 'SELL'];
                      return [`$${Number(v).toFixed(2)}`, name];
                    }} labelFormatter={d => d} />
                    <Line type="monotone" dataKey="close" stroke="#4f46e5" dot={false} strokeWidth={2} name="Close" />
                    {chartData[0]?.ma_50 && <Line type="monotone" dataKey="ma_50" stroke="#f59e0b" dot={false} strokeWidth={1} strokeDasharray="4 4" name="MA50" />}
                    {chartData[0]?.ma_200 && <Line type="monotone" dataKey="ma_200" stroke="#ef4444" dot={false} strokeWidth={1} strokeDasharray="4 4" name="MA200" />}
                    {chartTrade?.entry_date && (
                      <Line type="monotone" dataKey="buyMarker" stroke="none" dot={({ cx, cy, payload }) => payload.buyMarker ? (
                        <svg x={cx - 8} y={cy - 16} width={16} height={16}><polygon points="8,0 16,16 0,16" fill="#22c55e" /></svg>
                      ) : null} name="BUY" legendType="none" connectNulls={false} />
                    )}
                    {chartTrade?.exit_date && (
                      <Line type="monotone" dataKey="sellMarker" stroke="none" dot={({ cx, cy, payload }) => payload.sellMarker ? (
                        <svg x={cx - 8} y={cy} width={16} height={16}><polygon points="8,16 16,0 0,0" fill="#ef4444" /></svg>
                      ) : null} name="SELL" legendType="none" connectNulls={false} />
                    )}
                    <Legend />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex items-center justify-center h-64 text-gray-400">No chart data available</div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// Equity Curve Chart (Recharts)
function EquityCurveChart({ data }) {
  const formatDollar = (v) => `$${(v / 1000).toFixed(0)}k`;
  const formatDate = (d) => {
    if (!d) return '';
    const parts = d.split('-');
    return `${parts[1]}/${parts[2]}`;
  };

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={data} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis dataKey="date" tickFormatter={formatDate} tick={{ fontSize: 11 }} interval="preserveStartEnd" />
        <YAxis tickFormatter={formatDollar} tick={{ fontSize: 11 }} />
        <Tooltip
          formatter={(value, name) => [`$${value?.toLocaleString()}`, name]}
          labelFormatter={(label) => `Date: ${label}`}
        />
        <Legend />
        <Line type="monotone" dataKey="live_value" name="Live" stroke="#22c55e" strokeWidth={2} dot={false} />
        <Line type="monotone" dataKey="spy_value" name="SPY (benchmark)" stroke="#f59e0b" strokeWidth={1.5} strokeDasharray="5 5" dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}

// Trade Detail Expansion Card
function TradeDetailCard({ detail, onGenerateAutopsy }) {
  if (!detail) return null;

  const pnlColor = (detail.pnl_pct || 0) > 0 ? 'text-green-600' : (detail.pnl_pct || 0) < 0 ? 'text-red-600' : 'text-gray-600';

  const verdictColors = {
    good_entry: 'bg-green-100 text-green-700',
    bad_entry: 'bg-red-100 text-red-700',
    good_exit: 'bg-green-100 text-green-700',
    bad_exit: 'bg-red-100 text-red-700',
    unlucky: 'bg-amber-100 text-amber-700',
  };

  return (
    <div className="bg-gray-50 border-t border-gray-100 p-4 space-y-3">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {/* Signal Replay */}
        {detail.ensemble_score != null && (
          <div>
            <p className="text-xs text-gray-400">Signal Strength</p>
            <div className="flex items-center gap-2">
              <div className="flex-1 bg-gray-200 rounded-full h-2">
                <div
                  className={`rounded-full h-2 ${
                    detail.ensemble_score >= 88 ? 'bg-emerald-600' :
                    detail.ensemble_score >= 75 ? 'bg-emerald-400' :
                    detail.ensemble_score >= 61 ? 'bg-amber-400' : 'bg-gray-400'
                  }`}
                  style={{ width: `${Math.min(detail.ensemble_score, 100)}%` }}
                />
              </div>
              <span className="text-sm font-medium text-gray-700">
                {detail.signal_strength_label || detail.ensemble_score?.toFixed(0)}
              </span>
            </div>
          </div>
        )}
        {detail.momentum_rank != null && (
          <div>
            <p className="text-xs text-gray-400">Momentum Rank</p>
            <span className="inline-block bg-blue-100 text-blue-700 text-sm font-semibold px-2 py-0.5 rounded">
              #{detail.momentum_rank}
            </span>
          </div>
        )}
        {detail.pct_above_dwap != null && (
          <div>
            <p className="text-xs text-gray-400">Breakout %</p>
            <p className="text-sm font-medium text-gray-700">+{detail.pct_above_dwap?.toFixed(1)}%</p>
          </div>
        )}
        {detail.sector && (
          <div>
            <p className="text-xs text-gray-400">Sector</p>
            <span className="inline-block bg-gray-200 text-gray-700 text-xs font-medium px-2 py-0.5 rounded">
              {detail.sector}
            </span>
          </div>
        )}
      </div>

      {/* Timing + Performance */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 pt-2 border-t border-gray-200">
        <div>
          <p className="text-xs text-gray-400">Entry</p>
          <p className="text-sm text-gray-700">{formatDate(detail.entry_date)} @ ${detail.entry_price?.toFixed(2)}</p>
        </div>
        <div>
          <p className="text-xs text-gray-400">Exit</p>
          <p className="text-sm text-gray-700">
            {detail.exit_date ? `${formatDate(detail.exit_date)} @ $${detail.exit_price?.toFixed(2)}` : 'Open'}
          </p>
        </div>
        {detail.max_gain_pct != null && (
          <div>
            <p className="text-xs text-gray-400">Max Gain During Hold</p>
            <p className="text-sm font-medium text-green-600">+{detail.max_gain_pct}%</p>
          </div>
        )}
        <div>
          <p className="text-xs text-gray-400">Final P&L</p>
          <p className={`text-sm font-bold ${pnlColor}`}>
            {detail.pnl_pct != null ? `${detail.pnl_pct >= 0 ? '+' : ''}${detail.pnl_pct?.toFixed(1)}%` : '-'}
            {detail.pnl_dollars != null && (
              <span className="text-xs text-gray-400 ml-1">
                (${detail.pnl_dollars >= 0 ? '+' : ''}{detail.pnl_dollars?.toLocaleString(undefined, {minimumFractionDigits: 0, maximumFractionDigits: 0})})
              </span>
            )}
          </p>
        </div>
      </div>

      {/* AI Autopsy */}
      {detail.autopsy ? (
        <div className="pt-2 border-t border-gray-200">
          <div className="flex items-center gap-2 mb-2">
            <Sparkles size={14} className="text-purple-500" />
            <span className="text-xs font-semibold text-purple-700 uppercase tracking-wider">AI Autopsy</span>
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${verdictColors[detail.autopsy.verdict] || 'bg-gray-100 text-gray-600'}`}>
              {detail.autopsy.verdict?.replace('_', ' ')}
            </span>
            {detail.autopsy.score != null && (
              <span className="text-xs text-gray-400 ml-auto">Score: {detail.autopsy.score}/10</span>
            )}
          </div>
          <div className="space-y-1.5 text-sm text-gray-600">
            {detail.autopsy.entry_analysis && <p><strong className="text-gray-700">Entry:</strong> {detail.autopsy.entry_analysis}</p>}
            {detail.autopsy.exit_analysis && <p><strong className="text-gray-700">Exit:</strong> {detail.autopsy.exit_analysis}</p>}
            {detail.autopsy.regime_impact && <p><strong className="text-gray-700">Regime:</strong> {detail.autopsy.regime_impact}</p>}
            {detail.autopsy.lesson_learned && (
              <div className="bg-blue-50 border border-blue-100 rounded-lg px-3 py-2 mt-2">
                <p className="text-xs text-blue-700"><strong>Lesson:</strong> {detail.autopsy.lesson_learned}</p>
              </div>
            )}
          </div>
        </div>
      ) : detail.status === 'closed' && onGenerateAutopsy ? (
        <div className="pt-2 border-t border-gray-200">
          <button
            onClick={() => onGenerateAutopsy(detail.id)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-purple-600 border border-purple-300 rounded-lg hover:bg-purple-50"
          >
            <Sparkles size={12} />
            Generate AI Autopsy
          </button>
        </div>
      ) : null}
    </div>
  );
}

function StatCard({ icon, label, value, subtext, valueColor = 'text-gray-900' }) {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
      <div className="flex items-center gap-3 mb-2">
        {icon}
        <span className="text-sm font-medium text-gray-500">{label}</span>
      </div>
      <div className={`text-2xl font-bold ${valueColor}`}>{value}</div>
      {subtext && <p className="text-sm text-gray-500 mt-1">{subtext}</p>}
    </div>
  );
}


function NewsletterTab({ fetchWithAuth }) {
  const [draft, setDraft] = useState(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [locking, setLocking] = useState(false);
  const [sending, setSending] = useState(false);
  const [sendResult, setSendResult] = useState(null);
  const [editedSections, setEditedSections] = useState(null);
  const [previewMode, setPreviewMode] = useState(false);

  const loadDraft = async () => {
    setLoading(true);
    try {
      const res = await fetchWithAuth(`${API_URL}/api/admin/newsletter/draft`);
      if (res.ok) {
        const data = await res.json();
        setDraft(data);
        setEditedSections(JSON.parse(JSON.stringify(data.sections)));
      } else {
        setDraft(null);
        setEditedSections(null);
      }
    } catch { setDraft(null); }
    setLoading(false);
  };

  useEffect(() => { loadDraft(); }, []);

  const handleGenerate = async () => {
    setGenerating(true);
    const prevGeneratedAt = draft?.generated_at || '';
    try {
      await fetchWithAuth(`${API_URL}/api/admin/newsletter/generate`, { method: 'POST' });
      let attempts = 0;
      const poll = setInterval(async () => {
        attempts++;
        try {
          const res = await fetchWithAuth(`${API_URL}/api/admin/newsletter/draft`);
          if (res.ok) {
            const data = await res.json();
            if (data.generated_at && data.generated_at !== prevGeneratedAt) {
              setDraft(data);
              setEditedSections(JSON.parse(JSON.stringify(data.sections)));
              setGenerating(false);
              clearInterval(poll);
            }
          }
        } catch {}
        if (attempts >= 20) {
          setGenerating(false);
          clearInterval(poll);
          loadDraft();
        }
      }, 3000);
    } catch (e) { console.error(e); setGenerating(false); }
  };

  const handleSave = async () => {
    if (!draft || !editedSections) return;
    setSaving(true);
    try {
      const res = await fetchWithAuth(`${API_URL}/api/admin/newsletter/draft/${draft.date}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sections: editedSections }),
      });
      if (res.ok) {
        const data = await res.json();
        setDraft(data);
      }
    } catch (e) { console.error(e); }
    setSaving(false);
  };

  const handleLock = async () => {
    if (!draft) return;
    if (!confirm('Lock this draft? No more edits will be possible.')) return;
    setLocking(true);
    try {
      // Auto-save edits before locking
      if (editedSections) {
        await fetchWithAuth(`${API_URL}/api/admin/newsletter/draft/${draft.date}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ sections: editedSections }),
        });
      }
      const res = await fetchWithAuth(`${API_URL}/api/admin/newsletter/lock/${draft.date}`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setDraft(data);
      }
    } catch (e) { console.error(e); }
    setLocking(false);
  };

  const handleSend = async () => {
    if (!draft) return;
    if (!confirm('Send this newsletter to ALL free-list subscribers now?')) return;
    setSending(true);
    try {
      const res = await fetchWithAuth(`${API_URL}/api/admin/newsletter/send/${draft.date}`, { method: 'POST' });
      if (res.ok) {
        const result = await res.json();
        setSendResult(result);
      }
    } catch (e) { console.error(e); }
    setSending(false);
  };

  const [testSending, setTestSending] = useState(false);
  const [testResult, setTestResult] = useState(null);

  const handleTestSend = async () => {
    if (!draft) return;
    setTestSending(true);
    try {
      const res = await fetchWithAuth(`${API_URL}/api/admin/newsletter/test/${draft.date}`, { method: 'POST' });
      if (res.ok) {
        const result = await res.json();
        setTestResult(result);
      }
    } catch (e) { console.error(e); }
    setTestSending(false);
  };

  const updateSection = (idx, field, value) => {
    const updated = [...editedSections];
    if (field === 'items') {
      updated[idx] = { ...updated[idx], items: value };
    } else {
      updated[idx] = { ...updated[idx], [field]: value };
    }
    setEditedSections(updated);
  };

  const isLocked = draft?.status === 'locked';
  const isDirty = draft && editedSections && JSON.stringify(draft.sections) !== JSON.stringify(editedSections);

  if (loading) return (
    <div className="flex items-center justify-center py-20">
      <Loader2 className="w-6 h-6 animate-spin text-ink-mute" />
    </div>
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-ink">Market, Measured.</h2>
          <p className="text-sm text-ink-mute mt-1">Weekly newsletter editor</p>
        </div>
        <div className="flex items-center gap-3">
          {!draft && (
            <button
              onClick={handleGenerate}
              disabled={generating}
              className="flex items-center gap-2 px-4 py-2 bg-claret text-paper rounded hover:bg-ink transition-colors disabled:opacity-50"
            >
              {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
              {generating ? 'Generating...' : 'Generate Draft'}
            </button>
          )}
          {draft && !isLocked && (
            <>
              <button
                onClick={handleGenerate}
                disabled={generating}
                className="flex items-center gap-2 px-3 py-2 border border-rule text-ink-mute rounded hover:bg-paper-deep transition-colors disabled:opacity-50 text-sm"
              >
                {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                Regenerate
              </button>
              <button
                onClick={handleSave}
                disabled={saving || !isDirty}
                className="flex items-center gap-2 px-3 py-2 border border-rule text-ink-mute rounded hover:bg-paper-deep transition-colors disabled:opacity-50 text-sm"
              >
                {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Edit3 className="w-4 h-4" />}
                Save Edits
              </button>
              <button
                onClick={handleLock}
                disabled={locking}
                className="flex items-center gap-2 px-4 py-2 bg-claret text-paper rounded hover:bg-ink transition-colors disabled:opacity-50"
              >
                {locking ? <Loader2 className="w-4 h-4 animate-spin" /> : <Lock className="w-4 h-4" />}
                Lock & Approve
              </button>
            </>
          )}
          {draft && (
            <button
              onClick={handleTestSend}
              disabled={testSending}
              className="flex items-center gap-2 px-3 py-2 border border-rule text-ink-mute rounded hover:bg-paper-deep transition-colors disabled:opacity-50 text-sm"
            >
              {testSending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Mail className="w-4 h-4" />}
              {testSending ? 'Sending...' : 'Send Test to Me'}
            </button>
          )}
          {isLocked && (
            <button
              onClick={async () => {
                if (!confirm('Unlock this draft for further editing?')) return;
                try {
                  const res = await fetchWithAuth(`${API_URL}/api/admin/newsletter/unlock/${draft.date}`, { method: 'POST' });
                  if (res.ok) { const data = await res.json(); setDraft(data); }
                } catch (e) { console.error(e); }
              }}
              className="flex items-center gap-2 px-3 py-2 border border-rule text-ink-mute rounded hover:bg-paper-deep transition-colors text-sm"
            >
              <Lock className="w-4 h-4" /> Unlock
            </button>
          )}
          {isLocked && !sendResult && (
            <button
              onClick={handleSend}
              disabled={sending}
              className="flex items-center gap-2 px-4 py-2 bg-positive text-paper rounded hover:bg-positive/80 transition-colors disabled:opacity-50"
            >
              {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Mail className="w-4 h-4" />}
              {sending ? 'Sending...' : 'Send to All'}
            </button>
          )}
        </div>
      </div>

      {/* Status bar */}
      {draft && (
        <div className="flex items-center gap-4 text-sm border border-rule rounded p-3 bg-paper-card">
          <span className="font-mono text-ink-light">{draft.date}</span>
          <span className={`px-2 py-0.5 rounded text-xs font-medium ${
            isLocked ? 'bg-positive/10 text-positive' : 'bg-claret/10 text-claret'
          }`}>
            {isLocked ? 'LOCKED' : 'DRAFT'}
          </span>
          <span className="text-ink-mute">{draft.word_count} words</span>
          <span className="text-ink-light">{draft.regime}</span>
          {draft.fresh_count > 0 && <span className="text-positive">{draft.fresh_count} signals</span>}
          {isDirty && <span className="text-claret font-medium">Unsaved changes</span>}
        </div>
      )}

      {testResult && (
        <div className="p-3 bg-claret/10 border border-claret/30 rounded text-claret text-sm">
          Test email sent to {testResult.to}
        </div>
      )}

      {sendResult && (
        <div className="p-4 bg-positive/10 border border-positive/30 rounded text-positive">
          Newsletter sent: {sendResult.sent} delivered, {sendResult.failed} failed, {sendResult.total} total subscribers
        </div>
      )}

      {/* No draft state */}
      {!draft && !generating && (
        <div className="text-center py-16 border border-rule rounded bg-paper-card">
          <Mail className="w-10 h-10 text-ink-light mx-auto mb-3" />
          <p className="text-ink-mute">No newsletter draft yet.</p>
          <p className="text-sm text-ink-light mt-1">Generate one from this week's market data.</p>
        </div>
      )}

      {/* Editor / Preview toggle */}
      {draft && editedSections && (
        <>
          <div className="flex gap-2">
            <button
              onClick={() => setPreviewMode(false)}
              className={`px-3 py-1.5 text-sm rounded transition-colors ${!previewMode ? 'bg-ink text-paper' : 'bg-paper-deep text-ink-mute hover:text-ink'}`}
            >
              Edit
            </button>
            <button
              onClick={() => setPreviewMode(true)}
              className={`px-3 py-1.5 text-sm rounded transition-colors ${previewMode ? 'bg-ink text-paper' : 'bg-paper-deep text-ink-mute hover:text-ink'}`}
            >
              Preview
            </button>
          </div>

          {previewMode ? (
            /* Preview mode — renders like the newsletter web page */
            <div className="border border-rule rounded bg-paper-card p-8 max-w-[720px]">
              {editedSections.map((sec, i) => (
                <div key={i} className="mb-8 last:mb-0">
                  <p className="font-mono text-xs font-medium tracking-widest text-claret uppercase mb-2">
                    &sect; {sec.num} &middot; {sec.label}
                  </p>
                  {sec.title && (
                    <h3 className="text-lg font-semibold text-ink mb-3" dangerouslySetInnerHTML={{ __html: sec.title }} />
                  )}
                  {sec.body && (
                    <div className="text-sm text-ink-mute leading-relaxed whitespace-pre-wrap">{sec.body}</div>
                  )}
                  {sec.items && (
                    <ul className="list-none p-0 space-y-2 mt-2">
                      {sec.items.map((item, j) => (
                        <li key={j} className="pl-4 border-l-2 border-claret text-sm text-ink-mute leading-relaxed" dangerouslySetInnerHTML={{ __html: item }} />
                      ))}
                    </ul>
                  )}
                  {i < editedSections.length - 1 && (
                    <div className="flex items-center gap-2 my-6 text-rule-dark">
                      <span className="flex-1 h-px bg-rule" />
                      <span className="text-xs tracking-widest">···</span>
                      <span className="flex-1 h-px bg-rule" />
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            /* Edit mode — per-section textareas */
            <div className="space-y-6">
              {editedSections.map((sec, i) => (
                <div key={i} className="border border-rule rounded bg-paper-card overflow-hidden">
                  <div className="px-4 py-3 bg-paper-deep border-b border-rule flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-medium text-claret">&sect;{sec.num}</span>
                      <span className="text-sm font-medium text-ink">{sec.label}</span>
                    </div>
                    {isLocked && <Lock className="w-3.5 h-3.5 text-ink-light" />}
                  </div>
                  <div className="p-4 space-y-3">
                    {sec.title && (
                      <input
                        type="text"
                        value={sec.title}
                        onChange={(e) => updateSection(i, 'title', e.target.value)}
                        disabled={isLocked}
                        className="w-full px-3 py-2 border border-rule bg-paper text-ink font-medium disabled:opacity-60 disabled:bg-paper-deep"
                        placeholder="Section title"
                      />
                    )}
                    {sec.body !== undefined && !sec.items && (
                      <textarea
                        value={sec.body}
                        onChange={(e) => updateSection(i, 'body', e.target.value)}
                        disabled={isLocked}
                        rows={sec.num === '04' ? 4 : 8}
                        className="w-full px-3 py-2 border border-rule bg-paper text-ink-mute text-sm leading-relaxed resize-y disabled:opacity-60 disabled:bg-paper-deep font-mono"
                        placeholder="Section body"
                      />
                    )}
                    {sec.items && (
                      <div className="space-y-2">
                        {sec.items.map((item, j) => (
                          <textarea
                            key={j}
                            value={item}
                            onChange={(e) => {
                              const newItems = [...sec.items];
                              newItems[j] = e.target.value;
                              updateSection(i, 'items', newItems);
                            }}
                            disabled={isLocked}
                            rows={3}
                            className="w-full px-3 py-2 border border-rule bg-paper text-ink-mute text-sm leading-relaxed resize-y disabled:opacity-60 disabled:bg-paper-deep font-mono"
                            placeholder={`Anti-pitch item ${j + 1}`}
                          />
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
