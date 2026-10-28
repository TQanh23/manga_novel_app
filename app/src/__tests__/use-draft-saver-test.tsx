import { act, renderHook } from '@testing-library/react-native';
import { AppState, type AppStateStatus } from 'react-native';

import { authorSaveDraft, type EpisodeVersionSummary } from '@/api/generated';
import { AUTOSAVE_DELAY_MS, RETRY_DELAY_MS, useDraftSaver } from '@/studio/use-draft-saver';
import { deferred, fails, ok } from '@/testing/api';

jest.mock('@/api/generated');

const saveDraft = jest.mocked(authorSaveDraft);
const SAVED_AT = '2026-10-28T07:00:00Z';
const version = (createdAt = SAVED_AT): EpisodeVersionSummary => ({
  id: 'version-2',
  created_at: createdAt,
  is_published: false,
});

let appStateListener: ((status: AppStateStatus) => void) | null = null;

beforeEach(() => {
  jest.clearAllMocks();
  jest.useFakeTimers();
  saveDraft.mockReturnValue(ok(version()));
  jest.spyOn(AppState, 'addEventListener').mockImplementation((_type, listener) => {
    appStateListener = listener as (status: AppStateStatus) => void;
    return { remove: () => (appStateListener = null) } as ReturnType<typeof AppState.addEventListener>;
  });
});

afterEach(() => {
  jest.useRealTimers();
});

function open(savedHtml = '<p>Một.</p>', savedAt: string | null = '2026-10-27T09:00:00Z') {
  return renderHook(() => useDraftSaver({ episodeId: 'episode-1', savedHtml, savedAt }));
}

async function wait(ms: number) {
  await act(async () => {
    jest.advanceTimersByTime(ms);
  });
}

const sentTexts = () => saveDraft.mock.calls.map(([options]) => options.body.body_html);

test('FR-NV-01: the text is saved once the author stops typing, not while they type', async () => {
  const { result } = await open();
  expect(result.current.status).toEqual({ kind: 'saved', savedAt: '2026-10-27T09:00:00Z' });

  await act(async () => result.current.change('<p>Một. Hai</p>'));
  await wait(AUTOSAVE_DELAY_MS - 1);
  await act(async () => result.current.change('<p>Một. Hai. Ba.</p>'));
  await wait(AUTOSAVE_DELAY_MS - 1);
  expect(saveDraft).not.toHaveBeenCalled();
  expect(result.current.status).toEqual({ kind: 'unsaved' });

  await wait(1);

  expect(saveDraft.mock.lastCall?.[0]).toEqual({
    path: { episode_id: 'episode-1' },
    body: { body_html: '<p>Một. Hai. Ba.</p>' },
  });
  expect(saveDraft).toHaveBeenCalledTimes(1);
  expect(result.current.status).toEqual({ kind: 'saved', savedAt: SAVED_AT });
});

test('text changed back to what was saved is not saved again', async () => {
  const { result } = await open();

  await act(async () => result.current.change('<p>Một!</p>'));
  await act(async () => result.current.change('<p>Một.</p>'));
  await wait(AUTOSAVE_DELAY_MS * 2);

  expect(saveDraft).not.toHaveBeenCalled();
  expect(result.current.status.kind).toBe('saved');
});

test('one save is in flight at a time; what came meanwhile goes in the next', async () => {
  const first = deferred<EpisodeVersionSummary>();
  saveDraft.mockReturnValueOnce(first.promise);
  const { result } = await open();

  await act(async () => result.current.change('<p>Hai</p>'));
  await wait(AUTOSAVE_DELAY_MS);
  expect(result.current.status).toEqual({ kind: 'saving' });

  await act(async () => result.current.change('<p>Hai, ba</p>'));
  await wait(AUTOSAVE_DELAY_MS * 2);
  expect(saveDraft).toHaveBeenCalledTimes(1);

  await act(async () => first.resolve(version('2026-10-28T06:59:00Z')));

  expect(sentTexts()).toEqual(['<p>Hai</p>', '<p>Hai, ba</p>']);
  expect(result.current.status).toEqual({ kind: 'saved', savedAt: SAVED_AT });
});

test('a failed save says why and is tried again', async () => {
  saveDraft.mockReturnValueOnce(fails('rate_limited'));
  const { result } = await open();

  await act(async () => result.current.change('<p>Hai</p>'));
  await wait(AUTOSAVE_DELAY_MS);
  expect(result.current.status).toEqual({ kind: 'failed', error: 'rate_limited' });

  await wait(RETRY_DELAY_MS);

  expect(sentTexts()).toEqual(['<p>Hai</p>', '<p>Hai</p>']);
  expect(result.current.status).toEqual({ kind: 'saved', savedAt: SAVED_AT });
});

test('a save that never reached the server counts as failed', async () => {
  saveDraft.mockImplementationOnce(
    () => Promise.reject(new TypeError('Network request failed')) as Promise<never>,
  );
  const { result } = await open();

  await act(async () => result.current.change('<p>Hai</p>'));
  await wait(AUTOSAVE_DELAY_MS);

  expect(result.current.status).toEqual({ kind: 'failed', error: 'network_error' });
});

test('FR-NV-01: leaving the episode saves what was typed at once', async () => {
  const { result, unmount } = await open();

  await act(async () => result.current.change('<p>Hai</p>'));
  await act(async () => unmount());

  expect(sentTexts()).toEqual(['<p>Hai</p>']);
});

test('FR-NV-01: the app going to the background saves what was typed at once', async () => {
  const { result } = await open();

  await act(async () => result.current.change('<p>Hai</p>'));
  await act(async () => appStateListener?.('background'));

  expect(sentTexts()).toEqual(['<p>Hai</p>']);
});

test('an episode never saved before says so', async () => {
  const { result } = await open('', null);

  expect(result.current.status).toEqual({ kind: 'saved', savedAt: null });
});

test('settling saves what is pending and waits for the save to end', async () => {
  const save = deferred<EpisodeVersionSummary>();
  saveDraft.mockReturnValueOnce(save.promise);
  const { result } = await open();
  let settled = false;

  await act(async () => result.current.change('<p>Hai</p>'));
  await act(async () => {
    void result.current.settle().then(() => (settled = true));
  });
  expect(sentTexts()).toEqual(['<p>Hai</p>']);
  expect(settled).toBe(false);

  await act(async () => save.resolve(version()));

  expect(settled).toBe(true);
  expect(result.current.status).toEqual({ kind: 'saved', savedAt: SAVED_AT });
});

test('settling with nothing to save ends at once', async () => {
  const { result } = await open();

  await expect(result.current.settle()).resolves.toBeUndefined();
  expect(saveDraft).not.toHaveBeenCalled();
});

test('a version the API made itself counts as saved', async () => {
  const { result } = await open();

  await act(async () => result.current.change('<p>Đang gõ</p>'));
  await act(async () => result.current.reset('<p>Khôi phục</p>', '2026-10-28T08:00:00Z'));
  await wait(AUTOSAVE_DELAY_MS * 2);

  // The text typed before the restore is not sent over it.
  expect(saveDraft).not.toHaveBeenCalled();
  expect(result.current.status).toEqual({ kind: 'saved', savedAt: '2026-10-28T08:00:00Z' });

  await act(async () => result.current.change('<p>Khôi phục</p>'));
  await wait(AUTOSAVE_DELAY_MS);
  expect(saveDraft).not.toHaveBeenCalled();
});
