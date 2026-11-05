import { Link, type Href } from 'expo-router';
import type { ReactNode } from 'react';
import { StyleSheet, View } from 'react-native';
import { useTranslation } from 'react-i18next';

import { Flourish } from '@/components/ornaments';
import { ThemedText } from '@/components/themed-text';
import { Fonts, Spacing } from '@/constants/theme';

type SectionHeaderProps = {
  title: string;
  /** Where "See all" leads; without it there is no link. */
  seeAll?: Href;
  /** Anything else for the right-hand side, such as a sort toggle. */
  action?: ReactNode;
};

/** A section's heading: the title, an optional "See all" or other action, a flourish under both. */
export function SectionHeader({ title, seeAll, action }: SectionHeaderProps) {
  const { t } = useTranslation();
  return (
    <View style={styles.header}>
      <View style={styles.row}>
        <ThemedText accessibilityRole="header" style={styles.title}>
          {title}
        </ThemedText>
        {seeAll ? (
          <Link href={seeAll} accessibilityLabel={`${t('home.seeAll')}: ${title}`}>
            <ThemedText type="linkPrimary">{t('home.seeAll')}</ThemedText>
          </Link>
        ) : null}
        {action}
      </View>
      <Flourish />
    </View>
  );
}

const styles = StyleSheet.create({
  header: {
    gap: Spacing.one,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'baseline',
    justifyContent: 'space-between',
    gap: Spacing.three,
  },
  title: {
    fontFamily: Fonts.display,
    fontSize: 24,
    lineHeight: 32,
    flexShrink: 1,
  },
});
