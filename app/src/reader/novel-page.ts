import { TEXT_FAMILY } from '@/constants/theme';

import { PAGE_CLEANER } from './sanitize';

export type NovelAppearance = {
  font: 'sans' | 'serif';
  fontSize: number;
  text: string;
  background: string;
  /** Rules and quote bars. */
  muted: string;
  /** The gold of the chapter heading's flourish. */
  ornament: string;
};

/** Text around the episode: an opening above the first paragraph, an end mark below the last. */
export type NovelHeading = {
  /** A short line above the title, such as the work's name and the episode number. */
  eyebrow: string;
  title: string;
  /** The line under the last paragraph. */
  end: string;
};

export type NovelViewProps = {
  /** The episode's paragraphs, each one HTML block from the API. */
  paragraphs: string[];
  /** The paragraph to open at. */
  initialPosition: number;
  appearance: NovelAppearance;
  /** Called with the paragraph at the top of the screen whenever that changes. */
  onPosition: (position: number) => void;
  /**
   * Called with how far down the text the reader has scrolled, a whole
   * percentage, whenever that changes. Only for show: positions are saved by paragraph.
   */
  onProgress?: (percent: number) => void;
  heading?: NovelHeading;
};

/**
 * A small gold flourish: two C-scrolls about a lozenge. A constant, never
 * built from data, so it is safe to put in the page as markup.
 */
export const FLOURISH_SVG =
  '<svg width="96" height="20" viewBox="0 0 120 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.4">' +
  '<path d="M68 12 C74 4 86 4 90 10 C93 15 87 18 85 14"/><path d="M52 12 C46 4 34 4 30 10 C27 15 33 18 35 14"/>' +
  '<path d="M96 12 H118 M2 12 H24"/><path d="M60 4 L68 12 L60 20 L52 12 Z" fill="currentColor" fill-opacity="0.2"/>' +
  '<circle cx="60" cy="12" r="2" fill="currentColor"/></svg>';

// Stacks that cover Vietnamese, Korean and Japanese on Android and on desktop
// browsers. Serif is the app's own typeface (Latin and Vietnamese); Korean and
// Japanese fall through to Noto Serif CJK.
export const FONT_STACKS = {
  sans: 'system-ui, -apple-system, Roboto, "Noto Sans", "Noto Sans CJK KR", "Noto Sans CJK JP", sans-serif',
  serif: `"${TEXT_FAMILY}", Georgia, "Noto Serif", "Noto Serif CJK KR", "Noto Serif CJK JP", "Times New Roman", serif`,
} as const;

/** Space kept above the paragraph at the top, in CSS pixels. */
export const TOP_GAP = 16;

// Runs inside the page. Plain ES5, as it is a string and no bundler sees it.
// Each paragraph is parsed into an inert document and copied over by
// PAGE_CLEANER's `copy`.
const PAGE_SCRIPT = `(function () {
  ${PAGE_CLEANER}
  var TOP_GAP = ${TOP_GAP};
  var FONTS = ${JSON.stringify(FONT_STACKS)};

  var data = JSON.parse(document.getElementById('data').textContent);
  var article = document.getElementById('text');
  // The heading is text, set with textContent: a title can never become markup.
  if (data.heading) {
    document.getElementById('eyebrow').textContent = data.heading.eyebrow;
    document.getElementById('title').textContent = data.heading.title;
    document.getElementById('end-text').textContent = data.heading.end;
  } else {
    document.getElementById('heading').remove();
    document.getElementById('end').remove();
  }
  for (var i = 0; i < data.paragraphs.length; i++) {
    var parsed = new DOMParser().parseFromString('<!doctype html><body>' + data.paragraphs[i] + '</body>', 'text/html');
    var block = document.createElement('div');
    block.setAttribute('data-i', String(i));
    copy(parsed.body, block);
    article.appendChild(block);
  }
  var blocks = article.children;
  var top = data.position;

  function paragraphAtTop() {
    var edge = window.scrollY + TOP_GAP;
    var low = 0;
    var high = blocks.length - 1;
    while (low < high) {
      var middle = Math.floor((low + high) / 2);
      if (blocks[middle].offsetTop + blocks[middle].offsetHeight > edge) {
        high = middle;
      } else {
        low = middle + 1;
      }
    }
    return Math.max(0, low);
  }

  // The first paragraph opens at the very top, so the chapter heading shows.
  function scrollToParagraph(position) {
    var target = position > 0 ? blocks[position] : null;
    window.scrollTo(0, target ? Math.max(0, target.offsetTop - TOP_GAP) : 0);
  }

  function applyAppearance(appearance) {
    var style = document.documentElement.style;
    style.setProperty('--text', appearance.text);
    style.setProperty('--background', appearance.background);
    style.setProperty('--muted', appearance.muted);
    style.setProperty('--ornament', appearance.ornament);
    style.setProperty('--font', FONTS[appearance.font] || FONTS.serif);
    style.setProperty('--size', appearance.fontSize + 'px');
  }

  // Called by the app when the reader changes font, size or theme: the same
  // paragraph stays at the top.
  window.novel = {
    apply: function (appearance) {
      var keep = top;
      applyAppearance(appearance);
      scrollToParagraph(keep);
    }
  };

  applyAppearance(data.appearance);
  scrollToParagraph(top);
  window.addEventListener('load', function () { scrollToParagraph(top); });

  function percentRead() {
    var room = document.documentElement.scrollHeight - window.innerHeight;
    return room > 0 ? Math.min(100, Math.max(0, Math.round((window.scrollY / room) * 100))) : 100;
  }

  function post(message) {
    if (window.ReactNativeWebView) {
      window.ReactNativeWebView.postMessage(JSON.stringify(message));
    }
  }

  var frame = 0;
  var percent = -1;
  function report() {
    var position = paragraphAtTop();
    if (position !== top) {
      top = position;
      post({ position: position });
    }
    var now = percentRead();
    if (now !== percent) {
      percent = now;
      post({ progress: now });
    }
  }
  window.addEventListener('scroll', function () {
    cancelAnimationFrame(frame);
    frame = requestAnimationFrame(report);
  }, { passive: true });
  window.addEventListener('load', function () { percent = percentRead(); post({ progress: percent }); });
})();`;

/**
 * The whole page an Android WebView shows for an episode.
 *
 * The paragraphs go in as JSON data, never as markup, and the page builds
 * the text from them itself. The content security policy allows no
 * network access and no scripts but the page's own.
 */
export function novelPage({
  paragraphs,
  position,
  appearance,
  heading,
  fontCss = '',
}: {
  paragraphs: string[];
  position: number;
  appearance: NovelAppearance;
  heading?: NovelHeading;
  /** @font-face rules for the app's typeface, with the fonts as data URIs. */
  fontCss?: string;
}): string {
  // "<" escaped so no paragraph can close the data element early.
  const data = JSON.stringify({ paragraphs, position, appearance, heading }).replace(/</g, '\\u003c');
  return `<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; font-src data:">
<style>
  ${fontCss}
  html, body { margin: 0; background: var(--background); color: var(--text); }
  body { font-family: var(--font); font-size: var(--size); line-height: 1.7; }
  article { max-width: 40em; margin: 0 auto; padding: 16px 20px 96px; overflow-wrap: break-word; }
  blockquote { margin: 1em 0; padding-left: 1em; border-left: 3px solid var(--muted); }
  hr { border: none; border-top: 1px solid var(--muted); margin: 2em 0; }
  h2, h3 { line-height: 1.3; }
  #heading, #end { max-width: 40em; margin: 0 auto; padding: 0 20px; text-align: center; }
  #heading { padding-top: 40px; }
  #eyebrow { font-size: 0.72em; letter-spacing: 0.14em; text-transform: uppercase; color: var(--muted); }
  #title { font-size: 1.6em; font-weight: 700; line-height: 1.3; margin: 0.3em 0 0.2em; }
  .flourish { color: var(--ornament); }
  #end { padding-bottom: 120px; margin-top: -48px; }
  #end-text { font-size: 0.72em; letter-spacing: 0.14em; text-transform: uppercase; color: var(--muted); }
</style>
</head>
<body>
<header id="heading"><div id="eyebrow"></div><h1 id="title"></h1><div class="flourish">${FLOURISH_SVG}</div></header>
<article id="text"></article>
<footer id="end"><div class="flourish">${FLOURISH_SVG}</div><div id="end-text"></div></footer>
<script type="application/json" id="data">${data}</script>
<script>${PAGE_SCRIPT}</script>
</body>
</html>`;
}
