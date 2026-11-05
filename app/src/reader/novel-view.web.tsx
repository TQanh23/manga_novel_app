import { useEffect, useMemo, useRef } from 'react';

import { FLOURISH_SVG, FONT_STACKS, type NovelViewProps, TOP_GAP } from './novel-page';
import { sanitizeBlock } from './sanitize';
import { useTextFontCss } from './text-font';

export type { NovelAppearance, NovelHeading } from './novel-page';

/**
 * An episode's text on web, where the app already is a web page: the
 * paragraphs go straight into the DOM, cleaned again with DOMPurify. The view
 * scrolls itself and reports which paragraph is at the top.
 */
export default function NovelView({
  paragraphs,
  initialPosition,
  appearance,
  onPosition,
  onProgress,
  heading,
}: NovelViewProps) {
  const container = useRef<HTMLDivElement>(null);
  const top = useRef(initialPosition);
  const blocks = useMemo(() => paragraphs.map(sanitizeBlock), [paragraphs]);
  // The app's typeface for the serif setting; until it loads, the fallback serif.
  const fontCss = useTextFontCss() ?? '';

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
    let percent = -1;
    const report = () => {
      const position = paragraphAtTop(element);
      if (position !== top.current) {
        top.current = position;
        onPosition(position);
      }
      const now = percentRead(element);
      if (now !== percent) {
        percent = now;
        onProgress?.(now);
      }
    };
    const onScroll = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(report);
    };
    element.addEventListener('scroll', onScroll, { passive: true });
    frame = requestAnimationFrame(report);
    return () => {
      element.removeEventListener('scroll', onScroll);
      cancelAnimationFrame(frame);
    };
  }, [onPosition, onProgress]);

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
        ${fontCss}
        .novel blockquote { margin: 1em 0; padding-left: 1em; border-left: 3px solid ${appearance.muted}; }
        .novel hr { border: none; border-top: 1px solid ${appearance.muted}; margin: 2em 0; }
        .novel h2, .novel h3 { line-height: 1.3; }
        .novel-heading, .novel-end { max-width: 40em; margin: 0 auto; padding: 0 20px; text-align: center; }
        .novel-heading { padding-top: 40px; }
        .novel-eyebrow { font-size: 0.72em; letter-spacing: 0.14em; text-transform: uppercase; color: ${appearance.muted}; }
        .novel-title { font-size: 1.6em; font-weight: 700; line-height: 1.3; margin: 0.3em 0 0.2em; }
        .novel-flourish { color: ${appearance.ornament}; }
        .novel-end { padding-bottom: 120px; margin-top: -48px; }
      `}</style>
      {heading ? (
        <header className="novel-heading">
          <div className="novel-eyebrow">{heading.eyebrow}</div>
          <h1 className="novel-title">{heading.title}</h1>
          {/* A constant, never built from data. */}
          <div className="novel-flourish" dangerouslySetInnerHTML={{ __html: FLOURISH_SVG }} />
        </header>
      ) : null}
      <article
        className="novel"
        style={{ maxWidth: '40em', margin: '0 auto', padding: '16px 20px 96px', overflowWrap: 'break-word' }}>
        {blocks.map((html, index) => (
          // The HTML went through sanitizeBlock: allowlisted tags, no attributes.
          <div key={index} data-i={index} dangerouslySetInnerHTML={{ __html: html }} />
        ))}
      </article>
      {heading ? (
        <footer className="novel-end">
          <div className="novel-flourish" dangerouslySetInnerHTML={{ __html: FLOURISH_SVG }} />
          <div className="novel-eyebrow">{heading.end}</div>
        </footer>
      ) : null}
    </div>
  );
}

/** How far down the text the reader has scrolled, as a whole percentage. */
function percentRead(container: HTMLElement): number {
  const room = container.scrollHeight - container.clientHeight;
  return room > 0 ? Math.min(100, Math.max(0, Math.round((container.scrollTop / room) * 100))) : 100;
}

function paragraphElements(container: HTMLElement): HTMLElement[] {
  return Array.from(container.querySelectorAll<HTMLElement>('[data-i]'));
}

// The first paragraph opens at the very top, so the chapter heading shows.
function scrollToParagraph(container: HTMLElement, position: number) {
  const target = position > 0 ? paragraphElements(container)[position] : undefined;
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
