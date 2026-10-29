import { useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

import type { PublishTimePickerProps } from './publish-time-picker';

/** `date` as a datetime-local input writes it: local time, to the minute. */
function localValue(date: Date): string {
  const pad = (part: number) => String(part).padStart(2, '0');
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
    `T${pad(date.getHours())}:${pad(date.getMinutes())}`
  );
}

/** Picks when an episode goes live, on web: the browser's own date and time input. */
export default function PublishTimePicker({ label, value, onChange }: PublishTimePickerProps) {
  const theme = useTheme();
  // The earliest the browser offers; the screen and the API check again on send.
  const [min] = useState(() => localValue(new Date()));

  return (
    <View style={styles.field}>
      <ThemedText type="smallBold">{label}</ThemedText>
      <input
        type="datetime-local"
        aria-label={label}
        min={min}
        value={value ? localValue(value) : ''}
        onChange={(event) => {
          // Parsed as local time, as the input shows it.
          const chosen = new Date(event.target.value);
          if (!Number.isNaN(chosen.getTime())) {
            onChange(chosen);
          }
        }}
        style={{
          borderRadius: Spacing.two,
          border: 'none',
          padding: Spacing.three,
          fontSize: 16,
          fontFamily: 'inherit',
          color: theme.text,
          backgroundColor: theme.backgroundElement,
        }}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  field: {
    gap: Spacing.one,
  },
});
