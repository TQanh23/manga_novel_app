import { useCallback, useEffect, useRef } from 'react';
import { AppState } from 'react-native';

import { readerSaveProgress } from '@/api/generated';

/** How long the position has to stay put before it is saved. */
export const SAVE_DELAY_MS = 1500;

type Options = {
  episodeId: string;
  /** The position the API already holds for this reader, if any. */
  saved: number | null;
  /** False for a guest: there is nowhere to save to. */
  enabled: boolean;
};

/**
 * Saves the reading position once the reader has stopped scrolling, and
 * straight away when they leave the episode or the app goes to the background.
 * Returns the function to call with each new position.
 */
export function useProgressSaver({ episodeId, saved, enabled }: Options): (position: number) => void {
  const state = useRef<{
    saved: number | null;
    pending: number | null;
    timer: ReturnType<typeof setTimeout> | undefined;
  }>({ saved, pending: null, timer: undefined });
  const isEnabled = useRef(enabled);

  useEffect(() => {
    isEnabled.current = enabled;
  }, [enabled]);

  const flush = useCallback(() => {
    const current = state.current;
    clearTimeout(current.timer);
    current.timer = undefined;
    const position = current.pending;
    current.pending = null;
    if (position === null || position === current.saved || !isEnabled.current) {
      return;
    }
    const previous = current.saved;
    current.saved = position;
    // Not saved: forget that it was, so the next position is sent even if it is this one.
    const undo = () => {
      if (state.current.saved === position) {
        state.current.saved = previous;
      }
    };
    readerSaveProgress({ path: { episode_id: episodeId }, body: { position } }).then(
      ({ error }) => {
        if (error !== undefined) {
          undo();
        }
      },
      undo,
    );
  }, [episodeId]);

  useEffect(() => {
    const subscription = AppState.addEventListener('change', (status) => {
      if (status !== 'active') {
        flush();
      }
    });
    return () => {
      subscription.remove();
      flush();
    };
  }, [flush]);

  return useCallback(
    (position: number) => {
      if (!isEnabled.current) {
        return;
      }
      const current = state.current;
      current.pending = position;
      clearTimeout(current.timer);
      current.timer = setTimeout(flush, SAVE_DELAY_MS);
    },
    [flush],
  );
}
