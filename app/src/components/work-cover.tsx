import { StyleSheet, Text, View, type StyleProp, type ViewStyle } from 'react-native';
import { useTranslation } from 'react-i18next';

import type { WorkType } from '@/api/generated';
import { CORNER_POSITIONS, Corner, decorative } from '@/components/ornaments';
import { Fonts } from '@/constants/theme';
import { useScheme, useTheme } from '@/hooks/use-theme';

// The brand pastels in light mode; warm darks, one step above the page, in dark mode.
const GROUNDS = {
  light: ['#FFCED8', '#FFDDDD', '#FFE8C4', '#FFF4DE'],
  dark: ['#4A3238', '#3A2C22', '#33252A', '#3B2B33'],
} as const;

/** The same work always gets the same ground. */
function groundIndex(id: string): number {
  let hash = 0;
  for (const char of id) {
    hash = (hash * 31 + char.charCodeAt(0)) | 0;
  }
  return Math.abs(hash) % GROUNDS.light.length;
}

type WorkCoverProps = {
  work: { id: string; title: string; type: WorkType };
  width: number;
  style?: StyleProp<ViewStyle>;
};

/**
 * A work's cover. Works have no cover image yet, so this one is drawn: a
 * pastel ground, a gold frame with corner scrolls and the title's first
 * letter as a monogram. It is decoration; whatever holds it names the work.
 */
export function WorkCover({ work, width, style }: WorkCoverProps) {
  const { t } = useTranslation();
  const theme = useTheme();
  const scheme = useScheme();
  const height = Math.round((width * 4) / 3);
  const inset = Math.max(3, Math.round(width * 0.05));
  const corner = Math.max(10, Math.round(width * 0.2));
  // The first character as the reader sees it: Array.from keeps a Hangul
  // syllable or a kana whole, where indexing would split a surrogate pair.
  const monogram = Array.from(work.title.trim())[0] ?? '';
  const band = Math.max(8, Math.round(width * 0.075));

  return (
    <View
      {...decorative}
      style={[
        styles.cover,
        { width, height, backgroundColor: GROUNDS[scheme][groundIndex(work.id)] },
        style,
      ]}>
      <View
        style={[
          styles.frame,
          { top: inset, right: inset, bottom: inset, left: inset, borderColor: theme.ornament },
        ]}>
        <View style={[styles.innerRule, { borderColor: theme.ornament }]} />
        {CORNER_POSITIONS.map((at) => (
          <Corner key={at} at={at} color={theme.ornament} size={corner} />
        ))}
        <Text
          style={[
            styles.monogram,
            { color: theme.accent, fontSize: Math.round(width * 0.46), lineHeight: Math.round(width * 0.6) },
          ]}>
          {monogram}
        </Text>
        <Text
          numberOfLines={1}
          style={[
            styles.band,
            { color: theme.textSecondary, fontSize: band, bottom: Math.round(height * 0.07) },
          ]}>
          {t(`workType.${work.type}`)}
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  cover: {
    borderRadius: 4,
    overflow: 'hidden',
  },
  frame: {
    position: 'absolute',
    borderWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  innerRule: {
    position: 'absolute',
    top: 3,
    right: 3,
    bottom: 3,
    left: 3,
    borderWidth: StyleSheet.hairlineWidth,
    opacity: 0.6,
  },
  monogram: {
    fontFamily: Fonts.display,
    textAlign: 'center',
  },
  band: {
    position: 'absolute',
    left: 0,
    right: 0,
    fontFamily: Fonts.engraved,
    letterSpacing: 1.5,
    textAlign: 'center',
    textTransform: 'uppercase',
  },
});
