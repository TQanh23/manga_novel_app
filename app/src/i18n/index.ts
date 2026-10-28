import { getLocales } from 'expo-localization';
import { use as registerPlugin } from 'i18next';
import { initReactI18next } from 'react-i18next';

import type { Locale } from '@/api/generated';

import en from './locales/en.json';
import vi from './locales/vi.json';

export const LOCALES: readonly Locale[] = ['en', 'vi'];

// English is the reference: `satisfies` fails the typecheck when Vietnamese is
// missing a key that English has.
const resources = {
  en: { translation: en },
  vi: { translation: vi satisfies typeof en },
} as const;

declare module 'i18next' {
  interface CustomTypeOptions {
    defaultNS: 'translation';
    resources: (typeof resources)['en'];
  }
}

const i18n = registerPlugin(initReactI18next);

function deviceLocale(): Locale {
  return getLocales()[0]?.languageCode === 'vi' ? 'vi' : 'en';
}

export function currentLocale(): Locale {
  return i18n.language === 'vi' ? 'vi' : 'en';
}

/** Message for an API error code, falling back to a generic one for codes without copy. */
export function errorMessageKey(code: string) {
  const known = Object.keys(en.errors) as (keyof typeof en.errors)[];
  const match = known.find((key) => key === code) ?? 'unknown';
  return `errors.${match}` as const;
}

/**
 * A genre's name in the current language. Genres come from the API by slug;
 * one this build has no translation for falls back to the name the API sent.
 */
export function genreName(slug: string, fallback?: string): string {
  return slug in en.genres
    ? i18n.t(`genres.${slug as keyof typeof en.genres}`)
    : (fallback ?? slug);
}

/** A date as the current language writes it. */
export function formatDate(iso: string): string {
  return new Intl.DateTimeFormat(currentLocale(), { dateStyle: 'medium' }).format(new Date(iso));
}

void i18n.init({
  resources,
  lng: deviceLocale(),
  fallbackLng: 'en',
  // React already escapes what it renders.
  interpolation: { escapeValue: false },
});

export default i18n;
