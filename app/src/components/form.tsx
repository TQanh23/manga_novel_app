import type { PropsWithChildren } from 'react';
import {
  ActivityIndicator,
  Pressable,
  type PressableProps,
  ScrollView,
  StyleSheet,
  TextInput,
  type TextInputProps,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { Accent, Danger, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

const FORM_WIDTH = 420;

/** Full-height, scrollable page with its content in a centred column. */
export function Screen({ children }: PropsWithChildren) {
  return (
    <ThemedView style={styles.screen}>
      <SafeAreaView style={styles.screen}>
        <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
          <View style={styles.column}>{children}</View>
        </ScrollView>
      </SafeAreaView>
    </ThemedView>
  );
}

type TextFieldProps = TextInputProps & { label: string; hint?: string };

export function TextField({ label, hint, style, ...input }: TextFieldProps) {
  const theme = useTheme();
  return (
    <View style={styles.field}>
      <ThemedText type="smallBold">{label}</ThemedText>
      <TextInput
        accessibilityLabel={label}
        placeholderTextColor={theme.textSecondary}
        style={[
          styles.input,
          { color: theme.text, backgroundColor: theme.backgroundElement },
          style,
        ]}
        {...input}
      />
      {hint ? (
        <ThemedText type="small" themeColor="textSecondary">
          {hint}
        </ThemedText>
      ) : null}
    </View>
  );
}

type ButtonProps = Omit<PressableProps, 'children'> & {
  label: string;
  variant?: 'primary' | 'secondary';
  busy?: boolean;
};

export function Button({ label, variant = 'primary', busy = false, disabled, ...rest }: ButtonProps) {
  const theme = useTheme();
  const primary = variant === 'primary';
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ busy, disabled: disabled ?? busy }}
      disabled={disabled ?? busy}
      style={({ pressed }) => [
        styles.button,
        { backgroundColor: primary ? Accent : theme.backgroundElement },
        (pressed || busy) && styles.dimmed,
      ]}
      {...rest}>
      {busy ? (
        <ActivityIndicator color={primary ? '#ffffff' : theme.text} />
      ) : (
        <ThemedText type="smallBold" style={primary ? styles.onAccent : undefined}>
          {label}
        </ThemedText>
      )}
    </Pressable>
  );
}

export function ErrorText({ children }: PropsWithChildren) {
  return (
    <ThemedText type="small" accessibilityRole="alert" style={styles.error}>
      {children}
    </ThemedText>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
  },
  scroll: {
    flexGrow: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: Spacing.four,
  },
  column: {
    width: '100%',
    maxWidth: FORM_WIDTH,
    gap: Spacing.three,
  },
  field: {
    gap: Spacing.one,
  },
  input: {
    borderRadius: Spacing.two,
    paddingHorizontal: Spacing.three,
    paddingVertical: Spacing.three,
    fontSize: 16,
  },
  button: {
    minHeight: 48,
    borderRadius: Spacing.two,
    paddingHorizontal: Spacing.three,
    alignItems: 'center',
    justifyContent: 'center',
  },
  dimmed: {
    opacity: 0.7,
  },
  onAccent: {
    color: '#ffffff',
  },
  error: {
    color: Danger,
  },
});
