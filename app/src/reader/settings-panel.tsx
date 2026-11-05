import { StyleSheet, View } from 'react-native';
import { useTranslation } from 'react-i18next';

import { ChipGroup } from '@/components/chip';
import { OrnateFrame } from '@/components/ornaments';
import { ThemedText } from '@/components/themed-text';
import { Fonts, MaxContentWidth, Spacing } from '@/constants/theme';
import { FONT_SIZES, READER_FONTS, READER_THEMES, useReaderSettings } from '@/reader/settings';
import { useTheme } from '@/hooks/use-theme';

/** Font, size and theme for the text. It keeps the app's colours, so its controls read the same in any text theme. */
export function SettingsPanel() {
  const { t } = useTranslation();
  const theme = useTheme();
  const { settings, update } = useReaderSettings();
  return (
    <OrnateFrame style={styles.frame} frameStyle={styles.sheet}>
      <View style={[styles.preview, { borderColor: theme.border }]}>
        <ThemedText
          style={{
            fontFamily: settings.font === 'serif' ? Fonts.body : Fonts.sans,
            fontSize: FONT_SIZES[settings.size],
            lineHeight: FONT_SIZES[settings.size] * 1.5,
          }}>
          {t('reader.preview')}
        </ThemedText>
      </View>
      <ChipGroup
        label={t('reader.font')}
        options={READER_FONTS.map((font) => ({ value: font, label: t(`reader.fonts.${font}`) }))}
        value={settings.font}
        onChange={(font) => update({ font })}
      />
      <ChipGroup
        label={t('reader.size')}
        options={FONT_SIZES.map((size, index) => ({ value: String(index), label: String(size) }))}
        value={String(settings.size)}
        onChange={(size) => update({ size: Number(size) })}
      />
      <ChipGroup
        label={t('reader.theme')}
        options={READER_THEMES.map((value) => ({ value, label: t(`reader.themes.${value}`) }))}
        value={settings.theme}
        onChange={(value) => update({ theme: value })}
      />
    </OrnateFrame>
  );
}

const styles = StyleSheet.create({
  // Centred in the text's column, now that the reader spans the window.
  sheet: {
    width: '100%',
    maxWidth: MaxContentWidth,
  },
  frame: {
    padding: Spacing.three,
    gap: Spacing.three,
  },
  preview: {
    borderBottomWidth: StyleSheet.hairlineWidth,
    paddingBottom: Spacing.two,
    alignItems: 'center',
  },
});
