import { Link, Stack, useLocalSearchParams, useRouter } from 'expo-router';
import { type ReactNode, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { useTranslation } from 'react-i18next';

import { errorCode } from '@/api/client';
import {
  catalogueGetWork,
  catalogueListEpisodes,
  type EpisodeSummary,
  type LibraryResponse,
  readerAddFavourite,
  readerGetLibrary,
  readerRemoveFavourite,
  type WorkDetail,
} from '@/api/generated';
import { useLoad } from '@/api/hooks';
import { useSession } from '@/auth/session';
import { Chip } from '@/components/chip';
import { Button, ErrorText } from '@/components/form';
import { Page } from '@/components/page';
import { EmptyState, ErrorState, LoadingState } from '@/components/state-views';
import { ThemedText } from '@/components/themed-text';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { errorMessageKey, formatDate, genreName } from '@/i18n';

const SEPARATOR = ' · ';

/** A work's page: what it is about, and its published episodes. */
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
    return (
      <WorkDetails
        work={work.data}
        episodes={episodes.data}
        actions={
          <ReaderActions
            workId={work.data.id}
            episodes={episodes.data}
            // Without its library (still loading, or it failed) the page still works:
            // reading starts at episode 1 and the favourite button waits.
            library={library.data}
            signedIn={user !== null}
          />
        }
      />
    );
  };

  return (
    <Page>
      <Stack.Screen options={{ title: work.data?.title ?? t('work.title') }} />
      <ScrollView contentContainerStyle={styles.content}>{body()}</ScrollView>
    </Page>
  );
}

type WorkDetailsProps = {
  work: WorkDetail;
  episodes: EpisodeSummary[];
  actions: ReactNode;
};

function WorkDetails({ work, episodes, actions }: WorkDetailsProps) {
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
      {actions}

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

type ReaderActionsProps = {
  workId: string;
  episodes: EpisodeSummary[];
  library: LibraryResponse | null;
  signedIn: boolean;
};

/** Read on (or start), and keep the work as a favourite (FR-RD-05). */
function ReaderActions({ workId, episodes, library, signedIn }: ReaderActionsProps) {
  const { t } = useTranslation();
  const router = useRouter();
  // What the reader set here; until they do, what their library says.
  const [chosen, setChosen] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reading = library?.reading.find((entry) => entry.work.id === workId);
  const favourite = chosen ?? library?.favourites.some((work) => work.id === workId) ?? false;
  const first = episodes[0];

  const toggleFavourite = async () => {
    const next = !favourite;
    setChosen(next);
    setBusy(true);
    setError(null);
    const call = next ? readerAddFavourite : readerRemoveFavourite;
    const failure = await call({ path: { work_id: workId } }).then(
      ({ error: failed }) => (failed === undefined ? null : errorCode(failed)),
      () => 'network_error',
    );
    if (failure) {
      // Put the button back as it was.
      setChosen(!next);
      setError(failure);
    }
    setBusy(false);
  };

  const read = (episodeId: string) =>
    router.push({ pathname: '/read/[episodeId]', params: { episodeId } });

  return (
    <View style={styles.actions}>
      {reading ? (
        <Button
          label={t('work.continue', { number: reading.episode_number })}
          onPress={() => read(reading.episode_id)}
        />
      ) : first ? (
        <Button label={t('work.start')} onPress={() => read(first.id)} />
      ) : null}
      {signedIn ? (
        <Button
          label={favourite ? t('work.unfavourite') : t('work.favourite')}
          variant="secondary"
          busy={busy}
          disabled={busy || library === null}
          onPress={() => void toggleFavourite()}
        />
      ) : null}
      {error ? <ErrorText>{t(errorMessageKey(error))}</ErrorText> : null}
    </View>
  );
}

/** An episode in the list. Opens the reader. */
function EpisodeRow({ episode }: { episode: EpisodeSummary }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const price =
    episode.price_coins === 0 ? t('work.free') : t('work.coins', { count: episode.price_coins });
  const terms = episode.wuf_eligible ? [price, t('work.waitUntilFree')] : [price];

  return (
    <Link href={{ pathname: '/read/[episodeId]', params: { episodeId: episode.id } }} asChild>
      <Pressable
        accessibilityRole="link"
        accessibilityLabel={episode.title}
        style={({ pressed }) => [
          styles.episode,
          { backgroundColor: theme.backgroundElement },
          pressed && styles.pressed,
        ]}>
        <ThemedText type="small" themeColor="textSecondary">
          {[
            t('work.episodeNumber', { number: episode.number }),
            formatDate(episode.publish_at),
          ].join(SEPARATOR)}
        </ThemedText>
        <ThemedText>{episode.title}</ThemedText>
        <ThemedText type="smallBold" themeColor="textSecondary">
          {terms.join(SEPARATOR)}
        </ThemedText>
      </Pressable>
    </Link>
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
  pressed: {
    opacity: 0.7,
  },
  actions: {
    gap: Spacing.two,
  },
});
