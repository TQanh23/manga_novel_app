import { Asset } from 'expo-asset';
import { useEffect, useState } from 'react';

import { fontFaceRule, TEXT_FACES } from './text-font-css';

function dataUrl(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error ?? new Error('font could not be read'));
    reader.readAsDataURL(blob);
  });
}

// The editor runs in a sandboxed iframe with an opaque origin, which cannot
// fetch the app's font files, so on web too the fonts go in as data.
async function load(): Promise<string> {
  const rules = await Promise.all(
    TEXT_FACES.map(async ({ weight, module }) => {
      const response = await fetch(Asset.fromModule(module).uri);
      if (!response.ok) {
        throw new Error(`font request failed: ${response.status}`);
      }
      const url = await dataUrl(new Blob([await response.arrayBuffer()], { type: 'font/ttf' }));
      return fontFaceRule(weight, url);
    }),
  );
  return rules.join('\n');
}

let loading: Promise<string> | null = null;
let loaded: string | null = null;

/**
 * The @font-face rules a reader or editor page needs for the app's typeface.
 * `null` while they load (once per app run); an empty string if they could
 * not be read, and the page falls back to the system serif.
 */
export function useTextFontCss(): string | null {
  const [css, setCss] = useState(loaded);
  useEffect(() => {
    let live = true;
    loading ??= load().catch(() => '');
    void loading.then((rules) => {
      loaded = rules;
      if (live) {
        setCss(rules);
      }
    });
    return () => {
      live = false;
    };
  }, []);
  return css;
}
