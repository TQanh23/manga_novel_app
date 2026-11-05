import '@/i18n';

import { CormorantGaramond_700Bold } from '@expo-google-fonts/cormorant-garamond/700Bold';
import { PlayfairDisplay_700Bold } from '@expo-google-fonts/playfair-display/700Bold';
import { DarkTheme, DefaultTheme, SplashScreen, Stack, ThemeProvider } from 'expo-router';
import { useFonts } from 'expo-font';
import { useTranslation } from 'react-i18next';

import { SessionProvider, useSession } from '@/auth/session';
import { Colors, DISPLAY_FONT, ENGRAVED_FONT } from '@/constants/theme';
import { useScheme } from '@/hooks/use-theme';
import { ReaderSettingsProvider } from '@/reader/settings';

// Held until the silent sign-in has finished, so a signed-in user never sees
// the app flash by as a guest.
void SplashScreen.preventAutoHideAsync();

export default function RootLayout() {
  const scheme = useScheme();
  const base = scheme === 'dark' ? DarkTheme : DefaultTheme;
  const colors = Colors[scheme];
  // Headers, the stack's background and the tab bar's defaults follow the palette.
  const navigationTheme = {
    ...base,
    colors: {
      ...base.colors,
      primary: colors.accent,
      background: colors.background,
      card: colors.surface,
      text: colors.text,
      border: colors.border,
      notification: colors.accent,
    },
  };
  return (
    <ThemeProvider value={navigationTheme}>
      <SessionProvider>
        <ReaderSettingsProvider>
          <RootNavigator />
        </ReaderSettingsProvider>
      </SessionProvider>
    </ThemeProvider>
  );
}

function RootNavigator() {
  const { t } = useTranslation();
  const { user, isLoading } = useSession();
  // Held for the fonts too, so headings never jump from a fallback face.
  // A font that fails to load is not worth blocking the app for: the
  // fallback serif takes its place.
  const [fontsLoaded, fontError] = useFonts({
    [DISPLAY_FONT]: PlayfairDisplay_700Bold,
    [ENGRAVED_FONT]: CormorantGaramond_700Bold,
  });

  if (isLoading || (!fontsLoaded && !fontError)) {
    return null;
  }
  SplashScreen.hide();

  // Browsing and reading are open to guests. The studio is for authors, and
  // the sign-in screens are guarded from the other side: they are for people
  // who are signed out.
  return (
    <Stack
      screenOptions={{
        headerShown: false,
        headerTitleStyle: { fontFamily: DISPLAY_FONT, fontWeight: 'normal' },
      }}>
      <Stack.Screen name="(tabs)" />
      <Stack.Screen name="works/[workId]" options={{ headerShown: true, title: t('work.title') }} />
      <Stack.Screen name="read/[episodeId]" options={{ headerShown: true, title: t('reader.title') }} />
      <Stack.Protected guard={user?.roles.includes('author') ?? false}>
        <Stack.Screen name="studio/new" options={{ headerShown: true, title: t('studio.newTitle') }} />
        <Stack.Screen
          name="studio/[workId]"
          options={{ headerShown: true, title: t('studio.editTitle') }}
        />
        <Stack.Screen
          name="studio/episodes/[episodeId]"
          options={{ headerShown: true, title: t('studio.episode.text') }}
        />
        <Stack.Screen
          name="studio/glossary/[workId]"
          options={{ headerShown: true, title: t('studio.glossary.title') }}
        />
      </Stack.Protected>
      <Stack.Protected guard={user === null}>
        <Stack.Screen name="(auth)" />
      </Stack.Protected>
    </Stack>
  );
}
