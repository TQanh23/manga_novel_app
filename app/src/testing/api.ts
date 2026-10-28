/**
 * Helpers for tests that replace the generated API client with jest mocks:
 *
 *     jest.mock('@/api/generated');
 *
 * Every call of the generated client then resolves to whatever the test says.
 */

import type {
  EpisodeContentResponse,
  EpisodeSummary,
  GenreResponse,
  LibraryResponse,
  ReadingEntryResponse,
  UserResponse,
  WorkCard,
  WorkDetail,
  WorkPage,
} from '@/api/generated';

/** What a generated client call resolves to when the API answered with `data`. */
export function ok<T>(data: T): Promise<never> {
  return Promise.resolve({ data, error: undefined } as never);
}

/** What a generated client call resolves to when the API answered with an error envelope. */
export function fails(code: string): Promise<never> {
  return Promise.resolve({
    data: undefined,
    error: { error: { code, message: code, request_id: null } },
  } as never);
}

/** A call that stays pending until the test settles it. */
export function deferred<T>(): { promise: Promise<never>; resolve: (data: T) => void } {
  type Answer = { data: T; error: undefined };
  let settle: (answer: Answer) => void = () => {};
  const promise = new Promise<Answer>((resolve) => {
    settle = resolve;
  });
  return {
    promise: promise as Promise<never>,
    resolve: (data) => settle({ data, error: undefined }),
  };
}

export function work(overrides: Partial<WorkCard> = {}): WorkCard {
  return {
    id: '01a00000-0000-7000-8000-000000000001',
    type: 'novel',
    title: 'Người Giữ Đèn Bến Sương',
    synopsis: 'Một ngọn đèn ánh lam dẫn thuyền qua sương.',
    language: 'vi',
    status: 'ongoing',
    author: { id: '01a00000-0000-7000-8000-0000000000aa', display_name: 'Nguyễn Tác Giả' },
    genres: ['fantasy', 'mystery'],
    episode_count: 5,
    last_published_at: '2026-10-13T04:30:00Z',
    ...overrides,
  };
}

export function workDetail(overrides: Partial<WorkDetail> = {}): WorkDetail {
  return { ...work(), tags: ['Kỳ ảo', 'Bến sông'], ...overrides };
}

export function page(items: WorkCard[], hasMore = false): WorkPage {
  return { items, has_more: hasMore };
}

export function episode(number: number, overrides: Partial<EpisodeSummary> = {}): EpisodeSummary {
  return {
    id: `01a00000-0000-7000-8000-0000000001${String(number).padStart(2, '0')}`,
    number,
    title: `Chương ${number}`,
    publish_at: '2026-10-13T04:30:00Z',
    price_coins: 0,
    wuf_eligible: false,
    ...overrides,
  };
}

export function episodeContent(
  overrides: Partial<EpisodeContentResponse> = {},
): EpisodeContentResponse {
  return {
    id: '01a00000-0000-7000-8000-000000000102',
    work_id: '01a00000-0000-7000-8000-000000000001',
    number: 2,
    title: 'Chương 2: Dầu sương',
    publish_at: '2026-10-13T04:30:00Z',
    paragraphs: [
      '<h2>Dầu sương</h2>',
      '<p>Chiều nào cũng vậy, An Nhiên lại xách bình dầu lên Tháp Đèn.</p>',
      '<p>Ông Bách gọi vọng lên: <em>chậm thôi</em>.</p>',
    ],
    previous_episode_id: '01a00000-0000-7000-8000-000000000101',
    next_episode_id: '01a00000-0000-7000-8000-000000000103',
    position: null,
    ...overrides,
  };
}

export function readingEntry(overrides: Partial<ReadingEntryResponse> = {}): ReadingEntryResponse {
  return {
    work: work(),
    episode_id: '01a00000-0000-7000-8000-000000000102',
    episode_number: 2,
    episode_title: 'Chương 2: Dầu sương',
    position: 7,
    read_at: '2026-10-27T09:00:00Z',
    ...overrides,
  };
}

export function library(overrides: Partial<LibraryResponse> = {}): LibraryResponse {
  return { reading: [], favourites: [], ...overrides };
}

export const READER: UserResponse = {
  id: 'reader-1',
  email: 'reader1@example.com',
  display_name: 'Reader One',
  locale: 'en',
  status: 'active',
  roles: ['reader'],
};

export const GENRES: GenreResponse[] = [
  { slug: 'action', name: 'Action' },
  { slug: 'adventure', name: 'Adventure' },
  { slug: 'comedy', name: 'Comedy' },
  { slug: 'drama', name: 'Drama' },
  { slug: 'fantasy', name: 'Fantasy' },
  { slug: 'historical', name: 'Historical' },
  { slug: 'horror', name: 'Horror' },
  { slug: 'mystery', name: 'Mystery' },
  { slug: 'romance', name: 'Romance' },
  { slug: 'sci-fi', name: 'Sci-Fi' },
  { slug: 'slice-of-life', name: 'Slice of Life' },
  { slug: 'thriller', name: 'Thriller' },
];
