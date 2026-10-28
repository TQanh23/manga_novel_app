import { act, fireEvent } from '@testing-library/react-native';
import { Stack } from 'expo-router';
import { screen } from 'expo-router/testing-library';
import type { ComponentProps } from 'react';

import {
  authorGetDraft,
  authorGetEpisode,
  authorGetVersion,
  authorListVersions,
  authorRestoreVersion,
  authorSaveDraft,
  authorUpdateEpisode,
  type EpisodeVersionSummary,
} from '@/api/generated';
import EpisodeEditorScreen from '@/app/studio/episodes/[episodeId]';
import i18n from '@/i18n';
import type NovelView from '@/reader/novel-view';
import type RichTextEditor from '@/studio/rich-text-editor';
import { AUTOSAVE_DELAY_MS } from '@/studio/use-draft-saver';
import { authorEpisode, draft, fails, ok } from '@/testing/api';
import { openRouter } from '@/testing/router';

jest.mock('@/api/generated');
// The real editor is a web page; here the test sees what it is given and types through it.
const mockEditor = jest.fn((_props: ComponentProps<typeof RichTextEditor>) => null);
jest.mock('@/studio/rich-text-editor', () => ({
  __esModule: true,
  default: (props: ComponentProps<typeof RichTextEditor>) => mockEditor(props),
}));
// The version preview shows the text in the reader's view, also a web page.
const mockNovelView = jest.fn((_props: ComponentProps<typeof NovelView>) => null);
jest.mock('@/reader/novel-view', () => ({
  __esModule: true,
  default: (props: ComponentProps<typeof NovelView>) => mockNovelView(props),
}));

const getEpisode = jest.mocked(authorGetEpisode);
const getDraft = jest.mocked(authorGetDraft);
const saveDraft = jest.mocked(authorSaveDraft);
const updateEpisode = jest.mocked(authorUpdateEpisode);
const listVersions = jest.mocked(authorListVersions);
const getVersion = jest.mocked(authorGetVersion);
const restoreVersion = jest.mocked(authorRestoreVersion);

function version(index: number, overrides: Partial<EpisodeVersionSummary> = {}): EpisodeVersionSummary {
  return {
    id: `version-${index}`,
    // A minute older for each one further down the history.
    created_at: new Date(Date.UTC(2026, 9, 28, 8) - index * 60_000).toISOString(),
    is_published: false,
    ...overrides,
  };
}
// Newest first, as the API lists them; the second one is what readers see.
const VERSIONS = [version(0), version(1, { is_published: true }), version(2)];
const OLD_TEXT = '<p>Bản cũ: chiều nào cũng vậy.</p>';

const EPISODE = authorEpisode(2, { title: 'Chương 2: Dầu sương' });
const DRAFT = draft();

beforeEach(() => {
  jest.clearAllMocks();
  getEpisode.mockReturnValue(ok(EPISODE));
  getDraft.mockReturnValue(ok(DRAFT));
  saveDraft.mockReturnValue(
    ok({ id: 'version-2', created_at: '2026-10-28T07:00:00Z', is_published: false }),
  );
  updateEpisode.mockImplementation(({ body }) =>
    ok({ ...EPISODE, title: body.title ?? EPISODE.title }),
  );
  listVersions.mockReturnValue(ok(VERSIONS));
  getVersion.mockImplementation(({ path }) =>
    ok({ ...VERSIONS.find((item) => item.id === path.version_id)!, body_html: OLD_TEXT }),
  );
  restoreVersion.mockReturnValue(
    ok(version(-1, { id: 'restored', created_at: '2026-10-28T09:30:00Z' })),
  );
});

afterEach(async () => {
  jest.useRealTimers();
  await i18n.changeLanguage('en');
});

function editor(): ComponentProps<typeof RichTextEditor> {
  const props = mockEditor.mock.lastCall?.[0];
  if (!props) {
    throw new Error('The editor is not on the screen');
  }
  return props;
}

async function openEditor() {
  await openRouter(
    { _layout: () => <Stack />, 'studio/episodes/[episodeId]': EpisodeEditorScreen },
    `/studio/episodes/${EPISODE.id}`,
  );
  await screen.findByDisplayValue(EPISODE.title);
}

test('FR-NV-01: the editor opens on the newest saved text', async () => {
  await openEditor();

  expect(getDraft.mock.lastCall?.[0].path).toEqual({ episode_id: EPISODE.id });
  expect(editor().initialHtml).toBe(DRAFT.body_html);
  expect(screen.getByText(/^Saved at /)).toBeOnTheScreen();
});

test('FR-NV-01: what the author types is saved once they pause', async () => {
  await openEditor();
  jest.useFakeTimers();

  await act(async () => editor().onChange('<p>Chiều nào cũng vậy.</p>'));
  expect(screen.getByText('Unsaved changes')).toBeOnTheScreen();

  await act(async () => {
    jest.advanceTimersByTime(AUTOSAVE_DELAY_MS);
  });

  expect(saveDraft.mock.lastCall?.[0]).toEqual({
    path: { episode_id: EPISODE.id },
    body: { body_html: '<p>Chiều nào cũng vậy.</p>' },
  });
  expect(screen.getByText(/^Saved at /)).toBeOnTheScreen();
});

test('FR-NV-01: a save that failed says so', async () => {
  saveDraft.mockReturnValue(fails('rate_limited'));
  await openEditor();
  jest.useFakeTimers();

  await act(async () => editor().onChange('<p>Hai</p>'));
  await act(async () => {
    jest.advanceTimersByTime(AUTOSAVE_DELAY_MS);
  });

  expect(
    screen.getByText(
      'Not saved: Too many attempts. Wait a moment and try again. Trying again shortly.',
    ),
  ).toBeOnTheScreen();
});

test('an episode with nothing saved yet says so', async () => {
  getDraft.mockReturnValue(ok(draft({ version_id: null, body_html: '', saved_at: null })));
  await openEditor();

  expect(editor().initialHtml).toBe('');
  expect(screen.getByText('Nothing saved yet')).toBeOnTheScreen();
});

test('FR-NV-01: the title is saved when the author leaves the field', async () => {
  await openEditor();

  const title = screen.getByLabelText('Title');
  await fireEvent.changeText(title, '  Chương 2: Dầu và sương ');
  await fireEvent(title, 'blur');

  expect(updateEpisode.mock.lastCall?.[0]).toEqual({
    path: { episode_id: EPISODE.id },
    body: { title: 'Chương 2: Dầu và sương' },
  });
  expect(await screen.findByDisplayValue('Chương 2: Dầu và sương')).toBeOnTheScreen();
});

test('an emptied title goes back to the saved one, and nothing is sent', async () => {
  await openEditor();

  const title = screen.getByLabelText('Title');
  await fireEvent.changeText(title, '   ');
  await fireEvent(title, 'blur');

  expect(updateEpisode).not.toHaveBeenCalled();
  expect(screen.getByDisplayValue(EPISODE.title)).toBeOnTheScreen();
});

test('a manga episode has no text to edit yet', async () => {
  getDraft.mockReturnValue(fails('not_a_novel'));
  await openEditor();

  expect(screen.getByText('Uploading manga pages is not available yet.')).toBeOnTheScreen();
  expect(mockEditor).not.toHaveBeenCalled();
});

test("another author's episode reads as not found", async () => {
  getEpisode.mockReturnValue(fails('episode_not_found'));
  getDraft.mockReturnValue(fails('episode_not_found'));
  await openRouter(
    { _layout: () => <Stack />, 'studio/episodes/[episodeId]': EpisodeEditorScreen },
    '/studio/episodes/someone-elses',
  );

  expect(await screen.findByText('This episode does not exist or is not yours.')).toBeOnTheScreen();
  expect(mockEditor).not.toHaveBeenCalled();
});

test('NFR-13: the editor is in Vietnamese when that is the language', async () => {
  await i18n.changeLanguage('vi');
  await openEditor();
  jest.useFakeTimers();

  expect(screen.getByLabelText('Tiêu đề')).toBeOnTheScreen();
  expect(screen.getByText(/^Đã lưu lúc /)).toBeOnTheScreen();

  await act(async () => editor().onChange('<p>Hai</p>'));
  expect(screen.getByText('Có thay đổi chưa lưu')).toBeOnTheScreen();
});

async function openHistory() {
  await fireEvent.press(screen.getByRole('button', { name: 'Version history' }));
  return screen.findAllByRole('button', { name: /2026/ });
}

test('FR-NV-01: the history lists the saved versions, newest first, with what they are', async () => {
  await openEditor();

  const rows = await openHistory();

  expect(listVersions.mock.lastCall?.[0]).toEqual({
    path: { episode_id: EPISODE.id },
    query: { limit: 50 },
  });
  expect(rows).toHaveLength(3);
  expect(screen.getByText('Current')).toBeOnTheScreen();
  expect(screen.getByText('Published')).toBeOnTheScreen();
  expect(mockEditor).toHaveBeenCalled();
  expect(screen.getByRole('button', { name: 'Back to writing' })).toBeOnTheScreen();
});

test('FR-NV-01: what was typed is saved before the history opens', async () => {
  await openEditor();

  await act(async () => editor().onChange('<p>Vừa gõ</p>'));
  await openHistory();

  expect(saveDraft.mock.lastCall?.[0].body).toEqual({ body_html: '<p>Vừa gõ</p>' });
  expect(saveDraft.mock.invocationCallOrder[0]).toBeLessThan(listVersions.mock.invocationCallOrder[0]);
});

test('FR-NV-01: an old version is shown, and restoring it puts its text back in the editor', async () => {
  await openEditor();
  const rows = await openHistory();

  await fireEvent.press(rows[2]);
  expect(
    await screen.findByText(
      'Restoring adds a new version with this text. Nothing in the history is deleted.',
    ),
  ).toBeOnTheScreen();
  expect(getVersion.mock.lastCall?.[0].path).toEqual({
    episode_id: EPISODE.id,
    version_id: 'version-2',
  });
  expect(mockNovelView.mock.lastCall?.[0].paragraphs).toEqual([OLD_TEXT]);

  await fireEvent.press(screen.getByRole('button', { name: 'Restore this version' }));

  expect(restoreVersion.mock.lastCall?.[0].path).toEqual({
    episode_id: EPISODE.id,
    version_id: 'version-2',
  });
  expect(editor().initialHtml).toBe(OLD_TEXT);
  expect(screen.getByText(/^Saved at /)).toBeOnTheScreen();
  // The restore is the newest save; nothing is sent over it.
  expect(saveDraft).not.toHaveBeenCalled();
});

test('the newest version cannot be restored: it is the text already', async () => {
  await openEditor();
  const rows = await openHistory();

  await fireEvent.press(rows[0]);
  await screen.findByRole('button', { name: 'All versions' });

  expect(screen.queryByRole('button', { name: 'Restore this version' })).toBeNull();
});

test('a restore that failed says why and changes nothing', async () => {
  restoreVersion.mockReturnValue(fails('rate_limited'));
  await openEditor();
  const rows = await openHistory();

  await fireEvent.press(rows[1]);
  await fireEvent.press(await screen.findByRole('button', { name: 'Restore this version' }));

  expect(await screen.findByText('Too many attempts. Wait a moment and try again.')).toBeOnTheScreen();
  expect(screen.getByRole('button', { name: 'Back to writing' })).toBeOnTheScreen();
});

test('going back to writing reopens the editor on the text as it was left', async () => {
  await openEditor();
  await act(async () => editor().onChange('<p>Vừa gõ</p>'));
  await openHistory();

  await fireEvent.press(screen.getByRole('button', { name: 'Back to writing' }));

  expect(editor().initialHtml).toBe('<p>Vừa gõ</p>');
  expect(restoreVersion).not.toHaveBeenCalled();
});

test('older versions are fetched below the last one shown', async () => {
  const page = Array.from({ length: 50 }, (_, index) => version(index + 1, { id: `v${index}` }));
  listVersions.mockReturnValueOnce(ok(page)).mockReturnValueOnce(ok([version(60, { id: 'oldest' })]));
  await openEditor();
  await openHistory();

  await fireEvent.press(screen.getByRole('button', { name: 'Load more' }));

  expect(listVersions.mock.lastCall?.[0].query).toEqual({ limit: 50, before: 'v49' });
  expect(await screen.findAllByRole('button', { name: /2026/ })).toHaveLength(51);
  expect(screen.queryByRole('button', { name: 'Load more' })).toBeNull();
});
