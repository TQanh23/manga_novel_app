import { DateTimePickerAndroid } from '@react-native-community/datetimepicker';
import { StyleSheet, View } from 'react-native';

import { Button } from '@/components/form';
import { ThemedText } from '@/components/themed-text';
import { Spacing } from '@/constants/theme';
import { formatDateTime } from '@/i18n';

export type PublishTimePickerProps = {
  label: string;
  /** What the button says before a time is chosen. */
  placeholder: string;
  value: Date | null;
  onChange: (date: Date) => void;
};

/**
 * Picks when an episode goes live, on Android: the system's date dialog, then
 * its time dialog. Leaving either one keeps the time chosen before.
 */
export default function PublishTimePicker({ label, placeholder, value, onChange }: PublishTimePickerProps) {
  const open = () => {
    const start = value ?? new Date();
    DateTimePickerAndroid.open({
      value: start,
      mode: 'date',
      minimumDate: new Date(),
      onChange: (event, day) => {
        if (event.type !== 'set' || !day) {
          return;
        }
        DateTimePickerAndroid.open({
          value: start,
          mode: 'time',
          onChange: (next, time) => {
            if (next.type !== 'set' || !time) {
              return;
            }
            const chosen = new Date(day);
            chosen.setHours(time.getHours(), time.getMinutes(), 0, 0);
            onChange(chosen);
          },
        });
      },
    });
  };

  return (
    <View style={styles.field}>
      <ThemedText type="smallBold">{label}</ThemedText>
      <Button
        label={value ? formatDateTime(value.toISOString()) : placeholder}
        variant="secondary"
        onPress={open}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  field: {
    gap: Spacing.one,
  },
});
