/**
 * Bottom-sheet confirmation modal for Track and Sell actions.
 */

import React from 'react';
import {
  ActivityIndicator,
  Modal,
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { Fonts, FontSize, Palette, Radii, Spacing } from '@/constants/theme';

interface ConfirmModalProps {
  visible: boolean;
  title: string;
  children: React.ReactNode;
  confirmLabel: string;
  confirmColor?: string;
  onConfirm: () => void;
  onCancel: () => void;
  loading?: boolean;
}

export default function ConfirmModal({
  visible,
  title,
  children,
  confirmLabel,
  confirmColor = Palette.ink,
  onConfirm,
  onCancel,
  loading = false,
}: ConfirmModalProps) {
  return (
    <Modal
      visible={visible}
      transparent
      animationType="slide"
      onRequestClose={onCancel}
    >
      <Pressable style={styles.overlay} onPress={onCancel}>
        <Pressable style={styles.card} onPress={() => {}}>
          <Text style={styles.title}>{title}</Text>
          <View style={styles.body}>{children}</View>
          <View style={styles.buttons}>
            <Pressable
              style={({ pressed }) => [styles.cancelButton, pressed && styles.pressed]}
              onPress={onCancel}
              disabled={loading}
            >
              <Text style={styles.cancelText}>Cancel</Text>
            </Pressable>
            <Pressable
              style={({ pressed }) => [
                styles.confirmButton,
                { backgroundColor: confirmColor },
                pressed && styles.pressed,
              ]}
              onPress={onConfirm}
              disabled={loading}
            >
              {loading ? (
                <ActivityIndicator size="small" color={Palette.paper} />
              ) : (
                <Text style={styles.confirmText}>{confirmLabel}</Text>
              )}
            </Pressable>
          </View>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    // Dark scrim so the paper sheet reads as elevated
    backgroundColor: 'rgba(20,18,16,0.55)',
    justifyContent: 'flex-end',
  },
  card: {
    backgroundColor: Palette.paper,
    borderTopLeftRadius: Radii.xl,
    borderTopRightRadius: Radii.xl,
    borderTopWidth: 1,
    borderTopColor: Palette.rule,
    padding: Spacing.lg,
    paddingBottom: Spacing.xl + 16,
  },
  title: {
    color: Palette.ink,
    fontSize: FontSize.xl,
    fontFamily: Fonts.display.semibold,
    marginBottom: Spacing.md,
  },
  body: {
    marginBottom: Spacing.lg,
  },
  buttons: {
    flexDirection: 'row',
    gap: Spacing.sm,
  },
  pressed: {
    opacity: 0.85,
  },
  cancelButton: {
    flex: 1,
    paddingVertical: 14,
    borderRadius: Radii.md,
    backgroundColor: 'transparent',
    borderWidth: 1,
    borderColor: Palette.rule,
    alignItems: 'center',
  },
  cancelText: {
    color: Palette.inkMute,
    fontSize: FontSize.md,
    fontFamily: Fonts.body.medium,
    letterSpacing: 0.4,
  },
  confirmButton: {
    flex: 1,
    paddingVertical: 14,
    borderRadius: Radii.md,
    alignItems: 'center',
  },
  confirmText: {
    color: Palette.paper,
    fontSize: FontSize.md,
    fontFamily: Fonts.body.semibold,
    letterSpacing: 0.4,
  },
});
