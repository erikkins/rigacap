/**
 * Dashboard — main screen showing market regime, signal summary, and model portfolio.
 * Tabbed layout: Signals | Positions | History | Missed
 */

import React, { useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import * as SecureStore from 'expo-secure-store';
import { useRouter } from 'expo-router';
import {
  useDashboard,
  useTradeHistory,
  Position,
  MissedOpportunity,
  Signal,
  Trade,
  trackSignal,
  sellPosition,
} from '@/hooks/useSignals';
import { useLiveQuotes } from '@/hooks/useLiveQuotes';
import SignalCard from '@/components/SignalCard';
import RegimeBadge from '@/components/RegimeBadge';
import ConfirmModal from '@/components/ConfirmModal';
import { Colors, Fonts, FontSize, Palette, Radii, Spacing } from '@/constants/theme';

type Tab = 'signals' | 'positions' | 'history' | 'missed';

export default function DashboardScreen() {
  const { data, isLoading, error, refresh } = useDashboard();
  const { trades, isLoading: tradesLoading, refresh: refreshTrades } = useTradeHistory();
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<Tab>('signals');

  // Sector filter state
  const [excludedSectors, setExcludedSectors] = useState<string[]>([]);
  const [sectorFilterOpen, setSectorFilterOpen] = useState(false);

  // Load sector filter from storage on mount
  useEffect(() => {
    SecureStore.getItemAsync('rigacap_sector_filters').then(v => {
      if (v) try { setExcludedSectors(JSON.parse(v)); } catch {}
    });
    SecureStore.getItemAsync('rigacap_sector_filter_open').then(v => {
      if (v === 'true') setSectorFilterOpen(true);
    });
  }, []);

  // Persist sector filter changes
  useEffect(() => {
    SecureStore.setItemAsync('rigacap_sector_filters', JSON.stringify(excludedSectors));
  }, [excludedSectors]);
  useEffect(() => {
    SecureStore.setItemAsync('rigacap_sector_filter_open', String(sectorFilterOpen));
  }, [sectorFilterOpen]);

  // Track modal state
  const [trackModal, setTrackModal] = useState<{ signal: Signal } | null>(null);
  const [trackLoading, setTrackLoading] = useState(false);

  // Sell modal state
  const [sellModal, setSellModal] = useState<{ position: Position } | null>(null);
  const [sellLoading, setSellLoading] = useState(false);

  const handleTrack = async () => {
    if (!trackModal) return;
    setTrackLoading(true);
    try {
      await trackSignal(trackModal.signal.symbol, trackModal.signal.price);
      await refresh();
      setTrackModal(null);
      setActiveTab('positions');
    } catch (err: any) {
      Alert.alert('Error', err.response?.data?.detail || 'Failed to track signal');
    } finally {
      setTrackLoading(false);
    }
  };

  const handleSell = async () => {
    if (!sellModal) return;
    setSellLoading(true);
    try {
      await sellPosition(sellModal.position.id, sellModal.position.current_price);
      await Promise.all([refresh(), refreshTrades()]);
      setSellModal(null);
      setActiveTab('history');
    } catch (err: any) {
      Alert.alert('Error', err.response?.data?.detail || 'Failed to sell position');
    } finally {
      setSellLoading(false);
    }
  };

  // Live quotes — must be above early returns to preserve hook ordering
  const positions = data?.positions_with_guidance || [];
  const positionSymbols = useMemo(() => positions.map(p => p.symbol), [positions]);
  const portfolio = data?.model_portfolio;
  const portfolioSymbols = useMemo(
    () => (portfolio?.positions || []).map((p: any) => p.symbol),
    [portfolio],
  );
  const allSymbols = useMemo(
    () => [...new Set([...positionSymbols, ...portfolioSymbols])],
    [positionSymbols, portfolioSymbols],
  );
  const { quotes: liveQuotes, lastUpdate, refetch } = useLiveQuotes(allSymbols);

  const allSignals = data?.buy_signals || [];

  const livePositions = useMemo(() => {
    if (!Object.keys(liveQuotes).length) return positions;
    return positions.map(pos => {
      const quote = liveQuotes[pos.symbol];
      if (!quote) return pos;
      const livePrice = quote.price;
      const pnlPct = pos.entry_price > 0
        ? ((livePrice - pos.entry_price) / pos.entry_price) * 100
        : 0;
      const hwm = Math.max(pos.highest_price || pos.entry_price, livePrice);
      const stopPrice = hwm * 0.88; // 12% trailing stop
      const distToStop = stopPrice > 0 ? ((livePrice - stopPrice) / stopPrice) * 100 : 100;
      return {
        ...pos,
        current_price: livePrice,
        pnl_pct: pnlPct,
        highest_price: hwm,
        trailing_stop_level: stopPrice,
        distance_to_stop_pct: distToStop,
      };
    });
  }, [positions, liveQuotes]);

  // Sector filter — hooks must be above early returns
  const sectorCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    allSignals.forEach(s => { const sec = s.sector || 'Other'; counts[sec] = (counts[sec] || 0) + 1; });
    positions.forEach(p => { const sec = p.sector || 'Other'; counts[sec] = (counts[sec] || 0) + 1; });
    return counts;
  }, [allSignals, positions]);
  const activeSectors = useMemo(() => Object.keys(sectorCounts).sort(), [sectorCounts]);
  const filteredPositions = useMemo(() =>
    livePositions.filter(p => !excludedSectors.includes(p.sector || 'Other')),
    [livePositions, excludedSectors]
  );

  if (isLoading && !data) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color={Palette.claret} />
      </View>
    );
  }

  if (error && !data) {
    return (
      <View style={styles.center}>
        <Text style={styles.errorText}>{error}</Text>
      </View>
    );
  }

  const sectorFilter = (item: { sector?: string }) => !excludedSectors.includes(item.sector || 'Other');
  const signals = allSignals.filter(sectorFilter);
  const freshSignals = signals.filter((s) => s.is_fresh);
  const monitoringSignals = signals.filter((s) => !s.is_fresh);
  const freshCount = allSignals.filter(s => s.is_fresh).length; // unfiltered for badge
  const regime = data?.regime_forecast;
  const stats = data?.market_stats;
  const missed = data?.missed_opportunities || [];

  return (
    <>
      <ScrollView
        style={styles.container}
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl
            refreshing={isLoading}
            onRefresh={() => { refresh(); refetch(); if (activeTab === 'history') refreshTrades(); }}
            tintColor={Palette.claret}
          />
        }
      >
        {/* Market Regime */}
        {regime && (
          <RegimeBadge forecast={regime} marketStats={stats} />
        )}

        {/* Key Stats */}
        <View style={styles.statsRow}>
          <StatBox
            label="Portfolio"
            value={portfolio ? `$${portfolio.total_value?.toLocaleString(undefined, { maximumFractionDigits: 0 })}` : '—'}
          />
          <StatBox
            label="P&L"
            value={
              portfolio
                ? `${(portfolio.total_return_pct ?? 0) >= 0 ? '+' : ''}${portfolio.total_return_pct?.toFixed(1) ?? '0'}%`
                : '—'
            }
            change={portfolio?.total_return_pct}
          />
          <StatBox
            label="Signals"
            value={`${signals.length}`}
            sub={freshCount > 0 ? `${freshCount} fresh` : undefined}
          />
        </View>

        {/* Model Portfolio Summary */}
        {portfolio && (
          <View style={styles.portfolioCard}>
            <Text style={styles.sectionTitle}>Model Portfolio</Text>
            <View style={styles.portfolioStats}>
              <View>
                <Text style={styles.portfolioValue}>
                  ${portfolio.total_value?.toLocaleString(undefined, { maximumFractionDigits: 0 }) ?? '—'}
                </Text>
                <Text style={styles.portfolioLabel}>Total Value</Text>
              </View>
              <View>
                <Text
                  style={[
                    styles.portfolioReturn,
                    {
                      color:
                        (portfolio.total_return_pct ?? 0) >= 0
                          ? Colors.green
                          : Colors.red,
                    },
                  ]}
                >
                  {(portfolio.total_return_pct ?? 0) >= 0 ? '+' : ''}
                  {portfolio.total_return_pct?.toFixed(1) ?? '0'}%
                </Text>
                <Text style={styles.portfolioLabel}>Total Return</Text>
              </View>
            </View>
          </View>
        )}

        {/* Segmented Tab Bar */}
        <View style={styles.tabBar}>
          <TabPill label="Signals" tab="signals" active={activeTab} onPress={setActiveTab} />
          <TabPill label="Positions" tab="positions" active={activeTab} onPress={setActiveTab} />
          <TabPill label="History" tab="history" active={activeTab} onPress={setActiveTab} />
          <TabPill label="Missed" tab="missed" active={activeTab} onPress={setActiveTab} />
        </View>

        {/* Sector Filter */}
        {(activeTab === 'signals' || activeTab === 'positions') && activeSectors.length > 1 && (
          <View>
            <Pressable
              style={styles.filterToggle}
              onPress={() => setSectorFilterOpen(prev => !prev)}
            >
              <Text style={styles.filterToggleText}>Filter by Sector</Text>
              {excludedSectors.length > 0 && (
                <View style={styles.filterDot} />
              )}
              <Text style={styles.filterChevron}>{sectorFilterOpen ? '▲' : '▼'}</Text>
            </Pressable>
            {sectorFilterOpen && (
              <View style={styles.sectorPillRow}>
                {activeSectors.map(sector => {
                  const isExcluded = excludedSectors.includes(sector);
                  const count = sectorCounts[sector] || 0;
                  return (
                    <Pressable
                      key={sector}
                      style={[styles.sectorPill, isExcluded && styles.sectorPillExcluded]}
                      onPress={() => setExcludedSectors(prev =>
                        isExcluded ? prev.filter(s => s !== sector) : [...prev, sector]
                      )}
                    >
                      <Text style={[styles.sectorPillText, isExcluded && styles.sectorPillTextExcluded]}>
                        {sector}{isExcluded ? ` (${count})` : ''}
                      </Text>
                    </Pressable>
                  );
                })}
                {excludedSectors.length > 0 && (
                  <Pressable onPress={() => setExcludedSectors([])}>
                    <Text style={styles.sectorReset}>Reset</Text>
                  </Pressable>
                )}
              </View>
            )}
            {sectorFilterOpen && (
              <Text style={styles.filterDisclaimer}>
                Display filter only — the system scans the full universe regardless.
              </Text>
            )}
          </View>
        )}

        {/* Tab Content */}
        {activeTab === 'signals' && (
          <SignalsTab
            freshSignals={freshSignals}
            monitoringSignals={monitoringSignals}
            heldFreshCount={(data?.total_fresh_count || 0) - freshSignals.length}
            onSignalPress={(symbol) => router.push(`/signal/${symbol}`)}
            onTrack={(signal) => setTrackModal({ signal })}
          />
        )}
        {activeTab === 'positions' && (
          <>
            <PositionsTab
              positions={filteredPositions}
              onPositionPress={(symbol) => router.push(`/signal/${symbol}`)}
              onSell={(position) => setSellModal({ position })}
            />
            {livePositions.length > 0 && (
              <Text style={styles.lastUpdated}>
                {lastUpdate
                  ? `Updated ${lastUpdate.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}`
                  : 'Updating...'}
              </Text>
            )}
          </>
        )}
        {activeTab === 'history' && (
          <HistoryTab trades={trades} isLoading={tradesLoading} onTradePress={(symbol) => router.push(`/signal/${symbol}`)} />
        )}
        {activeTab === 'missed' && (
          <MissedTab
            missed={missed}
            onMissedPress={(symbol) => router.push(`/signal/${symbol}`)}
          />
        )}
      </ScrollView>

      {/* Track Confirmation Modal */}
      {trackModal && (
        <ConfirmModal
          visible
          title={`Track ${trackModal.signal.symbol}`}
          confirmLabel="Track"
          confirmColor={Colors.gold}
          onConfirm={handleTrack}
          onCancel={() => setTrackModal(null)}
          loading={trackLoading}
        >
          <View style={styles.modalRow}>
            <Text style={styles.modalLabel}>Price</Text>
            <Text style={styles.modalValue}>${(trackModal.signal.price ?? 0).toFixed(2)}</Text>
          </View>
          <View style={styles.modalRow}>
            <Text style={styles.modalLabel}>~Shares ($10k)</Text>
            <Text style={styles.modalValue}>
              {trackModal.signal.price ? Math.floor(10000 / trackModal.signal.price) : '—'}
            </Text>
          </View>
          <View style={styles.modalRow}>
            <Text style={styles.modalLabel}>Strength</Text>
            <Text style={styles.modalValue}>{trackModal.signal.signal_strength_label || 'Moderate'}</Text>
          </View>
        </ConfirmModal>
      )}

      {/* Sell Confirmation Modal */}
      {sellModal && (
        <ConfirmModal
          visible
          title={`Sell ${sellModal.position.symbol}`}
          confirmLabel="Sell"
          confirmColor={Colors.red}
          onConfirm={handleSell}
          onCancel={() => setSellModal(null)}
          loading={sellLoading}
        >
          <View style={styles.modalRow}>
            <Text style={styles.modalLabel}>Entry Price</Text>
            <Text style={styles.modalValue}>${(sellModal.position.entry_price ?? 0).toFixed(2)}</Text>
          </View>
          <View style={styles.modalRow}>
            <Text style={styles.modalLabel}>Current Price</Text>
            <Text style={styles.modalValue}>${(sellModal.position.current_price ?? 0).toFixed(2)}</Text>
          </View>
          <View style={styles.modalRow}>
            <Text style={styles.modalLabel}>P&L</Text>
            <Text
              style={[
                styles.modalValue,
                { color: (sellModal.position.pnl_pct ?? 0) >= 0 ? Colors.green : Colors.red },
              ]}
            >
              {(sellModal.position.pnl_pct ?? 0) >= 0 ? '+' : ''}{(sellModal.position.pnl_pct ?? 0).toFixed(1)}%
            </Text>
          </View>
          <View style={styles.modalRow}>
            <Text style={styles.modalLabel}>Shares</Text>
            <Text style={styles.modalValue}>{sellModal.position.shares}</Text>
          </View>
        </ConfirmModal>
      )}
    </>
  );
}

/* ── Tab Pill ─────────────────────────────────────────── */

function TabPill({
  label,
  tab,
  active,
  onPress,
}: {
  label: string;
  tab: Tab;
  active: Tab;
  onPress: (t: Tab) => void;
}) {
  const isActive = tab === active;
  return (
    <Pressable
      style={[styles.tabPill, isActive && styles.tabPillActive]}
      onPress={() => onPress(tab)}
    >
      <Text style={[styles.tabPillText, isActive && styles.tabPillTextActive]}>
        {label}
      </Text>
    </Pressable>
  );
}

/* ── Signals Tab ──────────────────────────────────────── */

function SignalsTab({
  freshSignals,
  monitoringSignals,
  heldFreshCount,
  onSignalPress,
  onTrack,
}: {
  freshSignals: Signal[];
  monitoringSignals: Signal[];
  heldFreshCount: number;
  onSignalPress: (symbol: string) => void;
  onTrack: (signal: Signal) => void;
}) {
  const hasAny = freshSignals.length > 0 || monitoringSignals.length > 0;

  if (!hasAny) {
    return (
      <View style={styles.emptyCard}>
        <Text style={styles.emptyText}>No active signals.</Text>
        <Text style={styles.emptySubtext}>Check back after the 4 PM ET scan.</Text>
      </View>
    );
  }

  return (
    <>
      {/* Fresh Signals */}
      <View style={styles.sectionHeader}>
        <View style={styles.sectionDot} />
        <Text style={[styles.sectionTitle, { color: Colors.green }]}>
          Buy Signals ({freshSignals.length})
        </Text>
      </View>
      {freshSignals.length > 0 ? (
        freshSignals.map((signal) => (
          <View key={signal.symbol}>
            <SignalCard
              signal={signal}
              onPress={() => onSignalPress(signal.symbol)}
            />
            <Pressable
              style={styles.trackButton}
              onPress={() => onTrack(signal)}
            >
              <Text style={styles.trackButtonText}>Track</Text>
            </Pressable>
          </View>
        ))
      ) : (
        <View style={styles.emptyCard}>
          <Text style={styles.emptyText}>
            {heldFreshCount > 0
              ? `Today's ${heldFreshCount} fresh signal${heldFreshCount > 1 ? 's are' : ' is'} already in your positions`
              : 'No fresh signals today'}
          </Text>
          {heldFreshCount === 0 && (
            <Text style={styles.emptySubtext}>
              Monitoring {monitoringSignals.length} strong momentum stock{monitoringSignals.length !== 1 ? 's' : ''} for entry
            </Text>
          )}
        </View>
      )}

      {/* Monitoring Signals */}
      {monitoringSignals.length > 0 && (
        <>
          <View style={styles.sectionHeader}>
            <View style={[styles.sectionDot, { backgroundColor: Colors.textMuted }]} />
            <View>
              <Text style={[styles.sectionTitle, { color: Colors.textMuted }]}>
                Monitoring ({monitoringSignals.length})
              </Text>
              <Text style={styles.sectionSubtitle}>
                Strong momentum — watching for fresh entry
              </Text>
            </View>
          </View>
          {monitoringSignals.map((signal) => (
            <SignalCard
              key={signal.symbol}
              signal={signal}
              onPress={() => onSignalPress(signal.symbol)}
            />
          ))}
        </>
      )}
    </>
  );
}

/* ── Positions Tab ────────────────────────────────────── */

function PositionsTab({
  positions,
  onPositionPress,
  onSell,
}: {
  positions: Position[];
  onPositionPress: (symbol: string) => void;
  onSell: (position: Position) => void;
}) {
  if (positions.length === 0) {
    return (
      <View style={styles.emptyCard}>
        <Text style={styles.emptyText}>No open positions</Text>
      </View>
    );
  }

  return (
    <>
      {positions.map((pos) => (
        <Pressable
          key={pos.symbol}
          style={({ pressed }) => [styles.positionCard, pressed && styles.pressed]}
          onPress={() => onPositionPress(pos.symbol)}
        >
          <View style={styles.positionHeader}>
            <Text style={styles.positionSymbol}>{pos.symbol}</Text>
            <Text
              style={[
                styles.positionPnl,
                { color: (pos.pnl_pct ?? 0) >= 0 ? Colors.green : Colors.red },
              ]}
            >
              {(pos.pnl_pct ?? 0) >= 0 ? '+' : ''}{(pos.pnl_pct ?? 0).toFixed(1)}%
            </Text>
          </View>
          <View style={styles.positionDetails}>
            <View style={styles.positionDetail}>
              <Text style={styles.positionDetailLabel}>Entry</Text>
              <Text style={styles.positionDetailValue}>${(pos.entry_price ?? 0).toFixed(2)}</Text>
            </View>
            <View style={styles.positionDetail}>
              <Text style={styles.positionDetailLabel}>Current</Text>
              <Text style={styles.positionDetailValue}>${(pos.current_price ?? 0).toFixed(2)}</Text>
            </View>
            <View style={styles.positionDetail}>
              <Text style={styles.positionDetailLabel}>High</Text>
              <Text style={styles.positionDetailValue}>${(pos.highest_price ?? 0).toFixed(2)}</Text>
            </View>
            <View style={styles.positionDetail}>
              <Text style={styles.positionDetailLabel}>Stop</Text>
              <Text style={styles.positionDetailValue}>
                {pos.trailing_stop_level ? `$${pos.trailing_stop_level.toFixed(2)}` : `$${((pos.highest_price ?? 0) * 0.88).toFixed(2)}`}
              </Text>
            </View>
          </View>
          {pos.sell_guidance && (
            <View style={styles.guidanceRow}>
              <Text style={styles.guidanceText}>{pos.sell_guidance}</Text>
            </View>
          )}
          <Pressable
            style={styles.sellButton}
            onPress={() => onSell(pos)}
          >
            <Text style={styles.sellButtonText}>Sell</Text>
          </Pressable>
        </Pressable>
      ))}
    </>
  );
}

/* ── History Tab ──────────────────────────────────────── */

function HistoryTab({
  trades,
  isLoading,
  onTradePress,
}: {
  trades: Trade[];
  isLoading: boolean;
  onTradePress: (symbol: string) => void;
}) {
  if (isLoading && trades.length === 0) {
    return (
      <View style={styles.emptyCard}>
        <ActivityIndicator color={Colors.gold} />
      </View>
    );
  }

  if (trades.length === 0) {
    return (
      <View style={styles.emptyCard}>
        <Text style={styles.emptyText}>No completed trades yet</Text>
      </View>
    );
  }

  const wins = trades.filter((t) => t.pnl_pct > 0).length;
  const winRate = ((wins / trades.length) * 100).toFixed(0);
  const avgReturn = (trades.reduce((sum, t) => sum + t.pnl_pct, 0) / trades.length).toFixed(1);

  return (
    <>
      {/* Summary Stats */}
      <View style={styles.historyStatsRow}>
        <View style={styles.historyStat}>
          <Text style={styles.historyStatValue}>{trades.length}</Text>
          <Text style={styles.historyStatLabel}>Trades</Text>
        </View>
        <View style={styles.historyStat}>
          <Text style={[styles.historyStatValue, { color: Colors.green }]}>{winRate}%</Text>
          <Text style={styles.historyStatLabel}>Win Rate</Text>
        </View>
        <View style={styles.historyStat}>
          <Text
            style={[
              styles.historyStatValue,
              { color: Number(avgReturn) >= 0 ? Colors.green : Colors.red },
            ]}
          >
            {Number(avgReturn) >= 0 ? '+' : ''}{avgReturn}%
          </Text>
          <Text style={styles.historyStatLabel}>Avg Return</Text>
        </View>
      </View>

      {/* Trade Cards */}
      {trades.map((trade) => (
        <Pressable key={trade.id} onPress={() => onTradePress(trade.symbol)} style={styles.tradeCard}>
          <View style={styles.tradeHeader}>
            <Text style={styles.tradeSymbol}>{trade.symbol}</Text>
            <Text
              style={[
                styles.tradePnl,
                { color: trade.pnl_pct >= 0 ? Colors.green : Colors.red },
              ]}
            >
              {trade.pnl_pct >= 0 ? '+' : ''}{trade.pnl_pct.toFixed(1)}%
            </Text>
          </View>
          <View style={styles.tradeDetails}>
            <View style={styles.tradeDetail}>
              <Text style={styles.tradeDetailLabel}>Entry</Text>
              <Text style={styles.tradeDetailValue}>
                ${trade.entry_price.toFixed(2)} · {trade.entry_date}
              </Text>
            </View>
            <View style={styles.tradeDetail}>
              <Text style={styles.tradeDetailLabel}>Exit</Text>
              <Text style={styles.tradeDetailValue}>
                ${trade.exit_price.toFixed(2)} · {trade.exit_date}
              </Text>
            </View>
          </View>
          <View style={styles.tradeFooter}>
            <View style={styles.exitBadge}>
              <Text style={styles.exitBadgeText}>{formatExitReason(trade.exit_reason)}</Text>
            </View>
            {trade.pnl !== 0 && (
              <Text
                style={[
                  styles.tradePnlDollar,
                  { color: trade.pnl >= 0 ? Colors.green : Colors.red },
                ]}
              >
                {trade.pnl >= 0 ? '+' : ''}${Math.abs(trade.pnl).toFixed(0)}
              </Text>
            )}
          </View>
        </Pressable>
      ))}
    </>
  );
}

/* ── Missed Tab ───────────────────────────────────────── */

function MissedTab({
  missed,
  onMissedPress,
}: {
  missed: MissedOpportunity[];
  onMissedPress: (symbol: string) => void;
}) {
  if (missed.length === 0) {
    return (
      <View style={styles.emptyCard}>
        <Text style={styles.emptyText}>No recent missed opportunities</Text>
      </View>
    );
  }

  return (
    <>
      {missed.map((m, i) => (
        <Pressable
          key={`${m.symbol}-${m.entry_date}-${i}`}
          style={({ pressed }) => [styles.missedCard, pressed && styles.pressed]}
          onPress={() => onMissedPress(m.symbol)}
        >
          <View style={styles.missedHeader}>
            <Text style={styles.missedSymbol}>{m.symbol}</Text>
            <Text style={[styles.missedReturn, { color: Colors.green }]}>
              +{m.would_be_return.toFixed(1)}%
            </Text>
          </View>
          <View style={styles.missedDetails}>
            <View style={styles.missedDetail}>
              <Text style={styles.missedDetailLabel}>Entry</Text>
              <Text style={styles.missedDetailValue}>
                ${m.entry_price.toFixed(2)} · {m.entry_date}
              </Text>
            </View>
            <View style={styles.missedDetail}>
              <Text style={styles.missedDetailLabel}>Exit</Text>
              <Text style={styles.missedDetailValue}>
                ${m.sell_price.toFixed(2)} · {m.sell_date}
              </Text>
            </View>
            <View style={styles.missedDetail}>
              <Text style={styles.missedDetailLabel}>Held</Text>
              <Text style={styles.missedDetailValue}>{m.days_held}d</Text>
            </View>
          </View>
          <View style={styles.exitReasonRow}>
            <Text style={styles.exitReasonText}>{formatExitReason(m.exit_reason)}</Text>
          </View>
        </Pressable>
      ))}
    </>
  );
}

function formatExitReason(reason: string): string {
  return reason
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/* ── StatBox ──────────────────────────────────────────── */

function StatBox({
  label,
  value,
  change,
  sub,
}: {
  label: string;
  value: string;
  change?: number;
  sub?: string;
}) {
  const valueColor =
    change != null
      ? change >= 0
        ? Colors.green
        : Colors.red
      : Colors.textPrimary;
  return (
    <View style={styles.statBox}>
      <Text style={styles.statLabel}>{label}</Text>
      <Text style={[styles.statValue, { color: valueColor }]}>{value}</Text>
      {sub && <Text style={styles.statSub}>{sub}</Text>}
    </View>
  );
}

/* ── Styles ───────────────────────────────────────────── */

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Palette.paper,
  },
  content: {
    padding: Spacing.md,
    gap: Spacing.md,
    paddingBottom: Spacing.xl,
  },
  center: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: Palette.paper,
  },
  errorText: {
    color: Palette.negative,
    fontSize: FontSize.md,
    fontFamily: Fonts.body.regular,
  },
  pressed: {
    opacity: 0.85,
  },

  // Stats row
  statsRow: {
    flexDirection: 'row',
    gap: Spacing.sm,
  },
  statBox: {
    flex: 1,
    backgroundColor: Palette.paperCard,
    borderRadius: Radii.md,
    borderWidth: 1,
    borderColor: Palette.rule,
    padding: Spacing.md,
    alignItems: 'center',
  },
  statLabel: {
    color: Palette.inkLight,
    fontSize: FontSize.xs,
    fontFamily: Fonts.body.regular,
    marginBottom: 4,
    letterSpacing: 0.4,
    textTransform: 'uppercase',
  },
  statValue: {
    color: Palette.ink,
    fontSize: FontSize.lg,
    fontFamily: Fonts.mono.medium,
  },
  statChange: {
    fontSize: FontSize.xs,
    fontFamily: Fonts.mono.medium,
    marginTop: 2,
  },
  statSub: {
    color: Palette.positive,
    fontSize: FontSize.xs,
    fontFamily: Fonts.body.regular,
    marginTop: 2,
  },

  // Portfolio card
  portfolioCard: {
    backgroundColor: Palette.paperCard,
    borderRadius: Radii.md,
    borderWidth: 1,
    borderColor: Palette.rule,
    padding: Spacing.md,
  },
  portfolioStats: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    marginTop: Spacing.sm,
  },
  portfolioValue: {
    color: Palette.ink,
    fontSize: FontSize.xl,
    fontFamily: Fonts.display.semibold,
    textAlign: 'center',
  },
  portfolioReturn: {
    fontSize: FontSize.xl,
    fontFamily: Fonts.mono.medium,
    textAlign: 'center',
  },
  portfolioLabel: {
    color: Palette.inkLight,
    fontSize: FontSize.xs,
    fontFamily: Fonts.body.regular,
    textAlign: 'center',
    marginTop: 4,
    letterSpacing: 0.4,
    textTransform: 'uppercase',
  },

  // Tab pill row (in-page tabs: Signals / Positions / History / Missed)
  tabBar: {
    flexDirection: 'row',
    backgroundColor: Palette.paperDeep,
    borderRadius: Radii.md,
    padding: 3,
    gap: 3,
  },
  tabPill: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: Radii.sm,
    alignItems: 'center',
  },
  tabPillActive: {
    backgroundColor: Palette.ink,
  },
  tabPillText: {
    color: Palette.inkMute,
    fontSize: FontSize.sm,
    fontFamily: Fonts.body.medium,
    letterSpacing: 0.3,
  },
  tabPillTextActive: {
    color: Palette.paper,
    fontFamily: Fonts.body.semibold,
  },

  // Sector filter
  filterToggle: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Palette.paperCard,
    borderRadius: Radii.md,
    borderWidth: 1,
    borderColor: Palette.rule,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
  },
  filterToggleText: {
    color: Palette.inkMute,
    fontSize: FontSize.xs,
    fontFamily: Fonts.body.semibold,
    flex: 1,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
  },
  filterDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: Palette.claret,
    marginRight: Spacing.sm,
  },
  filterChevron: {
    color: Palette.inkLight,
    fontSize: FontSize.xs,
  },
  sectorPillRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.xs,
    marginTop: Spacing.sm,
  },
  sectorPill: {
    backgroundColor: 'transparent',
    borderRadius: Radii.pill,
    paddingHorizontal: 12,
    paddingVertical: 5,
    borderWidth: 1,
    borderColor: Palette.ink,
  },
  sectorPillExcluded: {
    backgroundColor: 'transparent',
    borderColor: Palette.rule,
  },
  sectorPillText: {
    color: Palette.ink,
    fontSize: FontSize.xs,
    fontFamily: Fonts.body.medium,
  },
  sectorPillTextExcluded: {
    color: Palette.inkLight,
  },
  sectorReset: {
    color: Palette.claret,
    fontSize: FontSize.xs,
    fontFamily: Fonts.body.semibold,
    paddingVertical: 4,
    paddingHorizontal: 6,
  },
  filterDisclaimer: {
    color: Palette.inkLight,
    fontSize: 10,
    fontFamily: Fonts.display.italic,
    marginTop: Spacing.xs,
  },

  // Section headers
  sectionTitle: {
    color: Palette.ink,
    fontSize: FontSize.lg,
    fontFamily: Fonts.display.semibold,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
  },
  sectionDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: Palette.claret,
  },
  sectionSubtitle: {
    color: Palette.inkLight,
    fontSize: FontSize.xs,
    fontFamily: Fonts.body.regular,
    marginTop: 2,
  },

  // Empty state
  emptyCard: {
    backgroundColor: Palette.paperCard,
    borderRadius: Radii.md,
    borderWidth: 1,
    borderColor: Palette.rule,
    padding: Spacing.lg,
    alignItems: 'center',
  },
  emptyText: {
    color: Palette.inkMute,
    fontSize: FontSize.md,
    fontFamily: Fonts.body.regular,
  },
  emptySubtext: {
    color: Palette.inkLight,
    fontSize: FontSize.sm,
    fontFamily: Fonts.body.regular,
    marginTop: Spacing.xs,
  },

  // Track button (primary call-to-action)
  trackButton: {
    backgroundColor: Palette.ink,
    borderRadius: Radii.md,
    paddingVertical: 12,
    alignItems: 'center',
    marginTop: -4,
    marginBottom: Spacing.sm,
  },
  trackButtonText: {
    color: Palette.paper,
    fontSize: FontSize.sm,
    fontFamily: Fonts.body.semibold,
    letterSpacing: 0.4,
  },

  // Position cards
  positionCard: {
    backgroundColor: Palette.paperCard,
    borderRadius: Radii.md,
    borderWidth: 1,
    borderColor: Palette.rule,
    padding: Spacing.md,
  },
  positionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: Spacing.sm,
  },
  positionSymbol: {
    color: Palette.ink,
    fontSize: FontSize.lg,
    fontFamily: Fonts.display.semibold,
  },
  positionPnl: {
    fontSize: FontSize.lg,
    fontFamily: Fonts.mono.medium,
  },
  positionDetails: {
    flexDirection: 'row',
    gap: Spacing.lg,
  },
  positionDetail: {},
  positionDetailLabel: {
    color: Palette.inkLight,
    fontSize: FontSize.xs,
    fontFamily: Fonts.body.regular,
    marginBottom: 2,
    letterSpacing: 0.3,
    textTransform: 'uppercase',
  },
  positionDetailValue: {
    color: Palette.inkMute,
    fontSize: FontSize.sm,
    fontFamily: Fonts.mono.regular,
  },
  guidanceRow: {
    marginTop: Spacing.sm,
    paddingTop: Spacing.sm,
    borderTopWidth: 1,
    borderTopColor: Palette.rule,
  },
  guidanceText: {
    color: Palette.claret,
    fontSize: FontSize.xs,
    fontFamily: Fonts.display.italic,
  },

  // Sell button
  sellButton: {
    backgroundColor: 'transparent',
    borderRadius: Radii.md,
    borderWidth: 1,
    borderColor: Palette.negative,
    paddingVertical: 10,
    alignItems: 'center',
    marginTop: Spacing.sm,
  },
  sellButtonText: {
    color: Palette.negative,
    fontSize: FontSize.sm,
    fontFamily: Fonts.body.semibold,
    letterSpacing: 0.4,
  },

  // Live quote timestamp
  lastUpdated: {
    color: Palette.inkLight,
    fontSize: FontSize.xs,
    fontFamily: Fonts.body.regular,
    textAlign: 'center',
  },

  // History tab
  historyStatsRow: {
    flexDirection: 'row',
    gap: Spacing.sm,
  },
  historyStat: {
    flex: 1,
    backgroundColor: Palette.paperCard,
    borderRadius: Radii.md,
    borderWidth: 1,
    borderColor: Palette.rule,
    padding: Spacing.md,
    alignItems: 'center',
  },
  historyStatValue: {
    color: Palette.ink,
    fontSize: FontSize.lg,
    fontFamily: Fonts.mono.medium,
  },
  historyStatLabel: {
    color: Palette.inkLight,
    fontSize: FontSize.xs,
    fontFamily: Fonts.body.regular,
    marginTop: 4,
    letterSpacing: 0.4,
    textTransform: 'uppercase',
  },

  // Trade cards
  tradeCard: {
    backgroundColor: Palette.paperCard,
    borderRadius: Radii.md,
    borderWidth: 1,
    borderColor: Palette.rule,
    padding: Spacing.md,
  },
  tradeHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: Spacing.sm,
  },
  tradeSymbol: {
    color: Palette.ink,
    fontSize: FontSize.lg,
    fontFamily: Fonts.display.semibold,
  },
  tradePnl: {
    fontSize: FontSize.lg,
    fontFamily: Fonts.mono.medium,
  },
  tradeDetails: {
    gap: Spacing.xs,
  },
  tradeDetail: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  tradeDetailLabel: {
    color: Palette.inkLight,
    fontSize: FontSize.sm,
    fontFamily: Fonts.body.regular,
  },
  tradeDetailValue: {
    color: Palette.inkMute,
    fontSize: FontSize.sm,
    fontFamily: Fonts.mono.regular,
  },
  tradeFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: Spacing.sm,
    paddingTop: Spacing.sm,
    borderTopWidth: 1,
    borderTopColor: Palette.rule,
  },
  exitBadge: {
    backgroundColor: Palette.paperDeep,
    borderRadius: Radii.sm,
    paddingHorizontal: 8,
    paddingVertical: 3,
  },
  exitBadgeText: {
    color: Palette.inkMute,
    fontSize: FontSize.xs,
    fontFamily: Fonts.body.medium,
    letterSpacing: 0.3,
  },
  tradePnlDollar: {
    fontSize: FontSize.sm,
    fontFamily: Fonts.mono.regular,
  },

  // Modal rows
  modalRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: Spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: Palette.rule,
  },
  modalLabel: {
    color: Palette.inkMute,
    fontSize: FontSize.md,
    fontFamily: Fonts.body.regular,
  },
  modalValue: {
    color: Palette.ink,
    fontSize: FontSize.md,
    fontFamily: Fonts.mono.medium,
  },

  // Missed cards
  missedCard: {
    backgroundColor: Palette.paperCard,
    borderRadius: Radii.md,
    borderWidth: 1,
    borderColor: Palette.rule,
    padding: Spacing.md,
  },
  missedHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: Spacing.sm,
  },
  missedSymbol: {
    color: Palette.ink,
    fontSize: FontSize.lg,
    fontFamily: Fonts.display.semibold,
  },
  missedReturn: {
    fontSize: FontSize.lg,
    fontFamily: Fonts.mono.medium,
  },
  missedDetails: {
    flexDirection: 'row',
    gap: Spacing.lg,
    flexWrap: 'wrap',
  },
  missedDetail: {
    marginBottom: Spacing.xs,
  },
  missedDetailLabel: {
    color: Palette.inkLight,
    fontSize: FontSize.xs,
    fontFamily: Fonts.body.regular,
    marginBottom: 2,
    letterSpacing: 0.3,
    textTransform: 'uppercase',
  },
  missedDetailValue: {
    color: Palette.inkMute,
    fontSize: FontSize.sm,
    fontFamily: Fonts.mono.regular,
  },
  exitReasonRow: {
    marginTop: Spacing.sm,
    paddingTop: Spacing.sm,
    borderTopWidth: 1,
    borderTopColor: Palette.rule,
  },
  exitReasonText: {
    color: Palette.inkLight,
    fontSize: FontSize.xs,
    fontFamily: Fonts.body.regular,
  },
});
