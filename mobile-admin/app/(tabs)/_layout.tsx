/**
 * Admin tab navigator — Glance, Users, Portfolio, Ads.
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
          borderBottomWidth: 1,
          borderBottomColor: Palette.rule,
        },
        headerShadowVisible: false,
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
        name="index"
        options={{
          title: 'Glance',
          tabBarIcon: ({ color, size }) => <Ionicons name="pulse" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="users"
        options={{
          title: 'Users',
          tabBarIcon: ({ color, size }) => <Ionicons name="people-outline" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="portfolio"
        options={{
          title: 'Portfolio',
          tabBarIcon: ({ color, size }) => <Ionicons name="briefcase-outline" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="ads"
        options={{
          title: 'Ads',
          tabBarIcon: ({ color, size }) => <Ionicons name="megaphone-outline" size={size} color={color} />,
        }}
      />
    </Tabs>
  );
}
