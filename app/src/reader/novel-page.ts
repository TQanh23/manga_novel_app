import { PAGE_CLEANER } from './sanitize';

export type NovelAppearance = {
  font: 'sans' | 'serif';
  fontSize: number;
  text: string;
  background: string;
  /** Rules and quote bars. */
  muted: string;
};

export type NovelViewProps = {
  /** The episode's paragraphs, each one HTML block from the API. */
  paragraphs: string[];
  /** The paragraph to open at. */
  initialPosition: number;
  appearance: NovelAppearance;
  /** Called with the paragraph at the top of the screen whenever that changes. */
  onPosition: (position: number) => void;
};

// Stacks that cover Vietnamese, Korean and Japanese on Android and on desktop browsers.
export const FONT_STACKS = {
  sans: 'system-ui, -apple-system, Roboto, "Noto Sans", "Noto Sans CJK KR", "Noto Sans CJK JP", sans-serif',
  serif: 'Georgia, "Noto Serif", "Noto Serif CJK KR", "Noto Serif CJK JP", "Times New Roman", serif',
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

  function scrollToParagraph(position) {
    var target = blocks[position];
    window.scrollTo(0, target ? Math.max(0, target.offsetTop - TOP_GAP) : 0);
  }

  function applyAppearance(appearance) {
    var style = document.documentElement.style;
    style.setProperty('--text', appearance.text);
    style.setProperty('--background', appearance.background);
    style.setProperty('--muted', appearance.muted);
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

  var frame = 0;
  window.addEventListener('scroll', function () {
    cancelAnimationFrame(frame);
    frame = requestAnimationFrame(function () {
      var position = paragraphAtTop();
      if (position !== top) {
        top = position;
        if (window.ReactNativeWebView) {
          window.ReactNativeWebView.postMessage(JSON.stringify({ position: position }));
        }
      }
    });
  }, { passive: true });
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
}: {
  paragraphs: string[];
  position: number;
  appearance: NovelAppearance;
}): string {
  // "<" escaped so no paragraph can close the data element early.
  const data = JSON.stringify({ paragraphs, position, appearance }).replace(/</g, '\\u003c');
  return `<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'">
<style>
  html, body { margin: 0; background: var(--background); color: var(--text); }
  body { font-family: var(--font); font-size: var(--size); line-height: 1.7; }
  article { max-width: 40em; margin: 0 auto; padding: 16px 20px 96px; overflow-wrap: break-word; }
  blockquote { margin: 1em 0; padding-left: 1em; border-left: 3px solid var(--muted); }
  hr { border: none; border-top: 1px solid var(--muted); margin: 2em 0; }
  h2, h3 { line-height: 1.3; }
</style>
</head>
<body>
<article id="text"></article>
<script type="application/json" id="data">${data}</script>
<script>${PAGE_SCRIPT}</script>
</body>
</html>`;
}
