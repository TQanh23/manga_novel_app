import { fireEvent } from '@testing-library/react-native';
import { screen } from 'expo-router/testing-library';

import {
  catalogueGetWork,
  catalogueListEpisodes,
  catalogueListGenres,
  catalogueListWorks,
  type UserResponse,
} from '@/api/generated';
import AuthLayout from '@/app/(auth)/_layout';
import RegisterScreen from '@/app/(auth)/register';
import SignInScreen from '@/app/(auth)/sign-in';
import TabsLayout from '@/app/(tabs)/_layout';
import AccountScreen from '@/app/(tabs)/account';
import HomeScreen from '@/app/(tabs)/index';
import SearchScreen from '@/app/(tabs)/search';
import RootLayout from '@/app/_layout';
import WorkScreen from '@/app/works/[workId]';
import { useSession } from '@/auth/session';
import { episode, GENRES, ok, page, work, workDetail } from '@/testing/api';
import { openRouter } from '@/testing/router';

jest.mock('@/api/generated');
// The real provider signs in silently over the network; here the test says who is signed in.
jest.mock('@/auth/session', () => ({
  SessionProvider: ({ children }: { children: unknown }) => children,
  useSession: jest.fn(),
}));

const session = jest.mocked(useSession);
const signOut = jest.fn();
const becomeAuthor = jest.fn();

const READER: UserResponse = {
  id: 'reader-1',
  email: 'reader1@example.com',
  display_name: 'Reader One',
  locale: 'en',
  status: 'active',
  roles: ['reader'],
};

const APP = {
  _layout: RootLayout,
  '(tabs)/_layout': TabsLayout,
  '(tabs)/index': HomeScreen,
  '(tabs)/search': SearchScreen,
  '(tabs)/account': AccountScreen,
  'works/[workId]': WorkScreen,
  '(auth)/_layout': AuthLayout,
  '(auth)/sign-in': SignInScreen,
  '(auth)/register': RegisterScreen,
};

function signedInAs(user: UserResponse | null) {
  session.mockReturnValue({
    user,
    isLoading: false,
    signIn: jest.fn(),
    register: jest.fn(),
    becomeAuthor,
    signOut,
  });
}

beforeEach(() => {
  jest.clearAllMocks();
  signedInAs(null);
  jest.mocked(catalogueListGenres).mockReturnValue(ok(GENRES));
  jest.mocked(catalogueListWorks).mockReturnValue(ok(page([work({ id: 'lantern' })])));
  jest.mocked(catalogueGetWork).mockReturnValue(ok(workDetail({ id: 'lantern' })));
  jest.mocked(catalogueListEpisodes).mockReturnValue(ok([episode(1)]));
});

test('a guest lands on the catalogue without signing in', async () => {
  const router = await openRouter(APP, '/');

  expect(await screen.findByRole('link', { name: 'Người Giữ Đèn Bến Sương' })).toBeOnTheScreen();
  expect(router.pathname()).toBe('/');
});

test('a guest opens a work from the catalogue', async () => {
  const router = await openRouter(APP, '/');

  await fireEvent.press(await screen.findByRole('link', { name: 'Người Giữ Đèn Bến Sương' }));

  expect(router.pathname()).toBe('/works/lantern');
  expect(await screen.findByText('Episodes · 1 episode')).toBeOnTheScreen();
});

test('a guest can open a work page directly', async () => {
  const router = await openRouter(APP, '/works/lantern');

  expect(await screen.findByRole('header', { name: 'Người Giữ Đèn Bến Sương' })).toBeOnTheScreen();
  expect(router.pathname()).toBe('/works/lantern');
});

test('a guest can open search', async () => {
  const router = await openRouter(APP, '/search');

  expect(screen.getByLabelText('Search')).toBeOnTheScreen();
  expect(router.pathname()).toBe('/search');
});

test('the account tab offers a guest the way in', async () => {
  const router = await openRouter(APP, '/account');

  expect(screen.getByText('You are browsing as a guest')).toBeOnTheScreen();

  await fireEvent.press(screen.getByRole('button', { name: 'Sign in' }));

  expect(router.pathname()).toBe('/sign-in');
  expect(screen.getByLabelText('Password')).toBeOnTheScreen();
});

test('a guest can reach the sign-in and register screens', async () => {
  const signIn = await openRouter(APP, '/sign-in');
  expect(signIn.pathname()).toBe('/sign-in');

  const register = await openRouter(APP, '/register');
  expect(register.pathname()).toBe('/register');
  expect(screen.getByLabelText('Display name')).toBeOnTheScreen();
});

test('someone who is signed in is sent away from the sign-in screen', async () => {
  signedInAs(READER);

  const router = await openRouter(APP, '/sign-in');

  expect(router.pathname()).toBe('/');
  expect(await screen.findByRole('link', { name: 'Người Giữ Đèn Bến Sương' })).toBeOnTheScreen();
  expect(screen.queryByLabelText('Password')).toBeNull();
});

test('the account tab shows who is signed in and lets them sign out', async () => {
  signedInAs(READER);
  await openRouter(APP, '/account');

  expect(screen.getByText('Hello, Reader One')).toBeOnTheScreen();
  expect(screen.getByText('reader1@example.com')).toBeOnTheScreen();
  expect(screen.getByText('Reader')).toBeOnTheScreen();
  expect(screen.getByRole('button', { name: 'Become an author' })).toBeOnTheScreen();
  expect(screen.queryByText('You are browsing as a guest')).toBeNull();

  await fireEvent.press(screen.getByRole('button', { name: 'Sign out' }));

  expect(signOut).toHaveBeenCalledTimes(1);
});

test('an author is not asked to become one', async () => {
  signedInAs({ ...READER, roles: ['reader', 'author'] });
  await openRouter(APP, '/account');

  expect(screen.getByText('Author')).toBeOnTheScreen();
  expect(screen.queryByRole('button', { name: 'Become an author' })).toBeNull();
});
