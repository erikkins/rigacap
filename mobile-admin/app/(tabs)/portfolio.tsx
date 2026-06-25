/**
 * Portfolio — the live model portfolio: regime, total value, cash, positions.
 *
 * The /api/admin/model-portfolio shape isn't strongly typed on the client yet,
 * so fields are read defensively (multiple likely key names) and anything
 * missing renders as "—" rather than crashing.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { getCurrentRegime, getModelPortfolio } from '@/services/admin';
import StatCard from '@/components/StatCard';
import Section from '@/components/Section';
import { Fonts, FontSize, Palette, Radii, Regime, Spacing } from '@/constants/theme';

const pick = (obj: any, ...keys: string[]) => {
  for (const k of keys) if (obj?.[k] != null) return obj[k];
  return undefined;
};
const money = (n: any) => (typeof n === 'number' ? '$' + Math.round(n).toLocaleString('en-US') : '—');
const pct = (n: any) => (typeof n === 'number' ? `${n >= 0 ? '+' : ''}${n.toFixed(1)}%` : '—');

export default function Portfolio() {
  const [pf, setPf] = useState<any>(null);
  const [regime, setRegime] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    const [p, r] = await Promise.allSettled([getModelPortfolio(), getCurrentRegime()]);
    if (p.status === 'fulfilled') setPf(p.value);
    else setError('Could not load the portfolio.');
    if (r.status === 'fulfilled') setRegime(r.value);
    setLoading(false);
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

  const positions: any[] = pick(pf, 'positions', 'holdings', 'open_positions') || [];
  const totalValue = pick(pf, 'total_value', 'equity', 'portfolio_value', 'value');
  const cash = pick(pf, 'cash', 'cash_balance', 'available_cash');
  const totalReturn = pick(pf, 'total_return_pct', 'return_pct', 'pnl_pct');
  const regimeName = (pick(regime, 'regime', 'current_regime', 'name') || '').toString();
  const regimeColor = Regime[regimeName] || Palette.inkLight;

  return (
    <SafeAreaView style={styles.safe} edges={['bottom']}>
      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Palette.claret} />}
      >
        {regimeName ? (
          <View style={[styles.regime, { borderColor: regimeColor }]}>
            <View style={[styles.dot, { backgroundColor: regimeColor }]} />
            <Text style={styles.regimeText}>{regimeName.replace(/_/g, ' ')}</Text>
          </View>
        ) : null}

        <View style={styles.grid}>
          <StatCard label="Total value" value={money(totalValue)} />
          <StatCard label="Cash" value={money(cash)} />
          <StatCard
            label="Total return"
            value={pct(totalReturn)}
            tone={typeof totalReturn === 'number' ? (totalReturn >= 0 ? 'positive' : 'negative') : 'default'}
          />
          <StatCard label="Positions" value={positions.length || '—'} />
        </View>

        <Section title="Holdings" hint={positions.length ? `${positions.length} open` : ''}>
          {positions.length === 0 ? (
            <Text style={styles.empty}>Flat — 100% cash, or no position data exposed.</Text>
          ) : (
            positions.map((p, i) => {
              const sym = pick(p, 'symbol', 'ticker') || '?';
              const ret = pick(p, 'return_pct', 'pnl_pct', 'gain_pct', 'unrealized_pct');
              const val = pick(p, 'value', 'market_value', 'position_value');
              const shares = pick(p, 'shares', 'qty', 'quantity');
              return (
                <View key={`${sym}-${i}`} style={styles.posRow}>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.sym}>{sym}</Text>
                    <Text style={styles.posMeta}>
                      {shares != null ? `${shares} sh` : ''}
                      {val != null ? `${shares != null ? ' · ' : ''}${money(val)}` : ''}
                    </Text>
                  </View>
                  <Text
                    style={[
                      styles.posRet,
                      { color: typeof ret === 'number' ? (ret >= 0 ? Palette.positive : Palette.negative) : Palette.inkLight },
                    ]}
                  >
                    {pct(ret)}
                  </Text>
                </View>
              );
            })
          )}
        </Section>

        {error ? <Text style={styles.error}>{error}</Text> : null}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: Palette.paper },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: Palette.paper },
  content: { padding: Spacing.lg, paddingBottom: Spacing.xxl },
  regime: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    borderWidth: 1,
    borderRadius: Radii.pill,
    paddingHorizontal: Spacing.md,
    paddingVertical: 6,
    marginBottom: Spacing.lg,
  },
  dot: { width: 8, height: 8, borderRadius: 4, marginRight: Spacing.sm },
  regimeText: {
    fontFamily: Fonts.body.semibold,
    fontSize: FontSize.sm,
    color: Palette.ink,
    textTransform: 'capitalize',
    letterSpacing: 0.4,
  },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.md, marginBottom: Spacing.xl },
  posRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: Spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: Palette.rule,
  },
  sym: { fontFamily: Fonts.display.medium, fontSize: FontSize.lg, color: Palette.ink },
  posMeta: { fontFamily: Fonts.mono.regular, fontSize: FontSize.xs, color: Palette.inkMute, marginTop: 2 },
  posRet: { fontFamily: Fonts.mono.medium, fontSize: FontSize.md },
  empty: { fontFamily: Fonts.body.regular, fontSize: FontSize.md, color: Palette.inkMute },
  error: { fontFamily: Fonts.body.medium, fontSize: FontSize.sm, color: Palette.negative, marginTop: Spacing.md },
});
