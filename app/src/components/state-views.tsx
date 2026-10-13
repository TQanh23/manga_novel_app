import { ActivityIndicator, StyleSheet, View } from 'react-native';
import { useTranslation } from 'react-i18next';

import { Button, ErrorText } from '@/components/form';
import { ThemedText } from '@/components/themed-text';
import { Spacing } from '@/constants/theme';
import { errorMessageKey } from '@/i18n';

export function LoadingState() {
  const { t } = useTranslation();
  return (
    <View style={styles.state}>
      <ActivityIndicator accessibilityLabel={t('common.loading')} />
    </View>
  );
}

export function EmptyState({ message }: { message: string }) {
  return (
    <View style={styles.state}>
      <ThemedText themeColor="textSecondary" style={styles.centred}>
        {message}
      </ThemedText>
    </View>
  );
}

type ErrorStateProps = {
  /** An API error code. */
  code: string;
  onRetry: () => void;
};

export function ErrorState({ code, onRetry }: ErrorStateProps) {
  const { t } = useTranslation();
  return (
    <View style={styles.state}>
      <ErrorText>{t(errorMessageKey(code))}</ErrorText>
      <Button label={t('common.retry')} variant="secondary" onPress={onRetry} />
    </View>
  );
}

const styles = StyleSheet.create({
  state: {
    alignItems: 'center',
    gap: Spacing.three,
    padding: Spacing.five,
  },
  centred: {
    textAlign: 'center',
  },
});
