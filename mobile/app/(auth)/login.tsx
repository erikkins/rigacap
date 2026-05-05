/**
 * Login screen — email/password + Google + Apple Sign In.
 *
 * iOS: expo-auth-session (browser redirect with reversed client ID)
 * Android: @react-native-google-signin/google-signin (native SDK)
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
import * as AppleAuthentication from 'expo-apple-authentication';
import * as Google from 'expo-auth-session/providers/google';
import * as WebBrowser from 'expo-web-browser';
import { useAuth } from '@/hooks/useAuth';
import { Fonts, FontSize, Palette, Radii, Spacing } from '@/constants/theme';
import { GOOGLE_WEB_CLIENT_ID, GOOGLE_IOS_CLIENT_ID } from '@/constants/config';

WebBrowser.maybeCompleteAuthSession();

// Native Google Sign-In — only available on Android (native module not in iOS binary)
let GoogleSignin: any = null;
let statusCodes: any = {};
if (Platform.OS === 'android') {
  const nativeGoogle = require('@react-native-google-signin/google-signin');
  GoogleSignin = nativeGoogle.GoogleSignin;
  statusCodes = nativeGoogle.statusCodes;
  GoogleSignin.configure({ webClientId: GOOGLE_WEB_CLIENT_ID });
}

export default function LoginScreen() {
  const { login, loginWithApple, loginWithGoogle } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  // iOS: expo-auth-session browser redirect
  const iosReversedClientId = GOOGLE_IOS_CLIENT_ID.split('.').reverse().join('.');

  const [_googleRequest, googleResponse, googlePromptAsync] =
    Google.useIdTokenAuthRequest({
      iosClientId: GOOGLE_IOS_CLIENT_ID,
      androidClientId: GOOGLE_WEB_CLIENT_ID, // Unused on Android (native SDK handles it), but required by hook validation
      webClientId: GOOGLE_WEB_CLIENT_ID,
      redirectUri: Platform.OS === 'ios' ? `${iosReversedClientId}:/oauthredirect` : undefined,
    });

  // Handle iOS Google response
  React.useEffect(() => {
    try {
      if (googleResponse?.type === 'success') {
        const idToken = googleResponse.params.id_token;
        if (idToken) {
          loginWithGoogle(idToken).catch((err: any) => {
            Alert.alert(
              'Google Sign In Failed',
              err.response?.data?.detail || 'Could not sign in with Google'
            );
          });
        }
      } else if (googleResponse?.type === 'error') {
        Alert.alert('Google Sign In Failed', googleResponse.error?.message || 'Unknown error');
      }
    } catch {
      // Suppress crash in Expo Go — works in production build
    }
  }, [googleResponse]);

  // Android: native Google Sign-In
  const handleAndroidGoogleLogin = async () => {
    try {
      await GoogleSignin.hasPlayServices();
      const response = await GoogleSignin.signIn();
      const idToken = response.data?.idToken;
      if (idToken) {
        await loginWithGoogle(idToken);
      } else {
        Alert.alert('Google Sign In Failed', 'No ID token received');
      }
    } catch (err: any) {
      if (err.code === statusCodes.SIGN_IN_CANCELLED) {
        // User cancelled — do nothing
      } else if (err.code === statusCodes.IN_PROGRESS) {
        // Already in progress
      } else if (err.code === statusCodes.PLAY_SERVICES_NOT_AVAILABLE) {
        Alert.alert('Google Sign In Failed', 'Google Play Services not available');
      } else {
        Alert.alert(
          'Google Sign In Failed',
          err.response?.data?.detail || err.message || 'Unknown error'
        );
      }
    }
  };

  const handleGoogleLogin = () => {
    if (Platform.OS === 'android') {
      handleAndroidGoogleLogin();
    } else {
      googlePromptAsync();
    }
  };

  const handleLogin = async () => {
    if (!email || !password) {
      Alert.alert('Error', 'Please enter email and password');
      return;
    }
    setLoading(true);
    try {
      await login(email.trim().toLowerCase(), password);
    } catch (err: any) {
      Alert.alert(
        'Login Failed',
        err.response?.data?.detail || 'Invalid credentials'
      );
    } finally {
      setLoading(false);
    }
  };

  const handleAppleLogin = async () => {
    try {
      const credential = await AppleAuthentication.signInAsync({
        requestedScopes: [
          AppleAuthentication.AppleAuthenticationScope.FULL_NAME,
          AppleAuthentication.AppleAuthenticationScope.EMAIL,
        ],
      });
      if (credential.identityToken) {
        await loginWithApple(credential.identityToken, credential.fullName ?? undefined);
      }
    } catch (err: any) {
      if (err.code !== 'ERR_REQUEST_CANCELED') {
        Alert.alert('Apple Sign In Failed', err.message);
      }
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
        {/* Logo / Brand */}
        <View style={styles.brand}>
          <Text style={styles.logo}>RigaCap</Text>
          <Text style={styles.tagline}>
            Quantitative signals, weekly
          </Text>
        </View>

        {/* Email / Password */}
        <View style={styles.form}>
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
            placeholder="Password"
            placeholderTextColor={Palette.inkLight}
            value={password}
            onChangeText={setPassword}
            secureTextEntry
            textContentType="password"
          />

          <Pressable
            style={[styles.button, loading && styles.buttonDisabled]}
            onPress={handleLogin}
            disabled={loading}
          >
            <Text style={styles.buttonText}>
              {loading ? 'Signing In...' : 'Sign In'}
            </Text>
          </Pressable>
        </View>

        {/* Divider */}
        <View style={styles.divider}>
          <View style={styles.dividerLine} />
          <Text style={styles.dividerText}>or</Text>
          <View style={styles.dividerLine} />
        </View>

        {/* Social Login */}
        <View style={styles.social}>
          {/* Google Sign In — works on both platforms */}
          <Pressable style={styles.googleButton} onPress={handleGoogleLogin}>
            <Text style={styles.googleText}>Sign in with Google</Text>
          </Pressable>

          {/* Apple Sign In (iOS only) */}
          {Platform.OS === 'ios' && (
            <AppleAuthentication.AppleAuthenticationButton
              buttonType={
                AppleAuthentication.AppleAuthenticationButtonType.SIGN_IN
              }
              buttonStyle={
                AppleAuthentication.AppleAuthenticationButtonStyle.BLACK
              }
              cornerRadius={Radii.md}
              style={styles.appleButton}
              onPress={handleAppleLogin}
            />
          )}
        </View>

        {/* Register link */}
        <View style={styles.footer}>
          <Text style={styles.footerText}>Don't have an account? </Text>
          <Link href="/(auth)/register" asChild>
            <Pressable>
              <Text style={styles.footerLink}>Sign Up</Text>
            </Pressable>
          </Link>
        </View>

        {/* Disclaimer */}
        <Text style={styles.disclaimer}>
          Signals only — execute trades via your broker. Not financial advice.
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
    fontSize: FontSize.sm,
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
  divider: {
    flexDirection: 'row',
    alignItems: 'center',
    marginVertical: Spacing.lg,
  },
  dividerLine: {
    flex: 1,
    height: 1,
    backgroundColor: Palette.rule,
  },
  dividerText: {
    color: Palette.inkLight,
    marginHorizontal: Spacing.md,
    fontSize: FontSize.sm,
    fontFamily: Fonts.display.italic,
  },
  social: {
    gap: Spacing.md,
  },
  googleButton: {
    backgroundColor: Palette.paperCard,
    borderRadius: Radii.md,
    borderWidth: 1,
    borderColor: Palette.rule,
    paddingVertical: 14,
    paddingHorizontal: Spacing.md,
    alignItems: 'center',
    justifyContent: 'center',
  },
  googleText: {
    color: Palette.ink,
    fontSize: FontSize.md,
    fontFamily: Fonts.body.medium,
    lineHeight: 20,
    letterSpacing: 0.3,
  },
  appleButton: {
    height: 48,
    width: '100%',
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
