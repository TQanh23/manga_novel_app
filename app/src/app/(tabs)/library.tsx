import { Link, useRouter } from 'expo-router';
import { Pressable, ScrollView, StyleSheet, useWindowDimensions, View } from 'react-native';
import { useTranslation } from 'react-i18next';

import {
  type LibraryResponse,
  type ReadingEntryResponse,
  readerGetLibrary,
  type UserResponse,
  type WorkCard,
} from '@/api/generated';
import { useLoad } from '@/api/hooks';
import { useSession } from '@/auth/session';
import { Button, Screen } from '@/components/form';
import { Flourish, OrnateFrame, SectionTitle } from '@/components/ornaments';
import { Page } from '@/components/page';
import { SectionHeader } from '@/components/section-header';
import { ErrorState, LoadingState } from '@/components/state-views';
import { ThemedText } from '@/components/themed-text';
import { WorkCover } from '@/components/work-cover';
import { Fonts, Radius, Spacing } from '@/constants/theme';
import { useLayout } from '@/hooks/use-layout';
import { useTheme } from '@/hooks/use-theme';
import { useVisit } from '@/hooks/use-visit';
import { formatDate } from '@/i18n';

const SEPARATOR = ' · ';

/** What the reader is in the middle of, and the works they keep (FR-RD-05). */
export default function LibraryScreen() {
  const { t } = useTranslation();
  const router = useRouter();
  const { user } = useSession();

  if (!user) {
    return (
      <Screen>
        <SectionTitle title={t('library.title')} />
        <ThemedText themeColor="textSecondary">{t('library.guestHint')}</ThemedText>
        <Button label={t('auth.signIn')} onPress={() => router.push('/sign-in')} />
      </Screen>
    );
  }
  return <SignedInLibrary user={user} />;
}

function SignedInLibrary({ user }: { user: UserResponse }) {
  const { t } = useTranslation();
  // Each return to the tab asks again: the reader may have read on in the
  // meantime, here or on another device.
  const visit = useVisit();
  const library = useLoad(`library:${user.id}:${visit}`, () => readerGetLibrary());

  const summary = library.data
    ? [
        t('library.inProgress', { count: library.data.reading.length }),
        t('library.favouriteCount', { count: library.data.favourites.length }),
      ].join(SEPARATOR)
    : undefined;

  const body = () => {
    if (library.isLoading) {
      return <LoadingState />;
    }
    if (library.error || !library.data) {
      return <ErrorState code={library.error ?? 'unknown'} onRetry={library.reload} />;
    }
    return <Shelves library={library.data} />;
  };

  return (
    <Page wide>
      <ScrollView contentContainerStyle={styles.content}>
        <SectionTitle eyebrow={summary} title={t('library.title')} />
        {body()}
      </ScrollView>
    </Page>
  );
}

function Shelves({ library }: { library: LibraryResponse }) {
  const { t } = useTranslation();
  const { columns, isWide } = useLayout();
  const { width } = useWindowDimensions();
  // Three covers a row on a phone, fitted to the screen; a fixed size where there is room.
  const tileWidth = columns === 1 ? Math.floor((width - Spacing.three * 2 - Spacing.three * 2) / 3) : isWide ? 132 : 120;
  return (
    <>
      <View style={styles.section}>
        <SectionHeader title={t('library.reading')} />
        {library.reading.length === 0 ? (
          <EmptyShelf message={t('library.emptyReading')} />
        ) : (
          <View style={[styles.grid, columns > 1 && styles.gridRow]}>
            {library.reading.map((entry) => (
              <View key={entry.work.id} style={columns > 1 ? styles.half : undefined}>
                <ReadingCard entry={entry} />
              </View>
            ))}
          </View>
        )}
      </View>
      <View style={styles.section}>
        <SectionHeader title={t('library.favourites')} />
        {library.favourites.length === 0 ? (
          <EmptyShelf message={t('library.emptyFavourites')} />
        ) : (
          <View style={styles.shelf}>
            {library.favourites.map((work) => (
              <FavouriteTile key={work.id} work={work} width={tileWidth} />
            ))}
          </View>
        )}
      </View>
    </>
  );
}

/** A work the reader is in: where they are, how far that is, and a way straight back in. */
function ReadingCard({ entry }: { entry: ReadingEntryResponse }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const count = entry.work.episode_count;
  const share = count > 0 ? Math.min(1, entry.episode_number / count) : 0;
  return (
    <Link href={{ pathname: '/read/[episodeId]', params: { episodeId: entry.episode_id } }} asChild>
      {/* A static style: on web, <Link asChild> drops a Pressable's style function. */}
      <Pressable accessibilityRole="link" accessibilityLabel={entry.work.title} style={styles.fill}>
        <OrnateFrame style={styles.card} frameStyle={styles.fill}>
          <WorkCover work={entry.work} width={84} />
          <View style={styles.cardText}>
            <ThemedText type="eyebrow" themeColor="textSecondary" numberOfLines={1}>
              {t('library.readOn', { date: formatDate(entry.read_at) })}
            </ThemedText>
            <ThemedText numberOfLines={2} style={styles.title}>
              {entry.work.title}
            </ThemedText>
            <ThemedText type="small" numberOfLines={2}>
              {[t('work.episodeNumber', { number: entry.episode_number }), entry.episode_title].join(
                SEPARATOR,
              )}
            </ThemedText>
            <View style={styles.progress}>
              <ThemedText type="small" themeColor="textSecondary">
                {t('work.progress', { number: entry.episode_number, count })}
              </ThemedText>
              <View
                accessibilityElementsHidden
                importantForAccessibility="no-hide-descendants"
                style={[styles.track, { backgroundColor: theme.backgroundElement }]}>
                <View style={[styles.bar, { width: `${share * 100}%`, backgroundColor: theme.ornament }]} />
              </View>
            </View>
          </View>
        </OrnateFrame>
      </Pressable>
    </Link>
  );
}

/** A favourite, shown by its cover. Opens the work's page. */
function FavouriteTile({ work, width }: { work: WorkCard; width: number }) {
  const { t } = useTranslation();
  return (
    <Link href={{ pathname: '/works/[workId]', params: { workId: work.id } }} asChild>
      <Pressable
        accessibilityRole="link"
        accessibilityLabel={work.title}
        // One flat style: <Link asChild> refuses an array, and drops a function on web.
        style={StyleSheet.flatten([styles.tile, { width }])}>
        <WorkCover work={work} width={width} />
        <ThemedText numberOfLines={2} style={styles.tileTitle}>
          {work.title}
        </ThemedText>
        <ThemedText type="small" themeColor="textSecondary" numberOfLines={1}>
          {t('work.by', { author: work.author.display_name })}
        </ThemedText>
      </Pressable>
    </Link>
  );
}

/** A shelf with nothing on it yet: how it fills up, and the way to the catalogue. */
function EmptyShelf({ message }: { message: string }) {
  const { t } = useTranslation();
  const router = useRouter();
  return (
    <OrnateFrame style={styles.empty}>
      <ThemedText themeColor="textSecondary" style={styles.emptyText}>
        {message}
      </ThemedText>
      <Flourish style={styles.emptyFlourish} />
      <Button label={t('home.browseAll')} variant="secondary" onPress={() => router.push('/browse')} />
    </OrnateFrame>
  );
}

const styles = StyleSheet.create({
  content: {
    padding: Spacing.three,
    paddingBottom: Spacing.six,
    gap: Spacing.five,
  },
  section: {
    gap: Spacing.three,
  },
  grid: {
    gap: Spacing.three,
  },
  gridRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
  },
  // Two a row; a lone last card keeps the same width rather than stretching.
  half: {
    width: '48.5%',
  },
  fill: {
    flexGrow: 1,
  },
  card: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    padding: Spacing.three,
    gap: Spacing.three,
  },
  cardText: {
    flex: 1,
    gap: Spacing.half,
  },
  title: {
    fontFamily: Fonts.display,
    fontSize: 19,
    lineHeight: 25,
  },
  progress: {
    gap: Spacing.one,
    marginTop: Spacing.one,
  },
  track: {
    height: 4,
    borderRadius: Radius.pill,
    overflow: 'hidden',
  },
  bar: {
    height: '100%',
  },
  shelf: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.three,
  },
  tile: {
    gap: Spacing.one,
  },
  tileTitle: {
    fontFamily: Fonts.display,
    fontSize: 16,
    lineHeight: 21,
    marginTop: Spacing.one,
  },
  empty: {
    padding: Spacing.four,
    gap: Spacing.three,
    alignItems: 'center',
  },
  emptyText: {
    textAlign: 'center',
  },
  emptyFlourish: {
    alignSelf: 'stretch',
  },
});
