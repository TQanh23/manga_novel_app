import { fireEvent, within } from '@testing-library/react-native';
import { Stack } from 'expo-router';
import { screen } from 'expo-router/testing-library';

import {
  authorCreateWork,
  authorGetWork,
  authorListWorks,
  authorListWufPresets,
  authorUpdateWork,
  catalogueListGenres,
  type UserResponse,
} from '@/api/generated';
import StudioScreen from '@/app/(tabs)/studio';
import EditWorkScreen from '@/app/studio/[workId]';
import NewWorkScreen from '@/app/studio/new';
import { useSession } from '@/auth/session';
import i18n from '@/i18n';
import { AUTHOR, authorWork, fails, GENRES, ok, READER, WUF_PRESETS } from '@/testing/api';
import { openRouter } from '@/testing/router';

jest.mock('@/api/generated');
jest.mock('@/auth/session', () => ({ useSession: jest.fn() }));

const listWorks = jest.mocked(authorListWorks);
const getWork = jest.mocked(authorGetWork);
const createWork = jest.mocked(authorCreateWork);
const updateWork = jest.mocked(authorUpdateWork);
const session = jest.mocked(useSession);

function signedIn(user: UserResponse | null) {
  session.mockReturnValue({ user, isLoading: false } as ReturnType<typeof useSession>);
}

const LANTERN = authorWork({ id: 'lantern' });

beforeEach(() => {
  jest.clearAllMocks();
  signedIn(AUTHOR);
  jest.mocked(catalogueListGenres).mockReturnValue(ok(GENRES));
  jest.mocked(authorListWufPresets).mockReturnValue(ok(WUF_PRESETS));
  listWorks.mockReturnValue(ok([LANTERN, authorWork({ id: 'sample', title: 'Mẫu', is_sample: true })]));
  getWork.mockReturnValue(ok(LANTERN));
  createWork.mockReturnValue(ok(authorWork({ id: 'created' })));
  updateWork.mockImplementation(({ body }) => ok({ ...LANTERN, ...body }));
});

afterEach(async () => {
  await i18n.changeLanguage('en');
});

function openStudio(url: string) {
  return openRouter(
    {
      _layout: () => <Stack />,
      studio: StudioScreen,
      'studio/new': NewWorkScreen,
      'studio/[workId]': EditWorkScreen,
    },
    url,
  );
}

test('FR-NV-01: an author sees their works and opens one', async () => {
  const router = await openStudio('/studio');

  expect(await screen.findByRole('link', { name: LANTERN.title })).toBeOnTheScreen();
  expect(screen.getByText('Novel · Ongoing · Sample')).toBeOnTheScreen();

  await fireEvent.press(screen.getByRole('link', { name: LANTERN.title }));

  expect(router.pathname()).toBe('/studio/lantern');
  expect(await screen.findByDisplayValue(LANTERN.title)).toBeOnTheScreen();
});

test('FR-NV-01: a studio with no works says how to start', async () => {
  listWorks.mockReturnValue(ok([]));
  const router = await openStudio('/studio');

  expect(
    await screen.findByText('You have no works yet. Start one to publish your first episode.'),
  ).toBeOnTheScreen();

  await fireEvent.press(screen.getByRole('button', { name: 'New work' }));

  expect(router.pathname()).toBe('/studio/new');
});

test('the studio tells a reader it is for authors and asks for nothing', async () => {
  signedIn(READER);
  await openStudio('/studio');

  expect(
    screen.getByText('The studio is for authors. You can become one on the Account tab.'),
  ).toBeOnTheScreen();
  expect(listWorks).not.toHaveBeenCalled();
});

test('FR-NV-01: an author creates a manga with genres, tags and a wait-until-free period', async () => {
  const router = await openStudio('/studio/new');

  await fireEvent.press(await screen.findByRole('radio', { name: 'Manga' }));
  await fireEvent.changeText(screen.getByLabelText('Title'), '  Kiếm Sĩ Dưới Trăng ');
  await fireEvent.changeText(screen.getByLabelText('Synopsis'), 'Một thanh kiếm, một lời thề.');
  await fireEvent.press(screen.getByRole('radio', { name: 'Japanese' }));
  await fireEvent.press(screen.getByRole('checkbox', { name: 'Fantasy' }));
  await fireEvent.press(screen.getByRole('checkbox', { name: 'Action' }));
  // Commas of each content language separate tags; spaces belong to them.
  await fireEvent.changeText(screen.getByLabelText('Tags'), 'Kiếm sĩ, 武士、Trăng， Kiếm sĩ,');
  await fireEvent.press(screen.getByRole('radio', { name: '1 day' }));
  await fireEvent.press(screen.getByRole('button', { name: 'Create work' }));

  expect(createWork.mock.lastCall?.[0].body).toEqual({
    type: 'manga',
    title: 'Kiếm Sĩ Dưới Trăng',
    synopsis: 'Một thanh kiếm, một lời thề.',
    language: 'ja',
    wuf_preset_id: 'wuf-1d',
    genres: ['fantasy', 'action'],
    tags: ['Kiếm sĩ', '武士', 'Trăng'],
  });
  expect(router.pathname()).toBe('/studio/created');
});

test('FR-NV-01: the periods on offer are listed shortest first, after Off', async () => {
  await openStudio('/studio/new');

  const group = within(await screen.findByLabelText('Wait until free'));
  const labels = group.getAllByRole('radio').map((chip) => chip.props.accessibilityLabel);

  expect(labels).toEqual(['Off', '3 hours', '12 hours', '1 day', '3 days']);
  expect(screen.getByRole('radio', { name: 'Off' })).toBeSelected();
});

test('FR-NV-01: a work needs a title before anything is sent', async () => {
  await openStudio('/studio/new');

  await fireEvent.changeText(await screen.findByLabelText('Title'), '   ');
  await fireEvent.press(screen.getByRole('button', { name: 'Create work' }));

  expect(screen.getByText('Give the work a title.')).toBeOnTheScreen();
  expect(createWork).not.toHaveBeenCalled();
});

test('FR-NV-01: a fourth genre cannot be chosen', async () => {
  await openStudio('/studio/new');

  for (const name of ['Fantasy', 'Mystery', 'Drama']) {
    await fireEvent.press(await screen.findByRole('checkbox', { name }));
  }

  expect(screen.getByRole('checkbox', { name: 'Horror' })).toBeDisabled();
  expect(screen.getByRole('checkbox', { name: 'Drama' })).toBeEnabled();
});

test('FR-NV-01: tag length is counted in characters, whatever the script', async () => {
  await openStudio('/studio/new');
  await fireEvent.changeText(await screen.findByLabelText('Title'), 'Tiêu đề');

  await fireEvent.changeText(screen.getByLabelText('Tags'), 'ㄱ'.repeat(31));
  await fireEvent.press(screen.getByRole('button', { name: 'Create work' }));
  expect(screen.getByText('A tag has at most 30 characters.')).toBeOnTheScreen();
  expect(createWork).not.toHaveBeenCalled();

  // Thirty characters outside the Basic Multilingual Plane: sixty UTF-16 units.
  await fireEvent.changeText(screen.getByLabelText('Tags'), '𠀀'.repeat(30));
  await fireEvent.press(screen.getByRole('button', { name: 'Create work' }));
  expect(createWork.mock.lastCall?.[0].body?.tags).toEqual(['𠀀'.repeat(30)]);
});

test('FR-NV-01: a refused work says why and stays on the form', async () => {
  createWork.mockReturnValue(fails('invalid_wuf_preset'));
  const router = await openStudio('/studio/new');

  await fireEvent.changeText(await screen.findByLabelText('Title'), 'Tiêu đề');
  await fireEvent.press(screen.getByRole('button', { name: 'Create work' }));

  expect(
    await screen.findByText('That wait-until-free period is no longer offered. Choose another.'),
  ).toBeOnTheScreen();
  expect(router.pathname()).toBe('/studio/new');
});

test('FR-NV-01: editing a work sends only what changed', async () => {
  getWork.mockReturnValue(ok({ ...LANTERN, wuf_preset_id: 'retired-preset' }));
  await openStudio('/studio/lantern');

  await fireEvent.changeText(await screen.findByLabelText('Title'), 'Người Giữ Đèn');
  await fireEvent.press(screen.getByRole('radio', { name: 'Completed' }));
  await fireEvent.press(screen.getByRole('button', { name: 'Save changes' }));

  // The retired period is not sent back, so the API has nothing to refuse.
  expect(updateWork.mock.lastCall?.[0]).toEqual({
    path: { work_id: 'lantern' },
    body: { title: 'Người Giữ Đèn', status: 'completed' },
  });
  expect(await screen.findByText('Saved.')).toBeOnTheScreen();
  expect(screen.queryByRole('radio', { name: 'Manga' })).toBeNull();
});

test('FR-NV-01: a second save compares with what the first one saved', async () => {
  await openStudio('/studio/lantern');

  await fireEvent.changeText(await screen.findByLabelText('Title'), 'Người Giữ Đèn');
  await fireEvent.press(screen.getByRole('button', { name: 'Save changes' }));
  await screen.findByText('Saved.');
  await fireEvent.press(screen.getByRole('radio', { name: '3 hours' }));
  await fireEvent.press(screen.getByRole('button', { name: 'Save changes' }));

  expect(updateWork).toHaveBeenCalledTimes(2);
  expect(updateWork.mock.lastCall?.[0].body).toEqual({ wuf_preset_id: 'wuf-3h' });
});

test('FR-NV-01: turning wait-until-free off sends null', async () => {
  getWork.mockReturnValue(ok({ ...LANTERN, wuf_preset_id: 'wuf-1d' }));
  await openStudio('/studio/lantern');

  await fireEvent.press(await screen.findByRole('radio', { name: 'Off' }));
  await fireEvent.press(screen.getByRole('button', { name: 'Save changes' }));

  expect(updateWork.mock.lastCall?.[0].body).toEqual({ wuf_preset_id: null });
});

test('FR-NV-01: genres and tags are sent whole when one of them changes', async () => {
  await openStudio('/studio/lantern');

  await fireEvent.press(await screen.findByRole('checkbox', { name: 'Mystery' }));
  await fireEvent.changeText(screen.getByLabelText('Tags'), 'Bến sông, Đèn');
  await fireEvent.press(screen.getByRole('button', { name: 'Save changes' }));

  expect(updateWork.mock.lastCall?.[0].body).toEqual({
    genres: ['fantasy', 'mystery'],
    tags: ['Bến sông', 'Đèn'],
  });
});

test("FR-NV-01: another author's work reads as not found", async () => {
  getWork.mockReturnValue(fails('work_not_found'));
  await openStudio('/studio/someone-elses');

  expect(await screen.findByText('This work does not exist or is not yours.')).toBeOnTheScreen();
  expect(screen.queryByRole('button', { name: 'Save changes' })).toBeNull();
});

test('NFR-13: the studio form is in Vietnamese when that is the language', async () => {
  await i18n.changeLanguage('vi');
  await openStudio('/studio/new');

  expect(await screen.findByRole('radio', { name: 'Tiểu thuyết' })).toBeOnTheScreen();
  expect(screen.getByLabelText('Tiêu đề')).toBeOnTheScreen();
  expect(screen.getByRole('radio', { name: 'Tiếng Hàn' })).toBeOnTheScreen();
  expect(screen.getByRole('radio', { name: 'Tiếng Việt' })).toBeSelected();
  expect(screen.getByRole('radio', { name: '12 giờ' })).toBeOnTheScreen();
  expect(screen.getByRole('radio', { name: '3 ngày' })).toBeOnTheScreen();
  expect(screen.getByRole('button', { name: 'Tạo tác phẩm' })).toBeOnTheScreen();
});
