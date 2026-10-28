import { Link, useRouter } from 'expo-router';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { useTranslation } from 'react-i18next';

import {
  type LibraryResponse,
  type ReadingEntryResponse,
  readerGetLibrary,
  type UserResponse,
} from '@/api/generated';
import { useLoad } from '@/api/hooks';
import { useSession } from '@/auth/session';
import { Button, Screen } from '@/components/form';
import { Page } from '@/components/page';
import { EmptyState, ErrorState, LoadingState } from '@/components/state-views';
import { ThemedText } from '@/components/themed-text';
import { WorkCard } from '@/components/work-card';
import { Spacing } from '@/constants/theme';
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
        <ThemedText type="subtitle">{t('library.title')}</ThemedText>
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
    <Page>
      <ScrollView contentContainerStyle={styles.content}>
        <ThemedText type="subtitle">{t('library.title')}</ThemedText>
        {body()}
      </ScrollView>
    </Page>
  );
}

function Shelves({ library }: { library: LibraryResponse }) {
  const { t } = useTranslation();
  return (
    <>
      <View style={styles.section}>
        <ThemedText type="smallBold" accessibilityRole="header">
          {t('library.reading')}
        </ThemedText>
        {library.reading.length === 0 ? (
          <EmptyState message={t('library.emptyReading')} />
        ) : (
          library.reading.map((entry) => <ReadingRow key={entry.work.id} entry={entry} />)
        )}
      </View>
      <View style={styles.section}>
        <ThemedText type="smallBold" accessibilityRole="header">
          {t('library.favourites')}
        </ThemedText>
        {library.favourites.length === 0 ? (
          <EmptyState message={t('library.emptyFavourites')} />
        ) : (
          library.favourites.map((work) => <WorkCard key={work.id} work={work} />)
        )}
      </View>
    </>
  );
}

/** A work the reader is in. Opens the episode they read last, where they stopped. */
function ReadingRow({ entry }: { entry: ReadingEntryResponse }) {
  const { t } = useTranslation();
  const theme = useTheme();
  return (
    <Link href={{ pathname: '/read/[episodeId]', params: { episodeId: entry.episode_id } }} asChild>
      <Pressable
        accessibilityRole="link"
        accessibilityLabel={entry.work.title}
        style={({ pressed }) => [
          styles.row,
          { backgroundColor: theme.backgroundElement },
          pressed && styles.pressed,
        ]}>
        <ThemedText style={styles.title}>{entry.work.title}</ThemedText>
        <ThemedText type="small">
          {[t('work.episodeNumber', { number: entry.episode_number }), entry.episode_title].join(
            SEPARATOR,
          )}
        </ThemedText>
        <ThemedText type="small" themeColor="textSecondary">
          {t('library.readOn', { date: formatDate(entry.read_at) })}
        </ThemedText>
      </Pressable>
    </Link>
  );
}

const styles = StyleSheet.create({
  content: {
    padding: Spacing.three,
    paddingBottom: Spacing.five,
    gap: Spacing.four,
  },
  section: {
    gap: Spacing.three,
  },
  row: {
    borderRadius: Spacing.two,
    padding: Spacing.three,
    gap: Spacing.half,
  },
  title: {
    fontWeight: 700,
  },
  pressed: {
    opacity: 0.7,
  },
});
