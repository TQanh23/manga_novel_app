import { Link } from 'expo-router';
import { Pressable, StyleSheet, View } from 'react-native';
import { useTranslation } from 'react-i18next';

import type { WorkCard as Work } from '@/api/generated';
import { Chip } from '@/components/chip';
import { OrnateFrame } from '@/components/ornaments';
import { ThemedText } from '@/components/themed-text';
import { WorkCover } from '@/components/work-cover';
import { Fonts, Radius, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { formatDate, genreName } from '@/i18n';

const SEPARATOR = ' · ';
const COVER_WIDTH = 84;

/** A work in a list. Opens the work's page. */
export function WorkCard({ work }: { work: Work }) {
  const { t } = useTranslation();
  const theme = useTheme();

  return (
    <Link href={{ pathname: '/works/[workId]', params: { workId: work.id } }} asChild>
      <Pressable
        accessibilityRole="link"
        accessibilityLabel={work.title}
        style={styles.fill}>
        {/* The frame sits inside: on web, <Link asChild> drops a Pressable's style function. */}
        <OrnateFrame style={styles.card} frameStyle={styles.fill}>
          <WorkCover work={work} width={COVER_WIDTH} />
          <View style={styles.text}>
          <View style={[styles.kind, { backgroundColor: theme.highlight }]}>
            <ThemedText type="eyebrow" themeColor="textSecondary">
              {[t(`workType.${work.type}`), t(`workStatus.${work.status}`)].join(SEPARATOR)}
            </ThemedText>
          </View>
          <ThemedText style={styles.title}>{work.title}</ThemedText>
          <ThemedText type="small" themeColor="textSecondary">
            {t('work.by', { author: work.author.display_name })}
          </ThemedText>
          {work.genres.length > 0 ? (
            <View style={styles.genres}>
              {work.genres.map((slug) => (
                <Chip key={slug} label={genreName(slug)} />
              ))}
            </View>
          ) : null}
          <ThemedText type="small" themeColor="textSecondary">
            {[
              t('catalogue.episodeCount', { count: work.episode_count }),
              t('catalogue.updated', { date: formatDate(work.last_published_at) }),
            ].join(SEPARATOR)}
          </ThemedText>
          </View>
        </OrnateFrame>
      </Pressable>
    </Link>
  );
}

const styles = StyleSheet.create({
  // Grow to fill a grid cell, but never below the content's height.
  fill: {
    flexGrow: 1,
  },
  card: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    padding: Spacing.three,
    gap: Spacing.three,
  },
  text: {
    flex: 1,
    gap: Spacing.one,
  },
  kind: {
    alignSelf: 'flex-start',
    borderRadius: Radius.pill,
    paddingHorizontal: Spacing.two + Spacing.one,
    paddingVertical: Spacing.half,
    marginBottom: Spacing.one,
  },
  pressed: {
    opacity: 0.7,
  },
  title: {
    fontFamily: Fonts.display,
    fontSize: 21,
    lineHeight: 30,
    fontWeight: 'normal',
  },
  genres: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.two,
    marginVertical: Spacing.one,
  },
});
