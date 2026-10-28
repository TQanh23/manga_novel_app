'use dom';

import type { DOMProps } from 'expo/dom';
import { useEffect, useMemo, useRef } from 'react';

import { sanitizeBlock } from './sanitize';

export type NovelAppearance = {
  font: 'sans' | 'serif';
  fontSize: number;
  text: string;
  background: string;
  /** Rules and quote bars. */
  muted: string;
};

type NovelViewProps = {
  /** The episode's paragraphs, each one HTML block from the API. */
  paragraphs: string[];
  /** The paragraph to open at. */
  initialPosition: number;
  appearance: NovelAppearance;
  /** Called with the paragraph at the top of the screen whenever that changes. */
  onPosition: (position: number) => Promise<void>;
  dom?: DOMProps;
};

// Stacks that cover Vietnamese, Korean and Japanese on Android and on desktop browsers.
const FONT_STACKS = {
  sans: 'system-ui, -apple-system, Roboto, "Noto Sans", "Noto Sans CJK KR", "Noto Sans CJK JP", sans-serif',
  serif: 'Georgia, "Noto Serif", "Noto Serif CJK KR", "Noto Serif CJK JP", "Times New Roman", serif',
} as const;

const TOP_GAP = 16;

/**
 * An episode's text as a web page: the DOM on web, a WebView on Android.
 *
 * HTML is what the author wrote, so the browser lays it out; React Native has
 * no HTML renderer. The view scrolls itself and reports which paragraph is at
 * the top, so the screen around it can save the reading position.
 */
export default function NovelView({ paragraphs, initialPosition, appearance, onPosition }: NovelViewProps) {
  const container = useRef<HTMLDivElement>(null);
  const top = useRef(initialPosition);
  const blocks = useMemo(() => paragraphs.map(sanitizeBlock), [paragraphs]);

  // Open at the saved paragraph, and keep the same one at the top when the
  // text is laid out again in another font or size.
  useEffect(() => {
    if (container.current) {
      scrollToParagraph(container.current, top.current);
    }
  }, [blocks, appearance.font, appearance.fontSize]);

  useEffect(() => {
    const element = container.current;
    if (!element) {
      return;
    }
    let frame = 0;
    const onScroll = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const position = paragraphAtTop(element);
        if (position !== top.current) {
          top.current = position;
          void onPosition(position);
        }
      });
    };
    element.addEventListener('scroll', onScroll, { passive: true });
    return () => {
      element.removeEventListener('scroll', onScroll);
      cancelAnimationFrame(frame);
    };
  }, [onPosition]);

  return (
    <div
      ref={container}
      style={{
        position: 'absolute',
        inset: 0,
        overflowY: 'auto',
        background: appearance.background,
        color: appearance.text,
        fontFamily: FONT_STACKS[appearance.font],
        fontSize: appearance.fontSize,
        lineHeight: 1.7,
      }}>
      <style>{`
        .novel blockquote { margin: 1em 0; padding-left: 1em; border-left: 3px solid ${appearance.muted}; }
        .novel hr { border: none; border-top: 1px solid ${appearance.muted}; margin: 2em 0; }
        .novel h2, .novel h3 { line-height: 1.3; }
      `}</style>
      <article
        className="novel"
        style={{ maxWidth: '40em', margin: '0 auto', padding: '16px 20px 96px', overflowWrap: 'break-word' }}>
        {blocks.map((html, index) => (
          // The HTML went through sanitizeBlock: allowlisted tags, no attributes.
          <div key={index} data-i={index} dangerouslySetInnerHTML={{ __html: html }} />
        ))}
      </article>
    </div>
  );
}

function paragraphElements(container: HTMLElement): HTMLElement[] {
  return Array.from(container.querySelectorAll<HTMLElement>('[data-i]'));
}

function scrollToParagraph(container: HTMLElement, position: number) {
  const target = paragraphElements(container)[position];
  container.scrollTop = target ? Math.max(0, target.offsetTop - TOP_GAP) : 0;
}

/** The first paragraph not yet scrolled out of sight above the top edge. */
function paragraphAtTop(container: HTMLElement): number {
  const elements = paragraphElements(container);
  const edge = container.scrollTop + TOP_GAP;
  let low = 0;
  let high = elements.length - 1;
  while (low < high) {
    const middle = Math.floor((low + high) / 2);
    const element = elements[middle];
    if (element.offsetTop + element.offsetHeight > edge) {
      high = middle;
    } else {
      low = middle + 1;
    }
  }
  return Math.max(0, low);
}
