import { FONT_STACKS } from '@/reader/novel-page';
import { PAGE_CLEANER } from '@/reader/sanitize';

export type EditorAppearance = {
  text: string;
  background: string;
  /** The toolbar, rules, quote bars and the placeholder. */
  muted: string;
  toolbar: string;
};

/** What the toolbar's buttons do, by name. Each one is a label in `studio.editor`. */
export const EDITOR_COMMANDS = [
  'bold',
  'italic',
  'underline',
  'strike',
  'h2',
  'h3',
  'quote',
  'paragraph',
  'rule',
] as const;

export type EditorCommand = (typeof EDITOR_COMMANDS)[number];

/** How long typing has to pause before the page sends the text out. */
export const CHANGE_DELAY_MS = 250;

// Runs inside the page. Plain ES5, as it is a string and no bundler sees it.
//
// The editor is a contenteditable element; the browser does the editing, and
// what it makes is turned into what the API stores (D13) before it leaves
// the page: top-level blocks of allowlisted tags, without attributes.
// Pasted text arrives as plain text, one paragraph per line, so nothing from
// another page's markup gets in.
const PAGE_SCRIPT = `(function () {
  ${PAGE_CLEANER}
  var BLOCKS = ['p', 'h2', 'h3', 'blockquote', 'hr'];
  var COMMANDS = {
    bold: ['bold'],
    italic: ['italic'],
    underline: ['underline'],
    strike: ['strikeThrough'],
    h2: ['formatBlock', '<h2>'],
    h3: ['formatBlock', '<h3>'],
    quote: ['formatBlock', '<blockquote>'],
    paragraph: ['formatBlock', '<p>'],
    rule: ['insertHorizontalRule']
  };
  var CHANGE_DELAY = ${CHANGE_DELAY_MS};

  var data = JSON.parse(document.getElementById('data').textContent);
  var editor = document.getElementById('editor');

  function post(message) {
    var text = JSON.stringify(message);
    if (window.ReactNativeWebView) {
      window.ReactNativeWebView.postMessage(text);
    } else if (window.parent !== window) {
      window.parent.postMessage(text, '*');
    }
  }

  function element(tag) {
    return document.createElement(tag);
  }

  function parse(html) {
    return new DOMParser().parseFromString('<!doctype html><body>' + html + '</body>', 'text/html').body;
  }

  function isBlank(node) {
    return node.nodeType === 3 && !node.data.trim();
  }

  // The editor's content as the API stores it. Browsers make <strike> for
  // strikethrough and <div> for some new lines; runs of text or inline
  // elements outside a block become one paragraph; empty blocks are left out.
  function serialize() {
    var copyOf = editor.cloneNode(true);
    var strikes = copyOf.querySelectorAll('strike');
    for (var i = 0; i < strikes.length; i++) {
      var s = element('s');
      while (strikes[i].firstChild) {
        s.appendChild(strikes[i].firstChild);
      }
      strikes[i].parentNode.replaceChild(s, strikes[i]);
    }

    var out = element('div');
    var line = null;
    for (var node = copyOf.firstChild; node; node = node.nextSibling) {
      var tag = node.nodeType === 1 ? node.nodeName.toLowerCase() : null;
      if (tag && (BLOCKS.indexOf(tag) >= 0 || tag === 'div')) {
        line = null;
        var block = element(tag === 'div' ? 'p' : tag);
        copy(node, block);
        out.appendChild(block);
      } else if (tag === 'br') {
        line = null;
      } else if (tag || node.nodeType === 3) {
        if (!line) {
          line = element('p');
          out.appendChild(line);
        }
        var holder = element('div');
        holder.appendChild(node.cloneNode(true));
        copy(holder, line);
      }
    }
    for (var child = out.firstChild; child; ) {
      var next = child.nextSibling;
      if (child.nodeName.toLowerCase() !== 'hr' && !child.textContent.trim()) {
        out.removeChild(child);
      }
      child = next;
    }
    return out.innerHTML;
  }

  function load(html) {
    copy(parse(html), editor);
    for (var node = editor.firstChild; node; ) {
      var next = node.nextSibling;
      if (isBlank(node)) {
        editor.removeChild(node);
      }
      node = next;
    }
    if (!editor.firstChild) {
      var first = element('p');
      first.appendChild(element('br'));
      editor.appendChild(first);
    }
  }

  function showPlaceholder() {
    var empty = !editor.textContent.trim() && !editor.querySelector('hr');
    editor.className = empty ? 'empty' : '';
  }

  var timer = 0;
  var sent = null;

  function send() {
    clearTimeout(timer);
    var html = serialize();
    if (html !== sent) {
      sent = html;
      post({ type: 'change', html: html });
    }
  }

  function changed() {
    showPlaceholder();
    clearTimeout(timer);
    timer = setTimeout(send, CHANGE_DELAY);
  }

  // Where the author was, so a toolbar button acts on their selection.
  var range = null;
  document.addEventListener('selectionchange', function () {
    var selection = window.getSelection();
    if (selection && selection.rangeCount && editor.contains(selection.anchorNode)) {
      range = selection.getRangeAt(0).cloneRange();
    }
  });

  function run(name) {
    var command = COMMANDS[name];
    if (!command) {
      return;
    }
    editor.focus();
    if (range) {
      var selection = window.getSelection();
      selection.removeAllRanges();
      selection.addRange(range);
    }
    document.execCommand(command[0], false, command[1]);
    changed();
  }

  var buttons = document.querySelectorAll('#toolbar button');
  for (var b = 0; b < buttons.length; b++) {
    // Pressing a button must not take the selection away from the text.
    buttons[b].addEventListener('mousedown', function (event) { event.preventDefault(); });
    buttons[b].addEventListener('click', function (event) {
      run(event.currentTarget.getAttribute('data-command'));
    });
  }

  editor.addEventListener('paste', function (event) {
    event.preventDefault();
    var text = event.clipboardData ? event.clipboardData.getData('text/plain') : '';
    if (text) {
      document.execCommand('insertText', false, text);
    }
  });
  editor.addEventListener('drop', function (event) { event.preventDefault(); });
  editor.addEventListener('input', changed);
  editor.addEventListener('blur', send);

  try {
    document.execCommand('defaultParagraphSeparator', false, 'p');
  } catch (error) {}
  load(data.html);
  sent = serialize();
  showPlaceholder();
})();`;

// The glyph on each button. Its name for screen readers comes from the labels.
const GLYPHS: Record<EditorCommand, string> = {
  bold: '<b>B</b>',
  italic: '<i>I</i>',
  underline: '<u>U</u>',
  strike: '<s>S</s>',
  h2: 'H2',
  h3: 'H3',
  quote: '❝',
  paragraph: '¶',
  rule: '⁂',
};

function escapeAttribute(text: string): string {
  return text.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
}

/**
 * The page the editor runs in: an Android WebView shows it, and on web it is
 * the document of a sandboxed iframe. It posts `{type: 'change', html}` to
 * its host whenever the text has changed and typing has paused.
 *
 * The text goes in as JSON data, never as markup, and the page builds the
 * editor's content from it with the same cleaner the reader uses. The
 * content security policy allows no network access and no scripts but the
 * page's own.
 */
export function editorPage({
  html,
  appearance,
  labels,
  placeholder,
  label,
}: {
  html: string;
  appearance: EditorAppearance;
  labels: Record<EditorCommand, string>;
  placeholder: string;
  /** What the text area is called for screen readers. */
  label: string;
}): string {
  // "<" escaped so no text can close the data element early.
  const data = JSON.stringify({ html }).replace(/</g, '\\u003c');
  const buttons = EDITOR_COMMANDS.map(
    (command) =>
      `<button type="button" data-command="${command}" aria-label="${escapeAttribute(labels[command])}" title="${escapeAttribute(labels[command])}">${GLYPHS[command]}</button>`,
  ).join('');
  return `<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'">
<style>
  html, body { margin: 0; background: ${appearance.background}; color: ${appearance.text}; }
  body { font-family: ${FONT_STACKS.sans}; font-size: 17px; line-height: 1.7; }
  #toolbar { position: sticky; top: 0; z-index: 1; display: flex; flex-wrap: wrap; gap: 4px; padding: 6px 12px; background: ${appearance.toolbar}; }
  #toolbar button { min-width: 40px; min-height: 40px; border: none; border-radius: 8px; background: transparent; color: ${appearance.text}; font: inherit; font-size: 15px; }
  #toolbar button:active { background: ${appearance.background}; }
  #editor { position: relative; min-height: 60vh; max-width: 40em; margin: 0 auto; padding: 16px 20px 96px; outline: none; overflow-wrap: break-word; }
  #editor.empty::before { content: attr(data-placeholder); position: absolute; color: ${appearance.muted}; pointer-events: none; }
  #editor p { margin: 0 0 1em; }
  blockquote { margin: 1em 0; padding-left: 1em; border-left: 3px solid ${appearance.muted}; }
  hr { border: none; border-top: 1px solid ${appearance.muted}; margin: 2em 0; }
  h2, h3 { line-height: 1.3; }
</style>
</head>
<body>
<div id="toolbar" role="toolbar">${buttons}</div>
<article id="editor" contenteditable="true" role="textbox" aria-multiline="true" aria-label="${escapeAttribute(label)}" data-placeholder="${escapeAttribute(placeholder)}" spellcheck="true"></article>
<script type="application/json" id="data">${data}</script>
<script>${PAGE_SCRIPT}</script>
</body>
</html>`;
}

/** The HTML in a message from the page, or null when it is not a change of the text. */
export function changedHtml(message: unknown): string | null {
  if (typeof message !== 'string') {
    return null;
  }
  try {
    const parsed = JSON.parse(message) as { type?: unknown; html?: unknown };
    return parsed.type === 'change' && typeof parsed.html === 'string' ? parsed.html : null;
  } catch {
    return null;
  }
}
