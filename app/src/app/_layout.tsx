import '@/i18n';

import { DarkTheme, DefaultTheme, SplashScreen, Stack, ThemeProvider } from 'expo-router';
import { useColorScheme } from 'react-native';
import { useTranslation } from 'react-i18next';

import { SessionProvider, useSession } from '@/auth/session';

// Held until the silent sign-in has finished, so a signed-in user never sees
// the app flash by as a guest.
void SplashScreen.preventAutoHideAsync();

export default function RootLayout() {
  const colorScheme = useColorScheme();
  return (
    <ThemeProvider value={colorScheme === 'dark' ? DarkTheme : DefaultTheme}>
      <SessionProvider>
        <RootNavigator />
      </SessionProvider>
    </ThemeProvider>
  );
}

function RootNavigator() {
  const { t } = useTranslation();
  const { user, isLoading } = useSession();

  if (isLoading) {
    return null;
  }
  SplashScreen.hide();

  // Browsing and reading are open to guests. Only the sign-in screens are
  // guarded, and from the other side: they are for people who are signed out.
  return (
    <Stack screenOptions={{ headerShown: false }}>
      <Stack.Screen name="(tabs)" />
      <Stack.Screen name="works/[workId]" options={{ headerShown: true, title: t('work.title') }} />
      <Stack.Protected guard={user === null}>
        <Stack.Screen name="(auth)" />
      </Stack.Protected>
    </Stack>
  );
}
