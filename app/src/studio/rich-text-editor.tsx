import { useState } from 'react';
import { StyleSheet } from 'react-native';
import { WebView, type WebViewMessageEvent } from 'react-native-webview';

import { changedHtml, editorPage } from './editor-page';
import type { RichTextEditorProps } from './use-editor-page';
import { useEditorPage } from './use-editor-page';

/**
 * The episode text editor on Android: a WebView showing the editor page.
 * React Native has no rich-text input; the page's contenteditable is one.
 */
export default function RichTextEditor({ initialHtml, onChange }: RichTextEditorProps) {
  const options = useEditorPage();
  // Built once per episode (the screen remounts the editor for another one),
  // so the page never reloads under the author's cursor.
  const [page] = useState(() => editorPage({ html: initialHtml, ...options }));

  const onMessage = (event: WebViewMessageEvent) => {
    const html = changedHtml(event.nativeEvent.data);
    if (html !== null) {
      onChange(html);
    }
  };

  return (
    <WebView
      source={{ html: page }}
      originWhitelist={['*']}
      onMessage={onMessage}
      setSupportMultipleWindows={false}
      allowFileAccess={false}
      style={[styles.view, { backgroundColor: options.appearance.background }]}
    />
  );
}

const styles = StyleSheet.create({
  view: {
    flex: 1,
  },
});
