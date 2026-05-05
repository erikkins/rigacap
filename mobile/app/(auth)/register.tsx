/**
 * Registration screen.
 */

import React, { useState } from 'react';
import {
  Alert,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Link } from 'expo-router';
import { useAuth } from '@/hooks/useAuth';
import { Fonts, FontSize, Palette, Radii, Spacing } from '@/constants/theme';

export default function RegisterScreen() {
  const { register } = useAuth();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  const handleRegister = async () => {
    if (!name || !email || !password) {
      Alert.alert('Error', 'Please fill in all fields');
      return;
    }
    if (password.length < 8) {
      Alert.alert('Error', 'Password must be at least 8 characters');
      return;
    }
    setLoading(true);
    try {
      await register(email.trim().toLowerCase(), password, name.trim());
    } catch (err: any) {
      Alert.alert(
        'Registration Failed',
        err.response?.data?.detail || 'Could not create account'
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.container}>
    <KeyboardAvoidingView
      style={{ flex: 1 }}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
    >
      <ScrollView
        contentContainerStyle={styles.scroll}
        keyboardShouldPersistTaps="handled"
      >
        <View style={styles.brand}>
          <Text style={styles.logo}>RigaCap</Text>
          <Text style={styles.tagline}>Create your account</Text>
        </View>

        <View style={styles.form}>
          <TextInput
            style={styles.input}
            placeholder="Full Name"
            placeholderTextColor={Palette.inkLight}
            value={name}
            onChangeText={setName}
            textContentType="name"
          />
          <TextInput
            style={styles.input}
            placeholder="Email"
            placeholderTextColor={Palette.inkLight}
            value={email}
            onChangeText={setEmail}
            autoCapitalize="none"
            keyboardType="email-address"
            textContentType="emailAddress"
          />
          <TextInput
            style={styles.input}
            placeholder="Password (min 8 characters)"
            placeholderTextColor={Palette.inkLight}
            value={password}
            onChangeText={setPassword}
            secureTextEntry
            textContentType="newPassword"
          />

          <Pressable
            style={[styles.button, loading && styles.buttonDisabled]}
            onPress={handleRegister}
            disabled={loading}
          >
            <Text style={styles.buttonText}>
              {loading ? 'Creating Account...' : 'Start Free Trial'}
            </Text>
          </Pressable>

          <Text style={styles.trialNote}>
            7-day free trial. Subscribe at rigacap.com to continue after trial.
          </Text>
        </View>

        <View style={styles.footer}>
          <Text style={styles.footerText}>Already have an account? </Text>
          <Link href="/(auth)/login" asChild>
            <Pressable>
              <Text style={styles.footerLink}>Sign In</Text>
            </Pressable>
          </Link>
        </View>

        <Text style={styles.disclaimer}>
          By creating an account you agree to our Terms of Service and Privacy
          Policy. Signals only — not financial advice.
        </Text>
      </ScrollView>
    </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Palette.paper,
  },
  scroll: {
    flexGrow: 1,
    justifyContent: 'center',
    padding: Spacing.lg,
  },
  brand: {
    alignItems: 'center',
    marginBottom: Spacing.xl,
  },
  logo: {
    fontSize: 44,
    fontFamily: Fonts.display.semibold,
    color: Palette.ink,
    letterSpacing: -0.5,
  },
  tagline: {
    color: Palette.inkMute,
    fontSize: FontSize.md,
    fontFamily: Fonts.display.italic,
    marginTop: Spacing.xs,
  },
  form: {
    gap: Spacing.md,
  },
  input: {
    backgroundColor: Palette.paperCard,
    borderRadius: Radii.md,
    borderWidth: 1,
    borderColor: Palette.rule,
    padding: Spacing.md,
    color: Palette.ink,
    fontSize: FontSize.md,
    fontFamily: Fonts.body.regular,
  },
  button: {
    backgroundColor: Palette.ink,
    borderRadius: Radii.md,
    padding: Spacing.md,
    alignItems: 'center',
  },
  buttonDisabled: {
    opacity: 0.6,
  },
  buttonText: {
    color: Palette.paper,
    fontSize: FontSize.md,
    fontFamily: Fonts.body.semibold,
    letterSpacing: 0.4,
  },
  trialNote: {
    color: Palette.inkLight,
    fontSize: FontSize.xs,
    fontFamily: Fonts.display.italic,
    textAlign: 'center',
  },
  footer: {
    flexDirection: 'row',
    justifyContent: 'center',
    marginTop: Spacing.lg,
  },
  footerText: {
    color: Palette.inkMute,
    fontSize: FontSize.sm,
    fontFamily: Fonts.body.regular,
  },
  footerLink: {
    color: Palette.claret,
    fontSize: FontSize.sm,
    fontFamily: Fonts.body.semibold,
    letterSpacing: 0.3,
  },
  disclaimer: {
    color: Palette.inkLight,
    fontSize: FontSize.xs,
    fontFamily: Fonts.display.italic,
    textAlign: 'center',
    marginTop: Spacing.lg,
    lineHeight: 16,
  },
});
