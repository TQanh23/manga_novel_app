import { useEffect, useEffectEvent, useRef, useState } from 'react';

import { changedHtml, editorPage } from './editor-page';
import type { RichTextEditorProps } from './use-editor-page';
import { useEditorPage } from './use-editor-page';

/**
 * The episode text editor on web: the editor page in a sandboxed iframe. It
 * may run its own script and nothing else; it cannot reach the app's
 * document, storage or session, and talks to the app by message only.
 */
export default function RichTextEditor({ initialHtml, onChange }: RichTextEditorProps) {
  const options = useEditorPage();
  const frame = useRef<HTMLIFrameElement>(null);
  const [page] = useState(() => editorPage({ html: initialHtml, ...options }));
  const changed = useEffectEvent(onChange);

  useEffect(() => {
    const onMessage = (event: MessageEvent) => {
      if (event.source !== frame.current?.contentWindow) {
        return;
      }
      const html = changedHtml(event.data);
      if (html !== null) {
        changed(html);
      }
    };
    window.addEventListener('message', onMessage);
    return () => window.removeEventListener('message', onMessage);
  }, []);

  return (
    <iframe
      ref={frame}
      srcDoc={page}
      sandbox="allow-scripts"
      title={options.label}
      style={{ flex: 1, width: '100%', border: 'none', background: options.appearance.background }}
    />
  );
}
