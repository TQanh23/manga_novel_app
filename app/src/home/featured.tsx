import { useRouter } from 'expo-router';
import { StyleSheet, View } from 'react-native';
import { useTranslation } from 'react-i18next';

import { catalogueListEpisodes, type WorkCard } from '@/api/generated';
import { useLoad } from '@/api/hooks';
import { Chip } from '@/components/chip';
import { Button } from '@/components/form';
import { Flourish, OrnateFrame } from '@/components/ornaments';
import { ThemedText } from '@/components/themed-text';
import { WorkCover } from '@/components/work-cover';
import { Fonts, Spacing } from '@/constants/theme';
import { useLayout } from '@/hooks/use-layout';
import { genreName } from '@/i18n';

const SEPARATOR = ' · ';

/** The work at the top of the homepage: the most popular one, given room to show itself. */
export function Featured({ work }: { work: WorkCard }) {
  const { t } = useTranslation();
  const router = useRouter();
  const { isWide } = useLayout();
  // "Read now" goes straight to the first episode once the list is in; until then, to the work.
  const episodes = useLoad(`episodes:${work.id}`, () =>
    catalogueListEpisodes({ path: { work_id: work.id } }),
  );
  const first = episodes.data?.[0];
  const openWork = () => router.push({ pathname: '/works/[workId]', params: { workId: work.id } });
  const readNow = () =>
    first
      ? router.push({ pathname: '/read/[episodeId]', params: { episodeId: first.id } })
      : openWork();

  return (
    <OrnateFrame style={[styles.frame, isWide && styles.wide]}>
      <View style={isWide ? undefined : styles.coverRow}>
        <WorkCover work={work} width={isWide ? 220 : 168} />
      </View>
      <View style={styles.text}>
        <ThemedText type="eyebrow" themeColor="textSecondary">
          {[t('home.featured'), t(`workType.${work.type}`), t(`workStatus.${work.status}`)].join(
            SEPARATOR,
          )}
        </ThemedText>
        <ThemedText accessibilityRole="header" style={[styles.title, isWide && styles.titleWide]}>
          {work.title}
        </ThemedText>
        <ThemedText themeColor="textSecondary">
          {t('work.by', { author: work.author.display_name })}
        </ThemedText>
        {work.genres.length > 0 ? (
          <View style={styles.chips}>
            {work.genres.map((slug) => (
              <Chip key={slug} label={genreName(slug)} />
            ))}
          </View>
        ) : null}
        <Flourish />
        {work.synopsis ? (
          <ThemedText numberOfLines={isWide ? 4 : 3} style={styles.synopsis}>
            {work.synopsis}
          </ThemedText>
        ) : null}
        <View style={[styles.actions, isWide && styles.actionsWide]}>
          <Button label={t('home.readNow')} onPress={readNow} />
          <Button label={t('home.details')} variant="secondary" onPress={openWork} />
        </View>
      </View>
    </OrnateFrame>
  );
}

const styles = StyleSheet.create({
  frame: {
    padding: Spacing.four,
    gap: Spacing.four,
  },
  wide: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: Spacing.five,
  },
  coverRow: {
    alignItems: 'center',
  },
  text: {
    flex: 1,
    gap: Spacing.two,
  },
  title: {
    fontFamily: Fonts.display,
    fontSize: 30,
    lineHeight: 38,
  },
  titleWide: {
    fontSize: 38,
    lineHeight: 46,
  },
  chips: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.two,
  },
  synopsis: {
    fontStyle: 'italic',
  },
  actions: {
    gap: Spacing.two,
    marginTop: Spacing.two,
  },
  actionsWide: {
    flexDirection: 'row',
  },
});
