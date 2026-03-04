/**
 * Buy signal card — used in dashboard and signal list.
 */

import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Colors, FontSize, Spacing } from '@/constants/theme';
import { Signal } from '@/hooks/useSignals';

interface SignalCardProps {
  signal: Signal;
  onPress?: () => void;
}

export default function SignalCard({ signal, onPress }: SignalCardProps) {
  const strengthLabel = signal.signal_strength_label || (() => {
    const score = signal.ensemble_score || 0;
    if (score >= 88) return 'Very Strong';
    if (score >= 75) return 'Strong';
    if (score >= 61) return 'Moderate';
    return 'Weak';
  })();
  const strengthColor = strengthLabel === 'Very Strong' ? Colors.green
    : strengthLabel === 'Strong' ? '#86EFAC'
    : strengthLabel === 'Moderate' ? Colors.yellow
    : Colors.textMuted;

  return (
    <Pressable
      style={({ pressed }) => [styles.card, pressed && styles.pressed]}
      onPress={onPress}
    >
      <View style={styles.header}>
        <View style={styles.symbolRow}>
          <Text style={styles.symbol}>{signal.symbol}</Text>
          {signal.is_fresh && (
            <View style={styles.freshBadge}>
              <Text style={styles.freshText}>FRESH</Text>
            </View>
          )}
          <View style={[styles.strengthBadge, { backgroundColor: strengthColor + '22' }]}>
            <Text style={[styles.strengthText, { color: strengthColor }]}>{strengthLabel}</Text>
          </View>
        </View>
        <Text style={styles.price}>${(signal.price ?? 0).toFixed(2)}</Text>
      </View>

      <View style={styles.stats}>
        <StatItem label="Breakout" value={`+${(signal.pct_above_dwap ?? 0).toFixed(1)}%`} />
        <StatItem label="Rank" value={`#${signal.momentum_rank ?? '—'}`} />
        <StatItem label="Days" value={
          signal.days_since_entry != null ? `${signal.days_since_entry}d` :
          signal.days_since_crossover != null ? `${signal.days_since_crossover}d` : '—'
        } />
        {signal.sector ? <StatItem label="Sector" value={signal.sector} /> : null}
      </View>
    </Pressable>
  );
}

function StatItem({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.statItem}>
      <Text style={styles.statLabel}>{label}</Text>
      <Text style={styles.statValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: Colors.card,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: Colors.cardBorder,
    padding: Spacing.md,
    marginBottom: Spacing.sm,
  },
  pressed: {
    opacity: 0.8,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: Spacing.sm,
  },
  symbolRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
  },
  symbol: {
    color: Colors.textPrimary,
    fontSize: FontSize.lg,
    fontWeight: '700',
  },
  price: {
    color: Colors.textPrimary,
    fontSize: FontSize.lg,
    fontWeight: '600',
  },
  freshBadge: {
    backgroundColor: Colors.green + '22',
    borderRadius: 4,
    paddingHorizontal: 6,
    paddingVertical: 2,
  },
  freshText: {
    color: Colors.green,
    fontSize: FontSize.xs,
    fontWeight: '700',
  },
  strengthBadge: {
    borderRadius: 4,
    paddingHorizontal: 6,
    paddingVertical: 2,
  },
  strengthText: {
    fontSize: FontSize.xs,
    fontWeight: '700',
  },
  stats: {
    flexDirection: 'row',
    gap: Spacing.lg,
  },
  statItem: {},
  statLabel: {
    color: Colors.textMuted,
    fontSize: FontSize.xs,
    marginBottom: 2,
  },
  statValue: {
    color: Colors.textSecondary,
    fontSize: FontSize.sm,
    fontWeight: '600',
  },
});
