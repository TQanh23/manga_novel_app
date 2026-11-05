import { Platform, StyleSheet, Text, type TextProps, type TextStyle } from 'react-native';

import { Fonts, ThemeColor } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

export type ThemedTextProps = TextProps & {
  type?:
    | 'default'
    | 'title'
    | 'small'
    | 'smallBold'
    | 'subtitle'
    | 'eyebrow'
    | 'link'
    | 'linkPrimary'
    | 'code';
  themeColor?: ThemeColor;
};

const BOLD = new Set<TextStyle['fontWeight']>(['600', '700', '800', '900', 600, 700, 800, 900, 'bold']);

/**
 * Each weight of the typeface is its own font, and Android fakes a bolder face
 * when asked for a fontWeight. So a caller's bold becomes the bold face.
 */
function withFace(style: TextProps['style']): TextStyle {
  const flat = StyleSheet.flatten(style) ?? {};
  if (!BOLD.has(flat.fontWeight) || (flat.fontFamily && flat.fontFamily !== Fonts.body)) {
    return flat;
  }
  return { ...flat, fontFamily: Fonts.display, fontWeight: 'normal' };
}

export function ThemedText({ style, type = 'default', themeColor, ...rest }: ThemedTextProps) {
  const theme = useTheme();

  return (
    <Text
      style={withFace([
        { color: theme[themeColor ?? 'text'] },
        type === 'default' && styles.default,
        type === 'title' && styles.title,
        type === 'small' && styles.small,
        type === 'smallBold' && styles.smallBold,
        type === 'subtitle' && styles.subtitle,
        type === 'eyebrow' && styles.eyebrow,
        type === 'link' && styles.link,
        type === 'linkPrimary' && [styles.linkPrimary, { color: theme.accent }],
        type === 'code' && styles.code,
        style,
      ])}
      {...rest}
    />
  );
}

// Garamond's letters are small for their size, so it is set a point larger
// than the sans it replaces.
const styles = StyleSheet.create({
  small: {
    fontFamily: Fonts.body,
    fontSize: 15,
    lineHeight: 21,
  },
  smallBold: {
    fontFamily: Fonts.display,
    fontSize: 15,
    lineHeight: 21,
  },
  default: {
    fontFamily: Fonts.body,
    fontSize: 17,
    lineHeight: 25,
  },
  title: {
    fontFamily: Fonts.display,
    fontSize: 42,
    lineHeight: 52,
  },
  subtitle: {
    fontFamily: Fonts.display,
    fontSize: 32,
    lineHeight: 40,
  },
  /** Small capitals, as if engraved: kinds, statuses, field labels. */
  eyebrow: {
    fontFamily: Fonts.engraved,
    fontSize: 14,
    lineHeight: 20,
    letterSpacing: 1.4,
    textTransform: 'uppercase',
  },
  link: {
    fontFamily: Fonts.body,
    lineHeight: 30,
    fontSize: 15,
  },
  linkPrimary: {
    fontFamily: Fonts.display,
    lineHeight: 30,
    fontSize: 15,
  },
  code: {
    fontFamily: Fonts.mono,
    fontWeight: Platform.select({ android: 700 }) ?? 500,
    fontSize: 12,
  },
});

