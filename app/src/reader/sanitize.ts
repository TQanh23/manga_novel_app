import DOMPurify from 'dompurify';

/** The tags the API stores (`sanitize_html` in api/catalogue/text.py). No attributes at all. */
export const ALLOWED_TAGS = ['p', 'br', 'strong', 'b', 'em', 'i', 'u', 's', 'h2', 'h3', 'blockquote', 'hr'];

/**
 * One paragraph from the API, cleaned again before it goes into the page.
 *
 * The API already sanitized it; this is the second lock, should a bug there
 * ever let something through. Where there is no DOM to clean with (a static
 * render), nothing is rendered rather than something unchecked.
 */
export function sanitizeBlock(html: string): string {
  if (!DOMPurify.isSupported) {
    return '';
  }
  return DOMPurify.sanitize(html, { ALLOWED_TAGS, ALLOWED_ATTR: [] });
}
