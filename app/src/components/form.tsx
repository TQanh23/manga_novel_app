import Ionicons from '@expo/vector-icons/Ionicons';
import { type ComponentProps, createContext, type PropsWithChildren, use, useState } from 'react';
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

import { OrnateFrame } from '@/components/ornaments';
import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { Fonts, Radius, Spacing } from '@/constants/theme';
import { useLayout } from '@/hooks/use-layout';
import { useTheme } from '@/hooks/use-theme';

const FORM_WIDTH = 420;

/** Inside a narrow form column, buttons span it whatever the window's width. */
const InFormColumn = createContext(false);

/** Full-height, scrollable page with its content in a framed, centred panel. */
export function Screen({ children }: PropsWithChildren) {
  return (
    <ThemedView style={styles.screen}>
      <SafeAreaView style={styles.screen}>
        <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
          <OrnateFrame frameStyle={styles.column} style={styles.panel}>
            <InFormColumn value={true}>{children}</InFormColumn>
          </OrnateFrame>
        </ScrollView>
      </SafeAreaView>
    </ThemedView>
  );
}

type TextFieldProps = TextInputProps & { label: string; hint?: string };

export function TextField({ label, hint, style, onFocus, onBlur, ...input }: TextFieldProps) {
  const theme = useTheme();
  const [focused, setFocused] = useState(false);
  return (
    <View style={styles.field}>
      <ThemedText type="eyebrow">{label}</ThemedText>
      <TextInput
        accessibilityLabel={label}
        placeholderTextColor={theme.textSecondary}
        style={[
          styles.input,
          {
            color: theme.text,
            backgroundColor: theme.surface,
            borderColor: focused ? theme.accent : theme.border,
          },
          style,
        ]}
        onFocus={(event) => {
          setFocused(true);
          onFocus?.(event);
        }}
        onBlur={(event) => {
          setFocused(false);
          onBlur?.(event);
        }}
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
  /** A glyph before the label; decoration, as the label names the button. */
  icon?: ComponentProps<typeof Ionicons>['name'];
  /** Share a row equally with the buttons beside it, whatever the window's width. */
  fill?: boolean;
};

export function Button({
  label,
  variant = 'primary',
  busy = false,
  icon,
  fill = false,
  disabled,
  ...rest
}: ButtonProps) {
  const theme = useTheme();
  const { isWide } = useLayout();
  const inForm = use(InFormColumn);
  const primary = variant === 'primary';
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ busy, disabled: disabled ?? busy }}
      disabled={disabled ?? busy}
      style={({ pressed }) => [
        styles.button,
        // On a wide window a button is as wide as its label, not the whole page.
        isWide && !inForm && !fill && styles.natural,
        fill && styles.fill,
        primary
          ? { backgroundColor: theme.accent, borderColor: theme.accent }
          : { backgroundColor: theme.surface, borderColor: theme.ornament },
        (pressed || busy) && styles.dimmed,
      ]}
      {...rest}>
      {/* A cartouche: a hairline drawn just inside the edge. */}
      <View
        pointerEvents="none"
        style={[
          styles.inset,
          primary ? { borderColor: theme.onAccent, opacity: 0.35 } : { borderColor: theme.border },
        ]}
      />
      {busy ? (
        <ActivityIndicator color={primary ? theme.onAccent : theme.text} />
      ) : (
        <View style={styles.labelRow}>
          {icon ? (
            <Ionicons
              name={icon}
              size={16}
              color={primary ? theme.onAccent : theme.accent}
              accessibilityElementsHidden
              importantForAccessibility="no"
            />
          ) : null}
          <ThemedText
            type="eyebrow"
            numberOfLines={2}
            style={[styles.label, { color: primary ? theme.onAccent : theme.text }]}>
            {label}
          </ThemedText>
        </View>
      )}
    </Pressable>
  );
}

export function ErrorText({ children }: PropsWithChildren) {
  return (
    <ThemedText type="small" accessibilityRole="alert" themeColor="danger">
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
  },
  panel: {
    padding: Spacing.four,
    gap: Spacing.three,
  },
  field: {
    gap: Spacing.one,
  },
  input: {
    fontFamily: Fonts.body,
    borderWidth: 1,
    borderRadius: Radius.md,
    paddingHorizontal: Spacing.three,
    paddingVertical: Spacing.three,
    fontSize: 17,
  },
  button: {
    minHeight: 48,
    borderWidth: 1,
    borderRadius: Radius.md,
    paddingHorizontal: Spacing.three,
    alignItems: 'center',
    justifyContent: 'center',
  },
  inset: {
    position: 'absolute',
    top: 3,
    right: 3,
    bottom: 3,
    left: 3,
    borderWidth: 1,
    borderRadius: Radius.sm,
  },
  label: {
    fontSize: 15,
    textAlign: 'center',
    flexShrink: 1,
  },
  fill: {
    flex: 1,
    paddingHorizontal: Spacing.two,
  },
  labelRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.two,
  },
  natural: {
    alignSelf: 'flex-start',
    minWidth: 200,
    paddingHorizontal: Spacing.five,
  },
  dimmed: {
    opacity: 0.7,
  },
});
