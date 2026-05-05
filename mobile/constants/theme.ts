/**
 * RigaCap brand tokens — paper-backed editorial publication aesthetic.
 * Mirrors frontend/tailwind.config.js (post-Apr-27 rebrand).
 */

// ──────────────────────────────────────────────────────────────
// Typography
// ──────────────────────────────────────────────────────────────

export const Fonts = {
  display: {
    light: 'Fraunces_300Light',
    regular: 'Fraunces_400Regular',
    medium: 'Fraunces_500Medium',
    semibold: 'Fraunces_600SemiBold',
    italic: 'Fraunces_400Regular_Italic',
    italicLight: 'Fraunces_300Light_Italic',
  },
  body: {
    regular: 'IBMPlexSans_400Regular',
    medium: 'IBMPlexSans_500Medium',
    semibold: 'IBMPlexSans_600SemiBold',
    italic: 'IBMPlexSans_400Regular_Italic',
  },
  mono: {
    regular: 'IBMPlexMono_400Regular',
    medium: 'IBMPlexMono_500Medium',
  },
} as const;

// ──────────────────────────────────────────────────────────────
// Palette
// ──────────────────────────────────────────────────────────────

export const Palette = {
  // Paper backdrop
  paper: '#F5F1E8',
  paperDeep: '#EDE7D8',
  paperCard: '#FAF7F0',

  // Ink text
  ink: '#141210',
  inkMute: '#5A544E',
  inkLight: '#8A8279',

  // Claret accent
  claret: '#7A2430',
  claretLight: '#9A3444',

  // Rules / dividers
  rule: '#DDD5C7',
  ruleDark: '#C9BFAC',

  // Editorial green/red — softer than vivid Tailwind defaults
  positive: '#2D5F3F',
  negative: '#8F2D3D',

  // Functional / status (kept for charts and warnings)
  green: '#22C55E',
  red: '#EF4444',
  yellow: '#F59E0B',
  blue: '#3B82F6',
} as const;

// ──────────────────────────────────────────────────────────────
// Regime colors — functional, kept across rebrand
// ──────────────────────────────────────────────────────────────

// Tuned to contrast on the paper background (#F5F1E8). Strong colors stay
// vivid. Two adjustments from the original navy-bg palette:
// - rotating_bull was a pale mint (#BBF7D0) → sage/teal #4C9277, distinct
//   hue from strong_bull while staying bull-family.
// - weak_bull was a pale green (#86EFAC) → calmer sage #5DA974 with
//   enough darkness to read on paper.
// weak_bear (#FCA5A5) is borderline but Erik's choice to keep.
export const Regime: Record<string, string> = {
  strong_bull: '#22C55E',
  weak_bull: '#5DA974',
  rotating_bull: '#4C9277',
  range_bound: '#F59E0B',
  weak_bear: '#FCA5A5',
  panic_crash: '#EF4444',
  recovery: '#3B82F6',
};

// ──────────────────────────────────────────────────────────────
// Spacing / sizing
// ──────────────────────────────────────────────────────────────

export const Spacing = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
  xxl: 48,
} as const;

export const FontSize = {
  xs: 11,
  sm: 13,
  md: 15,
  lg: 18,
  xl: 22,
  xxl: 28,
  xxxl: 36,
} as const;

export const Radii = {
  sm: 4,
  md: 8,
  lg: 12,
  xl: 16,
  pill: 9999,
} as const;

