/**
 * Root layout — wraps entire app with auth provider and handles
 * routing between auth and main app based on login state.
 */

import React, { useCallback, useEffect } from 'react';
import { Stack, useRouter, useSegments } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { ActivityIndicator, View } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import * as Notifications from 'expo-notifications';
import * as Updates from 'expo-updates';
import * as ScreenOrientation from 'expo-screen-orientation';
import * as SplashScreen from 'expo-splash-screen';
import {
  useFonts as useFraunces,
  Fraunces_300Light,
  Fraunces_400Regular,
  Fraunces_500Medium,
  Fraunces_600SemiBold,
  Fraunces_300Light_Italic,
  Fraunces_400Regular_Italic,
} from '@expo-google-fonts/fraunces';
import {
  IBMPlexSans_400Regular,
  IBMPlexSans_500Medium,
  IBMPlexSans_600SemiBold,
  IBMPlexSans_400Regular_Italic,
} from '@expo-google-fonts/ibm-plex-sans';
import {
  IBMPlexMono_400Regular,
  IBMPlexMono_500Medium,
} from '@expo-google-fonts/ibm-plex-mono';
import { AuthProvider, useAuth } from '@/hooks/useAuth';
import { Palette } from '@/constants/theme';

SplashScreen.preventAutoHideAsync().catch(() => {});

function RootNavigator() {
  const { user, isLoading, twoFactorRequired } = useAuth();
  const segments = useSegments();
  const router = useRouter();

  useEffect(() => {
    if (isLoading) return;

    const inAuthGroup = segments[0] === '(auth)';

    // 2FA required — redirect to verify screen
    if (twoFactorRequired) {
      const currentScreen = (segments as string[])[1];
      if (currentScreen !== 'verify-2fa') {
        router.replace('/(auth)/verify-2fa' as any);
      }
      return;
    }

    if (!user && !inAuthGroup) {
      router.replace('/(auth)/login');
    } else if (user && inAuthGroup) {
      router.replace('/(tabs)/dashboard');
    }
  }, [user, isLoading, segments, twoFactorRequired]);

  // Handle notification taps — navigate to relevant screen
  useEffect(() => {
    const sub = Notifications.addNotificationResponseReceivedListener(
      (response) => {
        const data = response.notification.request.content.data;
        if (data?.screen === 'dashboard') {
          router.push('/(tabs)/dashboard');
        } else if (data?.screen === 'signal_detail' && data?.symbol) {
          router.push(`/signal/${data.symbol}`);
        }
      }
    );
    return () => sub.remove();
  }, []);

  if (isLoading) {
    return (
      <View
        style={{
          flex: 1,
          justifyContent: 'center',
          alignItems: 'center',
          backgroundColor: Palette.paper,
        }}
      >
        <ActivityIndicator size="large" color={Palette.claret} />
      </View>
    );
  }

  return (
    <Stack
      screenOptions={{
        headerShown: false,
        contentStyle: { backgroundColor: Palette.paper },
      }}
    />
  );
}

export default function RootLayout() {
  // Load editorial typography (Fraunces + IBM Plex Sans/Mono). The splash
  // screen stays visible until every weight is registered — prevents the
  // first-frame flash of system fonts.
  const [fontsLoaded, fontError] = useFraunces({
    Fraunces_300Light,
    Fraunces_400Regular,
    Fraunces_500Medium,
    Fraunces_600SemiBold,
    Fraunces_300Light_Italic,
    Fraunces_400Regular_Italic,
    IBMPlexSans_400Regular,
    IBMPlexSans_500Medium,
    IBMPlexSans_600SemiBold,
    IBMPlexSans_400Regular_Italic,
    IBMPlexMono_400Regular,
    IBMPlexMono_500Medium,
  });

  // Lock to portrait by default — signal detail unlocks landscape for chart
  useEffect(() => {
    ScreenOrientation.lockAsync(ScreenOrientation.OrientationLock.PORTRAIT_UP);
  }, []);

  // Check for OTA updates on launch
  useEffect(() => {
    if (__DEV__) return;
    (async () => {
      try {
        console.log('[OTA] Checking for updates...');
        const update = await Updates.checkForUpdateAsync();
        console.log('[OTA] Update available:', update.isAvailable);
        if (update.isAvailable) {
          console.log('[OTA] Fetching update...');
          await Updates.fetchUpdateAsync();
          console.log('[OTA] Reloading...');
          await Updates.reloadAsync();
        }
      } catch (e) {
        console.log('[OTA] Error:', e);
      }
    })();
  }, []);

  const onReady = useCallback(async () => {
    if (fontsLoaded || fontError) {
      await SplashScreen.hideAsync().catch(() => {});
    }
  }, [fontsLoaded, fontError]);

  if (!fontsLoaded && !fontError) {
    return null;
  }

  return (
    <SafeAreaProvider onLayout={onReady}>
      <AuthProvider>
        <StatusBar style="dark" />
        <RootNavigator />
      </AuthProvider>
    </SafeAreaProvider>
  );
}
