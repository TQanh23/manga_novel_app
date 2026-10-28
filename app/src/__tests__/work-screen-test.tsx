import { act, fireEvent } from '@testing-library/react-native';
import { Stack } from 'expo-router';
import { screen } from 'expo-router/testing-library';

import {
  catalogueGetWork,
  catalogueListEpisodes,
  readerAddFavourite,
  readerGetLibrary,
  readerRemoveFavourite,
  type UserResponse,
} from '@/api/generated';
import WorkScreen from '@/app/works/[workId]';
import { useSession } from '@/auth/session';
import i18n from '@/i18n';
import {
  deferred,
  episode,
  fails,
  library,
  ok,
  READER,
  readingEntry,
  work,
  workDetail,
} from '@/testing/api';
import { openRouter } from '@/testing/router';

jest.mock('@/api/generated');
jest.mock('@/auth/session', () => ({ useSession: jest.fn() }));

const getWork = jest.mocked(catalogueGetWork);
const listEpisodes = jest.mocked(catalogueListEpisodes);
const getLibrary = jest.mocked(readerGetLibrary);
const addFavourite = jest.mocked(readerAddFavourite);
const removeFavourite = jest.mocked(readerRemoveFavourite);
const session = jest.mocked(useSession);

function signedIn(user: UserResponse | null) {
  session.mockReturnValue({ user, isLoading: false } as ReturnType<typeof useSession>);
}

const detail = workDetail({ id: 'lantern' });
const NOT_FOUND = 'This work does not exist or has nothing published yet.';

beforeEach(() => {
  jest.clearAllMocks();
  signedIn(null);
  getLibrary.mockReturnValue(ok(library()));
  addFavourite.mockReturnValue(ok(undefined));
  removeFavourite.mockReturnValue(ok(undefined));
  getWork.mockReturnValue(ok(detail));
  listEpisodes.mockReturnValue(
    ok([
      episode(1),
      episode(2, { price_coins: 1 }),
      episode(3, { price_coins: 3, wuf_eligible: true }),
    ]),
  );
});

afterEach(async () => {
  await i18n.changeLanguage('en');
});

function openWork(id = 'lantern') {
  return openRouter(
    { _layout: () => <Stack />, 'works/[workId]': WorkScreen, 'read/[episodeId]': () => null },
    `/works/${id}`,
  );
}

test('FR-RD-03: a guest starts reading at episode 1 and has no favourites button', async () => {
  const router = await openWork();

  await fireEvent.press(await screen.findByRole('button', { name: 'Start reading' }));

  expect(router.pathname()).toBe(`/read/${episode(1).id}`);
  expect(screen.queryByRole('button', { name: 'Add to favourites' })).toBeNull();
  expect(getLibrary).not.toHaveBeenCalled();
});

test('FR-RD-05: a reader who is in the work continues where they stopped', async () => {
  signedIn(READER);
  getLibrary.mockReturnValue(
    ok(library({ reading: [readingEntry({ work: work({ id: 'lantern' }) })] })),
  );
  const router = await openWork();

  await fireEvent.press(await screen.findByRole('button', { name: 'Continue: episode 2' }));

  expect(router.pathname()).toBe(`/read/${readingEntry().episode_id}`);
});

test('FR-RD-05: a reader adds the work to their favourites and takes it out again', async () => {
  signedIn(READER);
  await openWork();

  await fireEvent.press(await screen.findByRole('button', { name: 'Add to favourites' }));
  await fireEvent.press(await screen.findByRole('button', { name: 'Remove from favourites' }));

  expect(addFavourite.mock.lastCall?.[0].path).toEqual({ work_id: 'lantern' });
  expect(removeFavourite.mock.lastCall?.[0].path).toEqual({ work_id: 'lantern' });
  expect(await screen.findByRole('button', { name: 'Add to favourites' })).toBeOnTheScreen();
});

test('FR-RD-05: a favourite already in the library shows as one', async () => {
  signedIn(READER);
  getLibrary.mockReturnValue(ok(library({ favourites: [work({ id: 'lantern' })] })));
  await openWork();

  expect(await screen.findByRole('button', { name: 'Remove from favourites' })).toBeOnTheScreen();
});

test('FR-RD-05: the button changes at once, before the API has answered', async () => {
  signedIn(READER);
  const answer = deferred<undefined>();
  addFavourite.mockReturnValue(answer.promise);
  await openWork();

  await fireEvent.press(await screen.findByRole('button', { name: 'Add to favourites' }));
  expect(await screen.findByRole('button', { name: 'Remove from favourites' })).toBeDisabled();

  await act(async () => answer.resolve(undefined));
  expect(screen.getByRole('button', { name: 'Remove from favourites' })).toBeEnabled();
});

test('FR-RD-05: a favourite that failed to save goes back, with the reason', async () => {
  signedIn(READER);
  addFavourite.mockReturnValue(fails('rate_limited'));
  await openWork();

  await fireEvent.press(await screen.findByRole('button', { name: 'Add to favourites' }));

  expect(
    await screen.findByText('Too many attempts. Wait a moment and try again.'),
  ).toBeOnTheScreen();
  expect(screen.getByRole('button', { name: 'Add to favourites' })).toBeEnabled();
});

test('FR-RD-02: a work page shows what the work is and who wrote it', async () => {
  await openWork();

  expect(await screen.findByRole('header', { name: 'Người Giữ Đèn Bến Sương' })).toBeOnTheScreen();
  expect(screen.getByText('by Nguyễn Tác Giả')).toBeOnTheScreen();
  expect(screen.getByText('Novel · Ongoing')).toBeOnTheScreen();
  expect(screen.getByText('Một ngọn đèn ánh lam dẫn thuyền qua sương.')).toBeOnTheScreen();
  // Genres are translated; tags are shown as their author wrote them.
  expect(screen.getByText('Fantasy')).toBeOnTheScreen();
  expect(screen.getByText('Mystery')).toBeOnTheScreen();
  expect(screen.getByText('Kỳ ảo')).toBeOnTheScreen();
  expect(screen.getByText('Bến sông')).toBeOnTheScreen();
  expect(getWork.mock.lastCall?.[0].path).toEqual({ work_id: 'lantern' });
  expect(listEpisodes.mock.lastCall?.[0].path).toEqual({ work_id: 'lantern' });
});

test('FR-RD-02: episodes are listed in order with what each one costs', async () => {
  await openWork();
  await screen.findByRole('header', { name: detail.title });

  expect(screen.getByText('Episodes · 3 episodes')).toBeOnTheScreen();
  expect(screen.getByText(/^Episode 1 · /)).toBeOnTheScreen();
  expect(screen.getByText('Chương 1')).toBeOnTheScreen();
  expect(screen.getByText('Free')).toBeOnTheScreen();
  expect(screen.getByText('1 coin')).toBeOnTheScreen();
  expect(screen.getByText('3 coins · Wait until free')).toBeOnTheScreen();
});

test('FR-RD-02: a work with nothing published reads as not found, with no retry', async () => {
  getWork.mockReturnValue(fails('work_not_found'));
  listEpisodes.mockReturnValue(fails('work_not_found'));
  await openWork('missing');

  expect(await screen.findByText(NOT_FOUND)).toBeOnTheScreen();
  expect(screen.queryByRole('button', { name: 'Try again' })).toBeNull();
});

test('FR-RD-02: a failed request can be tried again', async () => {
  getWork.mockReturnValueOnce(fails('rate_limited'));
  await openWork();

  expect(
    await screen.findByText('Too many attempts. Wait a moment and try again.'),
  ).toBeOnTheScreen();

  await fireEvent.press(screen.getByRole('button', { name: 'Try again' }));

  expect(await screen.findByRole('header', { name: detail.title })).toBeOnTheScreen();
});

test('FR-RD-02: a work without genres, tags or synopsis still has a page', async () => {
  getWork.mockReturnValue(ok(workDetail({ genres: [], tags: [], synopsis: '' })));
  listEpisodes.mockReturnValue(ok([episode(1)]));
  await openWork();

  expect(await screen.findByRole('header', { name: detail.title })).toBeOnTheScreen();
  expect(screen.queryByText('Tags')).toBeNull();
  expect(screen.getByText('Episodes · 1 episode')).toBeOnTheScreen();
});

test('NFR-13: the work page is in Vietnamese when that is the language', async () => {
  await i18n.changeLanguage('vi');
  await openWork();

  await screen.findByRole('header', { name: detail.title });
  expect(screen.getByText('của Nguyễn Tác Giả')).toBeOnTheScreen();
  expect(screen.getByText('Tiểu thuyết · Đang ra')).toBeOnTheScreen();
  expect(screen.getByText('Bí ẩn')).toBeOnTheScreen();
  expect(screen.getByText('Danh sách chương · 3 chương')).toBeOnTheScreen();
  expect(screen.getByText('Miễn phí')).toBeOnTheScreen();
  expect(screen.getByText('3 coin · Chờ miễn phí')).toBeOnTheScreen();
});
