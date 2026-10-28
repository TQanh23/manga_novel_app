import { Pressable, ScrollView, StyleSheet, View } from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { Accent, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

type ChipProps = {
  label: string;
  selected?: boolean;
  /** Without it the chip is a plain label. */
  onPress?: () => void;
  /** One of a group where exactly one is chosen, or one of several that can be. */
  role?: 'radio' | 'checkbox';
  disabled?: boolean;
};

export function Chip({
  label,
  selected = false,
  onPress,
  role = 'radio',
  disabled = false,
}: ChipProps) {
  const theme = useTheme();
  const style = [
    styles.chip,
    { backgroundColor: selected ? Accent : theme.backgroundElement },
    disabled && styles.disabled,
  ];
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
      accessibilityRole={role}
      accessibilityLabel={label}
      accessibilityState={
        role === 'radio' ? { selected, disabled } : { checked: selected, disabled }
      }
      disabled={disabled}
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

type ChipSetProps<T extends string> = {
  label: string;
  options: readonly { value: T; label: string }[];
  values: readonly T[];
  /** How many may be chosen. The others are disabled once that many are. */
  max?: number;
  onChange: (values: T[]) => void;
};

/** Chips of which any number up to `max` are chosen. Wraps onto more rows when it does not fit. */
export function ChipSet<T extends string>({
  label,
  options,
  values,
  max = Infinity,
  onChange,
}: ChipSetProps<T>) {
  const full = values.length >= max;
  return (
    <View style={styles.group} accessibilityLabel={label}>
      <ThemedText type="small" themeColor="textSecondary">
        {label}
      </ThemedText>
      <View style={styles.wrap}>
        {options.map((option) => {
          const selected = values.includes(option.value);
          return (
            <Chip
              key={option.value}
              role="checkbox"
              label={option.label}
              selected={selected}
              disabled={full && !selected}
              onPress={() =>
                onChange(
                  selected
                    ? values.filter((value) => value !== option.value)
                    : [...values, option.value],
                )
              }
            />
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.two,
  },
  chip: {
    borderRadius: Spacing.three,
    paddingHorizontal: Spacing.three,
    paddingVertical: Spacing.one,
  },
  onAccent: {
    color: '#ffffff',
  },
  disabled: {
    opacity: 0.5,
  },
  group: {
    gap: Spacing.one,
  },
  row: {
    gap: Spacing.two,
  },
});
