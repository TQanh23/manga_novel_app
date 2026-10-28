import { Pressable, ScrollView, StyleSheet, View } from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { Accent, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

type ChipProps = {
  label: string;
  selected?: boolean;
  /** Without it the chip is a plain label. */
  onPress?: () => void;
};

export function Chip({ label, selected = false, onPress }: ChipProps) {
  const theme = useTheme();
  const style = [styles.chip, { backgroundColor: selected ? Accent : theme.backgroundElement }];
  const text = (
    <ThemedText type={selected ? 'smallBold' : 'small'} style={selected ? styles.onAccent : undefined}>
      {label}
    </ThemedText>
  );

  if (!onPress) {
    return <View style={style}>{text}</View>;
  }
  return (
    <Pressable
      accessibilityRole="radio"
      accessibilityLabel={label}
      accessibilityState={{ selected }}
      onPress={onPress}
      style={style}>
      {text}
    </Pressable>
  );
}

type ChipGroupProps<T extends string> = {
  label: string;
  options: readonly { value: T; label: string }[];
  value: T;
  onChange: (value: T) => void;
};

/** One row of chips of which exactly one is selected. Scrolls sideways when it does not fit. */
export function ChipGroup<T extends string>({ label, options, value, onChange }: ChipGroupProps<T>) {
  return (
    <View style={styles.group} accessibilityRole="radiogroup" accessibilityLabel={label}>
      <ThemedText type="small" themeColor="textSecondary">
        {label}
      </ThemedText>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.row}>
        {options.map((option) => (
          <Chip
            key={option.value}
            label={option.label}
            selected={option.value === value}
            onPress={() => onChange(option.value)}
          />
        ))}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  chip: {
    borderRadius: Spacing.three,
    paddingHorizontal: Spacing.three,
    paddingVertical: Spacing.one,
  },
  onAccent: {
    color: '#ffffff',
  },
  group: {
    gap: Spacing.one,
  },
  row: {
    gap: Spacing.two,
  },
});
