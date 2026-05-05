/**
 * Settings screen — account info, subscription, notification prefs, logout.
 */

import React from 'react';
import {
  Alert,
  Linking,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { useAuth } from '@/hooks/useAuth';
import { Fonts, FontSize, Palette, Radii, Spacing } from '@/constants/theme';

export default function SettingsScreen() {
  const { user, logout } = useAuth();

  const handleLogout = () => {
    Alert.alert('Sign Out', 'Are you sure you want to sign out?', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Sign Out', style: 'destructive', onPress: logout },
    ]);
  };

  const sub = user?.subscription;

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
    >
      {/* Account */}
      <Text style={styles.sectionTitle}>Account</Text>
      <View style={styles.card}>
        <Row label="Email" value={user?.email || '—'} />
        <Row label="Name" value={user?.name || '—'} />
      </View>

      {/* Subscription */}
      <Text style={styles.sectionTitle}>Subscription</Text>
      <View style={styles.card}>
        <Row
          label="Status"
          value={sub?.status?.toUpperCase() || 'NONE'}
          valueColor={sub?.is_valid ? Palette.positive : Palette.negative}
        />
        {sub?.days_remaining != null && (
          <Row label="Days Remaining" value={`${sub.days_remaining}`} />
        )}
        <Pressable
          style={styles.linkRow}
          onPress={() => Linking.openURL('https://rigacap.com/#pricing')}
        >
          <Text style={styles.linkText}>Manage Subscription</Text>
          <Text style={styles.arrow}>→</Text>
        </Pressable>
      </View>

      {/* Links */}
      <Text style={styles.sectionTitle}>About</Text>
      <View style={styles.card}>
        <Pressable
          style={styles.linkRow}
          onPress={() => Linking.openURL('https://rigacap.com/privacy')}
        >
          <Text style={styles.linkText}>Privacy Policy</Text>
          <Text style={styles.arrow}>→</Text>
        </Pressable>
        <Pressable
          style={styles.linkRow}
          onPress={() => Linking.openURL('https://rigacap.com/terms')}
        >
          <Text style={styles.linkText}>Terms of Service</Text>
          <Text style={styles.arrow}>→</Text>
        </Pressable>
        <Pressable
          style={styles.linkRow}
          onPress={() => Linking.openURL('https://rigacap.com/contact')}
        >
          <Text style={styles.linkText}>Contact Us</Text>
          <Text style={styles.arrow}>→</Text>
        </Pressable>
      </View>

      {/* Disclaimer */}
      <View style={styles.disclaimerCard}>
        <Text style={styles.disclaimerTitle}>Disclaimer</Text>
        <Text style={styles.disclaimerText}>
          RigaCap provides trading signals only. We are not a broker and do not
          execute trades on your behalf. All signals should be considered
          informational — not financial advice. Always do your own research
          before making investment decisions.
        </Text>
      </View>

      {/* Logout */}
      <Pressable style={styles.logoutButton} onPress={handleLogout}>
        <Text style={styles.logoutText}>Sign Out</Text>
      </Pressable>

      <Text style={styles.version}>RigaCap v1.0.0</Text>
    </ScrollView>
  );
}

function Row({
  label,
  value,
  valueColor,
}: {
  label: string;
  value: string;
  valueColor?: string;
}) {
  return (
    <View style={styles.row}>
      <Text style={styles.rowLabel}>{label}</Text>
      <Text style={[styles.rowValue, valueColor ? { color: valueColor } : {}]}>
        {value}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Palette.paper,
  },
  content: {
    padding: Spacing.md,
    paddingBottom: Spacing.xl * 2,
    gap: Spacing.sm,
  },
  sectionTitle: {
    color: Palette.inkLight,
    fontSize: FontSize.xs,
    fontFamily: Fonts.body.medium,
    textTransform: 'uppercase',
    letterSpacing: 1.2,
    marginTop: Spacing.md,
    marginBottom: Spacing.xs,
  },
  card: {
    backgroundColor: Palette.paperCard,
    borderRadius: Radii.md,
    borderWidth: 1,
    borderColor: Palette.rule,
    overflow: 'hidden',
  },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: Spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: Palette.rule,
  },
  rowLabel: {
    color: Palette.inkMute,
    fontSize: FontSize.md,
    fontFamily: Fonts.body.regular,
  },
  rowValue: {
    color: Palette.ink,
    fontSize: FontSize.md,
    fontFamily: Fonts.body.medium,
  },
  linkRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: Spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: Palette.rule,
  },
  linkText: {
    color: Palette.claret,
    fontSize: FontSize.md,
    fontFamily: Fonts.body.medium,
  },
  arrow: {
    color: Palette.inkLight,
    fontSize: FontSize.md,
  },
  disclaimerCard: {
    backgroundColor: Palette.paperDeep,
    borderRadius: Radii.md,
    borderWidth: 1,
    borderColor: Palette.rule,
    padding: Spacing.md,
    marginTop: Spacing.md,
  },
  disclaimerTitle: {
    color: Palette.ink,
    fontSize: FontSize.sm,
    fontFamily: Fonts.display.semibold,
    marginBottom: Spacing.xs,
  },
  disclaimerText: {
    color: Palette.inkMute,
    fontSize: FontSize.xs,
    fontFamily: Fonts.body.regular,
    fontStyle: 'italic',
    lineHeight: 18,
  },
  logoutButton: {
    backgroundColor: 'transparent',
    borderRadius: Radii.md,
    borderWidth: 1,
    borderColor: Palette.negative,
    padding: Spacing.md,
    alignItems: 'center',
    marginTop: Spacing.lg,
  },
  logoutText: {
    color: Palette.negative,
    fontSize: FontSize.md,
    fontFamily: Fonts.body.semibold,
    letterSpacing: 0.4,
  },
  version: {
    color: Palette.inkLight,
    fontSize: FontSize.xs,
    fontFamily: Fonts.body.regular,
    textAlign: 'center',
    marginTop: Spacing.md,
  },
});
