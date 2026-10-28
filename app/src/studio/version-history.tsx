import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { useTranslation } from 'react-i18next';

import { errorCode } from '@/api/client';
import {
  authorGetVersion,
  authorListVersions,
  authorRestoreVersion,
  type EpisodeVersionSummary,
} from '@/api/generated';
import { useLoad } from '@/api/hooks';
import { Button, ErrorText } from '@/components/form';
import { EmptyState, ErrorState, LoadingState } from '@/components/state-views';
import { ThemedText } from '@/components/themed-text';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { errorMessageKey, formatDateTime } from '@/i18n';
import NovelView from '@/reader/novel-view';

const SEPARATOR = ' · ';
const PAGE_SIZE = 50;

type VersionHistoryProps = {
  episodeId: string;
  /** Called once a restore has made a new version with `html`. */
  onRestored: (html: string, version: EpisodeVersionSummary) => void;
};

/** An episode's saved versions, newest first: look at one, and restore it (FR-NV-01). */
export function VersionHistory({ episodeId, onRestored }: VersionHistoryProps) {
  const [chosen, setChosen] = useState<{ version: EpisodeVersionSummary; isNewest: boolean } | null>(
    null,
  );

  if (chosen) {
    return (
      <VersionPreview
        episodeId={episodeId}
        version={chosen.version}
        isNewest={chosen.isNewest}
        onBack={() => setChosen(null)}
        onRestored={onRestored}
      />
    );
  }
  return (
    <VersionList
      episodeId={episodeId}
      onChoose={(version, isNewest) => setChosen({ version, isNewest })}
    />
  );
}

function VersionList({
  episodeId,
  onChoose,
}: {
  episodeId: string;
  onChoose: (version: EpisodeVersionSummary, isNewest: boolean) => void;
}) {
  const { t } = useTranslation();
  const first = useLoad(`versions:${episodeId}`, () =>
    authorListVersions({ path: { episode_id: episodeId }, query: { limit: PAGE_SIZE } }),
  );
  // Older pages, fetched on request. The history only grows at its top, so
  // continuing below the last one shown never skips or repeats a version.
  const [older, setOlder] = useState<EpisodeVersionSummary[]>([]);
  const [lastPage, setLastPage] = useState<EpisodeVersionSummary[] | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [moreError, setMoreError] = useState<string | null>(null);

  if (first.isLoading) {
    return <LoadingState />;
  }
  if (first.error || !first.data) {
    return <ErrorState code={first.error ?? 'unknown'} onRetry={first.reload} />;
  }
  if (first.data.length === 0) {
    return <EmptyState message={t('studio.history.empty')} />;
  }

  const versions = [...first.data, ...older];
  const hasMore = (lastPage ?? first.data).length === PAGE_SIZE;

  const loadMore = async () => {
    setLoadingMore(true);
    setMoreError(null);
    const result = await authorListVersions({
      path: { episode_id: episodeId },
      query: { limit: PAGE_SIZE, before: versions[versions.length - 1].id },
    }).catch(() => null);
    setLoadingMore(false);
    if (!result?.data) {
      setMoreError(result ? errorCode(result.error) : 'network_error');
      return;
    }
    setOlder((shown) => [...shown, ...result.data]);
    setLastPage(result.data);
  };

  return (
    <ScrollView contentContainerStyle={styles.list}>
      {versions.map((version, index) => (
        <VersionRow
          key={version.id}
          version={version}
          isNewest={index === 0}
          onPress={() => onChoose(version, index === 0)}
        />
      ))}
      {moreError ? <ErrorText>{t(errorMessageKey(moreError))}</ErrorText> : null}
      {hasMore ? (
        <Button
          label={t('catalogue.loadMore')}
          variant="secondary"
          busy={loadingMore}
          onPress={() => void loadMore()}
        />
      ) : null}
    </ScrollView>
  );
}

function badges(t: ReturnType<typeof useTranslation>['t'], isNewest: boolean, isPublished: boolean) {
  return [
    ...(isNewest ? [t('studio.history.current')] : []),
    ...(isPublished ? [t('studio.history.published')] : []),
  ];
}

function VersionRow({
  version,
  isNewest,
  onPress,
}: {
  version: EpisodeVersionSummary;
  isNewest: boolean;
  onPress: () => void;
}) {
  const { t } = useTranslation();
  const theme = useTheme();
  const when = formatDateTime(version.created_at);
  const marks = badges(t, isNewest, version.is_published);
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={when}
      onPress={onPress}
      style={({ pressed }) => [
        styles.row,
        { backgroundColor: theme.backgroundElement },
        pressed && styles.pressed,
      ]}>
      <ThemedText>{when}</ThemedText>
      {marks.length > 0 ? (
        <ThemedText type="smallBold" themeColor="textSecondary">
          {marks.join(SEPARATOR)}
        </ThemedText>
      ) : null}
    </Pressable>
  );
}

function VersionPreview({
  episodeId,
  version,
  isNewest,
  onBack,
  onRestored,
}: {
  episodeId: string;
  version: EpisodeVersionSummary;
  isNewest: boolean;
  onBack: () => void;
  onRestored: VersionHistoryProps['onRestored'];
}) {
  const { t } = useTranslation();
  const theme = useTheme();
  const detail = useLoad(`version:${version.id}`, () =>
    authorGetVersion({ path: { episode_id: episodeId, version_id: version.id } }),
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const restore = async (html: string) => {
    setBusy(true);
    setError(null);
    const result = await authorRestoreVersion({
      path: { episode_id: episodeId, version_id: version.id },
    }).catch(() => null);
    setBusy(false);
    if (!result?.data) {
      setError(result ? errorCode(result.error) : 'network_error');
      return;
    }
    onRestored(html, result.data);
  };

  const body = () => {
    if (detail.isLoading) {
      return <LoadingState />;
    }
    if (detail.error || !detail.data) {
      return <ErrorState code={detail.error ?? 'unknown'} onRetry={detail.reload} />;
    }
    const html = detail.data.body_html;
    return (
      <>
        {isNewest ? null : (
          <View style={styles.actions}>
            <ThemedText type="small" themeColor="textSecondary">
              {t('studio.history.restoreHint')}
            </ThemedText>
            {error ? <ErrorText>{t(errorMessageKey(error))}</ErrorText> : null}
            <Button
              label={t('studio.history.restore')}
              busy={busy}
              onPress={() => void restore(html)}
            />
          </View>
        )}
        <View style={styles.text}>
          {/* The whole text as one block: only the API decides what a paragraph is. */}
          <NovelView
            paragraphs={[html]}
            initialPosition={0}
            appearance={{
              font: 'sans',
              fontSize: 17,
              text: theme.text,
              background: theme.background,
              muted: theme.textSecondary,
            }}
            onPosition={() => {}}
          />
        </View>
      </>
    );
  };

  const marks = badges(t, isNewest, version.is_published);
  return (
    <View style={styles.fill}>
      <View style={styles.actions}>
        <Button label={t('studio.history.allVersions')} variant="secondary" onPress={onBack} />
        <ThemedText type="smallBold" accessibilityRole="header">
          {[formatDateTime(version.created_at), ...marks].join(SEPARATOR)}
        </ThemedText>
      </View>
      {body()}
    </View>
  );
}

const styles = StyleSheet.create({
  fill: {
    flex: 1,
  },
  list: {
    padding: Spacing.three,
    paddingBottom: Spacing.five,
    gap: Spacing.two,
  },
  row: {
    borderRadius: Spacing.two,
    padding: Spacing.three,
    gap: Spacing.half,
  },
  pressed: {
    opacity: 0.7,
  },
  actions: {
    paddingHorizontal: Spacing.three,
    paddingBottom: Spacing.three,
    gap: Spacing.two,
  },
  text: {
    flex: 1,
  },
});
