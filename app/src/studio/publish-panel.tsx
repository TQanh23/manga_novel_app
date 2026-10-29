import { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { useTranslation } from 'react-i18next';

import { errorCode } from '@/api/client';
import {
  authorPublishEpisode,
  authorScheduleEpisode,
  authorUnscheduleEpisode,
  type EpisodeResponse,
} from '@/api/generated';
import { Button, ErrorText } from '@/components/form';
import { ThemedText } from '@/components/themed-text';
import { Spacing } from '@/constants/theme';
import { errorMessageKey, formatDateTime } from '@/i18n';
import PublishTimePicker from '@/studio/publish-time-picker';

const SEPARATOR = ' · ';

type Mode = 'idle' | 'publish' | 'schedule' | 'unschedule';
type Answer = { data?: EpisodeResponse; error?: unknown };

type Props = {
  episode: EpisodeResponse;
  /** How many times the text has changed in the editor; any change may be unpublished. */
  edits: number;
  /** Saves what is typed; false when that failed. */
  settle: () => Promise<boolean>;
};

/**
 * Puts the episode in front of readers, now or at a time the author picks
 * (FR-NV-01, FR-NV-02). Both take the newest save, so what is typed is saved
 * first. Publishing and calling a schedule off take two presses, written out
 * rather than as an Alert, which react-native-web does not show.
 */
export function PublishPanel({ episode: loaded, edits, settle }: Props) {
  const { t } = useTranslation();
  const [episode, setEpisode] = useState(loaded);
  // The edits that `episode` already accounts for.
  const [seen, setSeen] = useState(0);
  const [mode, setMode] = useState<Mode>('idle');
  const [when, setWhen] = useState<Date | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const changed = episode.has_unpublished_changes || edits > seen;

  const run = async (send: () => Promise<Answer>) => {
    setBusy(true);
    setError(null);
    const upTo = edits;
    if (!(await settle())) {
      setBusy(false);
      setError('draft_not_saved');
      return;
    }
    const result = await send().catch(() => null);
    setBusy(false);
    if (!result?.data) {
      setError(result ? errorCode(result.error) : 'network_error');
      return;
    }
    setEpisode(result.data);
    setSeen(upTo);
    setMode('idle');
    setWhen(null);
  };

  const publish = () => run(() => authorPublishEpisode({ path: { episode_id: episode.id } }));

  const schedule = () => {
    if (!when || when.getTime() <= Date.now()) {
      setError('publish_at_in_past');
      return;
    }
    void run(() =>
      authorScheduleEpisode({
        path: { episode_id: episode.id },
        body: { publish_at: when.toISOString() },
      }),
    );
  };

  const unschedule = () => run(() => authorUnscheduleEpisode({ path: { episode_id: episode.id } }));

  const switchTo = (next: Mode) => {
    setError(null);
    setMode(next);
  };

  const status =
    episode.status === 'scheduled' && episode.publish_at
      ? t('studio.episodeStatus.scheduled', { date: formatDateTime(episode.publish_at) })
      : t(`studio.episodeStatus.${episode.status}`);
  const state = changed && episode.status !== 'draft' ? [status, t('studio.unpublishedChanges')] : [status];

  const idleActions = () => {
    switch (episode.status) {
      case 'draft':
        return (
          <View style={styles.row}>
            <Button label={t('studio.publish.now')} onPress={() => switchTo('publish')} />
            <Button
              label={t('studio.publish.schedule')}
              variant="secondary"
              onPress={() => switchTo('schedule')}
            />
          </View>
        );
      case 'scheduled':
        return (
          <>
            {changed ? (
              <ThemedText type="small" themeColor="textSecondary">
                {t('studio.publish.scheduledChanges')}
              </ThemedText>
            ) : null}
            <View style={styles.row}>
              <Button label={t('studio.publish.now')} onPress={() => switchTo('publish')} />
              <Button
                label={t('studio.publish.reschedule')}
                variant="secondary"
                onPress={() => switchTo('schedule')}
              />
              <Button
                label={t('studio.publish.unschedule')}
                variant="secondary"
                onPress={() => switchTo('unschedule')}
              />
            </View>
          </>
        );
      case 'published':
        return changed ? (
          <View style={styles.row}>
            <Button label={t('studio.publish.changes')} onPress={() => switchTo('publish')} />
          </View>
        ) : null;
      case 'removed':
        return null;
    }
  };

  const actions = () => {
    const back = (
      <Button
        label={t('studio.publish.back')}
        variant="secondary"
        disabled={busy}
        onPress={() => switchTo('idle')}
      />
    );
    switch (mode) {
      case 'publish':
        return (
          <>
            <ThemedText accessibilityRole="alert">
              {episode.status === 'published'
                ? t('studio.publish.confirmChanges')
                : t('studio.publish.confirmNow')}
            </ThemedText>
            <Button label={t('studio.publish.confirm')} busy={busy} onPress={() => void publish()} />
            {back}
          </>
        );
      case 'schedule':
        return (
          <>
            <PublishTimePicker
              label={t('studio.publish.when')}
              placeholder={t('studio.publish.pickTime')}
              value={when}
              onChange={(date) => {
                setError(null);
                setWhen(date);
              }}
            />
            <Button
              label={
                when
                  ? t('studio.publish.scheduleFor', { date: formatDateTime(when.toISOString()) })
                  : t('studio.publish.schedule')
              }
              busy={busy}
              disabled={busy || !when}
              onPress={schedule}
            />
            {back}
          </>
        );
      case 'unschedule':
        return (
          <>
            <ThemedText accessibilityRole="alert">{t('studio.publish.confirmUnschedule')}</ThemedText>
            <Button
              label={t('studio.publish.unschedule')}
              busy={busy}
              onPress={() => void unschedule()}
            />
            {back}
          </>
        );
      case 'idle':
        return idleActions();
    }
  };

  return (
    <View style={styles.panel}>
      <ThemedText type="smallBold" themeColor="textSecondary" accessibilityLiveRegion="polite">
        {state.join(SEPARATOR)}
      </ThemedText>
      {actions()}
      {error ? <ErrorText>{t(errorMessageKey(error))}</ErrorText> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  panel: {
    gap: Spacing.two,
  },
  row: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.two,
  },
});
