import { useEffect, useRef, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { WebView, type WebViewMessageEvent } from 'react-native-webview';

import { novelPage, type NovelViewProps } from './novel-page';
import { useTextFontCss } from './text-font';

export type { NovelAppearance, NovelHeading } from './novel-page';

/**
 * An episode's text on Android: a WebView showing a page built for it.
 *
 * The paragraphs are HTML (D13) and React Native has no HTML renderer. The
 * page scrolls itself and posts the paragraph at the top as it changes.
 */
export default function NovelView(props: NovelViewProps) {
  // The page is built once, so it waits for the typeface rather than reflow later.
  const fontCss = useTextFontCss();
  if (fontCss === null) {
    return <View style={[styles.view, { backgroundColor: props.appearance.background }]} />;
  }
  return <NovelPage {...props} fontCss={fontCss} />;
}

function NovelPage({
  paragraphs,
  initialPosition,
  appearance,
  onPosition,
  onProgress,
  heading,
  fontCss,
}: NovelViewProps & { fontCss: string }) {
  const webView = useRef<WebView>(null);
  // Built once per episode (the screen remounts the view for another one).
  // Later changes of appearance are sent into the page, so it never reloads
  // and the reader keeps their place.
  const [page] = useState(() =>
    novelPage({ paragraphs, position: initialPosition, appearance, heading, fontCss }),
  );
  const style = JSON.stringify(appearance);

  useEffect(() => {
    webView.current?.injectJavaScript(`window.novel && window.novel.apply(${style}); true;`);
  }, [style]);

  const onMessage = (event: WebViewMessageEvent) => {
    try {
      const { position, progress } = JSON.parse(event.nativeEvent.data) as {
        position?: unknown;
        progress?: unknown;
      };
      if (typeof position === 'number' && Number.isInteger(position) && position >= 0) {
        onPosition(position);
      }
      if (typeof progress === 'number' && progress >= 0 && progress <= 100) {
        onProgress?.(Math.round(progress));
      }
    } catch {
      // Not a message from the page.
    }
  };

  return (
    <WebView
      ref={webView}
      source={{ html: page }}
      originWhitelist={['*']}
      onMessage={onMessage}
      setSupportMultipleWindows={false}
      allowFileAccess={false}
      style={[styles.view, { backgroundColor: appearance.background }]}
    />
  );
}

const styles = StyleSheet.create({
  view: {
    flex: 1,
  },
});
