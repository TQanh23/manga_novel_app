import { useState } from 'react';
import { type NativeSyntheticEvent, Pressable, StyleSheet, type TextLayoutEventData, View } from 'react-native';
import { useTranslation } from 'react-i18next';

import { SectionHeader } from '@/components/section-header';
import { ThemedText } from '@/components/themed-text';
import { Spacing } from '@/constants/theme';

const CLAMP = 5;
// Measuring lines is not reliable everywhere (tests, first web paint), so a
// long text is also judged by its length.
const LONG = 360;

/** What the work is about, folded to a few lines when it runs long. */
export function Synopsis({ text }: { text: string }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [overflows, setOverflows] = useState(text.length > LONG);

  const measure = (event: NativeSyntheticEvent<TextLayoutEventData>) => {
    if (!open && event.nativeEvent.lines.length > CLAMP) {
      setOverflows(true);
    }
  };

  return (
    <View style={styles.section}>
      <SectionHeader title={t('work.synopsis')} />
      <ThemedText numberOfLines={open ? undefined : CLAMP} onTextLayout={measure} style={styles.text}>
        {text}
      </ThemedText>
      {overflows ? (
        <Pressable accessibilityRole="button" onPress={() => setOpen((shown) => !shown)} style={styles.toggle}>
          <ThemedText type="linkPrimary">{open ? t('work.readLess') : t('work.readMore')}</ThemedText>
        </Pressable>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  section: {
    gap: Spacing.two,
  },
  text: {
    fontSize: 18,
    lineHeight: 28,
  },
  toggle: {
    alignSelf: 'flex-start',
  },
});
