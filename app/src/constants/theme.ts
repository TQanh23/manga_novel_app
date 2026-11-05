import '@/global.css';

import { Platform } from 'react-native';

/**
 * A warm pastel palette. In light mode the four brand pastels (#FFF4DE cream,
 * #FFDDDD blush, #FFCED8 rose, #FFE8C4 peach) are surfaces; a deep rose is the
 * one accent, dark enough for white text. Dark mode keeps the warmth with a
 * near-black brown base and uses the pastels for the accent and the text.
 * Every text colour here reaches 4.5:1 against every surface it is used on,
 * and the gold ornament 3:1 (the bar for graphics).
 */
export const Colors = {
  light: {
    text: '#3B2A2F',
    textSecondary: '#6E4F57',
    /** The page. */
    background: '#FFF4DE',
    /** Cards and sheets that sit on the page. */
    surface: '#FFFAF1',
    /** Chips, inputs and other controls. */
    backgroundElement: '#FFDDDD',
    backgroundSelected: '#FFCED8',
    /** Small badges and tags. */
    highlight: '#FFE8C4',
    border: '#F3C9C9',
    /** Primary buttons, links, the selected tab. */
    accent: '#A3304A',
    onAccent: '#FFFFFF',
    danger: '#B42318',
    /** Antique gold, for ornaments and rules only, never for text. */
    ornament: '#8E6A24',
  },
  dark: {
    text: '#FFF4DE',
    textSecondary: '#E3C3C3',
    background: '#1E1517',
    surface: '#2A1E21',
    backgroundElement: '#33252A',
    backgroundSelected: '#4A3238',
    highlight: '#3A2C22',
    border: '#4A3238',
    accent: '#FFCED8',
    onAccent: '#3B1820',
    danger: '#FF9C8F',
    ornament: '#D4AF6A',
  },
} as const;

export type ThemeColor = keyof typeof Colors.light & keyof typeof Colors.dark;
export type Palette = { [K in ThemeColor]: string };

/** A soft warm lift for cards. Dark mode relies on the border instead. */
export const Shadows = {
  light: '0 4px 16px rgba(163, 48, 74, 0.10)',
  dark: 'none',
} as const;

/** Baroque frames are crisp, not bubbly; pills stay for chips, which read as cartouches. */
export const Radius = {
  sm: 4,
  md: 6,
  lg: 8,
  pill: 999,
} as const;

/**
 * One typeface for the whole app: EB Garamond, a Garamond revival that covers
 * Vietnamese. Each weight is loaded under its own name in the root layout,
 * because Android picks a face by name, not by fontWeight.
 */
export const BODY_FONT = 'EBGaramond_500Medium';
/** Small engraved capitals: kinds, statuses, field labels, buttons, tabs. */
export const ENGRAVED_FONT = 'EBGaramond_600SemiBold';
/** Headings and anything bold. */
export const DISPLAY_FONT = 'EBGaramond_700Bold';
/** The family name the reader and editor pages declare with @font-face. */
export const TEXT_FAMILY = 'EB Garamond';

export const Fonts = Platform.select({
  ios: {
    /** iOS `UIFontDescriptorSystemDesignDefault` */
    sans: 'system-ui',
    /** iOS `UIFontDescriptorSystemDesignSerif` */
    serif: 'ui-serif',
    /** iOS `UIFontDescriptorSystemDesignRounded` */
    rounded: 'ui-rounded',
    /** iOS `UIFontDescriptorSystemDesignMonospaced` */
    mono: 'ui-monospace',
    display: DISPLAY_FONT,
    engraved: ENGRAVED_FONT,
    body: BODY_FONT,
  },
  default: {
    sans: 'normal',
    serif: 'serif',
    rounded: 'normal',
    mono: 'monospace',
    display: DISPLAY_FONT,
    engraved: ENGRAVED_FONT,
    body: BODY_FONT,
  },
  web: {
    sans: 'var(--font-display)',
    serif: 'var(--font-serif)',
    rounded: 'var(--font-rounded)',
    mono: 'var(--font-mono)',
    display: `${DISPLAY_FONT}, Georgia, serif`,
    engraved: `${ENGRAVED_FONT}, Georgia, serif`,
    body: `${BODY_FONT}, Georgia, serif`,
  },
});

export const Spacing = {
  half: 2,
  one: 4,
  two: 8,
  three: 16,
  four: 24,
  five: 32,
  six: 64,
} as const;

export const BottomTabInset = Platform.select({ ios: 50, android: 80 }) ?? 0;
export const MaxContentWidth = 800;
/** Pages that show a grid of works, not a column of text. */
export const MaxGridWidth = 1200;
