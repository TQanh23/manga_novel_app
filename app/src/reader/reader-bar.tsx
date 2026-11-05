import Ionicons from '@expo/vector-icons/Ionicons';
import type { ComponentProps, ReactNode } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useTranslation } from 'react-i18next';

import { ThemedText } from '@/components/themed-text';
import { Fonts, MaxContentWidth, Spacing } from '@/constants/theme';

export type ReaderPanel = 'none' | 'contents' | 'settings';

type ReaderBarProps = {
  number: number;
  /** How much of the episode is behind the reader, 0 to 100. */
  percent: number;
  colors: { bar: string; text: string; muted: string; ornament: string };
  panel: ReaderPanel;
  onPanel: (panel: ReaderPanel) => void;
  onPrevious: (() => void) | null;
  onNext: (() => void) | null;
};

/**
 * The reader's bar, in the text's own colours: previous and next, where the
 * reader is, and the contents and text settings. A gold line along its top
 * fills as the episode is read.
 */
export function ReaderBar({ number, percent, colors, panel, onPanel, onPrevious, onNext }: ReaderBarProps) {
  const { t } = useTranslation();
  const insets = useSafeAreaInsets();
  const toggle = (which: ReaderPanel) => onPanel(panel === which ? 'none' : which);

  return (
    <View style={[styles.bar, { backgroundColor: colors.bar, borderTopColor: colors.ornament, paddingBottom: insets.bottom }]}>
      {/* The bar and its gold line span the window; the controls keep to the text's column. */}
      <View
        accessibilityElementsHidden
        importantForAccessibility="no-hide-descendants"
        style={[styles.progress, { width: `${percent}%`, backgroundColor: colors.ornament }]}
      />
      <View style={styles.controls}>
      <BarButton label={t('reader.previous')} onPress={onPrevious}>
        <Glyph color={colors.text}>‹</Glyph>
      </BarButton>
      <View style={styles.where} accessibilityLiveRegion="polite">
        <ThemedText type="eyebrow" numberOfLines={1} style={{ color: colors.muted }}>
          {[t('work.episodeNumber', { number }), t('reader.progress', { percent })].join(' · ')}
        </ThemedText>
      </View>
      <BarButton label={t('reader.contents')} selected={panel === 'contents'} onPress={() => toggle('contents')}>
        <Icon name="list-outline" color={colors.text} selected={panel === 'contents'} ornament={colors.ornament} />
      </BarButton>
      <BarButton label={t('reader.settings')} selected={panel === 'settings'} onPress={() => toggle('settings')}>
        <Icon name="text-outline" color={colors.text} selected={panel === 'settings'} ornament={colors.ornament} />
      </BarButton>
      <BarButton label={t('reader.next')} onPress={onNext}>
        <Glyph color={colors.text}>›</Glyph>
      </BarButton>
      </View>
    </View>
  );
}

type BarButtonProps = {
  label: string;
  /** Without one, the button is there but cannot be pressed. */
  onPress: (() => void) | null;
  selected?: boolean;
  children: ReactNode;
};

function BarButton({ label, onPress, selected = false, children }: BarButtonProps) {
  const disabled = onPress === null;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ disabled, selected }}
      disabled={disabled}
      onPress={onPress ?? undefined}
      style={({ pressed }) => [styles.button, (pressed || disabled) && styles.dimmed]}>
      {children}
    </Pressable>
  );
}

function Glyph({ color, children }: { color: string; children: string }) {
  return <Text style={[styles.glyph, { color }]}>{children}</Text>;
}

function Icon({
  name,
  color,
  selected,
  ornament,
}: {
  name: ComponentProps<typeof Ionicons>['name'];
  color: string;
  selected: boolean;
  ornament: string;
}) {
  return <Ionicons name={name} size={22} color={selected ? ornament : color} />;
}

const styles = StyleSheet.create({
  bar: {
    width: '100%',
    borderTopWidth: 1,
  },
  controls: {
    flexDirection: 'row',
    alignItems: 'center',
    width: '100%',
    maxWidth: MaxContentWidth,
    alignSelf: 'center',
    paddingHorizontal: Spacing.one,
  },
  progress: {
    position: 'absolute',
    top: -1,
    left: 0,
    height: 3,
  },
  where: {
    flex: 1,
    alignItems: 'center',
  },
  button: {
    minHeight: 52,
    minWidth: 48,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: Spacing.two,
  },
  dimmed: {
    opacity: 0.35,
  },
  glyph: {
    fontFamily: Fonts.display,
    fontSize: 32,
    lineHeight: 36,
  },
});
