import { Stack, useLocalSearchParams, useRouter } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, useColorScheme, View } from 'react-native';
import { useTranslation } from 'react-i18next';

import { catalogueGetWork, type EpisodeContentResponse, readerGetEpisodeContent } from '@/api/generated';
import { useLoad } from '@/api/hooks';
import { useSession } from '@/auth/session';
import { Button } from '@/components/form';
import { Page } from '@/components/page';
import { EmptyState, ErrorState, LoadingState } from '@/components/state-views';
import { Colors, Spacing } from '@/constants/theme';
import NovelView, { type NovelAppearance } from '@/reader/novel-view';
import { ContentsSheet } from '@/reader/contents-sheet';
import { type ReaderPanel, ReaderBar } from '@/reader/reader-bar';
import { FONT_SIZES, type ReaderSettings, useReaderSettings } from '@/reader/settings';
import { SettingsPanel } from '@/reader/settings-panel';
import { useProgressSaver } from '@/reader/use-progress-saver';

/** A novel episode, read paragraph by paragraph, opening where the reader left off (FR-RD-03). */
export default function ReadScreen() {
  const { t } = useTranslation();
  const router = useRouter();
  const { episodeId } = useLocalSearchParams<{ episodeId: string }>();
  const { user } = useSession();
  // The position in the answer is the signed-in reader's own, so a new reader asks again.
  const content = useLoad(`content:${episodeId}:${user?.id ?? 'guest'}`, () =>
    readerGetEpisodeContent({ path: { episode_id: episodeId } }),
  );

  const body = () => {
    if (content.isLoading) {
      return <LoadingState />;
    }
    if (content.error === 'episode_locked') {
      return (
        <View style={styles.message}>
          <EmptyState message={t('reader.locked')} />
          <Button label={t('reader.back')} variant="secondary" onPress={() => router.back()} />
        </View>
      );
    }
    if (content.error === 'episode_not_found') {
      return <EmptyState message={t('reader.notFound')} />;
    }
    if (content.error === 'not_a_novel') {
      return <EmptyState message={t('reader.notANovel')} />;
    }
    if (content.error || !content.data) {
      return <ErrorState code={content.error ?? 'unknown'} onRetry={content.reload} />;
    }
    return <Reader key={content.data.id} episode={content.data} signedIn={user !== null} />;
  };

  const title = content.data
    ? t('reader.heading', { number: content.data.number, title: content.data.title })
    : t('reader.title');
  return (
    // Full width: the text sets its own measure, and the bar runs edge to edge.
    <Page full>
      <Stack.Screen options={{ title }} />
      {body()}
    </Page>
  );
}

function Reader({ episode, signedIn }: { episode: EpisodeContentResponse; signedIn: boolean }) {
  const { t } = useTranslation();
  const router = useRouter();
  const { settings } = useReaderSettings();
  const [panel, setPanel] = useState<ReaderPanel>('none');
  const appearance = useAppearance(settings);
  const savePosition = useProgressSaver({
    episodeId: episode.id,
    saved: episode.position,
    enabled: signedIn,
  });
  // The work's name heads the chapter. The text waits for it (or for its
  // failure), because the page is built once and a heading added later
  // would move the reader's place.
  const work = useLoad(`work:${episode.work_id}`, () =>
    catalogueGetWork({ path: { work_id: episode.work_id } }),
  );
  // The author may have published a shorter text since the position was saved.
  const start = Math.min(episode.position ?? 0, Math.max(0, episode.paragraphs.length - 1));
  // How far down the text the reader is, for the bar; the view reports it as they scroll.
  const [percent, setPercent] = useState(0);

  if (episode.paragraphs.length === 0) {
    return <EmptyState message={t('reader.empty')} />;
  }
  const open = (id: string) => router.replace({ pathname: '/read/[episodeId]', params: { episodeId: id } });
  const workTitle = work.data?.title ?? null;
  const episodeLabel = t('work.episodeNumber', { number: episode.number });

  return (
    <View style={[styles.reader, { backgroundColor: appearance.background }]}>
      {workTitle ? <Stack.Screen options={{ title: workTitle }} /> : null}
      <View style={styles.text}>
        {work.isLoading ? (
          <LoadingState />
        ) : (
          <NovelView
            paragraphs={episode.paragraphs}
            initialPosition={start}
            appearance={appearance}
            onPosition={savePosition}
            onProgress={setPercent}
            heading={{
              eyebrow: workTitle ? `${workTitle} · ${episodeLabel}` : episodeLabel,
              title: episode.title,
              end: t('reader.endOfEpisode', { number: episode.number }),
            }}
          />
        )}
      </View>
      {panel === 'none' ? null : (
        // Panels keep to the text's column, centred, now that the reader spans the window.
        <View style={styles.panels}>
          {panel === 'settings' ? <SettingsPanel /> : null}
          {panel === 'contents' ? (
            <ContentsSheet workId={episode.work_id} workTitle={workTitle} currentId={episode.id} />
          ) : null}
        </View>
      )}
      <ReaderBar
        number={episode.number}
        percent={percent}
        colors={appearance}
        panel={panel}
        onPanel={setPanel}
        onPrevious={episode.previous_episode_id ? () => open(episode.previous_episode_id as string) : null}
        onNext={episode.next_episode_id ? () => open(episode.next_episode_id as string) : null}
      />
    </View>
  );
}

/** The reader's own colours and type, apart from the app's theme. */
function useAppearance(settings: ReaderSettings): NovelAppearance & { bar: string } {
  const scheme = useColorScheme();
  const theme = settings.theme === 'system' ? (scheme === 'dark' ? 'dark' : 'light') : settings.theme;
  const colors = Colors[theme];
  return {
    font: settings.font,
    fontSize: FONT_SIZES[settings.size],
    text: colors.text,
    background: colors.background,
    muted: colors.textSecondary,
    ornament: colors.ornament,
    bar: colors.surface,
  };
}

const styles = StyleSheet.create({
  reader: {
    flex: 1,
  },
  text: {
    flex: 1,
  },
  message: {
    alignItems: 'center',
    gap: Spacing.three,
  },
  panels: {
    alignItems: 'center',
    padding: Spacing.two,
  },
});
