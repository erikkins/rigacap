/**
 * A single labelled metric tile for the glance grid.
 */

import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { Fonts, FontSize, Palette, Radii, Spacing } from '@/constants/theme';

interface Props {
  label: string;
  value: string | number;
  sub?: string;
  tone?: 'default' | 'positive' | 'negative' | 'warning';
}

const TONE: Record<NonNullable<Props['tone']>, string> = {
  default: Palette.ink,
  positive: Palette.positive,
  negative: Palette.negative,
  warning: Palette.yellow,
};

export default function StatCard({ label, value, sub, tone = 'default' }: Props) {
  return (
    <View style={styles.card}>
      <Text style={styles.label}>{label.toUpperCase()}</Text>
      <Text style={[styles.value, { color: TONE[tone] }]} numberOfLines={1} adjustsFontSizeToFit>
        {value}
      </Text>
      {sub ? <Text style={styles.sub}>{sub}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    flexGrow: 1,
    flexBasis: '46%',
    backgroundColor: Palette.paperCard,
    borderWidth: 1,
    borderColor: Palette.rule,
    borderRadius: Radii.lg,
    padding: Spacing.md,
  },
  label: {
    fontFamily: Fonts.body.medium,
    fontSize: FontSize.xs,
    letterSpacing: 0.6,
    color: Palette.inkLight,
    marginBottom: Spacing.xs,
  },
  value: {
    fontFamily: Fonts.display.semibold,
    fontSize: FontSize.xxl,
  },
  sub: {
    fontFamily: Fonts.body.regular,
    fontSize: FontSize.xs,
    color: Palette.inkMute,
    marginTop: 2,
  },
});
