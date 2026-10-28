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

/**
 * The cleaner of pages that a WebView shows, where DOMPurify is not loaded.
 * Plain ES5 that defines `copy(from, to)`: it copies a node's content from an
 * inert document (nothing in it runs or loads) element by element, keeping
 * allowlisted tags without any attributes, and text. Elements whose content
 * is code are dropped whole; any other element gives up its content only.
 */
export const PAGE_CLEANER = `
  var ALLOWED = ${JSON.stringify(ALLOWED_TAGS)};
  var DROPPED = ['script', 'style', 'iframe', 'object', 'embed', 'template', 'noscript', 'svg', 'math', 'textarea', 'select', 'title'];

  function copy(from, to) {
    for (var node = from.firstChild; node; node = node.nextSibling) {
      if (node.nodeType === 3) {
        to.appendChild(document.createTextNode(node.data));
      } else if (node.nodeType === 1) {
        var tag = node.nodeName.toLowerCase();
        if (ALLOWED.indexOf(tag) >= 0) {
          var element = document.createElement(tag);
          copy(node, element);
          to.appendChild(element);
        } else if (DROPPED.indexOf(tag) < 0) {
          copy(node, to);
        }
      }
    }
  }
`;
