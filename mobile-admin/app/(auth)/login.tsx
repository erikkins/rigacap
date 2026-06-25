/**
 * Admin login — email/password. Non-admin accounts are rejected.
 */

import React, { useState } from 'react';
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAuth } from '@/hooks/useAuth';
import { NotAdminError } from '@/services/auth';
import { Fonts, FontSize, Palette, Radii, Spacing } from '@/constants/theme';

export default function Login() {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const onSubmit = async () => {
    if (!email || !password) return;
    setBusy(true);
    setError(null);
    try {
      await login(email.trim(), password);
    } catch (err: any) {
      if (err instanceof NotAdminError) {
        setError('That account is not an administrator.');
      } else if (err?.response?.status === 401) {
        setError('Incorrect email or password.');
      } else {
        setError('Could not sign in. Check your connection and try again.');
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <SafeAreaView style={styles.safe}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        style={styles.flex}
      >
        <View style={styles.container}>
          <Text style={styles.kicker}>RIGACAP</Text>
          <Text style={styles.title}>Admin</Text>
          <Text style={styles.subtitle}>Sign in with your administrator account.</Text>

          <TextInput
            style={styles.input}
            placeholder="Email"
            placeholderTextColor={Palette.inkLight}
            autoCapitalize="none"
            autoCorrect={false}
            keyboardType="email-address"
            value={email}
            onChangeText={setEmail}
            editable={!busy}
          />
          <TextInput
            style={styles.input}
            placeholder="Password"
            placeholderTextColor={Palette.inkLight}
            secureTextEntry
            value={password}
            onChangeText={setPassword}
            editable={!busy}
            onSubmitEditing={onSubmit}
            returnKeyType="go"
          />

          {error ? <Text style={styles.error}>{error}</Text> : null}

          <TouchableOpacity
            style={[styles.button, busy && styles.buttonDisabled]}
            onPress={onSubmit}
            disabled={busy}
          >
            {busy ? (
              <ActivityIndicator color={Palette.paper} />
            ) : (
              <Text style={styles.buttonText}>Sign In</Text>
            )}
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: Palette.paper },
  flex: { flex: 1 },
  container: { flex: 1, justifyContent: 'center', paddingHorizontal: Spacing.xl },
  kicker: {
    fontFamily: Fonts.body.semibold,
    fontSize: FontSize.sm,
    letterSpacing: 3,
    color: Palette.claret,
    marginBottom: Spacing.xs,
  },
  title: {
    fontFamily: Fonts.display.semibold,
    fontSize: FontSize.xxxl,
    color: Palette.ink,
  },
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
    fontFamily: Fonts.body.regular,
    fontSize: FontSize.md,
    color: Palette.ink,
    marginBottom: Spacing.md,
  },
  error: {
    fontFamily: Fonts.body.medium,
    fontSize: FontSize.sm,
    color: Palette.negative,
    marginBottom: Spacing.md,
  },
  button: {
    backgroundColor: Palette.claret,
    borderRadius: Radii.md,
    paddingVertical: Spacing.md,
    alignItems: 'center',
    marginTop: Spacing.sm,
  },
  buttonDisabled: { opacity: 0.6 },
  buttonText: {
    fontFamily: Fonts.body.semibold,
    fontSize: FontSize.md,
    color: Palette.paper,
    letterSpacing: 0.5,
  },
});
