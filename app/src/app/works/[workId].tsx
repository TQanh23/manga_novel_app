import { Stack, useLocalSearchParams } from 'expo-router';
import { ScrollView, StyleSheet, View } from 'react-native';
import { useTranslation } from 'react-i18next';

import {
  catalogueGetWork,
  catalogueListEpisodes,
  type LibraryResponse,
  readerGetLibrary,
} from '@/api/generated';
import { useLoad } from '@/api/hooks';
import { useSession } from '@/auth/session';
import { Chip } from '@/components/chip';
import { Page } from '@/components/page';
import { EmptyState, ErrorState, LoadingState } from '@/components/state-views';
import { ThemedText } from '@/components/themed-text';
import { Spacing } from '@/constants/theme';
import { EpisodeTable } from '@/work/episode-table';
import { MoreLikeThis } from '@/work/more-like-this';
import { Synopsis } from '@/work/synopsis';
import { WorkHero } from '@/work/work-hero';

/**
 * A work's page (FR-RD-02): cover and facts, how far the reader has got,
 * what it is about, its episodes, and what to read after it.
 */
export default function WorkScreen() {
  const { t } = useTranslation();
  const { workId } = useLocalSearchParams<{ workId: string }>();

  const work = useLoad(`work:${workId}`, () => catalogueGetWork({ path: { work_id: workId } }));
  const episodes = useLoad(`episodes:${workId}`, () =>
    catalogueListEpisodes({ path: { work_id: workId } }),
  );
  // Whether the work is a favourite and where the reader is in it. A guest has no library.
  const { user } = useSession();
  const library = useLoad<LibraryResponse | null>(`library:${user?.id ?? 'guest'}`, () =>
    user ? readerGetLibrary() : Promise.resolve({ data: null }),
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
    const reading = library.data?.reading.find((entry) => entry.work.id === workId);
    return (
      <View style={styles.details}>
        <WorkHero
          work={work.data}
          episodes={episodes.data}
          // Without its library (still loading, or it failed) the page still works:
          // reading starts at episode 1 and the favourite button waits.
          library={library.data}
          reading={reading}
          signedIn={user !== null}
        />
        {work.data.synopsis ? <Synopsis text={work.data.synopsis} /> : null}
        {work.data.tags.length > 0 ? (
          <View style={styles.section}>
            <ThemedText type="eyebrow" themeColor="textSecondary">
              {t('work.tags')}
            </ThemedText>
            <View style={styles.chips}>
              {work.data.tags.map((tag) => (
                <Chip key={tag} label={tag} />
              ))}
            </View>
          </View>
        ) : null}
        <EpisodeTable episodes={episodes.data} readingId={reading?.episode_id} />
        <MoreLikeThis work={work.data} />
      </View>
    );
  };

  return (
    <Page>
      <Stack.Screen options={{ title: work.data?.title ?? t('work.title') }} />
      <ScrollView contentContainerStyle={styles.content}>{body()}</ScrollView>
    </Page>
  );
}

const styles = StyleSheet.create({
  content: {
    padding: Spacing.three,
    paddingBottom: Spacing.six,
  },
  details: {
    gap: Spacing.five,
  },
  section: {
    gap: Spacing.two,
  },
  chips: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.two,
  },
});
