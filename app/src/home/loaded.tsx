import type { ReactNode } from 'react';
import { StyleSheet, View } from 'react-native';

import type { Load } from '@/api/hooks';
import { ErrorState } from '@/components/state-views';
import { Radius, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

type LoadedProps<T> = {
  load: Load<T>;
  /** How tall the placeholder is while the section loads. */
  placeholderHeight: number;
  children: (data: T) => ReactNode;
};

/**
 * One homepage section's data: a quiet placeholder while it loads, a retry if
 * it fails, the section once it is there. Sections load and fail on their own.
 */
export function Loaded<T>({ load, placeholderHeight, children }: LoadedProps<T>) {
  const theme = useTheme();
  if (load.isLoading) {
    return (
      <View
        style={[
          styles.placeholder,
          { height: placeholderHeight, backgroundColor: theme.surface, borderColor: theme.border },
        ]}
      />
    );
  }
  if (load.error || load.data === null) {
    return <ErrorState code={load.error ?? 'unknown'} onRetry={load.reload} />;
  }
  return <>{children(load.data)}</>;
}

const styles = StyleSheet.create({
  placeholder: {
    borderWidth: 1,
    borderRadius: Radius.md,
    marginVertical: Spacing.one,
    opacity: 0.6,
  },
});
