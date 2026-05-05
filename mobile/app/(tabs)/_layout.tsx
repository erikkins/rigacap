/**
 * Tab navigator layout — Dashboard, Settings.
 *
 * Signals tab is hidden (href: null) — signal list lives inside the
 * Dashboard's "Signals" sub-tab. Kept registered so the route resolves.
 */

import React from 'react';
import { Tabs } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Fonts, FontSize, Palette } from '@/constants/theme';

export default function TabLayout() {
  return (
    <Tabs
      screenOptions={{
        headerStyle: {
          backgroundColor: Palette.paper,
          shadowOpacity: 0,
          elevation: 0,
          borderBottomWidth: 1,
          borderBottomColor: Palette.rule,
        },
        headerTintColor: Palette.ink,
        headerTitleStyle: {
          fontFamily: Fonts.display.semibold,
          fontSize: FontSize.lg,
          color: Palette.ink,
        },
        tabBarStyle: {
          backgroundColor: Palette.paper,
          borderTopColor: Palette.rule,
          borderTopWidth: 1,
          height: 64,
          paddingTop: 6,
          paddingBottom: 8,
        },
        tabBarActiveTintColor: Palette.claret,
        tabBarInactiveTintColor: Palette.inkLight,
        tabBarLabelStyle: {
          fontFamily: Fonts.body.medium,
          fontSize: FontSize.xs,
          letterSpacing: 0.4,
        },
      }}
    >
      <Tabs.Screen
        name="dashboard"
        options={{
          title: 'Dashboard',
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="stats-chart" size={size} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="signals"
        options={{
          href: null,
        }}
      />
      <Tabs.Screen
        name="settings"
        options={{
          title: 'Settings',
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="settings-outline" size={size} color={color} />
          ),
        }}
      />
    </Tabs>
  );
}
