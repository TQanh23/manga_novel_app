import { fireEvent } from '@testing-library/react-native';
import { Stack } from 'expo-router';
import { screen } from 'expo-router/testing-library';

import {
  authorCreateGlossaryEntry,
  authorDeleteGlossaryEntry,
  authorGetWork,
  authorListGlossary,
  authorUpdateGlossaryEntry,
  type GlossaryEntryResponse,
} from '@/api/generated';
import GlossaryScreen from '@/app/studio/glossary/[workId]';
import i18n from '@/i18n';
import {
  factValue,
  glossaryChanges,
  glossaryFields,
  glossaryValues,
} from '@/studio/glossary-form';
import { authorWork, fails, ok } from '@/testing/api';
import { openRouter } from '@/testing/router';

jest.mock('@/api/generated');

const listGlossary = jest.mocked(authorListGlossary);
const createEntry = jest.mocked(authorCreateGlossaryEntry);
const updateEntry = jest.mocked(authorUpdateGlossaryEntry);
const deleteEntry = jest.mocked(authorDeleteGlossaryEntry);

function entry(overrides: Partial<GlossaryEntryResponse> = {}): GlossaryEntryResponse {
  return {
    id: 'an-nhien',
    work_id: 'lantern',
    kind: 'character',
    name: 'Lê An Nhiên',
    aliases: ['An Nhiên'],
    // As the seed has it: a number among the text.
    attributes: { tuổi: 17, 'màu mắt': 'nâu' },
    translations: { en: 'Le An Nhien', ko: '레 안 니엔', ja: 'レ・アン・ニエン' },
    created_at: '2026-10-01T02:00:00Z',
    updated_at: '2026-10-13T04:30:00Z',
    ...overrides,
  };
}

const AN_NHIEN = entry();
const TOWER = entry({
  id: 'tower',
  kind: 'place',
  name: 'Tháp Đèn',
  aliases: [],
  attributes: { 'số bậc': 108 },
  translations: {},
});

beforeEach(() => {
  jest.clearAllMocks();
  jest.mocked(authorGetWork).mockReturnValue(ok(authorWork({ id: 'lantern', language: 'vi' })));
  listGlossary.mockReturnValue(ok([AN_NHIEN, TOWER]));
  createEntry.mockImplementation(({ body }) => ok(entry({ id: 'new', ...body })));
  updateEntry.mockImplementation(({ body }) => ok({ ...AN_NHIEN, ...body }));
  deleteEntry.mockReturnValue(ok(undefined));
});

afterEach(async () => {
  await i18n.changeLanguage('en');
});

function openGlossary() {
  return openRouter(
    { _layout: () => <Stack />, 'studio/glossary/[workId]': GlossaryScreen },
    '/studio/glossary/lantern',
  );
}

describe('the entry the form sends', () => {
  test('a fact the author did not touch keeps its type; a typed number becomes one', () => {
    expect(factValue({ id: 0, key: 'tuổi', value: '17', original: 17 })).toBe(17);
    expect(factValue({ id: 0, key: 'tuổi', value: '18', original: 17 })).toBe(18);
    expect(factValue({ id: 0, key: 'mã', value: '007' })).toBe('007');
    expect(factValue({ id: 0, key: 'màu mắt', value: ' xám ' })).toBe('xám');
    expect(factValue({ id: 0, key: 'bạn', value: '["Khải"]', original: ['Khải'] })).toEqual([
      'Khải',
    ]);
  });

  test('FR-NV-03: names and facts are cleaned up, blank rows left out', () => {
    const values = {
      ...glossaryValues(null, 'term'),
      name: '  Ánh lam ',
      aliases: 'đèn lam、青い灯， 푸른 등, đèn lam',
      translations: { en: ' Blue light ', ja: '  ' },
      facts: [
        { id: 0, key: ' màu ', value: 'lam' },
        { id: 1, key: '', value: '' },
      ],
    };

    expect(glossaryFields(values)).toEqual({
      fields: {
        kind: 'term',
        name: 'Ánh lam',
        aliases: ['đèn lam', '青い灯', '푸른 등'],
        attributes: { màu: 'lam' },
        translations: { en: 'Blue light' },
      },
    });
  });

  test.each([
    [{ name: '  ' }, 'nameRequired'],
    [{ facts: [{ id: 0, key: '', value: 'nâu' }] }, 'attributeKeyRequired'],
    [
      {
        facts: [
          { id: 0, key: 'tuổi', value: '17' },
          { id: 1, key: ' tuổi', value: '18' },
        ],
      },
      'duplicateKey',
    ],
    [
      { aliases: Array.from({ length: 21 }, (_, index) => `tên ${index}`).join(', ') },
      'tooManyAliases',
    ],
    [{ facts: [{ id: 0, key: 'ㄱ'.repeat(51), value: 'a' }] }, 'attributeKeyTooLong'],
  ])('what cannot be sent is caught first: %j', (change, problem) => {
    const values = { ...glossaryValues(null), name: 'Tên', ...change };

    expect(glossaryFields(values)).toMatchObject({ problem });
  });

  test('an edit sends only what changed, whatever order the facts are in', () => {
    const result = glossaryFields({
      ...glossaryValues(AN_NHIEN),
      facts: [
        { id: 1, key: 'màu mắt', value: 'nâu', original: 'nâu' },
        { id: 0, key: 'tuổi', value: '17', original: 17 },
      ],
      name: 'Lê An Nhiên',
    });
    if (!('fields' in result)) {
      throw new Error('expected fields');
    }

    expect(glossaryChanges(AN_NHIEN, result.fields)).toEqual({});
    expect(glossaryChanges(AN_NHIEN, { ...result.fields, aliases: ['Nhiên'] })).toEqual({
      aliases: ['Nhiên'],
    });
  });
});

test('FR-NV-03: the glossary lists its entries by kind', async () => {
  await openGlossary();

  expect(await screen.findByRole('header', { name: 'Characters' })).toBeOnTheScreen();
  expect(screen.getByRole('header', { name: 'Places' })).toBeOnTheScreen();
  expect(screen.queryByRole('header', { name: 'Terms' })).toBeNull();
  expect(screen.getByRole('button', { name: 'Lê An Nhiên' })).toBeOnTheScreen();
  expect(screen.getByText('An Nhiên')).toBeOnTheScreen();
  expect(screen.getByText('2 facts')).toBeOnTheScreen();
  expect(screen.getByText('1 fact')).toBeOnTheScreen();
  expect(listGlossary.mock.lastCall?.[0].path).toEqual({ work_id: 'lantern' });
});

test('FR-NV-03: an empty glossary says so', async () => {
  listGlossary.mockReturnValue(ok([]));
  await openGlossary();

  expect(await screen.findByText('Nothing noted yet.')).toBeOnTheScreen();
});

test('FR-NV-03: an author adds a place with its names and a fact', async () => {
  await openGlossary();

  await fireEvent.press(await screen.findByRole('button', { name: 'New entry' }));
  await fireEvent.press(screen.getByRole('radio', { name: 'Place' }));
  await fireEvent.changeText(screen.getByLabelText('Name'), 'Kinh Lạc');
  await fireEvent.changeText(screen.getByLabelText('Other names'), 'kinh thành');
  await fireEvent.changeText(screen.getByLabelText('Korean'), '낑 락');
  await fireEvent.press(screen.getByRole('button', { name: 'Add a fact' }));
  await fireEvent.changeText(screen.getByLabelText('Fact 1'), 'cách Bến Sương');
  await fireEvent.changeText(screen.getByLabelText('Value 1'), 'ba ngày thuyền');
  await fireEvent.press(screen.getByRole('button', { name: 'Add entry' }));

  expect(createEntry.mock.lastCall?.[0]).toEqual({
    path: { work_id: 'lantern' },
    body: {
      kind: 'place',
      name: 'Kinh Lạc',
      aliases: ['kinh thành'],
      attributes: { 'cách Bến Sương': 'ba ngày thuyền' },
      translations: { ko: '낑 락' },
    },
  });
  expect(await screen.findByRole('button', { name: 'New entry' })).toBeOnTheScreen();
  expect(listGlossary).toHaveBeenCalledTimes(2);
});

test('FR-NV-03: the name in the work’s own language has no field: it is the name', async () => {
  await openGlossary();

  await fireEvent.press(await screen.findByRole('button', { name: 'New entry' }));

  expect(screen.getByLabelText('Korean')).toBeOnTheScreen();
  expect(screen.getByLabelText('Japanese')).toBeOnTheScreen();
  expect(screen.getByLabelText('English')).toBeOnTheScreen();
  expect(screen.queryByLabelText('Vietnamese')).toBeNull();
});

test('FR-NV-03: editing an entry sends what changed and keeps the types of the rest', async () => {
  await openGlossary();

  await fireEvent.press(await screen.findByRole('button', { name: 'Lê An Nhiên' }));
  expect(screen.getByDisplayValue('17')).toBeOnTheScreen();
  await fireEvent.changeText(screen.getByDisplayValue('nâu'), 'nâu sẫm');
  await fireEvent.press(screen.getByRole('button', { name: 'Remove this fact: tuổi' }));
  await fireEvent.press(screen.getByRole('button', { name: 'Add a fact' }));
  await fireEvent.changeText(screen.getByLabelText('Fact 2'), 'tuổi');
  await fireEvent.changeText(screen.getByLabelText('Value 2'), '18');
  await fireEvent.press(screen.getByRole('button', { name: 'Save entry' }));

  expect(updateEntry.mock.lastCall?.[0]).toEqual({
    path: { work_id: 'lantern', entry_id: 'an-nhien' },
    body: { attributes: { 'màu mắt': 'nâu sẫm', tuổi: 18 } },
  });
});

test('FR-NV-03: a name already in the glossary is refused with the reason', async () => {
  createEntry.mockReturnValue(fails('glossary_entry_exists'));
  await openGlossary();

  await fireEvent.press(await screen.findByRole('button', { name: 'New entry' }));
  await fireEvent.changeText(screen.getByLabelText('Name'), 'Lê An Nhiên');
  await fireEvent.press(screen.getByRole('button', { name: 'Add entry' }));

  expect(
    await screen.findByText('This work already has an entry of that kind with that name.'),
  ).toBeOnTheScreen();
  expect(screen.getByLabelText('Name')).toBeOnTheScreen();
});

test('a fact with a value but no name is caught before anything is sent', async () => {
  await openGlossary();

  await fireEvent.press(await screen.findByRole('button', { name: 'New entry' }));
  await fireEvent.changeText(screen.getByLabelText('Name'), 'Vũ Khải');
  await fireEvent.press(screen.getByRole('button', { name: 'Add a fact' }));
  await fireEvent.changeText(screen.getByLabelText('Value 1'), 'nâu');
  await fireEvent.press(screen.getByRole('button', { name: 'Add entry' }));

  expect(screen.getByText('Every fact with a value needs a name.')).toBeOnTheScreen();
  expect(createEntry).not.toHaveBeenCalled();
});

test('cancel goes back to the list and sends nothing', async () => {
  await openGlossary();

  await fireEvent.press(await screen.findByRole('button', { name: 'Lê An Nhiên' }));
  await fireEvent.changeText(screen.getByLabelText('Name'), 'Ai đó');
  await fireEvent.press(screen.getByRole('button', { name: 'Cancel' }));

  expect(screen.getByRole('button', { name: 'Lê An Nhiên' })).toBeOnTheScreen();
  expect(updateEntry).not.toHaveBeenCalled();
});

test("another author's glossary reads as not found", async () => {
  jest.mocked(authorGetWork).mockReturnValue(fails('work_not_found'));
  listGlossary.mockReturnValue(fails('work_not_found'));
  await openGlossary();

  expect(await screen.findByText('This work does not exist or is not yours.')).toBeOnTheScreen();
});

test('NFR-13: the glossary is in Vietnamese when that is the language', async () => {
  await i18n.changeLanguage('vi');
  await openGlossary();

  expect(await screen.findByRole('header', { name: 'Nhân vật' })).toBeOnTheScreen();
  expect(screen.getByText('2 chi tiết')).toBeOnTheScreen();

  await fireEvent.press(screen.getByRole('button', { name: 'Mục mới' }));
  expect(screen.getByRole('radio', { name: 'Địa danh' })).toBeOnTheScreen();
  expect(screen.getByLabelText('Tiếng Hàn')).toBeOnTheScreen();
  expect(screen.getByRole('button', { name: 'Thêm chi tiết' })).toBeOnTheScreen();
});

test('FR-NV-03: deleting an entry asks first, then takes it out of the glossary', async () => {
  await openGlossary();
  await fireEvent.press(await screen.findByRole('button', { name: 'Lê An Nhiên' }));

  await fireEvent.press(screen.getByRole('button', { name: 'Delete entry' }));
  expect(
    screen.getByText('Delete “Lê An Nhiên” from the glossary? This cannot be undone.'),
  ).toBeOnTheScreen();
  expect(deleteEntry).not.toHaveBeenCalled();

  listGlossary.mockReturnValue(ok([TOWER]));
  await fireEvent.press(screen.getByRole('button', { name: 'Delete' }));

  expect(deleteEntry.mock.lastCall?.[0].path).toEqual({ work_id: 'lantern', entry_id: 'an-nhien' });
  expect(await screen.findByRole('button', { name: 'Tháp Đèn' })).toBeOnTheScreen();
  expect(screen.queryByRole('button', { name: 'Lê An Nhiên' })).toBeNull();
});

test('keeping the entry deletes nothing', async () => {
  await openGlossary();
  await fireEvent.press(await screen.findByRole('button', { name: 'Lê An Nhiên' }));

  await fireEvent.press(screen.getByRole('button', { name: 'Delete entry' }));
  await fireEvent.press(screen.getByRole('button', { name: 'Keep it' }));

  expect(deleteEntry).not.toHaveBeenCalled();
  expect(screen.getByRole('button', { name: 'Delete entry' })).toBeOnTheScreen();
});

test('a delete that failed says why and leaves the entry open', async () => {
  deleteEntry.mockReturnValue(fails('rate_limited'));
  await openGlossary();
  await fireEvent.press(await screen.findByRole('button', { name: 'Lê An Nhiên' }));

  await fireEvent.press(screen.getByRole('button', { name: 'Delete entry' }));
  await fireEvent.press(screen.getByRole('button', { name: 'Delete' }));

  expect(
    await screen.findByText('Too many attempts. Wait a moment and try again.'),
  ).toBeOnTheScreen();
  expect(screen.getByDisplayValue('Lê An Nhiên')).toBeOnTheScreen();
});

test('a new entry has nothing to delete', async () => {
  await openGlossary();

  await fireEvent.press(await screen.findByRole('button', { name: 'New entry' }));

  expect(screen.queryByRole('button', { name: 'Delete entry' })).toBeNull();
});
