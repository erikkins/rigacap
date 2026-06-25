/**
 * Portfolio — the live model portfolio: regime, value, cash, positions, and
 * live DAILY change (today's +/- $ and %) from /api/quotes/live, polled every
 * 30s like the subscriber app. Since-entry return is kept as a secondary read.
 *
 * The /api/admin/model-portfolio shape is read defensively (multiple likely key
 * names); missing fields render as "—" rather than crashing.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LiveQuote, getCurrentRegime, getLiveQuotes, getModelPortfolio } from '@/services/admin';
import StatCard from '@/components/StatCard';
import Section from '@/components/Section';
import { Fonts, FontSize, Palette, Radii, Regime, Spacing } from '@/constants/theme';

const pick = (obj: any, ...keys: string[]) => {
  for (const k of keys) if (obj?.[k] != null) return obj[k];
  return undefined;
};
const money = (n: any) => (typeof n === 'number' ? '$' + Math.round(n).toLocaleString('en-US') : '—');
const signedMoney = (n: any) =>
  typeof n === 'number' ? `${n >= 0 ? '+' : '−'}$${Math.abs(Math.round(n)).toLocaleString('en-US')}` : '—';
const pct = (n: any) => (typeof n === 'number' ? `${n >= 0 ? '+' : ''}${n.toFixed(1)}%` : '—');
const heldFor = (iso: any) => {
  if (!iso) return undefined;
  try {
    const d = Math.floor((Date.now() - new Date(iso).getTime()) / 86400000);
    return d <= 0 ? 'today' : `held ${d}d`;
  } catch {
    return undefined;
  }
};
const toneColor = (n: any) =>
  typeof n === 'number' ? (n >= 0 ? Palette.positive : Palette.negative) : Palette.inkLight;

export default function Portfolio() {
  const [pf, setPf] = useState<any>(null);
  const [regime, setRegime] = useState<any>(null);
  const [quotes, setQuotes] = useState<Record<string, LiveQuote>>({});
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

  const positions: any[] = pick(pf, 'open_positions', 'positions', 'holdings') || [];
  const symbolsKey = positions
    .map((p) => pick(p, 'symbol', 'ticker'))
    .filter(Boolean)
    .join(',');

  // Poll live quotes for the held symbols every 30s (matches the subscriber app).
  useEffect(() => {
    if (!symbolsKey) return;
    let active = true;
    const fetchQuotes = async () => {
      try {
        const q = await getLiveQuotes(symbolsKey.split(','));
        if (active) setQuotes(q);
      } catch {
        // quotes are best-effort — fall back to since-entry data
      }
    };
    fetchQuotes();
    const id = setInterval(fetchQuotes, 30000);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, [symbolsKey]);

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

  const totalValue = pick(pf, 'total_value', 'equity', 'portfolio_value', 'value');
  const cash = pick(pf, 'current_cash', 'cash', 'cash_balance', 'available_cash');
  const totalReturn = pick(pf, 'total_return_pct', 'return_pct', 'pnl_pct');
  const regimeName = (pick(regime, 'regime', 'current_regime', 'name') || '').toString();
  const regimeColor = Regime[regimeName] || Palette.inkLight;

  // Portfolio-level daily change from live quotes: Σ shares·change vs Σ shares·prev_close.
  let dayDollar = 0;
  let prevValue = 0;
  let haveQuotes = false;
  for (const p of positions) {
    const sym = pick(p, 'symbol', 'ticker');
    const shares = pick(p, 'shares', 'qty', 'quantity');
    const q = sym ? quotes[sym] : undefined;
    if (q && typeof shares === 'number') {
      dayDollar += q.change * shares;
      prevValue += (q.prev_close ?? q.price - q.change) * shares;
      haveQuotes = true;
    }
  }
  const dayPct = haveQuotes && prevValue > 0 ? (dayDollar / prevValue) * 100 : undefined;

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
          <StatCard
            label="Today"
            value={haveQuotes ? signedMoney(dayDollar) : '—'}
            sub={haveQuotes ? pct(dayPct) : 'live'}
            tone={haveQuotes ? (dayDollar >= 0 ? 'positive' : 'negative') : 'default'}
          />
          <StatCard label="Cash" value={money(cash)} />
          <StatCard
            label="Total return"
            value={pct(totalReturn)}
            tone={typeof totalReturn === 'number' ? (totalReturn >= 0 ? 'positive' : 'negative') : 'default'}
          />
        </View>

        <Section title="Holdings" hint={positions.length ? `${positions.length} open · live` : ''}>
          {positions.length === 0 ? (
            <Text style={styles.empty}>Flat — 100% cash, or no position data exposed.</Text>
          ) : (
            positions.map((p, i) => {
              const sym = pick(p, 'symbol', 'ticker') || '?';
              const shares = pick(p, 'shares', 'qty', 'quantity');
              const entry = pick(p, 'entry_price', 'cost_basis', 'avg_price');
              const held = heldFor(pick(p, 'entry_date', 'entered_at', 'opened_at'));
              const q = quotes[sym];
              const cur = q?.price ?? pick(p, 'current_price', 'price');
              const val =
                typeof cur === 'number' && typeof shares === 'number'
                  ? cur * shares
                  : pick(p, 'value', 'market_value', 'position_value');
              // Since-entry return — prefer a live recompute from entry→now, else the API's pnl_pct.
              const sinceEntry =
                typeof entry === 'number' && entry > 0 && typeof cur === 'number'
                  ? (cur / entry - 1) * 100
                  : pick(p, 'pnl_pct', 'return_pct', 'gain_pct', 'unrealized_pct');
              const sinceEntryDol =
                typeof entry === 'number' && typeof cur === 'number' && typeof shares === 'number'
                  ? (cur - entry) * shares
                  : pick(p, 'pnl_dollars', 'unrealized_pnl');
              const todayPct = q?.change_pct;
              const todayDol = q && typeof shares === 'number' ? q.change * shares : undefined;
              return (
                <View key={`${sym}-${i}`} style={styles.posRow}>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.sym}>{sym}</Text>
                    <Text style={styles.posMeta}>
                      {shares != null ? `${shares} sh` : ''}
                      {val != null ? `${shares != null ? ' · ' : ''}${money(val)}` : ''}
                      {held ? ` · ${held}` : ''}
                    </Text>
                    <Text style={styles.posPrices}>
                      {typeof entry === 'number' ? `entry $${entry.toFixed(2)}` : ''}
                      {typeof cur === 'number' ? ` → $${cur.toFixed(2)}` : ''}
                    </Text>
                  </View>
                  <View style={styles.posRight}>
                    <Text style={[styles.posReturn, { color: toneColor(sinceEntry) }]}>{pct(sinceEntry)}</Text>
                    <Text style={styles.posReturnLabel}>
                      {sinceEntryDol != null ? `${signedMoney(sinceEntryDol)} since entry` : 'since entry'}
                    </Text>
                    <Text style={[styles.posToday, { color: toneColor(todayPct) }]}>
                      {pct(todayPct)}
                      {todayDol != null ? ` · ${signedMoney(todayDol)}` : ''} today
                    </Text>
                  </View>
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
  posPrices: { fontFamily: Fonts.mono.regular, fontSize: FontSize.xs, color: Palette.inkLight, marginTop: 1 },
  posRight: { alignItems: 'flex-end', marginLeft: Spacing.sm },
  posReturn: { fontFamily: Fonts.mono.medium, fontSize: FontSize.lg },
  posReturnLabel: { fontFamily: Fonts.mono.regular, fontSize: 10, color: Palette.inkLight, marginTop: 1 },
  posToday: { fontFamily: Fonts.mono.regular, fontSize: FontSize.xs, marginTop: 3 },
  empty: { fontFamily: Fonts.body.regular, fontSize: FontSize.md, color: Palette.inkMute },
  error: { fontFamily: Fonts.body.medium, fontSize: FontSize.sm, color: Palette.negative, marginTop: Spacing.md },
});
