import Ionicons from '@expo/vector-icons/Ionicons';
import { Tabs } from 'expo-router/js-tabs';
import type { ComponentProps } from 'react';
import type { ColorValue } from 'react-native';
import { useTranslation } from 'react-i18next';

import { useSession } from '@/auth/session';
import { Accent } from '@/constants/theme';

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
  const isAuthor = user?.roles.includes('author') ?? false;
  return (
    <Tabs screenOptions={{ headerShown: false, tabBarActiveTintColor: Accent }}>
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
