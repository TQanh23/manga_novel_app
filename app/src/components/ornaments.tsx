import type { PropsWithChildren } from 'react';
import { StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';
import Svg, { Circle, G, Path } from 'react-native-svg';

import { ThemedText } from '@/components/themed-text';
import { Radius, Spacing } from '@/constants/theme';
import { useCardStyle, useTheme } from '@/hooks/use-theme';

// Ornaments are decoration: hidden from screen readers and from taps.
const decorative = {
  accessibilityElementsHidden: true,
  importantForAccessibility: 'no-hide-descendants',
  'aria-hidden': true,
  pointerEvents: 'none',
} as const;

const STROKE = 1.4;

/** The middle of a divider: a lozenge between two C-scrolls ending in leaves. */
function Motif({ color }: { color: string }) {
  const half = (
    <>
      <Path d="M68 12 C74 4 86 4 90 10 C93 15 87 18 85 14" stroke={color} strokeWidth={STROKE} fill="none" />
      <Path d="M96 12 C100 8 106 8 110 12 C106 16 100 16 96 12 Z" stroke={color} strokeWidth={1} fill={color} fillOpacity={0.25} />
      <Path d="M110 12 H120" stroke={color} strokeWidth={1} />
    </>
  );
  return (
    <Svg width={120} height={24} viewBox="0 0 120 24">
      {half}
      <G transform="translate(120 0) scale(-1 1)">{half}</G>
      <Path d="M60 4 L68 12 L60 20 L52 12 Z" stroke={color} strokeWidth={STROKE} fill={color} fillOpacity={0.2} />
      <Circle cx={60} cy={12} r={2} fill={color} />
    </Svg>
  );
}

/** A gold divider: hairline, motif, hairline, as wide as its container. */
export function Flourish({ style }: { style?: StyleProp<ViewStyle> }) {
  const theme = useTheme();
  const rule = [styles.rule, { backgroundColor: theme.ornament }];
  return (
    <View style={[styles.flourish, style]} {...decorative}>
      <View style={rule} />
      <Motif color={theme.ornament} />
      <View style={rule} />
    </View>
  );
}

const CORNER = 20;
const ROTATIONS = { topLeft: '0deg', topRight: '90deg', bottomRight: '180deg', bottomLeft: '270deg' } as const;

/** One corner scroll, drawn for the top left and turned for the others. */
function Corner({ at, color }: { at: keyof typeof ROTATIONS; color: string }) {
  return (
    <View style={[styles.corner, styles[at], { transform: [{ rotate: ROTATIONS[at] }] }]}>
      <Svg width={CORNER} height={CORNER} viewBox="0 0 40 40">
        <Path d="M3 37 V12 Q3 3 12 3 H37" stroke={color} strokeWidth={2.4} fill="none" />
        <Path d="M10 26 C10 16 16 10 26 10" stroke={color} strokeWidth={2.4} fill="none" />
        <Path d="M26 10 C31 10 33 14 30 17 C28 19 25 17 26 15" stroke={color} strokeWidth={2.4} fill="none" />
        <Path d="M10 26 C10 31 14 33 17 30 C19 28 17 25 15 26" stroke={color} strokeWidth={2.4} fill="none" />
        <Circle cx={11} cy={11} r={3} fill={color} />
      </Svg>
    </View>
  );
}

type OrnateFrameProps = PropsWithChildren<{
  /** The content's own layout: padding, gap. */
  style?: StyleProp<ViewStyle>;
  /** The frame's place in its parent: flex, margins. */
  frameStyle?: StyleProp<ViewStyle>;
}>;

/** A double rule, gold outside and blush inside, with a scroll in each corner. */
export function OrnateFrame({ children, style, frameStyle }: OrnateFrameProps) {
  const theme = useTheme();
  const card = useCardStyle();
  return (
    <View style={[card, styles.frame, frameStyle]}>
      <View style={[styles.inner, { borderColor: theme.border }, style]}>{children}</View>
      <View style={StyleSheet.absoluteFill} {...decorative}>
        {(Object.keys(ROTATIONS) as (keyof typeof ROTATIONS)[]).map((at) => (
          <Corner key={at} at={at} color={theme.ornament} />
        ))}
      </View>
    </View>
  );
}

/** A page or section heading in the display face, with an engraved line above and a flourish below. */
export function SectionTitle({ title, eyebrow }: { title: string; eyebrow?: string }) {
  return (
    <View style={styles.title}>
      {eyebrow ? (
        <ThemedText type="eyebrow" themeColor="textSecondary">
          {eyebrow}
        </ThemedText>
      ) : null}
      <ThemedText type="subtitle">{title}</ThemedText>
      <Flourish />
    </View>
  );
}

const styles = StyleSheet.create({
  flourish: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.one,
  },
  rule: {
    flex: 1,
    height: StyleSheet.hairlineWidth * 2,
    opacity: 0.6,
  },
  frame: {
    padding: 3,
  },
  inner: {
    // Grows to fill a stretched frame (a grid cell) but keeps its content's height otherwise.
    flexGrow: 1,
    borderWidth: 1,
    borderRadius: Radius.sm,
  },
  corner: {
    position: 'absolute',
    width: CORNER,
    height: CORNER,
  },
  topLeft: { top: 1, left: 1 },
  topRight: { top: 1, right: 1 },
  bottomRight: { bottom: 1, right: 1 },
  bottomLeft: { bottom: 1, left: 1 },
  title: {
    gap: Spacing.one,
  },
});
