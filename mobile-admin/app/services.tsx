/**
 * Service detail — everything we're connected to + individual statuses.
 * Pushed over the tabs from the Glance health banner. Pull to refresh.
 *
 * /service-status returns { overall_status, services{}, metrics{} } where each
 * services entry is heterogeneous (database: status+latency; market_data: nested
 * alpaca/yfinance health; stripe; scanner: signals_today…) but always has a
 * `status`. Rendered generically: status pill + scalar fields + nested statuses.
 */

import React, { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { ServiceStatus, getServiceStatus } from '@/services/admin';
import { Fonts, FontSize, Palette, Radii, Spacing } from '@/constants/theme';

function statusColor(s: any): string {
  const x = String(s ?? '').toLowerCase();
  if (x === 'ok' || x === 'up' || x === 'green' || x.includes('healthy')) return Palette.positive;
  if (x.includes('error') || x === 'red' || x.includes('down') || x.includes('fail')) return Palette.negative;
  if (x.includes('warn') || x.includes('degrad') || x === 'yellow' || x.includes('stale')) return Palette.yellow;
  return Palette.inkLight; // unknown / not_configured
}

const prettyName = (k: string) => k.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
const isScalar = (v: any) => v == null || ['string', 'number', 'boolean'].includes(typeof v);
const fmt = (v: any) => (v === null || v === undefined ? '—' : String(v));

function StatusPill({ status }: { status: any }) {
  const c = statusColor(status);
  return (
    <View style={[styles.pill, { borderColor: c }]}>
      <View style={[styles.pillDot, { backgroundColor: c }]} />
      <Text style={[styles.pillText, { color: c }]}>{fmt(status).toUpperCase()}</Text>
    </View>
  );
}

function ServiceCard({ name, val }: { name: string; val: any }) {
  const obj = val && typeof val === 'object' ? val : { status: val };
  const status = obj.status;
  const scalars = Object.entries(obj).filter(([k, v]) => k !== 'status' && isScalar(v));
  const nested = Object.entries(obj).filter(([, v]) => v && typeof v === 'object');

  return (
    <View style={styles.card}>
      <View style={styles.cardHeader}>
        <Text style={styles.cardTitle}>{prettyName(name)}</Text>
        <StatusPill status={status} />
      </View>
      {scalars.map(([k, v]) => (
        <View key={k} style={styles.kv}>
          <Text style={styles.k}>{prettyName(k)}</Text>
          <Text style={styles.v} numberOfLines={1}>
            {fmt(v)}
          </Text>
        </View>
      ))}
      {nested.map(([k, v]: [string, any]) => (
        <View key={k} style={styles.nested}>
          <View style={styles.kv}>
            <Text style={styles.k}>{prettyName(k)}</Text>
            {'status' in (v || {}) ? <StatusPill status={v.status} /> : null}
          </View>
          {Object.entries(v || {})
            .filter(([sk, sv]) => sk !== 'status' && isScalar(sv))
            .map(([sk, sv]) => (
              <View key={sk} style={[styles.kv, styles.kvSub]}>
                <Text style={[styles.k, styles.kSub]}>{prettyName(sk)}</Text>
                <Text style={[styles.v, styles.kSub]} numberOfLines={1}>
                  {fmt(sv)}
                </Text>
              </View>
            ))}
        </View>
      ))}
    </View>
  );
}

export default function Services() {
  const router = useRouter();
  const [svc, setSvc] = useState<ServiceStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setSvc(await getServiceStatus());
    } catch {
      setError('Could not load service status.');
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

  const services = svc?.services || {};
  const metrics = svc?.metrics || {};

  return (
    <SafeAreaView style={styles.safe} edges={['top', 'bottom']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} hitSlop={12} style={styles.back}>
          <Ionicons name="chevron-back" size={24} color={Palette.ink} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Service status</Text>
        {svc ? <StatusPill status={svc.overall_status} /> : <View style={{ width: 60 }} />}
      </View>

      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator size="large" color={Palette.claret} />
        </View>
      ) : (
        <ScrollView
          contentContainerStyle={styles.content}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Palette.claret} />}
        >
          {error ? <Text style={styles.error}>{error}</Text> : null}

          {Object.entries(services).map(([name, val]) => (
            <ServiceCard key={name} name={name} val={val} />
          ))}

          {Object.keys(metrics).length ? (
            <View style={styles.card}>
              <Text style={styles.cardTitle}>Metrics</Text>
              {Object.entries(metrics).map(([k, v]) => (
                <View key={k} style={styles.kv}>
                  <Text style={styles.k}>{prettyName(k)}</Text>
                  <Text style={styles.v} numberOfLines={1}>
                    {isScalar(v) ? fmt(v) : JSON.stringify(v)}
                  </Text>
                </View>
              ))}
            </View>
          ) : null}

          {!Object.keys(services).length && !error ? (
            <Text style={styles.empty}>No services reported.</Text>
          ) : null}
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: Palette.paper },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: Palette.rule,
  },
  back: { width: 40 },
  headerTitle: { fontFamily: Fonts.display.semibold, fontSize: FontSize.lg, color: Palette.ink },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  content: { padding: Spacing.lg, paddingBottom: Spacing.xxl },
  card: {
    backgroundColor: Palette.paperCard,
    borderWidth: 1,
    borderColor: Palette.rule,
    borderRadius: Radii.lg,
    padding: Spacing.md,
    marginBottom: Spacing.md,
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: Spacing.sm,
  },
  cardTitle: { fontFamily: Fonts.display.semibold, fontSize: FontSize.md, color: Palette.ink },
  kv: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 3 },
  kvSub: { paddingVertical: 1 },
  k: { fontFamily: Fonts.body.regular, fontSize: FontSize.sm, color: Palette.inkMute, flexShrink: 0 },
  kSub: { fontSize: FontSize.xs },
  v: {
    fontFamily: Fonts.mono.regular,
    fontSize: FontSize.xs,
    color: Palette.ink,
    flex: 1,
    textAlign: 'right',
    marginLeft: Spacing.md,
  },
  nested: {
    borderTopWidth: 1,
    borderTopColor: Palette.rule,
    marginTop: Spacing.sm,
    paddingTop: Spacing.sm,
  },
  pill: {
    flexDirection: 'row',
    alignItems: 'center',
    borderWidth: 1,
    borderRadius: Radii.pill,
    paddingHorizontal: 8,
    paddingVertical: 3,
  },
  pillDot: { width: 7, height: 7, borderRadius: 4, marginRight: 5 },
  pillText: { fontFamily: Fonts.body.semibold, fontSize: 10, letterSpacing: 0.5 },
  error: { fontFamily: Fonts.body.medium, fontSize: FontSize.sm, color: Palette.negative, marginBottom: Spacing.md },
  empty: { fontFamily: Fonts.body.regular, fontSize: FontSize.md, color: Palette.inkMute, textAlign: 'center', marginTop: Spacing.xxl },
});
