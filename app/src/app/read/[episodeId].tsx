import { Stack, useLocalSearchParams, useRouter } from 'expo-router';
import { useState } from 'react';
import { Pressable, StyleSheet, useColorScheme, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useTranslation } from 'react-i18next';

import { type EpisodeContentResponse, readerGetEpisodeContent } from '@/api/generated';
import { useLoad } from '@/api/hooks';
import { useSession } from '@/auth/session';
import { ChipGroup } from '@/components/chip';
import { Button } from '@/components/form';
import { Page } from '@/components/page';
import { EmptyState, ErrorState, LoadingState } from '@/components/state-views';
import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { Colors, Spacing } from '@/constants/theme';
import NovelView, { type NovelAppearance } from '@/reader/novel-view';
import {
  FONT_SIZES,
  READER_FONTS,
  READER_THEMES,
  type ReaderSettings,
  useReaderSettings,
} from '@/reader/settings';
import { useProgressSaver } from '@/reader/use-progress-saver';

/** A novel episode, read paragraph by paragraph, opening where the reader left off (FR-RD-03). */
export default function ReadScreen() {
  const { t } = useTranslation();
  const router = useRouter();
  const { episodeId } = useLocalSearchParams<{ episodeId: string }>();
  const { user } = useSession();
  // The position in the answer is the signed-in reader's own, so a new reader asks again.
  const content = useLoad(`content:${episodeId}:${user?.id ?? 'guest'}`, () =>
    readerGetEpisodeContent({ path: { episode_id: episodeId } }),
  );

  const body = () => {
    if (content.isLoading) {
      return <LoadingState />;
    }
    if (content.error === 'episode_locked') {
      return (
        <View style={styles.message}>
          <EmptyState message={t('reader.locked')} />
          <Button label={t('reader.back')} variant="secondary" onPress={() => router.back()} />
        </View>
      );
    }
    if (content.error === 'episode_not_found') {
      return <EmptyState message={t('reader.notFound')} />;
    }
    if (content.error === 'not_a_novel') {
      return <EmptyState message={t('reader.notANovel')} />;
    }
    if (content.error || !content.data) {
      return <ErrorState code={content.error ?? 'unknown'} onRetry={content.reload} />;
    }
    return <Reader key={content.data.id} episode={content.data} signedIn={user !== null} />;
  };

  const title = content.data
    ? t('reader.heading', { number: content.data.number, title: content.data.title })
    : t('reader.title');
  return (
    <Page>
      <Stack.Screen options={{ title }} />
      {body()}
    </Page>
  );
}

function Reader({ episode, signedIn }: { episode: EpisodeContentResponse; signedIn: boolean }) {
  const { t } = useTranslation();
  const router = useRouter();
  const { settings } = useReaderSettings();
  const [showSettings, setShowSettings] = useState(false);
  const insets = useSafeAreaInsets();
  const appearance = useAppearance(settings);
  const savePosition = useProgressSaver({
    episodeId: episode.id,
    saved: episode.position,
    enabled: signedIn,
  });

  if (episode.paragraphs.length === 0) {
    return <EmptyState message={t('reader.empty')} />;
  }
  // The author may have published a shorter text since the position was saved.
  const start = Math.min(episode.position ?? 0, episode.paragraphs.length - 1);
  const open = (id: string) => router.replace({ pathname: '/read/[episodeId]', params: { episodeId: id } });

  return (
    <View style={[styles.reader, { backgroundColor: appearance.background }]}>
      <View style={styles.text}>
        <NovelView
          paragraphs={episode.paragraphs}
          initialPosition={start}
          appearance={appearance}
          onPosition={async (position) => savePosition(position)}
          dom={{ style: styles.text }}
        />
      </View>
      {showSettings ? <SettingsPanel /> : null}
      <View style={[styles.bar, { backgroundColor: appearance.bar, paddingBottom: insets.bottom }]}>
        <BarButton
          label={t('reader.previous')}
          color={appearance.text}
          disabled={episode.previous_episode_id === null}
          onPress={() => episode.previous_episode_id && open(episode.previous_episode_id)}
        />
        <BarButton
          label={t('reader.settings')}
          color={appearance.text}
          selected={showSettings}
          onPress={() => setShowSettings((shown) => !shown)}
        />
        <BarButton
          label={t('reader.next')}
          color={appearance.text}
          disabled={episode.next_episode_id === null}
          onPress={() => episode.next_episode_id && open(episode.next_episode_id)}
        />
      </View>
    </View>
  );
}

/** The reader's own colours and type, apart from the app's theme. */
function useAppearance(settings: ReaderSettings): NovelAppearance & { bar: string } {
  const scheme = useColorScheme();
  const theme = settings.theme === 'system' ? (scheme === 'dark' ? 'dark' : 'light') : settings.theme;
  const colors = Colors[theme];
  return {
    font: settings.font,
    fontSize: FONT_SIZES[settings.size],
    text: colors.text,
    background: colors.background,
    muted: colors.textSecondary,
    bar: colors.backgroundElement,
  };
}

function SettingsPanel() {
  const { t } = useTranslation();
  const { settings, update } = useReaderSettings();
  return (
    // The panel keeps the app's colours, so its controls read the same whatever the text's theme.
    <ThemedView type="backgroundElement" style={styles.panel}>
      <ChipGroup
        label={t('reader.font')}
        options={READER_FONTS.map((font) => ({ value: font, label: t(`reader.fonts.${font}`) }))}
        value={settings.font}
        onChange={(font) => update({ font })}
      />
      <ChipGroup
        label={t('reader.size')}
        options={FONT_SIZES.map((size, index) => ({ value: String(index), label: String(size) }))}
        value={String(settings.size)}
        onChange={(size) => update({ size: Number(size) })}
      />
      <ChipGroup
        label={t('reader.theme')}
        options={READER_THEMES.map((theme) => ({ value: theme, label: t(`reader.themes.${theme}`) }))}
        value={settings.theme}
        onChange={(theme) => update({ theme })}
      />
    </ThemedView>
  );
}

type BarButtonProps = {
  label: string;
  color: string;
  onPress: () => void;
  disabled?: boolean;
  selected?: boolean;
};

function BarButton({ label, color, onPress, disabled = false, selected = false }: BarButtonProps) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ disabled, selected }}
      disabled={disabled}
      onPress={onPress}
      style={({ pressed }) => [styles.barButton, (pressed || disabled) && styles.dimmed]}>
      <ThemedText type={selected ? 'smallBold' : 'small'} style={{ color }}>
        {label}
      </ThemedText>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  reader: {
    flex: 1,
  },
  text: {
    flex: 1,
  },
  message: {
    alignItems: 'center',
    gap: Spacing.three,
  },
  panel: {
    gap: Spacing.two,
    padding: Spacing.three,
  },
  bar: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingHorizontal: Spacing.two,
  },
  barButton: {
    minHeight: 48,
    paddingHorizontal: Spacing.three,
    justifyContent: 'center',
  },
  dimmed: {
    opacity: 0.4,
  },
});
