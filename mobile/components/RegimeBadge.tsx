/**
 * Market regime indicator badge — tappable to expand full regime panel.
 */

import React, { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Colors, FontSize, Spacing } from '@/constants/theme';
import { RegimeForecast } from '@/hooks/useSignals';

const REGIME_LABELS: Record<string, string> = {
  strong_bull: 'Strong Bull',
  weak_bull: 'Weak Bull',
  rotating_bull: 'Rotating Bull',
  range_bound: 'Range Bound',
  weak_bear: 'Weak Bear',
  panic_crash: 'Panic / Crash',
  recovery: 'Recovery',
};

const REGIME_DESCRIPTIONS: Record<string, string> = {
  strong_bull: 'Broad market rally with strong breadth',
  weak_bull: 'Advancing market, narrow leadership',
  rotating_bull: 'Sector rotation driving gains',
  range_bound: 'Sideways, low conviction',
  weak_bear: 'Declining with selling pressure',
  panic_crash: 'Sharp selloff, elevated volatility',
  recovery: 'Rebounding from recent lows',
};

const ALL_REGIMES = [
  'strong_bull',
  'weak_bull',
  'rotating_bull',
  'range_bound',
  'weak_bear',
  'panic_crash',
  'recovery',
];

function getVixLabel(vix: number | null | undefined): { label: string; color: string } {
  if (vix == null) return { label: 'N/A', color: Colors.textSecondary };
  if (vix < 15) return { label: 'Calm', color: Colors.green };
  if (vix < 20) return { label: 'Normal', color: Colors.textSecondary };
  if (vix < 25) return { label: 'Elevated', color: Colors.amber ?? '#f59e0b' };
  if (vix < 35) return { label: 'High Fear', color: Colors.orange ?? '#f97316' };
  return { label: 'Extreme Fear', color: Colors.red };
}

interface RegimeBadgeProps {
  regime?: string;
  compact?: boolean;
  forecast?: RegimeForecast;
  marketStats?: {
    spy_price: number;
    spy_change_pct: number;
    vix_level: number;
  };
}

export default function RegimeBadge({
  regime,
  compact,
  forecast,
  marketStats,
}: RegimeBadgeProps) {
  const [expanded, setExpanded] = useState(false);

  const currentRegime = forecast?.current_regime || regime || '';
  const color = Colors.regime[currentRegime] || Colors.textMuted;
  const label = REGIME_LABELS[currentRegime] || currentRegime;

  if (compact) {
    return (
      <View style={[styles.compactBadge, { backgroundColor: color + '22' }]}>
        <View style={[styles.dot, { backgroundColor: color }]} />
        <Text style={[styles.compactText, { color }]}>{label}</Text>
      </View>
    );
  }

  // Collapsed banner (tap to expand)
  const banner = (
    <Pressable
      style={[styles.banner, { borderLeftColor: color }]}
      onPress={() => setExpanded((v) => !v)}
    >
      <View style={styles.bannerContent}>
        <View style={styles.bannerTopRow}>
          <View style={[styles.dot, { backgroundColor: color }]} />
          <Text style={styles.bannerLabel}>Market Regime</Text>
          <Text style={[styles.bannerValue, { color }]}>{label}</Text>
          <View style={{ flex: 1 }} />
          <Text style={styles.chevron}>{expanded ? '▲' : '▼'}</Text>
        </View>
        {marketStats?.spy_price != null && (
          <View style={styles.bannerBottomRow}>
            <Text style={styles.spyBanner}>
              SPY {marketStats.spy_price.toFixed(2)}
              {marketStats.spy_change_pct != null && (
                <Text style={{ color: marketStats.spy_change_pct >= 0 ? Colors.green : Colors.red }}>
                  {' '}({marketStats.spy_change_pct >= 0 ? '+' : ''}{marketStats.spy_change_pct.toFixed(2)}%)
                </Text>
              )}
            </Text>
          </View>
        )}
      </View>
    </Pressable>
  );

  if (!expanded || !forecast) return banner;

  // Get probabilities (prefer transition_probabilities, fall back to probabilities)
  const probs = forecast.transition_probabilities || forecast.probabilities || {};

  // Filter to >3% and sort descending
  const sortedProbs = Object.entries(probs)
    .filter(([, p]) => p > 3)
    .sort((a, b) => b[1] - a[1]);

  return (
    <View>
      {banner}
      <View style={styles.expandedPanel}>
        {/* Outlook / Risk / Action pills */}
        <View style={styles.pillRow}>
          {forecast.outlook && (
            <View style={[styles.pill, { backgroundColor: Colors.blue + '22' }]}>
              <Text style={[styles.pillText, { color: Colors.blue }]}>
                {forecast.outlook}
              </Text>
            </View>
          )}
          {forecast.risk_change && (
            <View style={[styles.pill, { backgroundColor: Colors.yellow + '22' }]}>
              <Text style={[styles.pillText, { color: Colors.yellow }]}>
                {forecast.risk_change}
              </Text>
            </View>
          )}
          {forecast.recommended_action && (
            <View style={[styles.pill, { backgroundColor: Colors.green + '22' }]}>
              <Text style={[styles.pillText, { color: Colors.green }]}>
                {forecast.recommended_action}
              </Text>
            </View>
          )}
        </View>

        {/* Outlook detail text */}
        {forecast.outlook_detail && (
          <Text style={styles.outlookDetail}>{forecast.outlook_detail}</Text>
        )}

        {/* SPY + VIX row */}
        {marketStats && (
          <View style={styles.marketRow}>
            <View style={styles.marketItem}>
              <Text style={styles.marketLabel}>S&P 500</Text>
              <Text style={styles.marketValue}>
                ${marketStats.spy_price?.toFixed(0) ?? '—'}
              </Text>
              {marketStats.spy_change_pct != null && (
                <Text
                  style={[
                    styles.marketChange,
                    { color: marketStats.spy_change_pct >= 0 ? Colors.green : Colors.red },
                  ]}
                >
                  {marketStats.spy_change_pct >= 0 ? '+' : ''}
                  {marketStats.spy_change_pct.toFixed(2)}%
                </Text>
              )}
            </View>
            <View style={styles.marketItem}>
              <Text style={styles.marketLabel}>Market Fear</Text>
              <Text style={[styles.marketValue, { color: getVixLabel(marketStats.vix_level).color }]}>
                {getVixLabel(marketStats.vix_level).label}
              </Text>
              <Text style={styles.marketChange}>VIX: {marketStats.vix_level?.toFixed(1) ?? '—'}</Text>
            </View>
          </View>
        )}

        {/* Transition probability bar */}
        {sortedProbs.length > 0 && (
          <View style={styles.probSection}>
            <Text style={styles.probTitle}>Transition Probabilities</Text>
            <View style={styles.probBar}>
              {sortedProbs.map(([regKey, pct]) => {
                const regColor = Colors.regime[regKey] || Colors.textMuted;
                return (
                  <View
                    key={regKey}
                    style={[
                      styles.probSegment,
                      { flex: pct, backgroundColor: regColor },
                    ]}
                  />
                );
              })}
            </View>
            <View style={styles.probLegend}>
              {sortedProbs.map(([regKey, pct]) => {
                const regColor = Colors.regime[regKey] || Colors.textMuted;
                return (
                  <View key={regKey} style={styles.probLegendItem}>
                    <View style={[styles.probDot, { backgroundColor: regColor }]} />
                    <Text style={styles.probLegendText}>
                      {REGIME_LABELS[regKey] || regKey} {pct.toFixed(0)}%
                    </Text>
                  </View>
                );
              })}
            </View>
          </View>
        )}

        {/* All 7 regimes list */}
        <View style={styles.regimeList}>
          {ALL_REGIMES.map((regKey) => {
            const regColor = Colors.regime[regKey] || Colors.textMuted;
            const isCurrent = regKey === currentRegime;
            const prob = probs[regKey];
            return (
              <View
                key={regKey}
                style={[
                  styles.regimeRow,
                  isCurrent && { backgroundColor: regColor + '15' },
                ]}
              >
                <View style={styles.regimeRowLeft}>
                  <View style={[styles.dot, { backgroundColor: regColor }]} />
                  <View>
                    <Text
                      style={[
                        styles.regimeName,
                        isCurrent && { color: regColor, fontWeight: '700' },
                      ]}
                    >
                      {REGIME_LABELS[regKey]}{isCurrent ? ' ●' : ''}
                    </Text>
                    <Text style={styles.regimeDesc}>
                      {REGIME_DESCRIPTIONS[regKey]}
                    </Text>
                  </View>
                </View>
                {prob != null && (
                  <Text style={[styles.regimeProb, { color: regColor }]}>
                    {prob.toFixed(0)}%
                  </Text>
                )}
              </View>
            );
          })}
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  banner: {
    backgroundColor: Colors.card,
    borderRadius: 8,
    borderLeftWidth: 3,
    padding: Spacing.md,
  },
  bannerContent: {
    gap: 4,
  },
  bannerTopRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
  },
  bannerBottomRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingLeft: 16,
  },
  bannerLabel: {
    color: Colors.textSecondary,
    fontSize: FontSize.sm,
  },
  bannerValue: {
    fontSize: FontSize.md,
    fontWeight: '700',
  },
  chevron: {
    color: Colors.textMuted,
    fontSize: 10,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  compactBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    borderRadius: 12,
    paddingHorizontal: 10,
    paddingVertical: 4,
    gap: 6,
  },
  compactText: {
    fontSize: FontSize.xs,
    fontWeight: '600',
  },

  // Expanded panel
  expandedPanel: {
    backgroundColor: Colors.card,
    borderRadius: 8,
    borderTopLeftRadius: 0,
    borderTopRightRadius: 0,
    marginTop: -4,
    padding: Spacing.md,
    gap: Spacing.md,
  },

  // Pills
  pillRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.sm,
  },
  pill: {
    borderRadius: 12,
    paddingHorizontal: 10,
    paddingVertical: 4,
  },
  pillText: {
    fontSize: FontSize.xs,
    fontWeight: '600',
  },

  outlookDetail: {
    color: Colors.textSecondary,
    fontSize: FontSize.sm,
    lineHeight: 18,
  },

  // SPY in collapsed banner
  spyBanner: {
    color: Colors.textPrimary,
    fontSize: FontSize.sm,
    fontWeight: '600',
  },

  // Market stats in expanded
  marketRow: {
    flexDirection: 'row',
    gap: Spacing.lg,
  },
  marketItem: {
    alignItems: 'center',
  },
  marketLabel: {
    color: Colors.textMuted,
    fontSize: FontSize.xs,
    marginBottom: 2,
  },
  marketValue: {
    color: Colors.textPrimary,
    fontSize: FontSize.md,
    fontWeight: '700',
  },
  marketChange: {
    fontSize: FontSize.xs,
    fontWeight: '600',
    marginTop: 2,
  },

  // Probability bar
  probSection: {
    gap: Spacing.xs,
  },
  probTitle: {
    color: Colors.textMuted,
    fontSize: FontSize.xs,
    fontWeight: '600',
  },
  probBar: {
    flexDirection: 'row',
    height: 6,
    borderRadius: 3,
    overflow: 'hidden',
  },
  probSegment: {
    height: 6,
  },
  probLegend: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.sm,
  },
  probLegendItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  probDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  probLegendText: {
    color: Colors.textMuted,
    fontSize: 10,
  },

  // All regimes list
  regimeList: {
    borderTopWidth: 1,
    borderTopColor: Colors.cardBorder,
    paddingTop: Spacing.sm,
  },
  regimeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: Spacing.sm,
    paddingHorizontal: Spacing.sm,
    borderRadius: 6,
  },
  regimeRowLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    flex: 1,
  },
  regimeName: {
    color: Colors.textSecondary,
    fontSize: FontSize.sm,
    fontWeight: '600',
  },
  regimeDesc: {
    color: Colors.textMuted,
    fontSize: 10,
    marginTop: 1,
  },
  regimeProb: {
    fontSize: FontSize.sm,
    fontWeight: '700',
    minWidth: 36,
    textAlign: 'right',
  },
});
