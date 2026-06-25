/**
 * Portfolio — the live model book, mobilized (NOT a copy of the web table).
 *
 * Header cards: Total Value / Today / Cash / Total Return, then a mini row of
 * Trades / Win Rate / Realized / Unrealized. Each holding is a compact card:
 *   line 1  SYM .................... +10.8%   (since-entry %)
 *   line 2  Jun 15 · 9d · 1.8 sh ... +$407    (since-entry $)
 *   line 3  entry $X → $Y · HWM $Z
 *   line 4  today +8.6% · +$331               (live daily move, if available)
 *
 * Current price + daily change come from /api/quotes/live (real-time in market
 * hours, polled 30s), falling back to the model-portfolio's current_price.
 * Every line is single-row (numberOfLines={1}) so nothing wraps.
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
const price2 = (n: any) => (typeof n === 'number' ? '$' + n.toFixed(2) : '—');
const pct = (n: any) => (typeof n === 'number' ? `${n >= 0 ? '+' : ''}${n.toFixed(1)}%` : '—');
const toneColor = (n: any) =>
  typeof n === 'number' ? (n >= 0 ? Palette.positive : Palette.negative) : Palette.inkLight;
const shortDate = (iso: any) => {
  if (!iso) return undefined;
  try {
    return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  } catch {
    return undefined;
  }
};
const daysHeld = (iso: any) => {
  if (!iso) return undefined;
  try {
    const d = Math.floor((Date.now() - new Date(iso).getTime()) / 86400000);
    return d <= 0 ? '0d' : `${d}d`;
  } catch {
    return undefined;
  }
};

function MiniStat({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <View style={styles.mini}>
      <Text style={styles.miniLabel}>{label.toUpperCase()}</Text>
      <Text style={[styles.miniValue, tone ? { color: tone } : null]} numberOfLines={1}>
        {value}
      </Text>
    </View>
  );
}

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

  useEffect(() => {
    if (!symbolsKey) return;
    let active = true;
    const fetchQuotes = async () => {
      try {
        const q = await getLiveQuotes(symbolsKey.split(','));
        if (active) setQuotes(q);
      } catch {
        // best-effort — falls back to model-portfolio current_price
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
  const trades = pick(pf, 'total_trades', 'trades');
  const winRate = pick(pf, 'win_rate', 'winrate');
  const realized = pick(pf, 'realized_pnl', 'total_pnl', 'realized');
  const unrealized = pick(pf, 'unrealized_pnl', 'unrealized');
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

        {/* Headline cards */}
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

        {/* Trades / Win Rate / Realized / Unrealized */}
        <View style={styles.miniRow}>
          <MiniStat label="Trades" value={trades != null ? String(trades) : '—'} />
          <MiniStat label="Win rate" value={typeof winRate === 'number' ? `${Math.round(winRate)}%` : '—'} />
          <MiniStat label="Realized" value={signedMoney(realized)} tone={toneColor(realized)} />
          <MiniStat label="Unrealized" value={signedMoney(unrealized)} tone={toneColor(unrealized)} />
        </View>

        <Section title="Open positions" hint={positions.length ? `${positions.length}` : ''}>
          {positions.length === 0 ? (
            <Text style={styles.empty}>Flat — 100% cash, or no position data exposed.</Text>
          ) : (
            positions.map((p, i) => {
              const sym = pick(p, 'symbol', 'ticker') || '?';
              const shares = pick(p, 'shares', 'qty', 'quantity');
              const entry = pick(p, 'entry_price', 'cost_basis', 'avg_price');
              const hwm = pick(p, 'highest_price', 'hwm', 'high_water_mark');
              const q = quotes[sym];
              const cur = q?.price ?? pick(p, 'current_price', 'price');
              const plPct =
                typeof entry === 'number' && entry > 0 && typeof cur === 'number'
                  ? (cur / entry - 1) * 100
                  : pick(p, 'pnl_pct', 'return_pct');
              const plDol =
                typeof entry === 'number' && typeof cur === 'number' && typeof shares === 'number'
                  ? (cur - entry) * shares
                  : pick(p, 'pnl_dollars', 'unrealized_pnl');
              const todayPct = q?.change_pct;
              const todayDol = q && typeof shares === 'number' ? q.change * shares : undefined;
              const meta = [shortDate(pick(p, 'entry_date', 'entered_at', 'opened_at')), daysHeld(pick(p, 'entry_date', 'entered_at', 'opened_at')), shares != null ? `${shares} sh` : null]
                .filter(Boolean)
                .join(' · ');
              return (
                <View key={`${sym}-${i}`} style={styles.posRow}>
                  <View style={styles.posLine}>
                    <Text style={styles.sym}>{sym}</Text>
                    <Text style={[styles.plPct, { color: toneColor(plPct) }]}>{pct(plPct)}</Text>
                  </View>
                  <View style={styles.posLine}>
                    <Text style={styles.posMeta} numberOfLines={1}>
                      {meta}
                    </Text>
                    <Text style={[styles.plDol, { color: toneColor(plDol) }]}>{signedMoney(plDol)}</Text>
                  </View>
                  <Text style={styles.posPrices} numberOfLines={1}>
                    {`entry ${price2(entry)} → ${price2(cur)}`}
                    {hwm != null ? ` · HWM ${price2(hwm)}` : ''}
                  </Text>
                  {q ? (
                    <Text style={[styles.posToday, { color: toneColor(todayPct) }]} numberOfLines={1}>
                      {`today ${pct(todayPct)}`}
                      {todayDol != null ? ` · ${signedMoney(todayDol)}` : ''}
                    </Text>
                  ) : null}
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
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.md, marginBottom: Spacing.md },
  miniRow: {
    flexDirection: 'row',
    backgroundColor: Palette.paperCard,
    borderWidth: 1,
    borderColor: Palette.rule,
    borderRadius: Radii.lg,
    paddingVertical: Spacing.md,
    marginBottom: Spacing.xl,
  },
  mini: { flex: 1, alignItems: 'center', paddingHorizontal: 2 },
  miniLabel: { fontFamily: Fonts.body.medium, fontSize: 9, letterSpacing: 0.5, color: Palette.inkLight },
  miniValue: { fontFamily: Fonts.display.semibold, fontSize: FontSize.md, color: Palette.ink, marginTop: 3 },
  posRow: { paddingVertical: Spacing.sm, borderBottomWidth: 1, borderBottomColor: Palette.rule },
  posLine: { flexDirection: 'row', alignItems: 'baseline', justifyContent: 'space-between' },
  sym: { fontFamily: Fonts.display.medium, fontSize: FontSize.lg, color: Palette.ink },
  plPct: { fontFamily: Fonts.mono.medium, fontSize: FontSize.md },
  posMeta: { fontFamily: Fonts.mono.regular, fontSize: FontSize.xs, color: Palette.inkMute, marginTop: 2, flex: 1, marginRight: Spacing.sm },
  plDol: { fontFamily: Fonts.mono.regular, fontSize: FontSize.xs },
  posPrices: { fontFamily: Fonts.mono.regular, fontSize: FontSize.xs, color: Palette.inkLight, marginTop: 3 },
  posToday: { fontFamily: Fonts.mono.regular, fontSize: FontSize.xs, marginTop: 2 },
  empty: { fontFamily: Fonts.body.regular, fontSize: FontSize.md, color: Palette.inkMute },
  error: { fontFamily: Fonts.body.medium, fontSize: FontSize.sm, color: Palette.negative, marginTop: Spacing.md },
});
