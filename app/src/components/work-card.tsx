import { Link } from 'expo-router';
import { Pressable, StyleSheet, View } from 'react-native';
import { useTranslation } from 'react-i18next';

import type { WorkCard as Work } from '@/api/generated';
import { Chip } from '@/components/chip';
import { ThemedText } from '@/components/themed-text';
import { Radius, Spacing } from '@/constants/theme';
import { useCardStyle, useTheme } from '@/hooks/use-theme';
import { formatDate, genreName } from '@/i18n';

const SEPARATOR = ' · ';

/** A work in a list. Opens the work's page. */
export function WorkCard({ work }: { work: Work }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const card = useCardStyle();

  return (
    <Link href={{ pathname: '/works/[workId]', params: { workId: work.id } }} asChild>
      <Pressable
        accessibilityRole="link"
        accessibilityLabel={work.title}
        style={styles.fill}>
        {/* The card's look sits on a View: on web, <Link asChild> drops a Pressable's style function. */}
        <View style={[styles.card, card]}>
          <View style={[styles.kind, { backgroundColor: theme.highlight }]}>
            <ThemedText type="smallBold" themeColor="textSecondary">
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
      </Pressable>
    </Link>
  );
}

const styles = StyleSheet.create({
  fill: {
    flex: 1,
  },
  card: {
    flex: 1,
    padding: Spacing.three,
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
    fontSize: 19,
    lineHeight: 26,
    fontWeight: 800,
  },
  genres: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.two,
    marginVertical: Spacing.one,
  },
});
