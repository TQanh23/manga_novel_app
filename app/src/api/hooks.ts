import { useEffect, useEffectEvent, useState } from 'react';

import { errorCode } from './client';
import type { WorkCard, WorkPage } from './generated';

export const PAGE_SIZE = 20;

/** What a generated client call resolves to: the data, or the API's error envelope. */
type ApiResult<T> = { data?: T; error?: unknown };

type Outcome<T> = { data: T; error: null } | { data: null; error: string };

async function settle<T>(call: () => Promise<ApiResult<T>>): Promise<Outcome<T>> {
  try {
    const { data, error } = await call();
    return data !== undefined ? { data, error: null } : { data: null, error: errorCode(error) };
  } catch {
    return { data: null, error: 'network_error' };
  }
}

export type Load<T> = {
  data: T | null;
  /** An API error code, to be shown through `errorMessageKey`. */
  error: string | null;
  isLoading: boolean;
  reload: () => void;
};

/**
 * Loads one thing and loads it again whenever `key` changes.
 *
 * `key` says what is being asked for; `load` may close over anything. An
 * answer that arrives after the key has moved on is dropped, so a slow
 * response can never replace a newer one.
 */
export function useLoad<T>(key: string, load: () => Promise<ApiResult<T>>): Load<T> {
  const [attempt, setAttempt] = useState(0);
  const [settled, setSettled] = useState<{ request: string; outcome: Outcome<T> } | null>(null);
  const request = `${key}#${attempt}`;
  const run = useEffectEvent(load);

  useEffect(() => {
    let stale = false;
    void settle(run).then((outcome) => {
      if (!stale) {
        setSettled({ request, outcome });
      }
    });
    return () => {
      stale = true;
    };
  }, [request]);

  const current = settled?.request === request ? settled.outcome : null;
  return {
    data: current?.data ?? null,
    error: current?.error ?? null,
    isLoading: current === null,
    reload: () => setAttempt((count) => count + 1),
  };
}

export type PagedWorks = {
  items: WorkCard[];
  hasMore: boolean;
  /** True while the first page of the current key is on its way. */
  isLoading: boolean;
  isLoadingMore: boolean;
  /** An API error code. With items on screen it is about loading more of them. */
  error: string | null;
  loadMore: () => void;
  reload: () => void;
};

type Pages = { request: string; items: WorkCard[]; hasMore: boolean; error: string | null };

/**
 * A list of works fetched page by page, started over whenever `key` changes.
 *
 * A null key means there is nothing to ask for yet (an empty search box):
 * nothing is fetched and the list is empty.
 */
export function usePagedWorks(
  key: string | null,
  fetchPage: (offset: number) => Promise<ApiResult<WorkPage>>,
): PagedWorks {
  const [attempt, setAttempt] = useState(0);
  const [pages, setPages] = useState<Pages | null>(null);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const request = key === null ? null : `${key}#${attempt}`;
  const fetchFrom = useEffectEvent(fetchPage);

  useEffect(() => {
    if (request === null) {
      return;
    }
    let stale = false;
    void settle(() => fetchFrom(0)).then((outcome) => {
      if (!stale) {
        setPages({
          request,
          items: outcome.data?.items ?? [],
          hasMore: outcome.data?.has_more ?? false,
          error: outcome.error,
        });
      }
    });
    return () => {
      stale = true;
    };
  }, [request]);

  const current = request !== null && pages?.request === request ? pages : null;

  const loadMore = () => {
    if (!current || !current.hasMore || isLoadingMore) {
      return;
    }
    setIsLoadingMore(true);
    void settle(() => fetchPage(current.items.length)).then((outcome) => {
      setIsLoadingMore(false);
      // Only if the list on screen is still the one this page belongs to.
      setPages((latest) => {
        if (latest?.request !== current.request) {
          return latest;
        }
        return outcome.data
          ? {
              ...latest,
              items: [...latest.items, ...outcome.data.items],
              hasMore: outcome.data.has_more,
              error: null,
            }
          : { ...latest, error: outcome.error };
      });
    });
  };

  return {
    items: current?.items ?? [],
    hasMore: current?.hasMore ?? false,
    isLoading: request !== null && current === null,
    isLoadingMore,
    error: current?.error ?? null,
    loadMore,
    reload: () => setAttempt((count) => count + 1),
  };
}
