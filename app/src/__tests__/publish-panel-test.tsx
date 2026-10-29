import { act, fireEvent } from '@testing-library/react-native';
import { Stack } from 'expo-router';
import { screen } from 'expo-router/testing-library';
import type { ComponentProps } from 'react';

import {
  authorGetDraft,
  authorGetEpisode,
  authorPublishEpisode,
  authorSaveDraft,
  authorScheduleEpisode,
  authorUnscheduleEpisode,
  type EpisodeResponse,
} from '@/api/generated';
import EpisodeEditorScreen from '@/app/studio/episodes/[episodeId]';
import i18n, { formatDateTime } from '@/i18n';
import type PublishTimePicker from '@/studio/publish-time-picker';
import type RichTextEditor from '@/studio/rich-text-editor';
import { authorEpisode, draft, fails, ok } from '@/testing/api';
import { openRouter } from '@/testing/router';

jest.mock('@/api/generated');
// The real editor is a web page; here the test types through what it is given.
const mockEditor = jest.fn((_props: ComponentProps<typeof RichTextEditor>) => null);
jest.mock('@/studio/rich-text-editor', () => ({
  __esModule: true,
  default: (props: ComponentProps<typeof RichTextEditor>) => mockEditor(props),
}));
// The version history, which the editor screen holds, shows text in this web page.
jest.mock('@/reader/novel-view', () => ({ __esModule: true, default: () => null }));
// The real picker opens system dialogs; here the test picks through what it is given.
const mockPicker = jest.fn((_props: ComponentProps<typeof PublishTimePicker>) => null);
jest.mock('@/studio/publish-time-picker', () => ({
  __esModule: true,
  default: (props: ComponentProps<typeof PublishTimePicker>) => mockPicker(props),
}));

const getEpisode = jest.mocked(authorGetEpisode);
const getDraft = jest.mocked(authorGetDraft);
const saveDraft = jest.mocked(authorSaveDraft);
const publishEpisode = jest.mocked(authorPublishEpisode);
const scheduleEpisode = jest.mocked(authorScheduleEpisode);
const unscheduleEpisode = jest.mocked(authorUnscheduleEpisode);

const DRAFT_EPISODE = authorEpisode(3, { latest_version_id: 'version-1' });
const PUBLISHED = authorEpisode(3, {
  status: 'published',
  publish_at: '2026-10-29T08:00:00Z',
  published_version_id: 'version-1',
  latest_version_id: 'version-1',
});
const LATER = new Date('2030-01-15T13:30:00Z');
const SCHEDULED = authorEpisode(3, {
  status: 'scheduled',
  publish_at: LATER.toISOString(),
  published_version_id: 'version-1',
  latest_version_id: 'version-1',
});

beforeEach(() => {
  jest.clearAllMocks();
  getEpisode.mockReturnValue(ok(DRAFT_EPISODE));
  getDraft.mockReturnValue(ok(draft()));
  saveDraft.mockReturnValue(
    ok({ id: 'version-2', created_at: '2026-10-29T07:00:00Z', is_published: false }),
  );
  publishEpisode.mockReturnValue(ok(PUBLISHED));
  scheduleEpisode.mockReturnValue(ok(SCHEDULED));
  unscheduleEpisode.mockReturnValue(ok(DRAFT_EPISODE));
});

afterEach(async () => {
  await i18n.changeLanguage('en');
});

function editor(): ComponentProps<typeof RichTextEditor> {
  const props = mockEditor.mock.lastCall?.[0];
  if (!props) {
    throw new Error('The editor is not on the screen');
  }
  return props;
}

function picker(): ComponentProps<typeof PublishTimePicker> {
  const props = mockPicker.mock.lastCall?.[0];
  if (!props) {
    throw new Error('The time picker is not on the screen');
  }
  return props;
}

async function openEditor(episode: EpisodeResponse = DRAFT_EPISODE) {
  getEpisode.mockReturnValue(ok(episode));
  await openRouter(
    { _layout: () => <Stack />, 'studio/episodes/[episodeId]': EpisodeEditorScreen },
    `/studio/episodes/${episode.id}`,
  );
  await screen.findByDisplayValue(episode.title);
}

const press = (name: string) => fireEvent.press(screen.getByRole('button', { name }));

test('FR-NV-01: publishing a draft takes two presses', async () => {
  await openEditor();

  await press('Publish now');
  expect(publishEpisode).not.toHaveBeenCalled();
  expect(
    screen.getByText('Publish this episode now? Readers can open it straight away.'),
  ).toBeOnTheScreen();

  await press('Publish');

  expect(publishEpisode.mock.lastCall?.[0]).toEqual({ path: { episode_id: DRAFT_EPISODE.id } });
  expect(await screen.findByText('Published')).toBeOnTheScreen();
  expect(screen.queryByRole('button', { name: 'Publish now' })).toBeNull();
});

test('FR-NV-01: what is typed is saved before the episode is published', async () => {
  await openEditor();

  await act(async () => editor().onChange('<p>Bản mới nhất.</p>'));
  await press('Publish now');
  await press('Publish');

  expect(saveDraft.mock.lastCall?.[0].body).toEqual({ body_html: '<p>Bản mới nhất.</p>' });
  expect(saveDraft.mock.invocationCallOrder[0]).toBeLessThan(
    publishEpisode.mock.invocationCallOrder[0]!,
  );
});

test('FR-NV-01: nothing is published while the newest text cannot be saved', async () => {
  saveDraft.mockReturnValue(fails('rate_limited'));
  await openEditor();

  await act(async () => editor().onChange('<p>Bản mới nhất.</p>'));
  await press('Publish now');
  await press('Publish');

  expect(publishEpisode).not.toHaveBeenCalled();
  expect(
    screen.getByText(
      'Your latest text is not saved yet, so nothing was published. Try again in a moment.',
    ),
  ).toBeOnTheScreen();
});

test('an episode with no text says why it was not published', async () => {
  publishEpisode.mockReturnValue(fails('nothing_to_publish'));
  await openEditor();

  await press('Publish now');
  await press('Publish');

  expect(await screen.findByText('Write some text before publishing.')).toBeOnTheScreen();
});

test('FR-NV-02: scheduling sends the chosen time', async () => {
  await openEditor();

  await press('Schedule');
  await act(async () => picker().onChange(LATER));
  await press(`Schedule for ${formatDateTime(LATER.toISOString())}`);

  expect(scheduleEpisode.mock.lastCall?.[0]).toEqual({
    path: { episode_id: DRAFT_EPISODE.id },
    body: { publish_at: LATER.toISOString() },
  });
  expect(
    await screen.findByText(`Scheduled for ${formatDateTime(LATER.toISOString())}`),
  ).toBeOnTheScreen();
});

test('FR-NV-02: a time already past is not sent', async () => {
  await openEditor();

  await press('Schedule');
  await act(async () => picker().onChange(new Date('2020-01-01T00:00:00Z')));
  await press(`Schedule for ${formatDateTime('2020-01-01T00:00:00Z')}`);

  expect(scheduleEpisode).not.toHaveBeenCalled();
  expect(screen.getByText('Choose a time in the future.')).toBeOnTheScreen();
});

test('FR-NV-02: scheduling waits for a time to be chosen', async () => {
  await openEditor();

  await press('Schedule');

  expect(screen.getByRole('button', { name: 'Schedule' })).toBeDisabled();
});

test('FR-NV-02: calling a schedule off takes two presses and makes it a draft again', async () => {
  await openEditor(SCHEDULED);

  await press('Cancel schedule');
  expect(unscheduleEpisode).not.toHaveBeenCalled();
  await press('Cancel schedule');

  expect(unscheduleEpisode.mock.lastCall?.[0]).toEqual({ path: { episode_id: SCHEDULED.id } });
  expect(await screen.findByText('Draft')).toBeOnTheScreen();
  expect(screen.getByRole('button', { name: 'Publish now' })).toBeOnTheScreen();
});

test('FR-NV-02: text saved after scheduling waits, and the screen says so', async () => {
  await openEditor({ ...SCHEDULED, has_unpublished_changes: true });

  expect(
    screen.getByText(
      'Changes saved after scheduling go live only if you schedule again or publish now.',
    ),
  ).toBeOnTheScreen();
  expect(screen.getByRole('button', { name: 'Change time' })).toBeOnTheScreen();
});

test('FR-NV-01: a published episode offers to publish only when it has changes', async () => {
  await openEditor(PUBLISHED);

  expect(screen.queryByRole('button', { name: 'Publish changes' })).toBeNull();
  expect(screen.queryByRole('button', { name: 'Schedule' })).toBeNull();

  await act(async () => editor().onChange('<p>Sửa một chữ.</p>'));
  expect(screen.getByText('Published · Unpublished changes')).toBeOnTheScreen();
  await press('Publish changes');
  await press('Publish');

  expect(publishEpisode).toHaveBeenCalledTimes(1);
  expect(await screen.findByText('Published')).toBeOnTheScreen();
  expect(screen.queryByRole('button', { name: 'Publish changes' })).toBeNull();
});

test('NFR-13: the publish controls are in Vietnamese when that is the language', async () => {
  await i18n.changeLanguage('vi');
  await openEditor();

  expect(screen.getByRole('button', { name: 'Đăng ngay' })).toBeOnTheScreen();
  expect(screen.getByRole('button', { name: 'Hẹn giờ đăng' })).toBeOnTheScreen();
});
