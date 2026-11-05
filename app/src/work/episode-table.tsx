import { Link } from 'expo-router';
import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { useTranslation } from 'react-i18next';

import type { EpisodeSummary } from '@/api/generated';
import { SectionHeader } from '@/components/section-header';
import { ThemedText } from '@/components/themed-text';
import { Fonts, Radius, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { formatDate } from '@/i18n';

const SEPARATOR = ' · ';

type EpisodeTableProps = {
  episodes: EpisodeSummary[];
  /** The episode the reader is on, marked in the list. */
  readingId: string | undefined;
};

/** A work's published episodes, oldest or newest first; each row opens the reader. */
export function EpisodeTable({ episodes, readingId }: EpisodeTableProps) {
  const { t } = useTranslation();
  const [newestFirst, setNewestFirst] = useState(false);
  const ordered = newestFirst ? [...episodes].reverse() : episodes;

  return (
    <View style={styles.section}>
      <SectionHeader
        title={[t('work.episodes'), t('catalogue.episodeCount', { count: episodes.length })].join(
          SEPARATOR,
        )}
        action={
          episodes.length > 1 ? (
            <Pressable accessibilityRole="button" onPress={() => setNewestFirst((shown) => !shown)}>
              <ThemedText type="linkPrimary">
                {newestFirst ? t('work.oldestFirst') : t('work.newestFirst')}
              </ThemedText>
            </Pressable>
          ) : null
        }
      />
      <View>
        {ordered.map((episode) => (
          <EpisodeRow key={episode.id} episode={episode} reading={episode.id === readingId} />
        ))}
      </View>
    </View>
  );
}

function EpisodeRow({ episode, reading }: { episode: EpisodeSummary; reading: boolean }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const price =
    episode.price_coins === 0 ? t('work.free') : t('work.coins', { count: episode.price_coins });
  const terms = episode.wuf_eligible ? [price, t('work.waitUntilFree')] : [price];

  return (
    <Link href={{ pathname: '/read/[episodeId]', params: { episodeId: episode.id } }} asChild>
      <Pressable
        accessibilityRole="link"
        accessibilityLabel={episode.title}
        // One flat style: <Link asChild> refuses an array, and drops a function on web.
        style={StyleSheet.flatten([
          styles.row,
          { borderBottomColor: theme.border },
          reading && { backgroundColor: theme.surface, borderColor: theme.accent, borderWidth: 1 },
        ])}>
        <Text
          accessibilityElementsHidden
          importantForAccessibility="no"
          style={[styles.numeral, { color: theme.ornament }]}>
          {episode.number}
        </Text>
        <View style={styles.text}>
          <ThemedText type="eyebrow" themeColor="textSecondary">
            {[t('work.episodeNumber', { number: episode.number }), formatDate(episode.publish_at)].join(
              SEPARATOR,
            )}
          </ThemedText>
          <ThemedText style={styles.title}>{episode.title}</ThemedText>
        </View>
        <View style={styles.badges}>
          {reading ? (
            <View style={[styles.badge, { backgroundColor: theme.accent }]}>
              <ThemedText type="eyebrow" style={[styles.badgeText, { color: theme.onAccent }]}>
                {t('work.reading')}
              </ThemedText>
            </View>
          ) : null}
          <View style={[styles.badge, { backgroundColor: theme.highlight }]}>
            <ThemedText type="smallBold" themeColor="textSecondary" style={styles.badgeText}>
              {terms.join(SEPARATOR)}
            </ThemedText>
          </View>
        </View>
      </Pressable>
    </Link>
  );
}

const styles = StyleSheet.create({
  section: {
    gap: Spacing.two,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.three,
    paddingVertical: Spacing.three,
    paddingHorizontal: Spacing.two,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderRadius: Radius.md,
  },
  numeral: {
    fontFamily: Fonts.display,
    fontSize: 28,
    lineHeight: 34,
    minWidth: 40,
    textAlign: 'center',
  },
  text: {
    flex: 1,
    gap: Spacing.half,
  },
  title: {
    fontFamily: Fonts.display,
    fontSize: 18,
    lineHeight: 24,
  },
  badges: {
    alignItems: 'flex-end',
    gap: Spacing.one,
  },
  badge: {
    borderRadius: Radius.pill,
    paddingHorizontal: Spacing.two + Spacing.half,
    paddingVertical: Spacing.half,
  },
  badgeText: {
    fontSize: 12,
    lineHeight: 16,
  },
});
