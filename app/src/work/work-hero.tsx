import { useRouter } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { useTranslation } from 'react-i18next';

import { errorCode } from '@/api/client';
import {
  type EpisodeSummary,
  type LibraryResponse,
  readerAddFavourite,
  readerRemoveFavourite,
  type ReadingEntryResponse,
  type WorkDetail,
} from '@/api/generated';
import { Chip } from '@/components/chip';
import { Button, ErrorText } from '@/components/form';
import { Flourish, OrnateFrame } from '@/components/ornaments';
import { ThemedText } from '@/components/themed-text';
import { WorkCover } from '@/components/work-cover';
import { Fonts, Radius, Spacing } from '@/constants/theme';
import { useLayout } from '@/hooks/use-layout';
import { useTheme } from '@/hooks/use-theme';
import { errorMessageKey, formatDate, genreName } from '@/i18n';

const SEPARATOR = ' · ';

type WorkHeroProps = {
  work: WorkDetail;
  episodes: EpisodeSummary[];
  /** The reader's library; null for a guest, or while it loads or if it failed. */
  library: LibraryResponse | null;
  /** Where the reader is in this work, if anywhere. */
  reading: ReadingEntryResponse | undefined;
  signedIn: boolean;
};

/** The top of a work's page: cover, what it is, how far the reader has got, and what to do next. */
export function WorkHero({ work, episodes, library, reading, signedIn }: WorkHeroProps) {
  const { t } = useTranslation();
  const { isWide } = useLayout();

  return (
    <OrnateFrame style={[styles.frame, isWide && styles.wide]}>
      <View style={isWide ? undefined : styles.coverRow}>
        <WorkCover work={work} width={isWide ? 220 : 180} />
      </View>
      <View style={styles.text}>
        <ThemedText type="eyebrow" themeColor="textSecondary">
          {[t(`workType.${work.type}`), t(`workStatus.${work.status}`)].join(SEPARATOR)}
        </ThemedText>
        <ThemedText accessibilityRole="header" style={[styles.title, isWide && styles.titleWide]}>
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
        <Flourish />
        <Stats work={work} count={episodes.length} />
        {reading ? <Progress number={reading.episode_number} count={episodes.length} /> : null}
        <ReaderActions
          workId={work.id}
          episodes={episodes}
          library={library}
          reading={reading}
          signedIn={signedIn}
        />
      </View>
    </OrnateFrame>
  );
}

/** Four engraved figures: how long the work is, whether it is finished, its language, when it last grew. */
function Stats({ work, count }: { work: WorkDetail; count: number }) {
  const { t } = useTranslation();
  const theme = useTheme();
  // One row on a wide window; two by two on a phone, where four would be cut short.
  const { isWide } = useLayout();
  const perRow = isWide ? 4 : 2;
  const cells = [
    { label: t('work.stats.episodes'), value: String(count) },
    { label: t('work.stats.status'), value: t(`workStatus.${work.status}`) },
    { label: t('work.stats.language'), value: t(`contentLanguage.${work.language}`) },
    { label: t('work.stats.updated'), value: formatDate(work.last_published_at) },
  ];
  return (
    <View style={[styles.stats, { borderColor: theme.ornament }]}>
      {cells.map((cell, index) => (
        <View
          key={cell.label}
          style={[
            styles.stat,
            { width: `${100 / perRow}%`, borderColor: theme.border },
            index % perRow > 0 && styles.statLeftRule,
            index >= perRow && styles.statTopRule,
          ]}>
          <ThemedText type="eyebrow" themeColor="textSecondary" numberOfLines={1} style={styles.statLabel}>
            {cell.label}
          </ThemedText>
          <ThemedText numberOfLines={1} style={styles.statValue}>
            {cell.value}
          </ThemedText>
        </View>
      ))}
    </View>
  );
}

/** How far into the work the reader is, as a line of gold. */
function Progress({ number, count }: { number: number; count: number }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const share = count > 0 ? Math.min(1, number / count) : 0;
  return (
    <View style={styles.progress}>
      <ThemedText type="small" themeColor="textSecondary">
        {t('work.progress', { number, count })}
      </ThemedText>
      <View
        accessibilityElementsHidden
        importantForAccessibility="no-hide-descendants"
        style={[styles.track, { backgroundColor: theme.backgroundElement }]}>
        <View style={[styles.fill, { width: `${share * 100}%`, backgroundColor: theme.ornament }]} />
      </View>
    </View>
  );
}

type ReaderActionsProps = {
  workId: string;
  episodes: EpisodeSummary[];
  library: LibraryResponse | null;
  reading: ReadingEntryResponse | undefined;
  signedIn: boolean;
};

/** Read on (or start), and keep the work as a favourite (FR-RD-05). */
function ReaderActions({ workId, episodes, library, reading, signedIn }: ReaderActionsProps) {
  const { t } = useTranslation();
  const router = useRouter();
  // What the reader set here; until they do, what their library says.
  const [chosen, setChosen] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
    <View style={styles.actionsBlock}>
      {/* One row on any width: the two buttons share it equally. */}
      <View style={styles.actions}>
        {reading ? (
          <Button
            label={t('work.continue', { number: reading.episode_number })}
            onPress={() => read(reading.episode_id)}
            fill
          />
        ) : first ? (
          <Button label={t('work.start')} onPress={() => read(first.id)} fill />
        ) : null}
        {signedIn ? (
          <Button
            label={favourite ? t('work.unfavourite') : t('work.favourite')}
            variant="secondary"
            icon={favourite ? 'heart' : 'heart-outline'}
            busy={busy}
            // Without its library (still loading, or it failed) the button waits.
            disabled={busy || library === null}
            onPress={() => void toggleFavourite()}
            fill
          />
        ) : null}
      </View>
      {error ? <ErrorText>{t(errorMessageKey(error))}</ErrorText> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  frame: {
    padding: Spacing.four,
    gap: Spacing.four,
  },
  wide: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    padding: Spacing.five,
  },
  coverRow: {
    alignItems: 'center',
  },
  text: {
    flex: 1,
    gap: Spacing.two,
  },
  title: {
    fontFamily: Fonts.display,
    fontSize: 30,
    lineHeight: 38,
  },
  titleWide: {
    fontSize: 36,
    lineHeight: 44,
  },
  chips: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.two,
  },
  stats: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    borderTopWidth: 1,
    borderBottomWidth: 1,
  },
  stat: {
    alignItems: 'center',
    paddingHorizontal: Spacing.one,
    paddingVertical: Spacing.two,
    gap: Spacing.half,
  },
  statLeftRule: {
    borderLeftWidth: 1,
  },
  statTopRule: {
    borderTopWidth: 1,
  },
  statLabel: {
    fontSize: 11,
    letterSpacing: 1,
  },
  statValue: {
    fontFamily: Fonts.display,
    fontSize: 15,
    lineHeight: 20,
  },
  progress: {
    gap: Spacing.one,
  },
  track: {
    height: 4,
    borderRadius: Radius.pill,
    overflow: 'hidden',
  },
  fill: {
    height: '100%',
  },
  actionsBlock: {
    gap: Spacing.two,
    marginTop: Spacing.one,
  },
  actions: {
    flexDirection: 'row',
    gap: Spacing.two,
  },
});
