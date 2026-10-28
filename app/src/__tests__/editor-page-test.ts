import { JSDOM } from 'jsdom';

import {
  CHANGE_DELAY_MS,
  changedHtml,
  EDITOR_COMMANDS,
  type EditorCommand,
  editorPage,
} from '@/studio/editor-page';

const LABELS = Object.fromEntries(EDITOR_COMMANDS.map((command) => [command, command])) as Record<
  EditorCommand,
  string
>;

type PageWindow = JSDOM['window'] & {
  ReactNativeWebView: { postMessage: (text: string) => void };
  stolen?: number;
};

/** The page as the Android WebView runs it: its own scripts on, nothing else. */
function load(html: string) {
  const posted: string[] = [];
  const commands: [string, string | undefined][] = [];
  const page = new JSDOM(
    editorPage({
      html,
      appearance: { text: '#000', background: '#fff', muted: '#666', toolbar: '#eee' },
      labels: LABELS,
      placeholder: 'Start writing…',
      label: 'Text',
    }),
    {
      runScripts: 'dangerously',
      pretendToBeVisual: true,
      beforeParse: (window) => {
        (window as PageWindow).ReactNativeWebView = { postMessage: (text) => posted.push(text) };
        // jsdom does no editing; the test records what the page asks for.
        window.document.execCommand = (command: string, _ui?: boolean, value?: string) => {
          commands.push([command, value]);
          return true;
        };
      },
    },
  );
  const window = page.window as PageWindow;
  const editor = window.document.getElementById('editor') as HTMLElement;
  return {
    window,
    editor,
    commands,
    /** Changes the editor's content as typing would, then lets the page send it. */
    async type(content: string) {
      editor.innerHTML = content;
      editor.dispatchEvent(new window.Event('input'));
      await new Promise((resolve) => setTimeout(resolve, CHANGE_DELAY_MS + 50));
    },
    sent: () => posted.map(changedHtml),
  };
}

test('FR-NV-01: the saved text opens in the editor, block by block', () => {
  const { editor } = load('<h2>Dầu sương</h2>\n<p>Ông <strong>Bách</strong> nói.</p>\n<hr>\n<p>月の下で</p>');

  expect(editor.innerHTML).toBe('<h2>Dầu sương</h2><p>Ông <strong>Bách</strong> nói.</p><hr><p>月の下で</p>');
  expect(editor.className).toBe('');
});

test('an empty episode opens on one empty paragraph, with the placeholder', () => {
  const { editor } = load('');

  expect(editor.innerHTML).toBe('<p><br></p>');
  expect(editor.className).toBe('empty');
  expect(editor.getAttribute('data-placeholder')).toBe('Start writing…');
});

test('FR-NV-01: what the author writes leaves the page as the API stores it', async () => {
  const page = load('<p>Một.</p>');

  // What browsers make while editing: <strike>, <div> lines, loose text,
  // styled spans and empty paragraphs.
  await page.type(
    'Mở đầu <b>đậm</b><div>Dòng <strike>gạch</strike></div><p><span style="color:red">그날 밤</span></p><p><br></p><hr><blockquote><p>引用</p></blockquote>',
  );

  expect(page.sent()).toEqual([
    '<p>Mở đầu <b>đậm</b></p><p>Dòng <s>gạch</s></p><p>그날 밤</p><hr><blockquote><p>引用</p></blockquote>',
  ]);
});

test('typing that changes nothing sends nothing', async () => {
  const page = load('<p>Một.</p>');

  await page.type('<p>Một.</p>');
  await page.type('<p>Một.</p><p><br></p>');

  expect(page.sent()).toEqual([]);
});

test('the text is sent once typing pauses, not on every key', async () => {
  const page = load('');

  page.editor.innerHTML = '<p>M</p>';
  page.editor.dispatchEvent(new page.window.Event('input'));
  page.editor.innerHTML = '<p>Mộ</p>';
  page.editor.dispatchEvent(new page.window.Event('input'));
  await page.type('<p>Một</p>');

  expect(page.sent()).toEqual(['<p>Một</p>']);
});

test('leaving the text sends it at once', () => {
  const page = load('');

  page.editor.innerHTML = '<p>Một</p>';
  page.editor.dispatchEvent(new page.window.Event('input'));
  page.editor.dispatchEvent(new page.window.Event('blur'));

  expect(page.sent()).toEqual(['<p>Một</p>']);
});

test.each([
  ['bold', 'bold', undefined],
  ['strike', 'strikeThrough', undefined],
  ['h2', 'formatBlock', '<h2>'],
  ['quote', 'formatBlock', '<blockquote>'],
  ['paragraph', 'formatBlock', '<p>'],
  ['rule', 'insertHorizontalRule', undefined],
])('the %s button runs %s', (command, browserCommand, value) => {
  const page = load('<p>Một</p>');

  const button = page.window.document.querySelector(`[data-command="${command}"]`) as HTMLElement;
  button.dispatchEvent(new page.window.MouseEvent('click', { bubbles: true }));

  expect(page.commands).toContainEqual([browserCommand, value]);
});

test('every button is named for screen readers', () => {
  const { window } = load('');

  const names = Array.from(window.document.querySelectorAll('#toolbar button')).map((button) =>
    button.getAttribute('aria-label'),
  );
  expect(names).toEqual([...EDITOR_COMMANDS]);
});

test('pasted text comes in as plain text', () => {
  const page = load('<p>Một</p>');

  const paste = new page.window.Event('paste', { cancelable: true }) as Event & {
    clipboardData: { getData: (type: string) => string };
  };
  paste.clipboardData = {
    getData: (type) => (type === 'text/plain' ? 'Dòng một\nDòng hai' : '<img src=x onerror="stolen=1">'),
  };
  page.editor.dispatchEvent(paste);

  expect(paste.defaultPrevented).toBe(true);
  expect(page.commands).toContainEqual(['insertText', 'Dòng một\nDòng hai']);
});

test.each([
  '<p>Kept.<script>window.stolen = 1</script></p>',
  '<p><img src="x" onerror="window.stolen = 1">Kept.</p>',
  '<p>a</script><script>window.stolen = 1</script></p>',
])('nothing in the saved text runs in the editor: %s', (html) => {
  const { window, editor } = load(html);

  expect(window.stolen).toBeUndefined();
  expect(editor.querySelector('script, img')).toBeNull();
});

test('only change messages carry text to the app', () => {
  expect(changedHtml(JSON.stringify({ type: 'change', html: '<p>a</p>' }))).toBe('<p>a</p>');
  expect(changedHtml(JSON.stringify({ type: 'other', html: '<p>a</p>' }))).toBeNull();
  expect(changedHtml(JSON.stringify({ type: 'change', html: 1 }))).toBeNull();
  expect(changedHtml('not json')).toBeNull();
  expect(changedHtml({ type: 'change', html: '<p>a</p>' })).toBeNull();
});
