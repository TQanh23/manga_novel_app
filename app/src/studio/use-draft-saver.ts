import { useCallback, useEffect, useRef, useState } from 'react';
import { AppState } from 'react-native';

import { errorCode } from '@/api/client';
import { authorSaveDraft } from '@/api/generated';

/** How long the author has to stop typing before the text is saved. */
export const AUTOSAVE_DELAY_MS = 2000;
/** How long a failed save waits before it is tried again. */
export const RETRY_DELAY_MS = 10_000;

export type DraftStatus =
  | { kind: 'saved'; savedAt: string | null }
  | { kind: 'unsaved' }
  | { kind: 'saving' }
  /** `error` is an API error code. */
  | { kind: 'failed'; error: string };

/** What a save came to: when the new version was made, or an API error code. */
type Outcome = { savedAt: string } | { error: string };

type Options = {
  episodeId: string;
  /** The newest save the API holds, and when it was made (null: never). */
  savedHtml: string;
  savedAt: string | null;
};

/**
 * Saves the episode's text once the author has stopped typing, and straight
 * away when they leave the episode or the app goes to the background
 * (FR-NV-01). Each save is a new version, so one is in flight at a time and
 * text that comes in meanwhile goes in the next. A failed save is tried again.
 */
export function useDraftSaver({ episodeId, savedHtml, savedAt }: Options): {
  status: DraftStatus;
  change: (html: string) => void;
  /** Saves what is pending now, and resolves once no save is in flight. */
  settle: () => Promise<void>;
  /** Takes `html` as saved at `savedAt`: a version the API made itself, such as a restore. */
  reset: (html: string, savedAt: string) => void;
} {
  const [status, setStatus] = useState<DraftStatus>({ kind: 'saved', savedAt });
  const state = useRef<{
    saved: string;
    savedAt: string | null;
    pending: string | null;
    inFlight: boolean;
    timer: ReturnType<typeof setTimeout> | undefined;
  }>({ saved: savedHtml, savedAt, pending: null, inFlight: false, timer: undefined });
  const mounted = useRef(true);
  // Who is waiting for the saves in flight to end.
  const waiting = useRef<(() => void)[]>([]);

  const report = useCallback((next: DraftStatus) => {
    if (mounted.current) {
      setStatus(next);
    }
  }, []);

  const flush = useCallback(() => {
    const current = state.current;
    // Named, so a save that ends can start the next one.
    function send() {
      clearTimeout(current.timer);
      current.timer = undefined;
      // The save in flight looks at what is pending when it ends.
      if (current.inFlight || current.pending === null) {
        return;
      }
      const html = current.pending;
      current.pending = null;
      if (html === current.saved) {
        report({ kind: 'saved', savedAt: current.savedAt });
        return;
      }

      current.inFlight = true;
      report({ kind: 'saving' });
      authorSaveDraft({ path: { episode_id: episodeId }, body: { body_html: html } })
        .then(
          ({ data, error }): Outcome =>
            data ? { savedAt: data.created_at } : { error: errorCode(error) },
          (): Outcome => ({ error: 'network_error' }),
        )
        .then((outcome) => {
          current.inFlight = false;
          if ('savedAt' in outcome) {
            current.saved = html;
            current.savedAt = outcome.savedAt;
            if (current.pending !== null && current.pending !== html) {
              send();
            } else {
              current.pending = null;
              report({ kind: 'saved', savedAt: outcome.savedAt });
            }
            return;
          }
          // Not saved: send it again later, unless newer text has replaced it.
          current.pending ??= html;
          report({ kind: 'failed', error: outcome.error });
          clearTimeout(current.timer);
          current.timer = setTimeout(send, RETRY_DELAY_MS);
        })
        .finally(() => {
          if (!current.inFlight) {
            waiting.current.splice(0).forEach((resume) => resume());
          }
        });
    }
    send();
  }, [episodeId, report]);

  useEffect(() => {
    mounted.current = true;
    const subscription = AppState.addEventListener('change', (next) => {
      if (next !== 'active') {
        flush();
      }
    });
    return () => {
      subscription.remove();
      mounted.current = false;
      flush();
    };
  }, [flush]);

  const change = useCallback(
    (html: string) => {
      const current = state.current;
      clearTimeout(current.timer);
      current.pending = html;
      if (current.inFlight) {
        current.timer = setTimeout(flush, AUTOSAVE_DELAY_MS);
        return;
      }
      if (html === current.saved) {
        current.pending = null;
        report({ kind: 'saved', savedAt: current.savedAt });
        return;
      }
      report({ kind: 'unsaved' });
      current.timer = setTimeout(flush, AUTOSAVE_DELAY_MS);
    },
    [flush, report],
  );

  const settle = useCallback(() => {
    flush();
    if (!state.current.inFlight) {
      return Promise.resolve();
    }
    return new Promise<void>((resume) => waiting.current.push(resume));
  }, [flush]);

  const reset = useCallback(
    (html: string, at: string) => {
      const current = state.current;
      clearTimeout(current.timer);
      current.timer = undefined;
      current.pending = null;
      current.saved = html;
      current.savedAt = at;
      report({ kind: 'saved', savedAt: at });
    },
    [report],
  );

  return { status, change, settle, reset };
}
