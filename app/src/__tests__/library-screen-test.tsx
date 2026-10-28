import { fireEvent } from '@testing-library/react-native';
import { screen } from 'expo-router/testing-library';

import { readerGetLibrary, type UserResponse } from '@/api/generated';
import LibraryScreen from '@/app/(tabs)/library';
import { useSession } from '@/auth/session';
import { fails, library, ok, READER, readingEntry, work } from '@/testing/api';
import { openRouter } from '@/testing/router';

jest.mock('@/api/generated');
jest.mock('@/auth/session', () => ({ useSession: jest.fn() }));

const getLibrary = jest.mocked(readerGetLibrary);
const session = jest.mocked(useSession);

const LANTERN = work({ id: 'lantern' });
const SWORD = work({ id: 'sword', title: 'Kiếm Sĩ Dưới Trăng' });

function signedIn(user: UserResponse | null) {
  session.mockReturnValue({ user, isLoading: false } as ReturnType<typeof useSession>);
}

beforeEach(() => {
  jest.clearAllMocks();
  signedIn(READER);
  getLibrary.mockReturnValue(
    ok(library({ reading: [readingEntry({ work: LANTERN })], favourites: [SWORD] })),
  );
});

function openLibrary() {
  return openRouter(
    {
      library: LibraryScreen,
      'read/[episodeId]': () => null,
      'works/[workId]': () => null,
      'sign-in': () => null,
    },
    '/library',
  );
}

test('FR-RD-05: the library shows what the reader is in and what they keep', async () => {
  await openLibrary();

  expect(await screen.findByRole('header', { name: 'Reading' })).toBeOnTheScreen();
  expect(screen.getByText('Episode 2 · Chương 2: Dầu sương')).toBeOnTheScreen();
  expect(screen.getByRole('link', { name: LANTERN.title })).toBeOnTheScreen();
  expect(screen.getByRole('header', { name: 'Favourites' })).toBeOnTheScreen();
  expect(screen.getByRole('link', { name: SWORD.title })).toBeOnTheScreen();
});

test('FR-RD-05: a work in progress opens the episode read last', async () => {
  const router = await openLibrary();

  await fireEvent.press(await screen.findByRole('link', { name: LANTERN.title }));

  expect(router.pathname()).toBe(`/read/${readingEntry().episode_id}`);
});

test('FR-RD-05: a favourite opens its work page', async () => {
  const router = await openLibrary();

  await fireEvent.press(await screen.findByRole('link', { name: SWORD.title }));

  expect(router.pathname()).toBe('/works/sword');
});

test('FR-RD-05: an empty library says how it fills up', async () => {
  getLibrary.mockReturnValue(ok(library()));
  await openLibrary();

  expect(await screen.findByText('Stories you start reading show up here.')).toBeOnTheScreen();
  expect(screen.getByText('Works you add to your favourites show up here.')).toBeOnTheScreen();
});

test('a library that failed to load can be asked for again', async () => {
  getLibrary.mockReturnValueOnce(fails('network_error'));
  await openLibrary();

  await fireEvent.press(await screen.findByRole('button', { name: 'Try again' }));

  expect(await screen.findByRole('link', { name: LANTERN.title })).toBeOnTheScreen();
  expect(getLibrary).toHaveBeenCalledTimes(2);
});

test('a guest is asked to sign in and nothing is fetched', async () => {
  signedIn(null);
  const router = await openLibrary();

  await fireEvent.press(screen.getByRole('button', { name: 'Sign in' }));

  expect(getLibrary).not.toHaveBeenCalled();
  expect(router.pathname()).toBe('/sign-in');
});
