import { act, renderHook, waitFor } from '@testing-library/react-native';

import type { WorkPage } from '@/api/generated';
import { useLoad, usePagedWorks } from '@/api/hooks';
import { deferred, fails, ok, page, work } from '@/testing/api';

const first = work({ id: 'w1', title: 'First' });
const second = work({ id: 'w2', title: 'Second' });
const third = work({ id: 'w3', title: 'Third' });

describe('usePagedWorks', () => {
  test('loads the first page, then appends the next one from the right offset', async () => {
    const fetchPage = jest
      .fn<Promise<never>, [number]>()
      .mockReturnValueOnce(ok(page([first, second], true)))
      .mockReturnValueOnce(ok(page([third], false)));

    const { result } = await renderHook(() => usePagedWorks('all', fetchPage));
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.items.map((item) => item.title)).toEqual(['First', 'Second']);
    expect(result.current.hasMore).toBe(true);

    await act(async () => result.current.loadMore());
    await waitFor(() => expect(result.current.items).toHaveLength(3));

    expect(fetchPage.mock.calls).toEqual([[0], [2]]);
    expect(result.current.hasMore).toBe(false);
    expect(result.current.error).toBeNull();
  });

  test('asks for nothing more once the last page is in', async () => {
    const fetchPage = jest.fn<Promise<never>, [number]>().mockReturnValue(ok(page([first], false)));

    const { result } = await renderHook(() => usePagedWorks('all', fetchPage));
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    await act(async () => result.current.loadMore());

    expect(fetchPage).toHaveBeenCalledTimes(1);
  });

  test('starts over from the first page when the key changes', async () => {
    const manga = deferred<WorkPage>();
    const fetchPage = jest
      .fn<Promise<never>, [number]>()
      .mockReturnValueOnce(ok(page([first, second], true)))
      .mockReturnValueOnce(manga.promise);

    const { result, rerender } = await renderHook(
      ({ filter }: { filter: string }) => usePagedWorks(filter, fetchPage),
      { initialProps: { filter: 'novel' } },
    );
    await waitFor(() => expect(result.current.items).toHaveLength(2));

    await rerender({ filter: 'manga' });

    // The old list is gone at once, not shown under the new filter.
    expect(result.current.items).toEqual([]);
    expect(result.current.isLoading).toBe(true);

    await act(async () => manga.resolve(page([third], false)));
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.items.map((item) => item.title)).toEqual(['Third']);
    expect(fetchPage.mock.calls).toEqual([[0], [0]]);
  });

  test('drops an answer that arrives after the key has moved on', async () => {
    const slow = deferred<WorkPage>();
    const fetchPage = jest
      .fn<Promise<never>, [number]>()
      .mockReturnValueOnce(slow.promise)
      .mockReturnValueOnce(ok(page([second])));

    const { result, rerender } = await renderHook(
      ({ query }: { query: string }) => usePagedWorks(query, fetchPage),
      { initialProps: { query: 'kie' } },
    );
    await rerender({ query: 'kiem' });
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await act(async () => slow.resolve(page([first])));

    expect(result.current.items.map((item) => item.title)).toEqual(['Second']);
  });

  test('reports an error on the first page and loads again on reload', async () => {
    const fetchPage = jest
      .fn<Promise<never>, [number]>()
      .mockReturnValueOnce(fails('rate_limited'))
      .mockReturnValueOnce(ok(page([first])));

    const { result } = await renderHook(() => usePagedWorks('all', fetchPage));
    await waitFor(() => expect(result.current.error).toBe('rate_limited'));
    expect(result.current.items).toEqual([]);

    await act(async () => result.current.reload());
    await waitFor(() => expect(result.current.items).toHaveLength(1));

    expect(result.current.error).toBeNull();
  });

  test('keeps what is on screen when loading more fails, and can try again', async () => {
    const fetchPage = jest
      .fn<Promise<never>, [number]>()
      .mockReturnValueOnce(ok(page([first], true)))
      .mockRejectedValueOnce(new Error('offline'))
      .mockReturnValueOnce(ok(page([second], false)));

    const { result } = await renderHook(() => usePagedWorks('all', fetchPage));
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await act(async () => result.current.loadMore());
    await waitFor(() => expect(result.current.error).toBe('network_error'));
    expect(result.current.items.map((item) => item.title)).toEqual(['First']);
    expect(result.current.hasMore).toBe(true);

    await act(async () => result.current.loadMore());
    await waitFor(() => expect(result.current.items).toHaveLength(2));
    expect(result.current.error).toBeNull();
  });

  test('fetches nothing while there is no key', async () => {
    const fetchPage = jest.fn<Promise<never>, [number]>().mockReturnValue(ok(page([first])));

    const { result, rerender } = await renderHook(
      ({ query }: { query: string | null }) => usePagedWorks(query, fetchPage),
      { initialProps: { query: null as string | null } },
    );

    expect(result.current.isLoading).toBe(false);
    expect(fetchPage).not.toHaveBeenCalled();

    await rerender({ query: 'den' });
    await waitFor(() => expect(result.current.items).toHaveLength(1));
  });
});

describe('useLoad', () => {
  test('loads, and loads again when the key changes', async () => {
    const one = deferred<string>();
    const two = deferred<string>();
    const load = jest
      .fn<Promise<never>, []>()
      .mockReturnValueOnce(one.promise)
      .mockReturnValueOnce(two.promise);

    const { result, rerender } = await renderHook(
      ({ id }: { id: string }) => useLoad<string>(`work:${id}`, load),
      { initialProps: { id: 'a' } },
    );
    expect(result.current.isLoading).toBe(true);
    await act(async () => one.resolve('one'));
    await waitFor(() => expect(result.current.data).toBe('one'));

    await rerender({ id: 'b' });

    // The previous work is not shown while the next one loads.
    expect(result.current.data).toBeNull();
    expect(result.current.isLoading).toBe(true);
    await act(async () => two.resolve('two'));
    await waitFor(() => expect(result.current.data).toBe('two'));
  });

  test('reports the API error code and recovers on reload', async () => {
    const load = jest
      .fn<Promise<never>, []>()
      .mockReturnValueOnce(fails('work_not_found'))
      .mockReturnValueOnce(ok('found'));

    const { result } = await renderHook(() => useLoad<string>('work:a', load));
    await waitFor(() => expect(result.current.error).toBe('work_not_found'));
    expect(result.current.data).toBeNull();

    await act(async () => result.current.reload());

    await waitFor(() => expect(result.current.data).toBe('found'));
    expect(result.current.error).toBeNull();
  });
});
