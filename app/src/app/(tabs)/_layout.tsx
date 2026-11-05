import Ionicons from '@expo/vector-icons/Ionicons';
import { Tabs } from 'expo-router/js-tabs';
import type { ComponentProps } from 'react';
import type { ColorValue } from 'react-native';
import { useTranslation } from 'react-i18next';

import { useSession } from '@/auth/session';
import { useLayout } from '@/hooks/use-layout';
import { useTheme } from '@/hooks/use-theme';

type IconName = ComponentProps<typeof Ionicons>['name'];

function icon(name: IconName) {
  function TabIcon({ color, size }: { color: ColorValue; size: number }) {
    return <Ionicons name={name} color={color} size={size} />;
  }
  return TabIcon;
}

export default function TabsLayout() {
  const { t } = useTranslation();
  const { user } = useSession();
  const theme = useTheme();
  const { isWide } = useLayout();
  const isAuthor = user?.roles.includes('author') ?? false;
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: theme.accent,
        tabBarInactiveTintColor: theme.textSecondary,
        tabBarLabelStyle: { fontWeight: 600 },
        // A bottom bar on phones; on a wide window, a sidebar with labels beside the icons.
        ...(isWide
          ? {
              tabBarPosition: 'left',
              tabBarVariant: 'material',
              tabBarLabelPosition: 'beside-icon',
              tabBarActiveBackgroundColor: theme.backgroundSelected,
              tabBarStyle: {
                backgroundColor: theme.surface,
                borderRightColor: theme.border,
                minWidth: 220,
                paddingTop: 24,
              },
            }
          : {
              tabBarStyle: { backgroundColor: theme.surface, borderTopColor: theme.border },
            }),
      }}>
      <Tabs.Screen name="index" options={{ title: t('tabs.home'), tabBarIcon: icon('home-outline') }} />
      <Tabs.Screen
        name="search"
        options={{ title: t('tabs.search'), tabBarIcon: icon('search-outline') }}
      />
      <Tabs.Screen
        name="library"
        options={{ title: t('tabs.library'), tabBarIcon: icon('library-outline') }}
      />
      <Tabs.Screen
        name="studio"
        // Only authors have a studio; for everyone else the tab is not there.
        options={{
          title: t('tabs.studio'),
          tabBarIcon: icon('create-outline'),
          href: isAuthor ? undefined : null,
        }}
      />
      <Tabs.Screen
        name="account"
        options={{ title: t('tabs.account'), tabBarIcon: icon('person-outline') }}
      />
    </Tabs>
  );
}
