import { useRouter } from 'expo-router';
import { ScrollView, StyleSheet, View } from 'react-native';
import { useTranslation } from 'react-i18next';

import {
  catalogueListGenres,
  catalogueListWorks,
  type LibraryResponse,
  readerGetLibrary,
} from '@/api/generated';
import { useLoad } from '@/api/hooks';
import { useSession } from '@/auth/session';
import { Button } from '@/components/form';
import { Flourish, SectionTitle } from '@/components/ornaments';
import { Page } from '@/components/page';
import { SectionHeader } from '@/components/section-header';
import { ThemedText } from '@/components/themed-text';
import { Spacing } from '@/constants/theme';
import { Featured } from '@/home/featured';
import { GenreGrid } from '@/home/genre-grid';
import { Loaded } from '@/home/loaded';
import { PopularList } from '@/home/popular-list';
import { Shelf, type ShelfItem } from '@/home/shelf';
import { useVisit } from '@/hooks/use-visit';
import { currentLocale, formatDate } from '@/i18n';

const POPULAR_COUNT = 5;
const NEW_COUNT = 10;

function greetingKey(hour: number): 'morning' | 'afternoon' | 'evening' {
  if (hour < 12) {
    return 'morning';
  }
  return hour < 18 ? 'afternoon' : 'evening';
}

/**
 * The reader's homepage (FR-RD-01): a featured work, where they left off,
 * what is popular, what is new, and the genres. Each section loads, and can
 * fail, on its own; an empty one is left out.
 */
export default function HomeScreen() {
  const { t } = useTranslation();
  const router = useRouter();
  const { user } = useSession();
  // Asked again on each return: the reader may have read on in the meantime.
  const visit = useVisit();

  const popular = useLoad('home:popular', () =>
    catalogueListWorks({ query: { sort: 'popular', limit: POPULAR_COUNT } }),
  );
  const fresh = useLoad('home:newest', () =>
    catalogueListWorks({ query: { sort: 'newest', limit: NEW_COUNT } }),
  );
  const genres = useLoad('genres', () => catalogueListGenres());
  const library = useLoad<LibraryResponse | null>(
    user ? `library:${user.id}:${visit}` : 'library:guest',
    () => (user ? readerGetLibrary() : Promise.resolve({ data: null })),
  );

  const today = new Intl.DateTimeFormat(currentLocale(), {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
  }).format(new Date());
  const greeting = user
    ? t(`home.greeting.${greetingKey(new Date().getHours())}`, { name: user.display_name })
    : t('home.greetingGuest');
  const reading = library.data?.reading ?? [];

  return (
    <Page wide>
      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.masthead}>
          <SectionTitle eyebrow={today} title={greeting} />
          <ThemedText themeColor="textSecondary">{t('home.tagline')}</ThemedText>
        </View>

        <Loaded load={popular} placeholderHeight={320}>
          {(data) => (data.items[0] ? <Featured work={data.items[0]} /> : null)}
        </Loaded>

        {reading.length > 0 ? (
          <View style={styles.section}>
            <SectionHeader title={t('home.continueReading')} seeAll="/library" />
            <Shelf
              items={reading.map(
                (entry): ShelfItem => ({
                  key: entry.episode_id,
                  work: entry.work,
                  label: `${t('home.continueReading')}: ${entry.work.title}`,
                  href: { pathname: '/read/[episodeId]', params: { episodeId: entry.episode_id } },
                  caption: t('work.episodeNumber', { number: entry.episode_number }),
                }),
              )}
            />
          </View>
        ) : null}

        <View style={styles.section}>
          <SectionHeader
            title={t('home.popular')}
            seeAll={{ pathname: '/browse', params: { sort: 'popular' } }}
          />
          <Loaded load={popular} placeholderHeight={240}>
            {(data) => <PopularList works={data.items} />}
          </Loaded>
        </View>

        <View style={styles.section}>
          <SectionHeader
            title={t('home.newReleases')}
            seeAll={{ pathname: '/browse', params: { sort: 'newest' } }}
          />
          <Loaded load={fresh} placeholderHeight={240}>
            {(data) => (
              <Shelf
                items={data.items.map(
                  (work): ShelfItem => ({
                    key: work.id,
                    work,
                    label: work.title,
                    href: { pathname: '/works/[workId]', params: { workId: work.id } },
                    caption: t('catalogue.updated', { date: formatDate(work.last_published_at) }),
                  }),
                )}
              />
            )}
          </Loaded>
        </View>

        <View style={styles.section}>
          <SectionHeader title={t('home.genres')} />
          <Loaded load={genres} placeholderHeight={160}>
            {(data) => <GenreGrid genres={data} />}
          </Loaded>
        </View>

        <View style={styles.footer}>
          <Button label={t('home.browseAll')} variant="secondary" onPress={() => router.push('/browse')} />
          <Flourish />
        </View>
      </ScrollView>
    </Page>
  );
}

const styles = StyleSheet.create({
  content: {
    padding: Spacing.three,
    paddingBottom: Spacing.six,
    gap: Spacing.five,
  },
  masthead: {
    gap: Spacing.two,
  },
  section: {
    gap: Spacing.three,
  },
  footer: {
    alignItems: 'center',
    gap: Spacing.three,
  },
});
