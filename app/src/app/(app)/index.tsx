import { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { useTranslation } from 'react-i18next';

import { useSession } from '@/auth/session';
import { Button, ErrorText, Screen } from '@/components/form';
import { LanguageSwitch } from '@/components/language-switch';
import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { Spacing } from '@/constants/theme';
import { errorMessageKey } from '@/i18n';

// Signed-in shell for Phase 0: who you are and which roles you hold. The
// catalogue replaces it in Phase 1.
export default function HomeScreen() {
  const { t } = useTranslation();
  const { user, becomeAuthor, signOut } = useSession();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (!user) {
    return null;
  }

  const requestAuthorRole = async () => {
    setBusy(true);
    setError(await becomeAuthor());
    setBusy(false);
  };

  return (
    <Screen>
      <ThemedText type="subtitle">{t('home.greeting', { name: user.display_name })}</ThemedText>

      <View style={styles.section}>
        <ThemedText type="small" themeColor="textSecondary">
          {t('home.email')}
        </ThemedText>
        <ThemedText>{user.email}</ThemedText>
      </View>

      <View style={styles.section}>
        <ThemedText type="small" themeColor="textSecondary">
          {t('home.roles')}
        </ThemedText>
        <View style={styles.roles}>
          {user.roles.map((role) => (
            <ThemedView key={role} type="backgroundElement" style={styles.role}>
              <ThemedText type="smallBold">{t(`roles.${role}`)}</ThemedText>
            </ThemedView>
          ))}
        </View>
      </View>

      {user.roles.includes('author') ? null : (
        <View style={styles.section}>
          <ThemedText type="small" themeColor="textSecondary">
            {t('home.becomeAuthorHint')}
          </ThemedText>
          <Button label={t('home.becomeAuthor')} busy={busy} onPress={requestAuthorRole} />
        </View>
      )}
      {error ? <ErrorText>{t(errorMessageKey(error))}</ErrorText> : null}

      <Button label={t('auth.signOut')} variant="secondary" onPress={signOut} />
      <LanguageSwitch />
    </Screen>
  );
}

const styles = StyleSheet.create({
  section: {
    gap: Spacing.two,
  },
  roles: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.two,
  },
  role: {
    borderRadius: Spacing.two,
    paddingHorizontal: Spacing.three,
    paddingVertical: Spacing.one,
  },
});
