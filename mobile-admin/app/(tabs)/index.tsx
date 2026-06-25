/**
 * Glance — the "is everything OK + how are we growing" home screen.
 * Pull to refresh. Pipeline-health banner up top, then growth + founding.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import {
  AdminStats,
  FoundingStatus,
  ServiceStatus,
  getFoundingStatus,
  getServiceStatus,
  getStats,
} from '@/services/admin';
import StatCard from '@/components/StatCard';
import Section from '@/components/Section';
import { Fonts, FontSize, Palette, Radii, Spacing } from '@/constants/theme';

const money = (n: number) =>
  '$' + Math.round(n).toLocaleString('en-US');

export default function Glance() {
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [svc, setSvc] = useState<ServiceStatus | null>(null);
  const [founding, setFounding] = useState<FoundingStatus | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    const [s, v, f] = await Promise.allSettled([
      getStats(),
      getServiceStatus(),
      getFoundingStatus(),
    ]);
    if (s.status === 'fulfilled') setStats(s.value);
    if (v.status === 'fulfilled') setSvc(v.value);
    if (f.status === 'fulfilled') setFounding(f.value);
    if (s.status === 'rejected' && v.status === 'rejected') {
      setError('Could not reach the server.');
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  }, [load]);

  const health = (svc?.overall_status || 'unknown').toLowerCase();
  const healthTone =
    health.includes('ok') || health.includes('healthy') || health.includes('up')
      ? 'ok'
      : health.includes('degrad') || health.includes('warn')
      ? 'warn'
      : health === 'unknown'
      ? 'unknown'
      : 'down';

  const bannerColor = {
    ok: Palette.positive,
    warn: Palette.yellow,
    down: Palette.negative,
    unknown: Palette.inkLight,
  }[healthTone];

  const seatsRemaining =
    founding?.seats_remaining ??
    (founding?.seats_total != null && founding?.seats_taken != null
      ? founding.seats_total - founding.seats_taken
      : undefined);

  return (
    <SafeAreaView style={styles.safe} edges={['bottom']}>
      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Palette.claret} />}
      >
        {/* Pipeline health banner */}
        <View style={[styles.banner, { borderColor: bannerColor }]}>
          <View style={[styles.dot, { backgroundColor: bannerColor }]} />
          <View style={{ flex: 1 }}>
            <Text style={styles.bannerTitle}>
              {healthTone === 'ok'
                ? 'All systems nominal'
                : healthTone === 'warn'
                ? 'Degraded — check services'
                : healthTone === 'down'
                ? 'Something is down'
                : 'Status unknown'}
            </Text>
            <Text style={styles.bannerSub}>
              {svc ? `overall_status: ${svc.overall_status}` : 'Pull to refresh'}
            </Text>
          </View>
        </View>

        {error ? <Text style={styles.error}>{error}</Text> : null}

        {/* Growth */}
        <Section title="Growth" hint={stats ? `MRR ${money(stats.mrr)}` : ''}>
          <View style={styles.grid}>
            <StatCard label="New today" value={stats?.new_users_today ?? '—'} tone="positive" />
            <StatCard label="New this week" value={stats?.new_users_week ?? '—'} />
            <StatCard label="Paid subs" value={stats?.paid_subscribers ?? '—'} />
            <StatCard label="Active trials" value={stats?.active_trials ?? '—'} />
            <StatCard label="Total users" value={stats?.total_users ?? '—'} />
            <StatCard
              label="MRR"
              value={stats ? money(stats.mrr) : '—'}
              tone="positive"
            />
          </View>
        </Section>

        {/* Founding seats */}
        {founding ? (
          <Section title="Founding seats">
            <View style={styles.grid}>
              <StatCard
                label="Seats left"
                value={seatsRemaining ?? '—'}
                tone={seatsRemaining != null && seatsRemaining <= 40 ? 'warning' : 'default'}
                sub={founding.is_open === false ? 'Closed' : 'Open'}
              />
              <StatCard
                label="Taken"
                value={founding.seats_taken ?? '—'}
                sub={founding.seats_total ? `of ${founding.seats_total}` : undefined}
              />
            </View>
          </Section>
        ) : null}

        <Text style={styles.footnote}>Pull down to refresh · data is live from the API</Text>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: Palette.paper },
  content: { padding: Spacing.lg, paddingBottom: Spacing.xxl },
  banner: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Palette.paperCard,
    borderWidth: 1,
    borderLeftWidth: 4,
    borderRadius: Radii.lg,
    padding: Spacing.md,
    marginBottom: Spacing.xl,
  },
  dot: { width: 10, height: 10, borderRadius: 5, marginRight: Spacing.md },
  bannerTitle: { fontFamily: Fonts.display.medium, fontSize: FontSize.md, color: Palette.ink },
  bannerSub: { fontFamily: Fonts.mono.regular, fontSize: FontSize.xs, color: Palette.inkLight, marginTop: 2 },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.md },
  error: { fontFamily: Fonts.body.medium, fontSize: FontSize.sm, color: Palette.negative, marginBottom: Spacing.md },
  footnote: {
    fontFamily: Fonts.body.regular,
    fontSize: FontSize.xs,
    color: Palette.inkLight,
    textAlign: 'center',
    marginTop: Spacing.md,
  },
});
