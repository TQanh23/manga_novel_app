import type { PropsWithChildren } from 'react';
import { StyleSheet, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ThemedView } from '@/components/themed-view';
import { MaxContentWidth, MaxGridWidth } from '@/constants/theme';

/**
 * Full-height page whose content sits in a centred column on wide screens.
 * `wide` gives a grid of works room for several columns.
 */
export function Page({ children, wide = false }: PropsWithChildren<{ wide?: boolean }>) {
  return (
    <ThemedView style={styles.fill}>
      <SafeAreaView style={styles.fill} edges={['top', 'left', 'right']}>
        <View style={[styles.column, wide && styles.wide]}>{children}</View>
      </SafeAreaView>
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  fill: {
    flex: 1,
  },
  column: {
    flex: 1,
    width: '100%',
    maxWidth: MaxContentWidth,
    alignSelf: 'center',
  },
  wide: {
    maxWidth: MaxGridWidth,
  },
});
