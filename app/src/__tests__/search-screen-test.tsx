import { act, fireEvent, waitFor } from '@testing-library/react-native';
import { screen } from 'expo-router/testing-library';

import { catalogueSearchWorks } from '@/api/generated';
import SearchScreen from '@/app/(tabs)/search';
import { fails, ok, page, work } from '@/testing/api';
import { openRouter } from '@/testing/router';

jest.mock('@/api/generated');

const search = jest.mocked(catalogueSearchWorks);

const HINT = 'Search by title, author or tag. Vietnamese works with or without diacritics.';
const DEBOUNCE_MS = 300;

beforeEach(() => {
  jest.clearAllMocks();
  search.mockReturnValue(ok(page([work()])));
});

async function openSearch() {
  // The router's test renderer switches jest to fake timers, so the debounce
  // only passes when a test advances the clock.
  await openRouter({ index: SearchScreen, 'works/[workId]': () => null }, '/');
  return screen.getByLabelText('Search');
}

async function type(box: ReturnType<typeof screen.getByLabelText>, text: string) {
  await fireEvent.changeText(box, text);
}

async function wait(ms: number) {
  await act(async () => {
    jest.advanceTimersByTime(ms);
  });
}

test('FR-RD-06: nothing is searched until something is typed', async () => {
  await openSearch();
  await wait(DEBOUNCE_MS * 2);

  expect(screen.getByText(HINT)).toBeOnTheScreen();
  expect(search).not.toHaveBeenCalled();
});

test('FR-RD-06: a search runs once typing has paused, with the text as typed', async () => {
  const box = await openSearch();

  await type(box, '  kiếm sĩ ');
  await wait(DEBOUNCE_MS - 1);
  expect(search).not.toHaveBeenCalled();

  await wait(1);

  // Trimmed, but the diacritics go to the API untouched: matching is its job.
  expect(search).toHaveBeenCalledTimes(1);
  expect(search.mock.lastCall?.[0].query).toEqual({ q: 'kiếm sĩ', limit: 20, offset: 0 });
  expect(await screen.findByRole('link', { name: 'Người Giữ Đèn Bến Sương' })).toBeOnTheScreen();
});

test('FR-RD-06: typing quickly sends one request, for the last text', async () => {
  const box = await openSearch();

  for (const text of ['n', 'ng', 'ngu', 'nguoi giu den']) {
    await type(box, text);
    await wait(100);
  }
  await wait(DEBOUNCE_MS);

  expect(search).toHaveBeenCalledTimes(1);
  expect(search.mock.lastCall?.[0].query.q).toBe('nguoi giu den');
});

test('FR-RD-06: spaces alone are not a search', async () => {
  const box = await openSearch();

  await type(box, '   ');
  await wait(DEBOUNCE_MS * 2);

  expect(search).not.toHaveBeenCalled();
  expect(screen.getByText(HINT)).toBeOnTheScreen();
});

test('FR-RD-06: a search that finds nothing says what it looked for', async () => {
  search.mockReturnValue(ok(page([])));
  const box = await openSearch();

  await type(box, 'không có truyện này');
  await wait(DEBOUNCE_MS);

  expect(await screen.findByText('Nothing found for “không có truyện này”.')).toBeOnTheScreen();
});

test('FR-RD-06: clearing the box clears the results', async () => {
  const box = await openSearch();
  await type(box, 'den');
  await wait(DEBOUNCE_MS);
  await screen.findByRole('link', { name: 'Người Giữ Đèn Bến Sương' });

  await type(box, '');
  await wait(DEBOUNCE_MS);

  expect(screen.queryByRole('link', { name: 'Người Giữ Đèn Bến Sương' })).toBeNull();
  expect(screen.getByText(HINT)).toBeOnTheScreen();
  expect(search).toHaveBeenCalledTimes(1);
});

test('FR-RD-06: a failed search can be tried again', async () => {
  search.mockReturnValueOnce(fails('network_error'));
  const box = await openSearch();
  await type(box, 'den');
  await wait(DEBOUNCE_MS);

  expect(
    await screen.findByText('Could not reach the server. Check your connection.'),
  ).toBeOnTheScreen();

  await fireEvent.press(screen.getByRole('button', { name: 'Try again' }));

  await waitFor(() => expect(search).toHaveBeenCalledTimes(2));
  expect(await screen.findByRole('link', { name: 'Người Giữ Đèn Bến Sương' })).toBeOnTheScreen();
});
