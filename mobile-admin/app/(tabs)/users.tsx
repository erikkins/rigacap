/**
 * Users — searchable-ish list of accounts, newest first, with founder/trial/
 * paid badges. Sign-out lives at the bottom.
 */

import React, { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  RefreshControl,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { UserSummary, getUsers } from '@/services/admin';
import { useAuth } from '@/hooks/useAuth';
import { Fonts, FontSize, Palette, Radii, Spacing } from '@/constants/theme';

function Badge({ text, color }: { text: string; color: string }) {
  return (
    <View style={[styles.badge, { borderColor: color }]}>
      <Text style={[styles.badgeText, { color }]}>{text}</Text>
    </View>
  );
}

function relDate(iso: string): string {
  try {
    const d = new Date(iso).getTime();
    const days = Math.floor((Date.now() - d) / 86400000);
    if (days <= 0) return 'today';
    if (days === 1) return 'yesterday';
    if (days < 30) return `${days}d ago`;
    return `${Math.floor(days / 30)}mo ago`;
  } catch {
    return iso;
  }
}

function Row({ u }: { u: UserSummary }) {
  const status = (u.subscription_status || '').toLowerCase();
  return (
    <View style={styles.row}>
      <View style={{ flex: 1 }}>
        <View style={styles.rowTop}>
          <Text style={styles.email} numberOfLines={1}>
            {u.email}
          </Text>
          {u.is_founding ? <Badge text="★ FOUNDER" color={Palette.claret} /> : null}
        </View>
        <Text style={styles.meta}>
          {u.name ? `${u.name} · ` : ''}joined {relDate(u.created_at)}
          {u.last_login ? ` · seen ${relDate(u.last_login)}` : ' · never logged in'}
        </Text>
      </View>
      <View style={styles.rowRight}>
        {!u.is_active ? (
          <Badge text="DISABLED" color={Palette.negative} />
        ) : status.includes('active') || status.includes('paid') ? (
          <Badge text="PAID" color={Palette.positive} />
        ) : status.includes('trial') ? (
          <Badge
            text={u.trial_days_remaining != null ? `TRIAL ${u.trial_days_remaining}d` : 'TRIAL'}
            color={Palette.yellow}
          />
        ) : (
          <Badge text={status ? status.toUpperCase() : 'FREE'} color={Palette.inkLight} />
        )}
      </View>
    </View>
  );
}

export default function Users() {
  const { logout } = useAuth();
  const [users, setUsers] = useState<UserSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const data = await getUsers(1, 100);
      setUsers(data.users);
      setTotal(data.total);
    } catch {
      setError('Could not load users.');
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
      <FlatList
        data={users}
        keyExtractor={(u) => u.id}
        renderItem={({ item }) => <Row u={item} />}
        ItemSeparatorComponent={() => <View style={styles.sep} />}
        contentContainerStyle={styles.list}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Palette.claret} />}
        ListHeaderComponent={
          <Text style={styles.count}>
            {total.toLocaleString()} accounts · showing {users.length}
          </Text>
        }
        ListEmptyComponent={<Text style={styles.empty}>{error || 'No users yet.'}</Text>}
        ListFooterComponent={
          <TouchableOpacity style={styles.signout} onPress={logout}>
            <Text style={styles.signoutText}>Sign out</Text>
          </TouchableOpacity>
        }
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: Palette.paper },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: Palette.paper },
  list: { padding: Spacing.lg },
  count: {
    fontFamily: Fonts.mono.regular,
    fontSize: FontSize.xs,
    color: Palette.inkLight,
    marginBottom: Spacing.md,
  },
  row: { flexDirection: 'row', alignItems: 'center', paddingVertical: Spacing.sm },
  rowTop: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm },
  rowRight: { marginLeft: Spacing.sm },
  email: { fontFamily: Fonts.body.semibold, fontSize: FontSize.md, color: Palette.ink, flexShrink: 1 },
  meta: { fontFamily: Fonts.body.regular, fontSize: FontSize.xs, color: Palette.inkMute, marginTop: 2 },
  sep: { height: 1, backgroundColor: Palette.rule },
  badge: {
    borderWidth: 1,
    borderRadius: Radii.sm,
    paddingHorizontal: 6,
    paddingVertical: 2,
  },
  badgeText: { fontFamily: Fonts.body.semibold, fontSize: 10, letterSpacing: 0.5 },
  empty: { fontFamily: Fonts.body.regular, fontSize: FontSize.md, color: Palette.inkMute, textAlign: 'center', marginTop: Spacing.xxl },
  signout: {
    marginTop: Spacing.xxl,
    paddingVertical: Spacing.md,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: Palette.rule,
    borderRadius: Radii.md,
  },
  signoutText: { fontFamily: Fonts.body.medium, fontSize: FontSize.sm, color: Palette.claret },
});
