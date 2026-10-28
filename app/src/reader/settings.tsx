import AsyncStorage from '@react-native-async-storage/async-storage';
import { createContext, type PropsWithChildren, use, useEffect, useMemo, useRef, useState } from 'react';

export const FONT_SIZES = [16, 18, 20, 22, 24] as const;
export const READER_FONTS = ['serif', 'sans'] as const;
export const READER_THEMES = ['system', 'light', 'dark'] as const;

export type ReaderFont = (typeof READER_FONTS)[number];
export type ReaderTheme = (typeof READER_THEMES)[number];

export type ReaderSettings = {
  font: ReaderFont;
  /** An index into FONT_SIZES. */
  size: number;
  theme: ReaderTheme;
};

export const DEFAULT_SETTINGS: ReaderSettings = { font: 'serif', size: 1, theme: 'system' };

const STORAGE_KEY = 'reader-settings';

type ReaderSettingsContext = {
  settings: ReaderSettings;
  update: (change: Partial<ReaderSettings>) => void;
};

const SettingsContext = createContext<ReaderSettingsContext | null>(null);

export function useReaderSettings(): ReaderSettingsContext {
  const context = use(SettingsContext);
  if (!context) {
    throw new Error('useReaderSettings must be used inside <ReaderSettingsProvider>');
  }
  return context;
}

/** What was stored, field by field; anything missing or unknown is the default. */
export function parseSettings(raw: string | null): ReaderSettings {
  let stored: Partial<Record<keyof ReaderSettings, unknown>> = {};
  try {
    const value: unknown = JSON.parse(raw ?? 'null');
    if (value && typeof value === 'object') {
      stored = value;
    }
  } catch {
    // Unreadable: start over from the defaults.
  }
  const { font, size, theme } = stored;
  return {
    font: READER_FONTS.find((option) => option === font) ?? DEFAULT_SETTINGS.font,
    size:
      typeof size === 'number' && Number.isInteger(size) && size >= 0 && size < FONT_SIZES.length
        ? size
        : DEFAULT_SETTINGS.size,
    theme: READER_THEMES.find((option) => option === theme) ?? DEFAULT_SETTINGS.theme,
  };
}

/**
 * How the reader likes to read, kept on this device.
 *
 * Storage can fail (a private browser window, a full disk); the reader then
 * reads with the defaults and their changes last until the app closes.
 */
export function ReaderSettingsProvider({ children }: PropsWithChildren) {
  const [settings, setSettings] = useState(DEFAULT_SETTINGS);
  // A change made before the stored settings arrive wins over them.
  const changed = useRef(false);

  useEffect(() => {
    let cancelled = false;
    AsyncStorage.getItem(STORAGE_KEY).then(
      (raw) => {
        if (!cancelled && !changed.current) {
          setSettings(parseSettings(raw));
        }
      },
      () => {},
    );
    return () => {
      cancelled = true;
    };
  }, []);

  const context = useMemo<ReaderSettingsContext>(
    () => ({
      settings,
      update: (change) => {
        changed.current = true;
        const next = { ...settings, ...change };
        setSettings(next);
        AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(next)).catch(() => {});
      },
    }),
    [settings],
  );

  return <SettingsContext value={context}>{children}</SettingsContext>;
}
