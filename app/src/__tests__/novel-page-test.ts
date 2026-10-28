import { JSDOM } from 'jsdom';

import { type NovelAppearance, novelPage } from '@/reader/novel-page';

const APPEARANCE: NovelAppearance = {
  font: 'serif',
  fontSize: 18,
  text: '#000000',
  background: '#ffffff',
  muted: '#60646C',
};

/** The page as the Android WebView runs it: its own scripts on, nothing else. */
function load(paragraphs: string[]) {
  const page = new JSDOM(novelPage({ paragraphs, position: 0, appearance: APPEARANCE }), {
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

  expect(html).toContain(
    `content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'"`,
  );
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
