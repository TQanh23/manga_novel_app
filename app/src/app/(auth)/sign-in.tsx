import { Link } from 'expo-router';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { useSession } from '@/auth/session';
import { Button, ErrorText, Screen, TextField } from '@/components/form';
import { LanguageSwitch } from '@/components/language-switch';
import { ThemedText } from '@/components/themed-text';
import { errorMessageKey } from '@/i18n';

export default function SignInScreen() {
  const { t } = useTranslation();
  const { signIn } = useSession();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true);
    setError(await signIn({ email: email.trim(), password }));
    setBusy(false);
  };

  return (
    <Screen>
      <ThemedText type="subtitle">{t('auth.signInTitle')}</ThemedText>
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
        value={password}
        onChangeText={setPassword}
        autoComplete="current-password"
        secureTextEntry
        onSubmitEditing={submit}
      />
      {error ? <ErrorText>{t(errorMessageKey(error))}</ErrorText> : null}
      <Button
        label={t('auth.signIn')}
        busy={busy}
        disabled={busy || !email || !password}
        onPress={submit}
      />
      <Link href="/register">
        <ThemedText type="linkPrimary">{t('auth.noAccount')}</ThemedText>
      </Link>
      <LanguageSwitch />
    </Screen>
  );
}
