import { useRouter } from 'expo-router';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { useTranslation } from 'react-i18next';

import { catalogueListEpisodes } from '@/api/generated';
import { useLoad } from '@/api/hooks';
import { OrnateFrame, SectionTitle } from '@/components/ornaments';
import { ErrorState, LoadingState } from '@/components/state-views';
import { ThemedText } from '@/components/themed-text';
import { Fonts, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

type ContentsSheetProps = {
  workId: string;
  workTitle: string | null;
  currentId: string;
};

/** The work's episodes, the current one marked; choosing one opens it in place. */
export function ContentsSheet({ workId, workTitle, currentId }: ContentsSheetProps) {
  const { t } = useTranslation();
  const router = useRouter();
  const theme = useTheme();
  const episodes = useLoad(`episodes:${workId}`, () => catalogueListEpisodes({ path: { work_id: workId } }));

  const body = () => {
    if (episodes.isLoading) {
      return <LoadingState />;
    }
    if (episodes.error || !episodes.data) {
      return <ErrorState code={episodes.error ?? 'unknown'} onRetry={episodes.reload} />;
    }
    return episodes.data.map((episode) => {
      const current = episode.id === currentId;
      return (
        <Pressable
          key={episode.id}
          accessibilityRole="button"
          accessibilityLabel={t('reader.heading', { number: episode.number, title: episode.title })}
          accessibilityState={{ selected: current }}
          onPress={() =>
            current || router.replace({ pathname: '/read/[episodeId]', params: { episodeId: episode.id } })
          }
          style={[styles.row, { borderBottomColor: theme.border }, current && { backgroundColor: theme.backgroundSelected }]}>
          <ThemedText style={[styles.number, { color: theme.ornament }]}>{episode.number}</ThemedText>
          <ThemedText numberOfLines={1} style={[styles.title, current && { color: theme.accent }]}>
            {episode.title}
          </ThemedText>
        </Pressable>
      );
    });
  };

  return (
    <OrnateFrame style={styles.frame} frameStyle={styles.sheet}>
      <SectionTitle eyebrow={workTitle ?? undefined} title={t('reader.contents')} />
      <ScrollView style={styles.list}>
        <View>{body()}</View>
      </ScrollView>
    </OrnateFrame>
  );
}

const styles = StyleSheet.create({
  sheet: {
    margin: Spacing.two,
  },
  frame: {
    padding: Spacing.three,
    gap: Spacing.two,
  },
  list: {
    maxHeight: 320,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.three,
    paddingVertical: Spacing.two,
    paddingHorizontal: Spacing.two,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  number: {
    fontFamily: Fonts.display,
    fontSize: 20,
    minWidth: 28,
    textAlign: 'center',
  },
  title: {
    flex: 1,
  },
});
