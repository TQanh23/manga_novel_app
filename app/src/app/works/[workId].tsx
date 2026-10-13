import { Stack, useLocalSearchParams } from 'expo-router';
import { ScrollView, StyleSheet, View } from 'react-native';
import { useTranslation } from 'react-i18next';

import {
  catalogueGetWork,
  catalogueListEpisodes,
  type EpisodeSummary,
  type WorkDetail,
} from '@/api/generated';
import { useLoad } from '@/api/hooks';
import { Chip } from '@/components/chip';
import { Page } from '@/components/page';
import { EmptyState, ErrorState, LoadingState } from '@/components/state-views';
import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { Spacing } from '@/constants/theme';
import { formatDate, genreName } from '@/i18n';

const SEPARATOR = ' · ';

/** A work's page: what it is about, and its published episodes. */
export default function WorkScreen() {
  const { t } = useTranslation();
  const { workId } = useLocalSearchParams<{ workId: string }>();

  const work = useLoad(`work:${workId}`, () => catalogueGetWork({ path: { work_id: workId } }));
  const episodes = useLoad(`episodes:${workId}`, () =>
    catalogueListEpisodes({ path: { work_id: workId } }),
  );

  const body = () => {
    if (work.isLoading || episodes.isLoading) {
      return <LoadingState />;
    }
    // A work with nothing published answers exactly like one that does not exist.
    if (work.error === 'work_not_found' || episodes.error === 'work_not_found') {
      return <EmptyState message={t('work.notFound')} />;
    }
    const error = work.error ?? episodes.error;
    if (error || !work.data || !episodes.data) {
      return (
        <ErrorState
          code={error ?? 'unknown'}
          onRetry={() => {
            work.reload();
            episodes.reload();
          }}
        />
      );
    }
    return <WorkDetails work={work.data} episodes={episodes.data} />;
  };

  return (
    <Page>
      <Stack.Screen options={{ title: work.data?.title ?? t('work.title') }} />
      <ScrollView contentContainerStyle={styles.content}>{body()}</ScrollView>
    </Page>
  );
}

function WorkDetails({ work, episodes }: { work: WorkDetail; episodes: EpisodeSummary[] }) {
  const { t } = useTranslation();
  return (
    <View style={styles.details}>
      <ThemedText type="smallBold" themeColor="textSecondary">
        {[t(`workType.${work.type}`), t(`workStatus.${work.status}`)].join(SEPARATOR)}
      </ThemedText>
      <ThemedText type="subtitle" accessibilityRole="header">
        {work.title}
      </ThemedText>
      <ThemedText themeColor="textSecondary">
        {t('work.by', { author: work.author.display_name })}
      </ThemedText>

      {work.genres.length > 0 ? (
        <View style={styles.chips}>
          {work.genres.map((slug) => (
            <Chip key={slug} label={genreName(slug)} />
          ))}
        </View>
      ) : null}

      {work.synopsis ? <ThemedText>{work.synopsis}</ThemedText> : null}

      {work.tags.length > 0 ? (
        <View style={styles.section}>
          <ThemedText type="small" themeColor="textSecondary">
            {t('work.tags')}
          </ThemedText>
          <View style={styles.chips}>
            {work.tags.map((tag) => (
              <Chip key={tag} label={tag} />
            ))}
          </View>
        </View>
      ) : null}

      <View style={styles.section}>
        <ThemedText type="smallBold">
          {[t('work.episodes'), t('catalogue.episodeCount', { count: episodes.length })].join(
            SEPARATOR,
          )}
        </ThemedText>
        {episodes.map((episode) => (
          <EpisodeRow key={episode.id} episode={episode} />
        ))}
      </View>
    </View>
  );
}

function EpisodeRow({ episode }: { episode: EpisodeSummary }) {
  const { t } = useTranslation();
  const price =
    episode.price_coins === 0 ? t('work.free') : t('work.coins', { count: episode.price_coins });
  const terms = episode.wuf_eligible ? [price, t('work.waitUntilFree')] : [price];

  return (
    <ThemedView type="backgroundElement" style={styles.episode}>
      <ThemedText type="small" themeColor="textSecondary">
        {[t('work.episodeNumber', { number: episode.number }), formatDate(episode.publish_at)].join(
          SEPARATOR,
        )}
      </ThemedText>
      <ThemedText>{episode.title}</ThemedText>
      <ThemedText type="smallBold" themeColor="textSecondary">
        {terms.join(SEPARATOR)}
      </ThemedText>
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  content: {
    padding: Spacing.three,
    paddingBottom: Spacing.five,
  },
  details: {
    gap: Spacing.three,
  },
  section: {
    gap: Spacing.two,
  },
  chips: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.two,
  },
  episode: {
    borderRadius: Spacing.two,
    padding: Spacing.three,
    gap: Spacing.half,
  },
});
