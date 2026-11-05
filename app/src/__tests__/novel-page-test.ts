import { JSDOM } from 'jsdom';

import { type NovelAppearance, type NovelHeading, novelPage } from '@/reader/novel-page';

const APPEARANCE: NovelAppearance = {
  font: 'serif',
  fontSize: 18,
  text: '#000000',
  background: '#ffffff',
  muted: '#60646C',
  ornament: '#8E6A24',
};

/** The page as the Android WebView runs it: its own scripts on, nothing else. */
function load(paragraphs: string[], heading?: NovelHeading) {
  const page = new JSDOM(novelPage({ paragraphs, position: 0, appearance: APPEARANCE, heading }), {
    runScripts: 'dangerously',
    pretendToBeVisual: true,
    // jsdom lays nothing out, so it cannot scroll.
    beforeParse: (window) => {
      window.scrollTo = () => {};
    },
  });
  const { document } = page.window;
  return {
    window: page.window,
    document,
    blocks: Array.from(document.querySelectorAll('#text > [data-i]')).map((block) => block.innerHTML),
  };
}

test('FR-RD-03: every paragraph becomes one block of the page, in order', () => {
  const paragraphs = [
    '<h2>Dầu sương</h2>',
    '<p>Ông <strong>Bách</strong> nói: <em>chậm</em> <u>thôi</u> <s>nhé</s>.<br>月の下で</p>',
    '<blockquote><p>그날 밤, 비가 내렸다.</p></blockquote>',
    '<hr>',
  ];

  expect(load(paragraphs).blocks).toEqual(paragraphs);
});

test.each([
  ['<p>Kept.<script>window.stolen = 1</script></p>', '<p>Kept.</p>'],
  ['<p onclick="window.stolen = 1" style="color:red" class="x">Kept.</p>', '<p>Kept.</p>'],
  ['<p><img src="x" onerror="window.stolen = 1">Kept.</p>', '<p>Kept.</p>'],
  ['<p><a href="javascript:window.stolen = 1">Kept.</a></p>', '<p>Kept.</p>'],
  ['<p><iframe src="https://example.com"></iframe><svg><script>1</script></svg>Kept.</p>', '<p>Kept.</p>'],
  ['<p><span>Kept.</span></p>', '<p>Kept.</p>'],
])('the page drops what the API should never have sent: %s', (html, clean) => {
  const { blocks, window } = load([html]);

  expect(blocks).toEqual([clean]);
  expect((window as unknown as { stolen?: number }).stolen).toBeUndefined();
});

test('a paragraph cannot break out of the data it is carried in', () => {
  const { blocks, window } = load(['<p>a</script><script>window.stolen = 1</script></p>']);

  expect((window as unknown as { stolen?: number }).stolen).toBeUndefined();
  expect(blocks).toEqual(['<p>a</p>']);
});

test('the page allows no network access and no scripts but its own', () => {
  const html = novelPage({ paragraphs: [], position: 0, appearance: APPEARANCE });

  // Fonts only as data the page carries, never fetched.
  expect(html).toContain(
    `content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; font-src data:"`,
  );
});

test('the page carries the font rules it is given', () => {
  const fontCss = '@font-face { font-family: "EB Garamond"; src: url("data:font/ttf;base64,AAAA"); }';
  const html = novelPage({ paragraphs: [], position: 0, appearance: APPEARANCE, fontCss });

  expect(html).toContain(fontCss);
});

test('the reader changes how the page looks without reloading it', () => {
  const { window } = load(['<p>Một.</p>']);
  const novel = (window as unknown as { novel: { apply: (a: NovelAppearance) => void } }).novel;

  novel.apply({ ...APPEARANCE, font: 'sans', fontSize: 24, background: '#000000' });

  const style = window.document.documentElement.style;
  expect(style.getPropertyValue('--size')).toBe('24px');
  expect(style.getPropertyValue('--background')).toBe('#000000');
  expect(style.getPropertyValue('--font')).toContain('system-ui');
});

test('FR-RD-03: the chapter heading and end mark are text, whatever the titles hold', () => {
  const { document, window, blocks } = load(['<p>Một.</p>', '<p>Hai.</p>'], {
    eyebrow: 'Người Giữ Đèn · Episode 1',
    title: '<b>Bold</b><img src=x onerror="window.stolen = 1">',
    end: 'End of episode 1',
  });

  expect(document.getElementById('eyebrow')?.textContent).toBe('Người Giữ Đèn · Episode 1');
  expect(document.getElementById('title')?.textContent).toBe('<b>Bold</b><img src=x onerror="window.stolen = 1">');
  expect(document.querySelector('#title b, #title img')).toBeNull();
  expect(document.getElementById('end-text')?.textContent).toBe('End of episode 1');
  expect((window as unknown as { stolen?: number }).stolen).toBeUndefined();
  // Outside the article: paragraph indexes, and so saved positions, are as before.
  expect(blocks).toEqual(['<p>Một.</p>', '<p>Hai.</p>']);
  expect(document.querySelectorAll('#text > *')).toHaveLength(2);
});

test('FR-RD-03: without a heading the page has none', () => {
  const { document } = load(['<p>Một.</p>']);

  expect(document.getElementById('heading')).toBeNull();
  expect(document.getElementById('end')).toBeNull();
});
