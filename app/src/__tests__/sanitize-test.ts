/**
 * @jest-environment jsdom
 */

import { sanitizeBlock } from '@/reader/sanitize';

test.each([
  ['<p>Kept.</p><script>steal()</script>', '<p>Kept.</p>'],
  ['<p onclick="steal()" style="color:red" class="x">Kept.</p>', '<p>Kept.</p>'],
  ['<p><img src="x" onerror="steal()">Kept.</p>', '<p>Kept.</p>'],
  ['<p><a href="javascript:steal()">Kept.</a></p>', '<p>Kept.</p>'],
  ['<p><iframe src="https://example.com"></iframe>Kept.</p>', '<p>Kept.</p>'],
])('the reader drops what the API should never have sent: %s', (html, clean) => {
  expect(sanitizeBlock(html)).toBe(clean);
});

test('the formatting authors write is kept', () => {
  const html =
    '<blockquote><p>Ông <strong>Bách</strong> nói: <em>chậm</em> <u>thôi</u> <s>nhé</s>.<br>月の下で</p></blockquote>';

  expect(sanitizeBlock(html)).toBe(html);
  expect(sanitizeBlock('<h2>Một</h2>')).toBe('<h2>Một</h2>');
  expect(sanitizeBlock('<hr>')).toBe('<hr>');
});
