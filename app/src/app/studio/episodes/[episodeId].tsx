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
  type EpisodeVersionSummary,
} from '@/api/generated';
import { useLoad } from '@/api/hooks';
import { Button, ErrorText, TextField } from '@/components/form';
import { Page } from '@/components/page';
import { EmptyState, ErrorState, LoadingState } from '@/components/state-views';
import { ThemedText } from '@/components/themed-text';
import { Danger, Spacing } from '@/constants/theme';
import { errorMessageKey, formatTime } from '@/i18n';
import { PublishPanel } from '@/studio/publish-panel';
import RichTextEditor from '@/studio/rich-text-editor';
import { type DraftStatus, useDraftSaver } from '@/studio/use-draft-saver';
import { VersionHistory } from '@/studio/version-history';

const MAX_TITLE = 200;

/**
 * Write an episode: its title, its text with autosave, its versions, and
 * publishing it now or later (FR-NV-01, FR-NV-02, D13).
 */
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
  const { t } = useTranslation();
  const { status, change, settle, reset } = useDraftSaver({
    episodeId: episode.id,
    savedHtml: draft.body_html,
    savedAt: draft.saved_at,
  });
  // The text as the author left it. The editor reopens on it after the history.
  const [html, setHtml] = useState(draft.body_html);
  const [mode, setMode] = useState<'write' | 'opening' | 'history'>('write');
  // Each one may be a change readers have not seen yet.
  const [edits, setEdits] = useState(0);

  const write = (next: string) => {
    setHtml(next);
    setEdits((count) => count + 1);
    change(next);
  };

  // What is typed goes in first, so the history ends with it.
  const openHistory = async () => {
    setMode('opening');
    await settle();
    setMode('history');
  };

  const restored = (text: string, version: EpisodeVersionSummary) => {
    reset(text, version.created_at);
    setHtml(text);
    setEdits((count) => count + 1);
    setMode('write');
  };

  return (
    <View style={styles.fill}>
      <View style={styles.header}>
        <EpisodeTitle episode={episode} />
        <PublishPanel episode={episode} edits={edits} settle={settle} />
        <View style={styles.statusRow}>
          <View style={styles.status}>
            <SaveStatus status={status} />
          </View>
          {mode === 'history' ? (
            <Button
              label={t('studio.history.close')}
              variant="secondary"
              onPress={() => setMode('write')}
            />
          ) : (
            <Button
              label={t('studio.history.open')}
              variant="secondary"
              busy={mode === 'opening'}
              onPress={() => void openHistory()}
            />
          )}
        </View>
      </View>
      {mode === 'history' ? (
        <VersionHistory episodeId={episode.id} onRestored={restored} />
      ) : (
        <RichTextEditor initialHtml={html} onChange={write} />
      )}
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
  statusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.two,
  },
  status: {
    flex: 1,
  },
  failed: {
    color: Danger,
  },
});
