import { Asset } from 'expo-asset';
import { File } from 'expo-file-system';
import { useEffect, useState } from 'react';

import { fontFaceRule, TEXT_FACES } from './text-font-css';

// A WebView page has no access to the app's files (allowFileAccess is off,
// and its CSP allows no network), so the font goes in as data.
async function load(): Promise<string> {
  const rules = await Promise.all(
    TEXT_FACES.map(async ({ weight, module }) => {
      const [asset] = await Asset.loadAsync(module);
      if (!asset?.localUri) {
        throw new Error('font asset has no local file');
      }
      const data = await new File(asset.localUri).base64();
      return fontFaceRule(weight, `data:font/ttf;base64,${data}`);
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
