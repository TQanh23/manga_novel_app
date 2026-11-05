import { Link } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { useTranslation } from 'react-i18next';

import type { WorkCard } from '@/api/generated';
import { ThemedText } from '@/components/themed-text';
import { WorkCover } from '@/components/work-cover';
import { Fonts, Spacing } from '@/constants/theme';
import { useLayout } from '@/hooks/use-layout';
import { useTheme } from '@/hooks/use-theme';
import { genreName } from '@/i18n';

const NUMERALS = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X'];
const SEPARATOR = ' · ';

/** The most popular works, ranked with Roman numerals. Two columns on a wide window. */
export function PopularList({ works }: { works: WorkCard[] }) {
  const { isWide } = useLayout();
  return (
    <View style={[styles.list, isWide && styles.columns]}>
      {works.map((work, index) => (
        <View key={work.id} style={isWide ? styles.half : undefined}>
          <RankedRow work={work} rank={index + 1} />
        </View>
      ))}
    </View>
  );
}

function RankedRow({ work, rank }: { work: WorkCard; rank: number }) {
  const { t } = useTranslation();
  const theme = useTheme();
  return (
    <Link href={{ pathname: '/works/[workId]', params: { workId: work.id } }} asChild>
      <Pressable
        accessibilityRole="link"
        accessibilityLabel={`${t('home.rank', { rank })}: ${work.title}`}
        // One flat style: <Link asChild> refuses an array, and drops a function on web.
        style={StyleSheet.flatten([styles.row, { borderBottomColor: theme.border }])}>
        <Text
          {...{ accessibilityElementsHidden: true, importantForAccessibility: 'no' as const }}
          style={[styles.numeral, { color: theme.ornament }]}>
          {NUMERALS[rank - 1] ?? String(rank)}
        </Text>
        <WorkCover work={work} width={60} />
        <View style={styles.text}>
          <ThemedText numberOfLines={2} style={styles.title}>
            {work.title}
          </ThemedText>
          <ThemedText type="small" themeColor="textSecondary" numberOfLines={1}>
            {t('work.by', { author: work.author.display_name })}
          </ThemedText>
          {work.genres.length > 0 ? (
            <ThemedText type="eyebrow" themeColor="textSecondary" numberOfLines={1}>
              {work.genres.map((slug) => genreName(slug)).join(SEPARATOR)}
            </ThemedText>
          ) : null}
        </View>
      </Pressable>
    </Link>
  );
}

const styles = StyleSheet.create({
  list: {
    gap: Spacing.one,
  },
  columns: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    columnGap: Spacing.five,
  },
  half: {
    width: '47%',
    flexGrow: 1,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.three,
    paddingVertical: Spacing.two,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  numeral: {
    fontFamily: Fonts.display,
    fontSize: 30,
    lineHeight: 36,
    width: 52,
    textAlign: 'center',
  },
  text: {
    flex: 1,
    gap: Spacing.half,
  },
  title: {
    fontFamily: Fonts.display,
    fontSize: 18,
    lineHeight: 24,
  },
});
