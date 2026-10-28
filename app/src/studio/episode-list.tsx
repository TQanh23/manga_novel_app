import { Link, useRouter } from 'expo-router';
import { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { useTranslation } from 'react-i18next';

import { errorCode } from '@/api/client';
import { authorCreateEpisode, authorListEpisodes, type EpisodeResponse } from '@/api/generated';
import { useLoad } from '@/api/hooks';
import { Button, ErrorText, TextField } from '@/components/form';
import { EmptyState, ErrorState, LoadingState } from '@/components/state-views';
import { ThemedText } from '@/components/themed-text';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { useVisit } from '@/hooks/use-visit';
import { errorMessageKey, formatDateTime } from '@/i18n';

const SEPARATOR = ' · ';
const MAX_TITLE = 200;

/** A work's episodes, drafts and all, and the way to add the next one (FR-NV-01). */
export function EpisodeList({ workId }: { workId: string }) {
  const { t } = useTranslation();
  // Coming back from the editor shows what was saved there.
  const visit = useVisit();
  const episodes = useLoad(`author-episodes:${workId}:${visit}`, () =>
    authorListEpisodes({ path: { work_id: workId } }),
  );

  const body = () => {
    if (episodes.isLoading) {
      return <LoadingState />;
    }
    if (episodes.error || !episodes.data) {
      return <ErrorState code={episodes.error ?? 'unknown'} onRetry={episodes.reload} />;
    }
    if (episodes.data.length === 0) {
      return <EmptyState message={t('studio.noEpisodes')} />;
    }
    return episodes.data.map((episode) => <EpisodeRow key={episode.id} episode={episode} />);
  };

  return (
    <View style={styles.section}>
      <ThemedText type="smallBold" accessibilityRole="header">
        {t('studio.episodes')}
      </ThemedText>
      {body()}
      <NewEpisode workId={workId} />
    </View>
  );
}

function EpisodeRow({ episode }: { episode: EpisodeResponse }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const status =
    episode.status === 'scheduled' && episode.publish_at
      ? t('studio.episodeStatus.scheduled', { date: formatDateTime(episode.publish_at) })
      : t(`studio.episodeStatus.${episode.status}`);
  const state = episode.has_unpublished_changes ? [status, t('studio.unpublishedChanges')] : [status];

  return (
    <Link href={{ pathname: '/studio/episodes/[episodeId]', params: { episodeId: episode.id } }} asChild>
      <Pressable
        accessibilityRole="link"
        accessibilityLabel={episode.title}
        style={({ pressed }) => [
          styles.row,
          { backgroundColor: theme.backgroundElement },
          pressed && styles.pressed,
        ]}>
        <ThemedText type="small" themeColor="textSecondary">
          {t('work.episodeNumber', { number: episode.number })}
        </ThemedText>
        <ThemedText>{episode.title}</ThemedText>
        <ThemedText type="smallBold" themeColor="textSecondary">
          {state.join(SEPARATOR)}
        </ThemedText>
      </Pressable>
    </Link>
  );
}

/** Names the next episode and opens it in the editor. */
function NewEpisode({ workId }: { workId: string }) {
  const { t } = useTranslation();
  const router = useRouter();
  const [title, setTitle] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const add = async () => {
    setBusy(true);
    setError(null);
    const result = await authorCreateEpisode({
      path: { work_id: workId },
      body: { title: title.trim() },
    }).catch(() => null);
    setBusy(false);
    if (!result?.data) {
      setError(result ? errorCode(result.error) : 'network_error');
      return;
    }
    setTitle('');
    router.push({ pathname: '/studio/episodes/[episodeId]', params: { episodeId: result.data.id } });
  };

  return (
    <View style={styles.section}>
      <TextField
        label={t('studio.newEpisodeTitle')}
        value={title}
        maxLength={MAX_TITLE}
        onChangeText={setTitle}
      />
      {error ? <ErrorText>{t(errorMessageKey(error))}</ErrorText> : null}
      <Button
        label={t('studio.addEpisode')}
        variant="secondary"
        busy={busy}
        disabled={busy || !title.trim()}
        onPress={() => void add()}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  section: {
    gap: Spacing.three,
  },
  row: {
    borderRadius: Spacing.two,
    padding: Spacing.three,
    gap: Spacing.half,
  },
  pressed: {
    opacity: 0.7,
  },
});
