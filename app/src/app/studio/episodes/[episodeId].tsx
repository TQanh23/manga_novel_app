import { Stack, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { useTranslation } from 'react-i18next';

import { errorCode } from '@/api/client';
import {
  authorGetDraft,
  authorGetEpisode,
  authorUpdateEpisode,
  type EpisodeDraft,
  type EpisodeResponse,
} from '@/api/generated';
import { useLoad } from '@/api/hooks';
import { ErrorText, TextField } from '@/components/form';
import { Page } from '@/components/page';
import { EmptyState, ErrorState, LoadingState } from '@/components/state-views';
import { ThemedText } from '@/components/themed-text';
import { Danger, Spacing } from '@/constants/theme';
import { errorMessageKey, formatTime } from '@/i18n';
import RichTextEditor from '@/studio/rich-text-editor';
import { type DraftStatus, useDraftSaver } from '@/studio/use-draft-saver';

const MAX_TITLE = 200;

/** Write an episode: its title, and its text with autosave (FR-NV-01, D13). */
export default function EpisodeEditorScreen() {
  const { t } = useTranslation();
  const { episodeId } = useLocalSearchParams<{ episodeId: string }>();
  const episode = useLoad(`author-episode:${episodeId}`, () =>
    authorGetEpisode({ path: { episode_id: episodeId } }),
  );
  const draft = useLoad(`author-draft:${episodeId}`, () =>
    authorGetDraft({ path: { episode_id: episodeId } }),
  );

  const body = () => {
    if (episode.isLoading || draft.isLoading) {
      return <LoadingState />;
    }
    // Another author's episode answers exactly like one that does not exist.
    if (episode.error === 'episode_not_found') {
      return <EmptyState message={t('studio.episode.notFound')} />;
    }
    if (episode.error || !episode.data) {
      return <ErrorState code={episode.error ?? 'unknown'} onRetry={episode.reload} />;
    }
    // A manga episode has pages, not text; uploading them comes with Phase 2.
    if (draft.error === 'not_a_novel') {
      return (
        <View style={styles.header}>
          <EpisodeTitle episode={episode.data} />
          <EmptyState message={t('studio.episode.manga')} />
        </View>
      );
    }
    if (draft.error || !draft.data) {
      return <ErrorState code={draft.error ?? 'unknown'} onRetry={draft.reload} />;
    }
    return <EpisodeEditor key={episodeId} episode={episode.data} draft={draft.data} />;
  };

  return (
    <Page>
      <Stack.Screen
        options={{
          title: episode.data
            ? t('work.episodeNumber', { number: episode.data.number })
            : t('studio.episode.text'),
        }}
      />
      {body()}
    </Page>
  );
}

function EpisodeEditor({ episode, draft }: { episode: EpisodeResponse; draft: EpisodeDraft }) {
  const { status, change } = useDraftSaver({
    episodeId: episode.id,
    savedHtml: draft.body_html,
    savedAt: draft.saved_at,
  });

  return (
    <View style={styles.fill}>
      <View style={styles.header}>
        <EpisodeTitle episode={episode} />
        <SaveStatus status={status} />
      </View>
      <RichTextEditor initialHtml={draft.body_html} onChange={change} />
    </View>
  );
}

/** The episode's title, saved when the author leaves the field. */
function EpisodeTitle({ episode }: { episode: EpisodeResponse }) {
  const { t } = useTranslation();
  const [title, setTitle] = useState(episode.title);
  const [saved, setSaved] = useState(episode.title);
  const [error, setError] = useState<string | null>(null);

  const save = async () => {
    const next = title.trim();
    if (!next || next === saved) {
      setTitle(saved);
      return;
    }
    const result = await authorUpdateEpisode({
      path: { episode_id: episode.id },
      body: { title: next },
    }).catch(() => null);
    if (!result?.data) {
      setError(result ? errorCode(result.error) : 'network_error');
      return;
    }
    setError(null);
    setSaved(result.data.title);
    setTitle(result.data.title);
  };

  return (
    <>
      <TextField
        label={t('studio.episode.title')}
        value={title}
        maxLength={MAX_TITLE}
        onChangeText={setTitle}
        onBlur={() => void save()}
        onSubmitEditing={() => void save()}
      />
      {error ? <ErrorText>{t(errorMessageKey(error))}</ErrorText> : null}
    </>
  );
}

function SaveStatus({ status }: { status: DraftStatus }) {
  const { t } = useTranslation();
  const text = (() => {
    switch (status.kind) {
      case 'saved':
        return status.savedAt
          ? t('studio.editor.saved', { time: formatTime(status.savedAt) })
          : t('studio.editor.nothingSaved');
      case 'unsaved':
        return t('studio.editor.unsaved');
      case 'saving':
        return t('studio.editor.saving');
      case 'failed':
        return t('studio.editor.failed', { reason: t(errorMessageKey(status.error)) });
    }
  })();
  return (
    <ThemedText
      type="small"
      themeColor="textSecondary"
      accessibilityLiveRegion="polite"
      style={status.kind === 'failed' ? styles.failed : undefined}>
      {text}
    </ThemedText>
  );
}

const styles = StyleSheet.create({
  fill: {
    flex: 1,
  },
  header: {
    padding: Spacing.three,
    gap: Spacing.two,
  },
  failed: {
    color: Danger,
  },
});
