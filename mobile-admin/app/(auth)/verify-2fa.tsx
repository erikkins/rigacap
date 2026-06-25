/**
 * 2FA challenge — 6-digit TOTP (or backup code), with optional device trust.
 */

import React, { useState } from 'react';
import {
  ActivityIndicator,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAuth } from '@/hooks/useAuth';
import { NotAdminError } from '@/services/auth';
import { Fonts, FontSize, Palette, Radii, Spacing } from '@/constants/theme';

export default function Verify2FA() {
  const { verify2FA, cancel2FA } = useAuth();
  const [code, setCode] = useState('');
  const [trust, setTrust] = useState(false);
  const [backup, setBackup] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const onSubmit = async () => {
    if (code.length < 6) return;
    setBusy(true);
    setError(null);
    try {
      await verify2FA(code.trim(), trust, backup);
    } catch (err: any) {
      if (err instanceof NotAdminError) setError('That account is not an administrator.');
      else setError('Invalid code. Try again.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.container}>
        <Text style={styles.title}>Two-factor</Text>
        <Text style={styles.subtitle}>
          Enter the {backup ? 'backup' : '6-digit'} code from your authenticator.
        </Text>

        <TextInput
          style={styles.input}
          placeholder={backup ? 'Backup code' : '123456'}
          placeholderTextColor={Palette.inkLight}
          keyboardType={backup ? 'default' : 'number-pad'}
          autoCapitalize="none"
          value={code}
          onChangeText={setCode}
          editable={!busy}
          maxLength={backup ? 16 : 6}
          onSubmitEditing={onSubmit}
        />

        <View style={styles.row}>
          <Text style={styles.rowLabel}>Trust this device for 30 days</Text>
          <Switch value={trust} onValueChange={setTrust} disabled={busy} />
        </View>

        {error ? <Text style={styles.error}>{error}</Text> : null}

        <TouchableOpacity
          style={[styles.button, busy && styles.buttonDisabled]}
          onPress={onSubmit}
          disabled={busy}
        >
          {busy ? <ActivityIndicator color={Palette.paper} /> : <Text style={styles.buttonText}>Verify</Text>}
        </TouchableOpacity>

        <TouchableOpacity onPress={() => setBackup((b) => !b)} disabled={busy}>
          <Text style={styles.link}>{backup ? 'Use authenticator code' : 'Use a backup code'}</Text>
        </TouchableOpacity>
        <TouchableOpacity onPress={cancel2FA} disabled={busy}>
          <Text style={[styles.link, { color: Palette.inkLight }]}>Cancel</Text>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: Palette.paper },
  container: { flex: 1, justifyContent: 'center', paddingHorizontal: Spacing.xl },
  title: { fontFamily: Fonts.display.semibold, fontSize: FontSize.xxxl, color: Palette.ink },
  subtitle: {
    fontFamily: Fonts.body.regular,
    fontSize: FontSize.md,
    color: Palette.inkMute,
    marginTop: Spacing.xs,
    marginBottom: Spacing.xl,
  },
  input: {
    backgroundColor: Palette.paperCard,
    borderWidth: 1,
    borderColor: Palette.rule,
    borderRadius: Radii.md,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.md,
    fontFamily: Fonts.mono.medium,
    fontSize: FontSize.xl,
    letterSpacing: 4,
    textAlign: 'center',
    color: Palette.ink,
    marginBottom: Spacing.md,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: Spacing.md,
  },
  rowLabel: { fontFamily: Fonts.body.regular, fontSize: FontSize.sm, color: Palette.inkMute },
  error: { fontFamily: Fonts.body.medium, fontSize: FontSize.sm, color: Palette.negative, marginBottom: Spacing.md },
  button: {
    backgroundColor: Palette.claret,
    borderRadius: Radii.md,
    paddingVertical: Spacing.md,
    alignItems: 'center',
  },
  buttonDisabled: { opacity: 0.6 },
  buttonText: { fontFamily: Fonts.body.semibold, fontSize: FontSize.md, color: Palette.paper, letterSpacing: 0.5 },
  link: {
    fontFamily: Fonts.body.medium,
    fontSize: FontSize.sm,
    color: Palette.claret,
    textAlign: 'center',
    marginTop: Spacing.lg,
  },
});
