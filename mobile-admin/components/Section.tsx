/**
 * A titled section block with an optional right-aligned hint.
 */

import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { Fonts, FontSize, Palette, Spacing } from '@/constants/theme';

export default function Section({
  title,
  hint,
  children,
}: {
  title: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <View style={styles.wrap}>
      <View style={styles.header}>
        <Text style={styles.title}>{title}</Text>
        {hint ? <Text style={styles.hint}>{hint}</Text> : null}
      </View>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { marginBottom: Spacing.xl },
  header: {
    flexDirection: 'row',
    alignItems: 'baseline',
    justifyContent: 'space-between',
    marginBottom: Spacing.md,
  },
  title: {
    fontFamily: Fonts.display.semibold,
    fontSize: FontSize.lg,
    color: Palette.ink,
  },
  hint: {
    fontFamily: Fonts.mono.regular,
    fontSize: FontSize.xs,
    color: Palette.inkLight,
  },
});
