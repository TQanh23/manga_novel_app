import { act, fireEvent, waitFor } from '@testing-library/react-native';
import { Stack } from 'expo-router';
import { screen } from 'expo-router/testing-library';
import type { ComponentProps } from 'react';

import {
  catalogueGetWork,
  catalogueListEpisodes,
  readerGetEpisodeContent,
  readerSaveProgress,
  type UserResponse,
} from '@/api/generated';
import ReadScreen from '@/app/read/[episodeId]';
import { useSession } from '@/auth/session';
import { Colors } from '@/constants/theme';
import type NovelView from '@/reader/novel-view';
import { ReaderSettingsProvider } from '@/reader/settings';
import { SAVE_DELAY_MS } from '@/reader/use-progress-saver';
import { episode, episodeContent, fails, ok, workDetail } from '@/testing/api';
import { openRouter } from '@/testing/router';

jest.mock('@/api/generated');
jest.mock('@/auth/session', () => ({ useSession: jest.fn() }));
// The real view is a web page (a DOM component); here the test sees what it is given.
const mockNovelView = jest.fn((_props: ComponentProps<typeof NovelView>) => null);
jest.mock('@/reader/novel-view', () => ({
  __esModule: true,
  default: (props: ComponentProps<typeof NovelView>) => mockNovelView(props),
}));

const getContent = jest.mocked(readerGetEpisodeContent);
const getWork = jest.mocked(catalogueGetWork);
const listEpisodes = jest.mocked(catalogueListEpisodes);
const saveProgress = jest.mocked(readerSaveProgress);
const session = jest.mocked(useSession);

const READER: UserResponse = {
  id: 'reader-1',
  email: 'reader1@example.com',
  display_name: 'Reader One',
  locale: 'en',
  status: 'active',
  roles: ['reader'],
};
const CHAPTER_2 = episodeContent();
const CHAPTER_3 = episodeContent({
  id: CHAPTER_2.next_episode_id ?? '',
  number: 3,
  title: 'Chương 3',
  previous_episode_id: CHAPTER_2.id,
  next_episode_id: null,
});

function signedIn(user: UserResponse | null) {
  session.mockReturnValue({ user, isLoading: false } as ReturnType<typeof useSession>);
}

beforeEach(() => {
  jest.clearAllMocks();
  signedIn(READER);
  getContent.mockImplementation(({ path }) =>
    ok(path.episode_id === CHAPTER_3.id ? CHAPTER_3 : CHAPTER_2),
  );
  getWork.mockReturnValue(ok(workDetail({ id: CHAPTER_2.work_id })));
  listEpisodes.mockReturnValue(
    ok([
      episode(1),
      episode(2, { id: CHAPTER_2.id, title: CHAPTER_2.title }),
      episode(3, { id: CHAPTER_3.id, title: CHAPTER_3.title }),
    ]),
  );
  saveProgress.mockImplementation(({ body }) =>
    ok({ episode_id: CHAPTER_2.id, position: body.position, saved_at: '2026-10-28T07:00:00Z' }),
  );
});

function view(): ComponentProps<typeof NovelView> {
  const props = mockNovelView.mock.lastCall?.[0];
  if (!props) {
    throw new Error('The novel view is not on the screen');
  }
  return props;
}

async function openEpisode(id = CHAPTER_2.id) {
  const router = await openRouter(
    {
      _layout: () => (
        <ReaderSettingsProvider>
          <Stack />
        </ReaderSettingsProvider>
      ),
      'read/[episodeId]': ReadScreen,
    },
    `/read/${id}`,
  );
  await screen.findByRole('button', { name: 'Next' });
  return router;
}

async function scrollTo(position: number) {
  await act(async () => {
    await view().onPosition(position);
  });
}

async function wait(ms: number) {
  await act(async () => {
    jest.advanceTimersByTime(ms);
  });
}

test('FR-RD-03: the episode is shown paragraph by paragraph, from the top on a first read', async () => {
  await openEpisode();

  expect(getContent.mock.lastCall?.[0].path).toEqual({ episode_id: CHAPTER_2.id });
  expect(view().paragraphs).toEqual(CHAPTER_2.paragraphs);
  expect(view().initialPosition).toBe(0);
});

test('FR-RD-03: the reader opens at the paragraph they stopped at', async () => {
  getContent.mockReturnValue(ok(episodeContent({ position: 2 })));
  await openEpisode();

  expect(view().initialPosition).toBe(2);
});

test('FR-RD-03: a position past a shortened text opens at its last paragraph', async () => {
  getContent.mockReturnValue(ok(episodeContent({ position: 40 })));
  await openEpisode();

  expect(view().initialPosition).toBe(CHAPTER_2.paragraphs.length - 1);
});

test('FR-RD-05: the position is saved once scrolling has stopped', async () => {
  await openEpisode();

  await scrollTo(1);
  await scrollTo(2);
  await wait(SAVE_DELAY_MS - 1);
  expect(saveProgress).not.toHaveBeenCalled();

  await wait(1);
  expect(saveProgress).toHaveBeenCalledTimes(1);
  expect(saveProgress.mock.lastCall?.[0]).toMatchObject({
    path: { episode_id: CHAPTER_2.id },
    body: { position: 2 },
  });
});

test('FR-RD-05: coming back to the saved paragraph sends nothing', async () => {
  getContent.mockReturnValue(ok(episodeContent({ position: 1 })));
  await openEpisode();

  await scrollTo(2);
  await scrollTo(1);
  await wait(SAVE_DELAY_MS);

  expect(saveProgress).not.toHaveBeenCalled();
});

test('FR-RD-05: a position that failed to save is sent again', async () => {
  await openEpisode();
  saveProgress.mockReturnValueOnce(fails('network_error'));

  await scrollTo(2);
  await wait(SAVE_DELAY_MS);
  await scrollTo(2);
  await wait(SAVE_DELAY_MS);

  expect(saveProgress).toHaveBeenCalledTimes(2);
});

test('FR-RD-03: a guest reads without anything being saved', async () => {
  signedIn(null);
  await openEpisode();

  await scrollTo(2);
  await wait(SAVE_DELAY_MS * 2);

  expect(view().paragraphs).toEqual(CHAPTER_2.paragraphs);
  expect(saveProgress).not.toHaveBeenCalled();
});

test('FR-RD-03: next opens the following episode and saves the position at once', async () => {
  await openEpisode();
  await scrollTo(2);

  await fireEvent.press(screen.getByRole('button', { name: 'Next' }));
  await screen.findByRole('button', { name: 'Previous' });

  expect(saveProgress).toHaveBeenCalledTimes(1);
  expect(saveProgress.mock.lastCall?.[0].body).toEqual({ position: 2 });
  expect(getContent.mock.lastCall?.[0].path).toEqual({ episode_id: CHAPTER_3.id });
  expect(view().paragraphs).toEqual(CHAPTER_3.paragraphs);
  // The last episode has nothing after it.
  expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled();
});

test('FR-RD-03: changing the text settings restyles the page', async () => {
  await openEpisode();

  await fireEvent.press(screen.getByRole('button', { name: 'Text' }));
  await fireEvent.press(screen.getByRole('radio', { name: 'Sans-serif' }));
  await fireEvent.press(screen.getByRole('radio', { name: '22' }));
  await fireEvent.press(screen.getByRole('radio', { name: 'Dark' }));

  expect(view().appearance).toMatchObject({
    font: 'sans',
    fontSize: 22,
    background: Colors.dark.background,
    text: Colors.dark.text,
  });
});

test('FR-RD-03: a paid episode shows that it is locked, and no text', async () => {
  getContent.mockReturnValue(fails('episode_locked'));
  await openRouter(
    {
      _layout: () => (
        <ReaderSettingsProvider>
          <Stack />
        </ReaderSettingsProvider>
      ),
      'read/[episodeId]': ReadScreen,
    },
    `/read/${CHAPTER_2.id}`,
  );

  expect(
    await screen.findByText('This episode has to be unlocked before you can read it.'),
  ).toBeOnTheScreen();
  expect(mockNovelView).not.toHaveBeenCalled();
});

test('FR-RD-03: the chapter opens with the work and episode and closes with an end mark', async () => {
  await openEpisode();

  await waitFor(() =>
    expect(view().heading).toEqual({
      eyebrow: `Người Giữ Đèn Bến Sương · Episode ${CHAPTER_2.number}`,
      title: CHAPTER_2.title,
      end: `End of episode ${CHAPTER_2.number}`,
    }),
  );
  expect(getWork).toHaveBeenCalledWith({ path: { work_id: CHAPTER_2.work_id } });
});

test('FR-RD-03: without the work, the chapter still opens, headed by its number alone', async () => {
  getWork.mockReturnValue(fails('rate_limited'));
  await openEpisode();

  await waitFor(() => expect(view().heading?.eyebrow).toBe(`Episode ${CHAPTER_2.number}`));
});

test('FR-RD-05: the bar shows how far into the episode the reader has scrolled', async () => {
  await openEpisode();
  expect(screen.getByText('Episode 2 · 0%')).toBeOnTheScreen();

  await act(async () => {
    view().onProgress?.(100);
  });

  expect(screen.getByText('Episode 2 · 100%')).toBeOnTheScreen();
});

test('FR-RD-03: contents lists the episodes and opens the one chosen', async () => {
  const router = await openEpisode();

  await fireEvent.press(screen.getByRole('button', { name: 'Contents' }));
  expect(await screen.findByRole('button', { name: `2. ${CHAPTER_2.title}` })).toBeSelected();
  await fireEvent.press(screen.getByRole('button', { name: `3. ${CHAPTER_3.title}` }));

  await waitFor(() => expect(router.pathname()).toBe(`/read/${CHAPTER_3.id}`));
});

test('FR-RD-03: contents and text settings never show at once', async () => {
  await openEpisode();

  await fireEvent.press(screen.getByRole('button', { name: 'Contents' }));
  expect(await screen.findByRole('button', { name: `1. ${episode(1).title}` })).toBeOnTheScreen();

  await fireEvent.press(screen.getByRole('button', { name: 'Text' }));
  expect(screen.getByLabelText('Font')).toBeOnTheScreen();
  expect(screen.queryByRole('button', { name: `1. ${episode(1).title}` })).toBeNull();

  await fireEvent.press(screen.getByRole('button', { name: 'Text' }));
  expect(screen.queryByLabelText('Font')).toBeNull();
});
