import { fireEvent, waitFor, within } from '@testing-library/react-native';
import { screen } from 'expo-router/testing-library';

import { catalogueListGenres, catalogueListWorks } from '@/api/generated';
import HomeScreen from '@/app/(tabs)/index';
import i18n from '@/i18n';
import { fails, GENRES, ok, page, work } from '@/testing/api';
import { openRouter } from '@/testing/router';

jest.mock('@/api/generated');

const listWorks = jest.mocked(catalogueListWorks);
const listGenres = jest.mocked(catalogueListGenres);

const lantern = work();

beforeEach(() => {
  jest.clearAllMocks();
  listGenres.mockReturnValue(ok(GENRES));
  listWorks.mockReturnValue(ok(page([lantern])));
});

afterEach(async () => {
  await i18n.changeLanguage('en');
});

async function openHome() {
  return openRouter({ index: HomeScreen, 'works/[workId]': () => null }, '/');
}

/** The query of the most recent catalogue request. */
function lastQuery() {
  return listWorks.mock.lastCall?.[0]?.query;
}

async function choose(group: string, option: string) {
  const row = screen.getByLabelText(group);
  await fireEvent.press(within(row).getByRole('radio', { name: option }));
}

test('FR-RD-01: a guest sees the catalogue, newest first', async () => {
  await openHome();

  const card = await screen.findByRole('link', { name: 'Người Giữ Đèn Bến Sương' });
  expect(within(card).getByText('by Nguyễn Tác Giả')).toBeOnTheScreen();
  expect(within(card).getByText('Novel · Ongoing')).toBeOnTheScreen();
  expect(within(card).getByText('Fantasy')).toBeOnTheScreen();
  expect(within(card).getByText('Mystery')).toBeOnTheScreen();
  expect(within(card).getByText(/^5 episodes · Updated /)).toBeOnTheScreen();
  expect(lastQuery()).toEqual({ sort: 'newest', limit: 20, offset: 0 });
});

test('FR-RD-01: each filter narrows the request, and they combine', async () => {
  await openHome();
  await screen.findByRole('link', { name: lantern.title });

  await choose('Format', 'Manga');
  await waitFor(() => expect(lastQuery()).toMatchObject({ type: 'manga' }));

  await choose('Status', 'Completed');
  await waitFor(() => expect(lastQuery()).toMatchObject({ type: 'manga', status: 'completed' }));

  await choose('Genre', 'Slice of Life');
  await waitFor(() =>
    expect(lastQuery()).toEqual({
      type: 'manga',
      status: 'completed',
      genre: 'slice-of-life',
      sort: 'newest',
      limit: 20,
      offset: 0,
    }),
  );

  await choose('Sort by', 'Popular');
  await waitFor(() => expect(lastQuery()).toMatchObject({ sort: 'popular' }));

  // "All" lifts one filter and leaves the others.
  await choose('Format', 'All');
  await waitFor(() =>
    expect(lastQuery()).toEqual({
      status: 'completed',
      genre: 'slice-of-life',
      sort: 'popular',
      limit: 20,
      offset: 0,
    }),
  );
});

test('FR-RD-01: the chosen filter is the selected one', async () => {
  await openHome();
  await screen.findByRole('link', { name: lantern.title });
  const format = screen.getByLabelText('Format');

  expect(within(format).getByRole('radio', { name: 'All' })).toBeSelected();

  await choose('Format', 'Novel');

  expect(within(format).getByRole('radio', { name: 'Novel' })).toBeSelected();
  expect(within(format).getByRole('radio', { name: 'All' })).not.toBeSelected();
});

test('FR-RD-01: genres come from the API, translated where this build knows them', async () => {
  listGenres.mockReturnValue(ok([...GENRES, { slug: 'isekai', name: 'Isekai' }]));
  await openHome();
  await screen.findByRole('link', { name: lantern.title });
  const genres = screen.getByLabelText('Genre');

  expect(within(genres).getAllByRole('radio')).toHaveLength(14);
  expect(within(genres).getByRole('radio', { name: 'Sci-Fi' })).toBeOnTheScreen();
  // No translation for it here, so the API's own name is shown.
  expect(within(genres).getByRole('radio', { name: 'Isekai' })).toBeOnTheScreen();
});

test('FR-RD-01: an empty catalogue says so', async () => {
  listWorks.mockReturnValue(ok(page([])));
  await openHome();

  expect(await screen.findByText('No works match these filters.')).toBeOnTheScreen();
});

test('FR-RD-01: a failed request can be tried again', async () => {
  listWorks.mockReturnValueOnce(fails('rate_limited'));
  await openHome();

  expect(
    await screen.findByText('Too many attempts. Wait a moment and try again.'),
  ).toBeOnTheScreen();

  await fireEvent.press(screen.getByRole('button', { name: 'Try again' }));

  expect(await screen.findByRole('link', { name: lantern.title })).toBeOnTheScreen();
  expect(listWorks).toHaveBeenCalledTimes(2);
});

test('FR-RD-01: more works load from where the list ends', async () => {
  const older = work({ id: 'older', title: 'The Lantern Road' });
  listWorks.mockReturnValueOnce(ok(page([lantern], true))).mockReturnValueOnce(ok(page([older])));
  await openHome();
  await screen.findByRole('link', { name: lantern.title });

  await fireEvent.press(screen.getByRole('button', { name: 'Load more' }));

  expect(await screen.findByRole('link', { name: 'The Lantern Road' })).toBeOnTheScreen();
  expect(screen.getByRole('link', { name: lantern.title })).toBeOnTheScreen();
  expect(lastQuery()).toMatchObject({ offset: 1 });
  expect(screen.queryByRole('button', { name: 'Load more' })).toBeNull();
});

test('FR-RD-02: a card opens the page of its work', async () => {
  const router = await openHome();

  await fireEvent.press(await screen.findByRole('link', { name: lantern.title }));

  expect(router.pathname()).toBe(`/works/${lantern.id}`);
});

test('NFR-13: the catalogue is in Vietnamese when that is the language', async () => {
  await i18n.changeLanguage('vi');
  await openHome();

  const card = await screen.findByRole('link', { name: lantern.title });
  expect(screen.getByText('Khám phá')).toBeOnTheScreen();
  expect(within(card).getByText('Tiểu thuyết · Đang ra')).toBeOnTheScreen();
  expect(within(card).getByText('Kỳ ảo')).toBeOnTheScreen();
  expect(within(card).getByText(/^5 chương · Cập nhật /)).toBeOnTheScreen();
  expect(screen.getByLabelText('Thể loại')).toBeOnTheScreen();
});
