/**
 * Buy signal card — used in dashboard and signal list.
 */

import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Fonts, FontSize, Palette, Radii, Spacing } from '@/constants/theme';
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
  // Editorial palette: claret for strongest signals, ink-mute for the rest.
  // Avoid loud green/yellow which fight the paper aesthetic.
  const strengthColor =
    strengthLabel === 'Very Strong' ? Palette.claret
    : strengthLabel === 'Strong' ? Palette.claretLight
    : strengthLabel === 'Moderate' ? Palette.inkMute
    : Palette.inkLight;

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
          <View style={[styles.strengthBadge, { borderColor: strengthColor }]}>
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
    backgroundColor: Palette.paperCard,
    borderRadius: Radii.md,
    borderWidth: 1,
    borderColor: Palette.rule,
    padding: Spacing.md,
    marginBottom: Spacing.sm,
  },
  pressed: {
    opacity: 0.85,
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
    color: Palette.ink,
    fontSize: FontSize.lg,
    fontFamily: Fonts.display.semibold,
  },
  price: {
    color: Palette.ink,
    fontSize: FontSize.lg,
    fontFamily: Fonts.mono.medium,
  },
  freshBadge: {
    borderRadius: Radii.sm,
    paddingHorizontal: 6,
    paddingVertical: 2,
    backgroundColor: Palette.claret,
  },
  freshText: {
    color: Palette.paper,
    fontSize: FontSize.xs,
    fontFamily: Fonts.body.semibold,
    letterSpacing: 0.6,
  },
  strengthBadge: {
    borderRadius: Radii.sm,
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderWidth: 1,
  },
  strengthText: {
    fontSize: FontSize.xs,
    fontFamily: Fonts.body.medium,
    letterSpacing: 0.4,
  },
  stats: {
    flexDirection: 'row',
    gap: Spacing.lg,
  },
  statItem: {},
  statLabel: {
    color: Palette.inkLight,
    fontSize: FontSize.xs,
    fontFamily: Fonts.body.regular,
    marginBottom: 2,
    letterSpacing: 0.4,
    textTransform: 'uppercase',
  },
  statValue: {
    color: Palette.inkMute,
    fontSize: FontSize.sm,
    fontFamily: Fonts.mono.regular,
  },
});
