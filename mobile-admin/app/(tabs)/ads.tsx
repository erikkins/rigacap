/**
 * Ads — Google Ads spend/clicks/conversions at a glance.
 *
 * MILESTONE 2: the backend /api/admin/ads/summary endpoint isn't built yet
 * (needs server-side Google Ads API auth — developer token + OAuth refresh
 * token; creds must never live in the app). Until that ships, getAdsSummary()
 * returns null on 404 and we render a "not configured" state. The full layout
 * is already here so wiring the endpoint lights it up with no UI work.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { AdsSummary, getAdsSummary } from '@/services/admin';
import StatCard from '@/components/StatCard';
import Section from '@/components/Section';
import { Fonts, FontSize, Palette, Radii, Spacing } from '@/constants/theme';

const money = (n: any) => (typeof n === 'number' ? '$' + n.toFixed(2) : '—');
const int = (n: any) => (typeof n === 'number' ? n.toLocaleString('en-US') : '—');

export default function Ads() {
  const [ads, setAds] = useState<AdsSummary | null>(null);
  const [notConfigured, setNotConfigured] = useState(false);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const data = await getAdsSummary();
      if (data === null) {
        setNotConfigured(true);
      } else {
        setAds(data);
        setNotConfigured(false);
      }
    } catch {
      setError('Could not load ad stats.');
    } finally {
      setLoading(false);
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

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color={Palette.claret} />
      </View>
    );
  }

  return (
    <SafeAreaView style={styles.safe} edges={['bottom']}>
      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Palette.claret} />}
      >
        {notConfigured ? (
          <View style={styles.placeholder}>
            <Text style={styles.phTitle}>Ads API not connected yet</Text>
            <Text style={styles.phBody}>
              This tab lights up once the backend Google Ads endpoint
              (<Text style={styles.mono}>/api/admin/ads/summary</Text>) is wired with a
              developer token + OAuth refresh token. The layout is ready.
            </Text>
          </View>
        ) : (
          <>
            <Section title="Spend" hint={ads?.date_range || 'last 14 days'}>
              <View style={styles.grid}>
                <StatCard label="Spend" value={money(ads?.spend)} />
                <StatCard label="Clicks" value={int(ads?.clicks)} />
                <StatCard label="Impressions" value={int(ads?.impressions)} />
                <StatCard label="Avg CPC" value={money(ads?.cpc)} />
                <StatCard
                  label="Conversions"
                  value={int(ads?.conversions)}
                  tone={typeof ads?.conversions === 'number' && ads.conversions > 0 ? 'positive' : 'default'}
                />
              </View>
            </Section>

            {ads?.campaigns?.length ? (
              <Section title="Campaigns">
                {ads.campaigns.map((c, i) => (
                  <View key={i} style={styles.campRow}>
                    <Text style={styles.campName} numberOfLines={1}>
                      {c.name || c.campaign || `Campaign ${i + 1}`}
                    </Text>
                    <Text style={styles.campSpend}>{money(c.spend)}</Text>
                  </View>
                ))}
              </Section>
            ) : null}
          </>
        )}

        {error ? <Text style={styles.error}>{error}</Text> : null}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: Palette.paper },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: Palette.paper },
  content: { padding: Spacing.lg, paddingBottom: Spacing.xxl },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.md },
  placeholder: {
    backgroundColor: Palette.paperCard,
    borderWidth: 1,
    borderColor: Palette.rule,
    borderRadius: Radii.lg,
    padding: Spacing.lg,
    marginTop: Spacing.xl,
  },
  phTitle: { fontFamily: Fonts.display.semibold, fontSize: FontSize.lg, color: Palette.ink, marginBottom: Spacing.sm },
  phBody: { fontFamily: Fonts.body.regular, fontSize: FontSize.sm, color: Palette.inkMute, lineHeight: 20 },
  mono: { fontFamily: Fonts.mono.regular, fontSize: FontSize.xs, color: Palette.claret },
  campRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: Spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: Palette.rule,
  },
  campName: { fontFamily: Fonts.body.medium, fontSize: FontSize.sm, color: Palette.ink, flex: 1, marginRight: Spacing.md },
  campSpend: { fontFamily: Fonts.mono.medium, fontSize: FontSize.sm, color: Palette.ink },
  error: { fontFamily: Fonts.body.medium, fontSize: FontSize.sm, color: Palette.negative, marginTop: Spacing.md },
});
