import { Link } from 'expo-router';
import { Pressable, StyleSheet, View } from 'react-native';
import { useTranslation } from 'react-i18next';

import type { WorkCard as Work } from '@/api/generated';
import { Chip } from '@/components/chip';
import { ThemedText } from '@/components/themed-text';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { formatDate, genreName } from '@/i18n';

const SEPARATOR = ' · ';

/** A work in a list. Opens the work's page. */
export function WorkCard({ work }: { work: Work }) {
  const { t } = useTranslation();
  const theme = useTheme();

  return (
    <Link href={{ pathname: '/works/[workId]', params: { workId: work.id } }} asChild>
      <Pressable
        accessibilityRole="link"
        accessibilityLabel={work.title}
        style={({ pressed }) => [
          styles.card,
          { backgroundColor: theme.backgroundElement },
          pressed && styles.pressed,
        ]}>
        <ThemedText type="smallBold" themeColor="textSecondary">
          {[t(`workType.${work.type}`), t(`workStatus.${work.status}`)].join(SEPARATOR)}
        </ThemedText>
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
      </Pressable>
    </Link>
  );
}

const styles = StyleSheet.create({
  card: {
    borderRadius: Spacing.three,
    padding: Spacing.three,
    gap: Spacing.one,
  },
  pressed: {
    opacity: 0.7,
  },
  title: {
    fontSize: 18,
    fontWeight: 700,
  },
  genres: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.two,
    marginVertical: Spacing.one,
  },
});
