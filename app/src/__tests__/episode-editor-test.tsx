import { act, fireEvent } from '@testing-library/react-native';
import { Stack } from 'expo-router';
import { screen } from 'expo-router/testing-library';
import type { ComponentProps } from 'react';

import {
  authorGetDraft,
  authorGetEpisode,
  authorSaveDraft,
  authorUpdateEpisode,
} from '@/api/generated';
import EpisodeEditorScreen from '@/app/studio/episodes/[episodeId]';
import i18n from '@/i18n';
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

const getEpisode = jest.mocked(authorGetEpisode);
const getDraft = jest.mocked(authorGetDraft);
const saveDraft = jest.mocked(authorSaveDraft);
const updateEpisode = jest.mocked(authorUpdateEpisode);

const EPISODE = authorEpisode(2, { title: 'Chương 2: Dầu sương' });
const DRAFT = draft();

beforeEach(() => {
  jest.clearAllMocks();
  getEpisode.mockReturnValue(ok(EPISODE));
  getDraft.mockReturnValue(ok(DRAFT));
  saveDraft.mockReturnValue(
    ok({ id: 'version-2', created_at: '2026-10-28T07:00:00Z', is_published: false }),
  );
  updateEpisode.mockImplementation(({ body }) => ok({ ...EPISODE, title: body.title ?? EPISODE.title }));
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
