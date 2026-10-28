import i18n, { formatDate, genreName } from '@/i18n';
import en from '@/i18n/locales/en.json';
import vi from '@/i18n/locales/vi.json';
import { GENRES } from '@/testing/api';

afterEach(async () => {
  await i18n.changeLanguage('en');
});

test('every genre the API offers has a name in English and in Vietnamese', () => {
  for (const { slug } of GENRES) {
    expect(en.genres).toHaveProperty([slug]);
    expect(vi.genres).toHaveProperty([slug]);
  }
  expect(Object.keys(en.genres).sort()).toEqual(GENRES.map((genre) => genre.slug).sort());
});

test('a genre is named in the current language', async () => {
  expect(genreName('slice-of-life')).toBe('Slice of Life');

  await i18n.changeLanguage('vi');

  expect(genreName('slice-of-life')).toBe('Đời thường');
});

test('a genre this build does not know falls back to the name the API sent', () => {
  expect(genreName('isekai', 'Isekai')).toBe('Isekai');
  expect(genreName('isekai')).toBe('isekai');
});

test('dates follow the current language', async () => {
  const english = formatDate('2026-10-13T04:30:00Z');

  await i18n.changeLanguage('vi');
  const vietnamese = formatDate('2026-10-13T04:30:00Z');

  expect(english).toMatch(/Oct/);
  expect(vietnamese).toMatch(/thg 10|tháng 10/);
});
