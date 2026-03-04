/**
 * Individual signal detail screen.
 *
 * Portrait: data card + compact chart.
 * Landscape: full-screen interactive chart with pinch-to-zoom.
 */

import React, { useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Dimensions,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { Stack, useLocalSearchParams } from 'expo-router';
import * as ScreenOrientation from 'expo-screen-orientation';
import api from '@/services/api';
import PriceChart from '@/components/PriceChart';
import { useChartData } from '@/hooks/useChartData';
import { useStockInfo } from '@/hooks/useStockInfo';
import { useLiveQuotes } from '@/hooks/useLiveQuotes';
import { Colors, FontSize, Spacing } from '@/constants/theme';

type DataSource = 'signal' | 'position' | 'missed' | 'chart_only';

interface StockData {
  source: DataSource;
  symbol: string;
  price: number;
  // Signal fields
  pct_above_dwap?: number;
  is_strong?: boolean;
  is_fresh?: boolean;
  momentum_rank?: number;
  ensemble_score?: number;
  dwap_crossover_date?: string | null;
  ensemble_entry_date?: string | null;
  days_since_crossover?: number | null;
  days_since_entry?: number | null;
  sector?: string;
  signal_strength_label?: string;
  // Position fields
  entry_price?: number;
  entry_date?: string | null;
  shares?: number;
  pnl_pct?: number;
  high_water_mark?: number;
  trailing_stop_level?: number;
  distance_to_stop_pct?: number;
  action?: string;
  action_reason?: string;
  // Missed fields
  missed_gain_pct?: number;
  signal_date?: string;
}

const PERIOD_OPTIONS = [
  { label: '1M', days: 30 },
  { label: '3M', days: 90 },
  { label: '6M', days: 180 },
  { label: '1Y', days: 252 },
];

export default function SignalDetailScreen() {
  const { symbol } = useLocalSearchParams<{ symbol: string }>();
  const [stockData, setStockData] = useState<StockData | null>(null);
  const [loading, setLoading] = useState(true);
  const [isLandscape, setIsLandscape] = useState(false);
  const [chartDays, setChartDays] = useState(180);

  const { data: chartData, isLoading: chartLoading } = useChartData(
    symbol || '',
    chartDays
  );
  const { info: stockInfo } = useStockInfo(symbol || '');

  // Unlock landscape for this screen, lock back on unmount
  useEffect(() => {
    ScreenOrientation.unlockAsync();
    const sub = ScreenOrientation.addOrientationChangeListener((event) => {
      const o = event.orientationInfo.orientation;
      setIsLandscape(
        o === ScreenOrientation.Orientation.LANDSCAPE_LEFT ||
        o === ScreenOrientation.Orientation.LANDSCAPE_RIGHT
      );
    });

    // Check initial orientation
    ScreenOrientation.getOrientationAsync().then((o) => {
      setIsLandscape(
        o === ScreenOrientation.Orientation.LANDSCAPE_LEFT ||
        o === ScreenOrientation.Orientation.LANDSCAPE_RIGHT
      );
    });

    return () => {
      sub.remove();
      ScreenOrientation.lockAsync(ScreenOrientation.OrientationLock.PORTRAIT_UP);
    };
  }, []);

  // Fetch data — search buy_signals, positions, and missed opportunities
  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get('/api/signals/dashboard');

        // Check buy signals
        const sig = data.buy_signals?.find((s: any) => s.symbol === symbol);
        if (sig) {
          setStockData({ source: 'signal', ...sig });
          return;
        }

        // Check positions
        const pos = data.positions_with_guidance?.find((p: any) => p.symbol === symbol);
        if (pos) {
          setStockData({
            source: 'position',
            symbol: pos.symbol,
            price: pos.current_price,
            entry_price: pos.entry_price,
            entry_date: pos.entry_date,
            shares: pos.shares,
            pnl_pct: pos.pnl_pct,
            high_water_mark: pos.high_water_mark,
            trailing_stop_level: pos.trailing_stop_level,
            distance_to_stop_pct: pos.distance_to_stop_pct,
            action: pos.action,
            action_reason: pos.action_reason,
          });
          return;
        }

        // Check missed opportunities
        const missed = data.missed_opportunities?.find((m: any) => m.symbol === symbol);
        if (missed) {
          setStockData({
            source: 'missed',
            symbol: missed.symbol,
            price: missed.current_price || missed.price || 0,
            missed_gain_pct: missed.gain_pct,
            signal_date: missed.signal_date,
            ensemble_score: missed.ensemble_score,
          });
          return;
        }

        // Not found in any list — still show chart
        setStockData({ source: 'chart_only', symbol: symbol || '', price: 0 });
      } catch {
        // On error, still show chart
        setStockData({ source: 'chart_only', symbol: symbol || '', price: 0 });
      } finally {
        setLoading(false);
      }
    })();
  }, [symbol]);

  // Live quotes — hooks must be above early returns to preserve call order
  const { quotes: liveQuotes, lastUpdate: liveLastUpdate } = useLiveQuotes(symbol ? [symbol] : []);

  const liveStockData = useMemo(() => {
    if (!stockData || stockData.source !== 'position') return stockData;
    const quote = liveQuotes[stockData.symbol];
    if (!quote) return stockData;
    const livePrice = quote.price;
    const entryPrice = stockData.entry_price || 0;
    const pnlPct = entryPrice > 0 ? ((livePrice - entryPrice) / entryPrice) * 100 : 0;
    const hwm = Math.max(stockData.high_water_mark || entryPrice, livePrice);
    const stopPrice = hwm * 0.88; // 12% trailing stop
    const distToStop = stopPrice > 0 ? ((livePrice - stopPrice) / stopPrice) * 100 : 100;
    return {
      ...stockData,
      price: livePrice,
      pnl_pct: pnlPct,
      high_water_mark: hwm,
      trailing_stop_level: stopPrice,
      distance_to_stop_pct: distToStop,
    };
  }, [stockData, liveQuotes]);

  if (loading) {
    return (
      <View style={styles.center}>
        <Stack.Screen options={{ title: symbol || 'Stock', headerShown: !isLandscape, headerBackTitle: 'Back', headerStyle: { backgroundColor: Colors.navy }, headerTintColor: Colors.textPrimary }} />
        <ActivityIndicator size="large" color={Colors.gold} />
      </View>
    );
  }

  const d = liveStockData!;
  const displayPrice = d.price || (chartData.length > 0 ? chartData[chartData.length - 1]?.close : 0) || 0;

  // ── Landscape: full-screen chart ──
  if (isLandscape) {
    return (
      <View style={styles.landscapeWrap}>
        <Stack.Screen options={{ headerShown: false }} />
        <View style={styles.landscapeHeader}>
          <Text style={styles.landscapeSymbol}>{d.symbol}</Text>
          {displayPrice > 0 && <Text style={styles.landscapePrice}>${displayPrice.toFixed(2)}</Text>}
        </View>
        <View style={styles.landscapePeriods}>
          {PERIOD_OPTIONS.map((p) => (
            <Pressable
              key={p.label}
              onPress={() => setChartDays(p.days)}
              style={[styles.periodButton, chartDays === p.days && styles.periodActive]}
            >
              <Text style={[styles.periodText, chartDays === p.days && styles.periodTextActive]}>
                {p.label}
              </Text>
            </Pressable>
          ))}
        </View>
        {chartLoading ? (
          <View style={styles.center}><ActivityIndicator color={Colors.gold} /></View>
        ) : (
          <PriceChart
            data={chartData}
            entryDate={d.ensemble_entry_date || d.entry_date}
            breakoutDate={d.dwap_crossover_date}
            isLandscape
          />
        )}
        <Text style={styles.landscapeHint}>Pinch to zoom  |  Drag for crosshair</Text>
      </View>
    );
  }

  // ── Portrait: chart + data card ──
  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Stack.Screen
        options={{
          title: d.symbol,
          headerStyle: { backgroundColor: Colors.navy },
          headerTintColor: Colors.textPrimary,
          headerBackTitle: 'Back',
          headerShown: true,
        }}
      />

      {/* Chart */}
      <View>
        <View style={styles.periodRow}>
          {PERIOD_OPTIONS.map((p) => (
            <Pressable
              key={p.label}
              onPress={() => setChartDays(p.days)}
              style={[styles.periodButton, chartDays === p.days && styles.periodActive]}
            >
              <Text style={[styles.periodText, chartDays === p.days && styles.periodTextActive]}>
                {p.label}
              </Text>
            </Pressable>
          ))}
        </View>
        {chartLoading ? (
          <View style={[styles.chartPlaceholder]}>
            <ActivityIndicator color={Colors.gold} />
          </View>
        ) : (
          <PriceChart
            data={chartData}
            entryDate={d.ensemble_entry_date || d.entry_date}
            breakoutDate={d.dwap_crossover_date}
          />
        )}
        <Text style={styles.rotateHint}>Rotate for full-screen chart</Text>
      </View>

      {/* Header */}
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <Text style={styles.symbol}>{d.symbol}</Text>
          {stockInfo?.name && (
            <Text style={styles.companyName}>{stockInfo.name}</Text>
          )}
          <View style={styles.badges}>
            {d.source === 'signal' && d.is_fresh && (
              <View style={styles.freshBadge}><Text style={styles.freshText}>FRESH</Text></View>
            )}
            {d.source === 'signal' && d.is_strong && (
              <View style={styles.strongBadge}><Text style={styles.strongText}>STRONG</Text></View>
            )}
            {d.source === 'position' && (
              <View style={[styles.freshBadge, { backgroundColor: Colors.gold + '22' }]}>
                <Text style={[styles.freshText, { color: Colors.gold }]}>POSITION</Text>
              </View>
            )}
            {d.source === 'position' && d.action === 'sell' && (
              <View style={[styles.freshBadge, { backgroundColor: Colors.red + '22' }]}>
                <Text style={[styles.freshText, { color: Colors.red }]}>SELL</Text>
              </View>
            )}
            {d.source === 'position' && d.action === 'warning' && (
              <View style={[styles.freshBadge, { backgroundColor: '#F59E0B22' }]}>
                <Text style={[styles.freshText, { color: '#F59E0B' }]}>WARNING</Text>
              </View>
            )}
          </View>
        </View>
        {displayPrice > 0 && <Text style={styles.price}>${displayPrice.toFixed(2)}</Text>}
      </View>

      {/* Company Info */}
      {stockInfo && (
        <View style={styles.companySection}>
          {stockInfo.sector && stockInfo.industry && (
            <View style={styles.industryBadge}>
              <Text style={styles.industryText}>
                {stockInfo.sector} — {stockInfo.industry}
              </Text>
            </View>
          )}
          {stockInfo.description && (
            <Text style={styles.companyDesc} numberOfLines={4}>
              {stockInfo.description}
            </Text>
          )}
        </View>
      )}

      {/* Signal-specific data */}
      {d.source === 'signal' && (() => {
        const label = d.signal_strength_label || (() => {
          const s = d.ensemble_score || 0;
          if (s >= 88) return 'Very Strong';
          if (s >= 75) return 'Strong';
          if (s >= 61) return 'Moderate';
          return 'Weak';
        })();
        const color = label === 'Very Strong' ? Colors.green
          : label === 'Strong' ? '#86EFAC'
          : label === 'Moderate' ? '#F59E0B'
          : Colors.textMuted;
        return (
          <>
            <View style={[styles.strengthCard, { borderColor: color + '33', backgroundColor: color + '15' }]}>
              <Text style={[styles.strengthCardLabel, { color }]}>Signal Strength</Text>
              <Text style={[styles.strengthCardValue, { color }]}>{label}</Text>
            </View>
            <View style={styles.grid}>
              <DetailRow label="Breakout %" value={`+${(d.pct_above_dwap ?? 0).toFixed(1)}%`} />
              <DetailRow label="Momentum Rank" value={`#${d.momentum_rank}`} />
              <DetailRow label="Breakout Date" value={d.dwap_crossover_date || '—'} />
              <DetailRow label="Days Since Breakout" value={d.days_since_crossover != null ? `${d.days_since_crossover}` : '—'} />
              <DetailRow label="Entry Date" value={d.ensemble_entry_date || '—'} />
              <DetailRow label="Days Since Entry" value={d.days_since_entry != null ? `${d.days_since_entry}` : '—'} />
              {d.sector && <DetailRow label="Sector" value={d.sector} />}
            </View>
          </>
        );
      })()}

      {/* Position-specific data */}
      {d.source === 'position' && (
        <>
          {d.pnl_pct != null && (
            <View style={[styles.scoreCard, { borderColor: (d.pnl_pct >= 0 ? Colors.green : Colors.red) + '33', backgroundColor: (d.pnl_pct >= 0 ? Colors.green : Colors.red) + '15' }]}>
              <Text style={[styles.scoreLabel, { color: d.pnl_pct >= 0 ? Colors.green : Colors.red }]}>P&L</Text>
              <Text style={[styles.scoreValue, { color: d.pnl_pct >= 0 ? Colors.green : Colors.red }]}>
                {d.pnl_pct >= 0 ? '+' : ''}{d.pnl_pct.toFixed(1)}%
              </Text>
            </View>
          )}
          <View style={styles.grid}>
            <DetailRow label="Entry Price" value={d.entry_price ? `$${d.entry_price.toFixed(2)}` : '—'} />
            <DetailRow label="Entry Date" value={d.entry_date || '—'} />
            <DetailRow label="Shares" value={d.shares != null ? `${d.shares}` : '—'} />
            <DetailRow label="High Water Mark" value={d.high_water_mark ? `$${d.high_water_mark.toFixed(2)}` : '—'} />
            <DetailRow label="Trailing Stop" value={d.trailing_stop_level ? `$${d.trailing_stop_level.toFixed(2)}` : '—'} />
            <DetailRow label="Distance to Stop" value={d.distance_to_stop_pct != null ? `${d.distance_to_stop_pct.toFixed(1)}%` : '—'} />
          </View>
          {d.action_reason && (
            <View style={[styles.scoreCard, { borderColor: Colors.cardBorder, backgroundColor: Colors.card }]}>
              <Text style={[styles.scoreLabel, { color: Colors.textSecondary }]}>Guidance</Text>
              <Text style={[styles.detailValue, { textAlign: 'center', lineHeight: 20 }]}>{d.action_reason}</Text>
            </View>
          )}
          <Text style={styles.lastUpdated}>
            {liveLastUpdate
              ? `Updated ${liveLastUpdate.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}`
              : 'Updating...'}
          </Text>
        </>
      )}

      {/* Missed opportunity data */}
      {d.source === 'missed' && (
        <View style={styles.grid}>
          {d.missed_gain_pct != null && <DetailRow label="Missed Gain" value={`+${d.missed_gain_pct.toFixed(1)}%`} />}
          {d.signal_date && <DetailRow label="Signal Date" value={d.signal_date} />}
          {d.ensemble_score != null && <DetailRow label="Ensemble Score" value={d.ensemble_score.toFixed(1)} />}
        </View>
      )}

      {/* Disclaimer */}
      <Text style={styles.disclaimer}>
        {d.source === 'signal'
          ? 'This is a buy signal, not a recommendation. Execute via your broker. Always do your own research.'
          : 'Past performance does not guarantee future results. Always do your own research.'}
      </Text>
    </ScrollView>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.detailRow}>
      <Text style={styles.detailLabel}>{label}</Text>
      <Text style={styles.detailValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
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
    backgroundColor: Colors.background,
  },
  emptyText: {
    color: Colors.textMuted,
    fontSize: FontSize.md,
  },
  // Portrait chart
  periodRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: Spacing.sm,
    marginBottom: Spacing.sm,
  },
  periodButton: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 6,
    backgroundColor: Colors.card,
  },
  periodActive: {
    backgroundColor: Colors.gold + '33',
  },
  periodText: {
    color: Colors.textMuted,
    fontSize: FontSize.xs,
    fontWeight: '600',
  },
  periodTextActive: {
    color: Colors.gold,
  },
  chartPlaceholder: {
    height: 220,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: Colors.card,
    borderRadius: 12,
  },
  rotateHint: {
    color: Colors.textMuted,
    fontSize: FontSize.xs,
    textAlign: 'center',
    marginTop: Spacing.xs,
  },
  // Landscape
  landscapeWrap: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  landscapeHeader: {
    position: 'absolute',
    top: Spacing.sm,
    left: Spacing.lg,
    zIndex: 10,
    flexDirection: 'row',
    alignItems: 'baseline',
    gap: Spacing.sm,
  },
  landscapeSymbol: {
    color: Colors.textPrimary,
    fontSize: FontSize.lg,
    fontWeight: '800',
  },
  landscapePrice: {
    color: Colors.gold,
    fontSize: FontSize.md,
    fontWeight: '600',
  },
  landscapePeriods: {
    position: 'absolute',
    top: Spacing.sm,
    right: Spacing.lg,
    zIndex: 10,
    flexDirection: 'row',
    gap: Spacing.xs,
  },
  landscapeHint: {
    position: 'absolute',
    bottom: 4,
    left: 0,
    right: 0,
    textAlign: 'center',
    color: Colors.textMuted,
    fontSize: 9,
    opacity: 0.6,
  },
  // Data card
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  headerLeft: {
    gap: Spacing.sm,
  },
  symbol: {
    color: Colors.textPrimary,
    fontSize: FontSize.xxl,
    fontWeight: '800',
  },
  badges: {
    flexDirection: 'row',
    gap: Spacing.sm,
  },
  freshBadge: {
    backgroundColor: Colors.green + '22',
    borderRadius: 4,
    paddingHorizontal: 8,
    paddingVertical: 3,
  },
  freshText: {
    color: Colors.green,
    fontSize: FontSize.xs,
    fontWeight: '700',
  },
  strongBadge: {
    backgroundColor: Colors.gold + '22',
    borderRadius: 4,
    paddingHorizontal: 8,
    paddingVertical: 3,
  },
  strongText: {
    color: Colors.gold,
    fontSize: FontSize.xs,
    fontWeight: '700',
  },
  price: {
    color: Colors.textPrimary,
    fontSize: FontSize.xxl,
    fontWeight: '700',
  },
  companyName: {
    color: Colors.textSecondary,
    fontSize: FontSize.sm,
  },
  companySection: {
    gap: Spacing.sm,
  },
  industryBadge: {
    alignSelf: 'flex-start',
    backgroundColor: '#4338CA22',
    borderRadius: 12,
    paddingHorizontal: 10,
    paddingVertical: 4,
  },
  industryText: {
    color: '#818CF8',
    fontSize: FontSize.xs,
    fontWeight: '600',
  },
  companyDesc: {
    color: Colors.textMuted,
    fontSize: FontSize.sm,
    lineHeight: 18,
  },
  scoreCard: {
    backgroundColor: Colors.gold + '15',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: Colors.gold + '33',
    padding: Spacing.lg,
    alignItems: 'center',
  },
  scoreLabel: {
    color: Colors.gold,
    fontSize: FontSize.sm,
    fontWeight: '600',
    marginBottom: Spacing.xs,
  },
  scoreValue: {
    color: Colors.gold,
    fontSize: 48,
    fontWeight: '800',
  },
  strengthCard: {
    borderRadius: 12,
    borderWidth: 1,
    padding: Spacing.lg,
    alignItems: 'center',
  },
  strengthCardLabel: {
    fontSize: FontSize.sm,
    fontWeight: '600',
    marginBottom: Spacing.xs,
  },
  strengthCardValue: {
    fontSize: FontSize.xxl,
    fontWeight: '800',
  },
  grid: {
    backgroundColor: Colors.card,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: Colors.cardBorder,
    overflow: 'hidden',
  },
  detailRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: Spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: Colors.cardBorder,
  },
  detailLabel: {
    color: Colors.textSecondary,
    fontSize: FontSize.md,
  },
  detailValue: {
    color: Colors.textPrimary,
    fontSize: FontSize.md,
    fontWeight: '600',
  },
  lastUpdated: {
    color: Colors.textMuted,
    fontSize: FontSize.xs,
    textAlign: 'center',
  },
  disclaimer: {
    color: Colors.textMuted,
    fontSize: FontSize.xs,
    textAlign: 'center',
    lineHeight: 18,
    marginTop: Spacing.md,
  },
});
