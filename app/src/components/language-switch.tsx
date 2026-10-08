import { Pressable, StyleSheet, View } from 'react-native';
import { useTranslation } from 'react-i18next';

import { ThemedText } from '@/components/themed-text';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { currentLocale, LOCALES } from '@/i18n';

export function LanguageSwitch() {
  const { t, i18n } = useTranslation();
  const theme = useTheme();
  const active = currentLocale();

  return (
    <View style={styles.row} accessibilityRole="radiogroup" accessibilityLabel={t('common.language')}>
      <ThemedText type="small" themeColor="textSecondary">
        {t('common.language')}
      </ThemedText>
      {LOCALES.map((locale) => (
        <Pressable
          key={locale}
          accessibilityRole="radio"
          accessibilityState={{ selected: locale === active }}
          onPress={() => void i18n.changeLanguage(locale)}
          style={[
            styles.option,
            { backgroundColor: locale === active ? theme.backgroundSelected : 'transparent' },
          ]}>
          <ThemedText type={locale === active ? 'smallBold' : 'small'}>
            {t(`common.languageName.${locale}`)}
          </ThemedText>
        </Pressable>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.two,
  },
  option: {
    borderRadius: Spacing.two,
    paddingHorizontal: Spacing.three,
    paddingVertical: Spacing.two,
  },
});
