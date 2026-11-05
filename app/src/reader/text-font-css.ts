import { EBGaramond_400Regular } from '@expo-google-fonts/eb-garamond/400Regular';
import { EBGaramond_700Bold } from '@expo-google-fonts/eb-garamond/700Bold';

import { TEXT_FAMILY } from '@/constants/theme';

/**
 * The faces the reader and editor pages carry: regular and bold. Italic is
 * left to the browser to slant, which saves a third font file per page.
 */
export const TEXT_FACES = [
  { weight: 400, module: EBGaramond_400Regular },
  { weight: 700, module: EBGaramond_700Bold },
] as const;

/** One @font-face rule for the text family. */
export function fontFaceRule(weight: number, url: string): string {
  return `@font-face { font-family: "${TEXT_FAMILY}"; font-weight: ${weight}; font-style: normal; font-display: block; src: url("${url}") format("truetype"); }`;
}
