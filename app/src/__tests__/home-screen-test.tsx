import { fireEvent, waitFor, within } from '@testing-library/react-native';
import { useLocalSearchParams } from 'expo-router';
import { screen } from 'expo-router/testing-library';
import { Text } from 'react-native';

import {
  catalogueListEpisodes,
  catalogueListGenres,
  catalogueListWorks,
  readerGetLibrary,
  type UserResponse,
} from '@/api/generated';
import HomeScreen from '@/app/(tabs)/index';
import { useSession } from '@/auth/session';
import i18n from '@/i18n';
import { episode, fails, GENRES, library, ok, page, READER, readingEntry, work } from '@/testing/api';
import { openRouter } from '@/testing/router';

jest.mock('@/api/generated');
jest.mock('@/auth/session', () => ({ useSession: jest.fn() }));

const listWorks = jest.mocked(catalogueListWorks);
const listGenres = jest.mocked(catalogueListGenres);
const listEpisodes = jest.mocked(catalogueListEpisodes);
const getLibrary = jest.mocked(readerGetLibrary);
const session = jest.mocked(useSession);

const LANTERN = work({ id: 'lantern' });
const BAKERY = work({ id: 'bakery', title: 'The Dragon Who Ran a Bakery', language: 'en' });
const BOOKSHOP = work({ id: 'bookshop', title: '서울의 마지막 서점', language: 'ko' });
const FRESH = work({ id: 'fresh', title: '月夜の旅猫', language: 'ja' });

function signedIn(user: UserResponse | null) {
  session.mockReturnValue({ user, isLoading: false } as ReturnType<typeof useSession>);
}

/** Popular and newest are the same endpoint; answer each by its sort. */
function catalogue({ popular = [LANTERN, BAKERY, BOOKSHOP], newest = [FRESH, LANTERN] } = {}) {
  listWorks.mockImplementation(((options?: { query?: { sort?: string } }) =>
    ok(page(options?.query?.sort === 'popular' ? popular : newest))) as typeof catalogueListWorks);
}

beforeEach(() => {
  jest.clearAllMocks();
  signedIn(null);
  catalogue();
  listGenres.mockReturnValue(ok(GENRES));
  listEpisodes.mockReturnValue(ok([episode(1, { id: 'lantern-1' }), episode(2)]));
  getLibrary.mockReturnValue(ok(library()));
});

afterEach(async () => {
  await i18n.changeLanguage('en');
});

function BrowseStub() {
  const { genre, sort } = useLocalSearchParams<{ genre?: string; sort?: string }>();
  return <Text>{`browse genre=${genre ?? '-'} sort=${sort ?? '-'}`}</Text>;
}

function openHome() {
  return openRouter(
    {
      index: HomeScreen,
      browse: BrowseStub,
      library: () => null,
      'works/[workId]': () => null,
      'read/[episodeId]': () => null,
    },
    '/',
  );
}

test('FR-RD-01: a guest sees the featured work, the popular ranking, new releases and genres', async () => {
  await openHome();

  const featured = await screen.findByRole('header', { name: LANTERN.title });
  expect(featured).toBeOnTheScreen();
  expect(screen.getByText('Welcome, reader')).toBeOnTheScreen();
  expect(screen.getByRole('link', { name: `Number 1: ${LANTERN.title}` })).toBeOnTheScreen();
  expect(screen.getByRole('link', { name: `Number 2: ${BAKERY.title}` })).toBeOnTheScreen();
  expect(screen.getByRole('link', { name: `Number 3: ${BOOKSHOP.title}` })).toBeOnTheScreen();
  expect(screen.getByRole('link', { name: FRESH.title })).toBeOnTheScreen();
  expect(screen.getByRole('link', { name: 'Slice of Life' })).toBeOnTheScreen();
  expect(listWorks).toHaveBeenCalledWith({ query: { sort: 'popular', limit: 5 } });
  expect(listWorks).toHaveBeenCalledWith({ query: { sort: 'newest', limit: 10 } });
  // A guest has no library, so it is never asked for.
  expect(getLibrary).not.toHaveBeenCalled();
  expect(screen.queryByText('Continue reading')).toBeNull();
});

test('FR-RD-01: "Read now" opens the featured work at its first episode', async () => {
  const router = await openHome();
  await screen.findByRole('header', { name: LANTERN.title });
  await waitFor(() => expect(listEpisodes).toHaveBeenCalledWith({ path: { work_id: 'lantern' } }));

  await fireEvent.press(screen.getByRole('button', { name: 'Read now' }));

  expect(router.pathname()).toBe('/read/lantern-1');
});

test('FR-RD-01: "Details" opens the featured work', async () => {
  const router = await openHome();
  await screen.findByRole('header', { name: LANTERN.title });

  await fireEvent.press(screen.getByRole('button', { name: 'Details' }));

  expect(router.pathname()).toBe('/works/lantern');
});

test('FR-RD-05: a signed-in reader with history continues where they stopped', async () => {
  signedIn(READER);
  getLibrary.mockReturnValue(
    ok(library({ reading: [readingEntry({ work: BAKERY, episode_id: 'bakery-2', episode_number: 2 })] })),
  );
  const router = await openHome();

  const tile = await screen.findByRole('link', { name: `Continue reading: ${BAKERY.title}` });
  expect(within(tile).getByText('Episode 2')).toBeOnTheScreen();
  expect(screen.getByText(/^Good (morning|afternoon|evening), Reader One$/)).toBeOnTheScreen();

  await fireEvent.press(tile);

  expect(router.pathname()).toBe('/read/bakery-2');
});

test('FR-RD-05: a signed-in reader with nothing started sees no empty shelf', async () => {
  signedIn(READER);
  await openHome();
  await screen.findByRole('header', { name: LANTERN.title });

  await waitFor(() => expect(getLibrary).toHaveBeenCalled());
  expect(screen.queryByText('Continue reading')).toBeNull();
});

test('FR-RD-01: a genre tile opens the catalogue filtered to that genre', async () => {
  const router = await openHome();

  await fireEvent.press(await screen.findByRole('link', { name: 'Fantasy' }));

  expect(router.pathname()).toBe('/browse');
  expect(screen.getByText('browse genre=fantasy sort=-')).toBeOnTheScreen();
});

test('FR-RD-01: "See all" opens the catalogue sorted as the section is', async () => {
  await openHome();

  await fireEvent.press(await screen.findByRole('link', { name: 'See all: New releases' }));

  expect(screen.getByText('browse genre=- sort=newest')).toBeOnTheScreen();
});

test('FR-RD-01: a section that fails offers a retry while the others show', async () => {
  listWorks.mockImplementation(((options?: { query?: { sort?: string } }) =>
    options?.query?.sort === 'popular'
      ? fails('rate_limited')
      : ok(page([FRESH]))) as typeof catalogueListWorks);
  await openHome();

  expect(await screen.findByRole('link', { name: FRESH.title })).toBeOnTheScreen();
  expect(screen.getAllByRole('button', { name: 'Try again' }).length).toBeGreaterThan(0);

  catalogue();
  await fireEvent.press(screen.getAllByRole('button', { name: 'Try again' })[0]);

  expect(await screen.findByRole('header', { name: LANTERN.title })).toBeOnTheScreen();
});

test('NFR-13: the homepage is in Vietnamese when that is the language', async () => {
  await i18n.changeLanguage('vi');
  await openHome();

  await screen.findByRole('header', { name: LANTERN.title });
  expect(screen.getByText('Chào mừng bạn đọc')).toBeOnTheScreen();
  expect(screen.getByRole('button', { name: 'Đọc ngay' })).toBeOnTheScreen();
  expect(screen.getByRole('header', { name: 'Thịnh hành' })).toBeOnTheScreen();
  expect(screen.getByRole('link', { name: `Hạng 1: ${LANTERN.title}` })).toBeOnTheScreen();
  expect(screen.getByRole('link', { name: 'Kỳ ảo' })).toBeOnTheScreen();
});
