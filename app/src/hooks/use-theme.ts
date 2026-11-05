/**
 * Learn more about light and dark modes:
 * https://docs.expo.dev/guides/color-schemes/
 */

import type { ViewStyle } from 'react-native';

import { Colors, Radius, Shadows } from '@/constants/theme';
import { useColorScheme } from '@/hooks/use-color-scheme';

export function useScheme(): 'light' | 'dark' {
  const scheme = useColorScheme();
  return scheme === 'dark' ? 'dark' : 'light';
}

export function useTheme() {
  return Colors[useScheme()];
}

/** The outer, gold rule of a card or a tappable row; `OrnateFrame` draws the rest. */
export function useCardStyle(): ViewStyle {
  const scheme = useScheme();
  const theme = Colors[scheme];
  return {
    backgroundColor: theme.surface,
    borderColor: theme.ornament,
    borderWidth: 1,
    borderRadius: Radius.md,
    boxShadow: Shadows[scheme],
  };
}
