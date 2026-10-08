import { Link } from 'expo-router';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { useSession } from '@/auth/session';
import { Button, ErrorText, Screen, TextField } from '@/components/form';
import { LanguageSwitch } from '@/components/language-switch';
import { ThemedText } from '@/components/themed-text';
import { currentLocale, errorMessageKey } from '@/i18n';

const MIN_PASSWORD_LENGTH = 8;

export default function RegisterScreen() {
  const { t } = useTranslation();
  const { register } = useSession();
  const [displayName, setDisplayName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Counted in characters, as the API does: Korean, Japanese and Vietnamese
  // passwords are not penalised for their byte length.
  const complete =
    displayName.trim().length > 0 && email.length > 0 && [...password].length >= MIN_PASSWORD_LENGTH;

  const submit = async () => {
    setBusy(true);
    setError(
      await register({
        email: email.trim(),
        password,
        displayName: displayName.trim(),
        // The account starts in the language the form was filled in.
        locale: currentLocale(),
      }),
    );
    setBusy(false);
  };

  return (
    <Screen>
      <ThemedText type="subtitle">{t('auth.registerTitle')}</ThemedText>
      <TextField
        label={t('auth.displayName')}
        value={displayName}
        onChangeText={setDisplayName}
        autoComplete="name"
        maxLength={80}
      />
      <TextField
        label={t('auth.email')}
        value={email}
        onChangeText={setEmail}
        autoCapitalize="none"
        autoComplete="email"
        autoCorrect={false}
        inputMode="email"
      />
      <TextField
        label={t('auth.password')}
        hint={t('auth.passwordHint')}
        value={password}
        onChangeText={setPassword}
        autoComplete="new-password"
        secureTextEntry
        onSubmitEditing={submit}
      />
      {error ? <ErrorText>{t(errorMessageKey(error))}</ErrorText> : null}
      <Button
        label={t('auth.register')}
        busy={busy}
        disabled={busy || !complete}
        onPress={submit}
      />
      <Link href="/sign-in">
        <ThemedText type="linkPrimary">{t('auth.haveAccount')}</ThemedText>
      </Link>
      <LanguageSwitch />
    </Screen>
  );
}
