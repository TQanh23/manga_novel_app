import { Link, type Href } from 'expo-router';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';

import type { WorkCard } from '@/api/generated';
import { ThemedText } from '@/components/themed-text';
import { WorkCover } from '@/components/work-cover';
import { Fonts, Spacing } from '@/constants/theme';
import { useLayout } from '@/hooks/use-layout';

const COVER_WIDTH = 132;

export type ShelfItem = {
  key: string;
  work: Pick<WorkCard, 'id' | 'title' | 'type'>;
  /** What the tile is called for screen readers. */
  label: string;
  href: Href;
  /** The line under the title: an episode, a date. */
  caption: string;
};

/**
 * A row of covers. On a phone it scrolls sideways; on a wide window, where a
 * mouse has no swipe, it wraps onto more rows.
 */
export function Shelf({ items }: { items: ShelfItem[] }) {
  const { isWide } = useLayout();
  const tiles = items.map((item) => <ShelfTile key={item.key} item={item} />);
  if (isWide) {
    return <View style={styles.wrap}>{tiles}</View>;
  }
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.row}>
      {tiles}
    </ScrollView>
  );
}

function ShelfTile({ item }: { item: ShelfItem }) {
  return (
    <Link href={item.href} asChild>
      {/* A static style: on web, <Link asChild> drops a Pressable's style function. */}
      <Pressable accessibilityRole="link" accessibilityLabel={item.label} style={styles.tile}>
        <WorkCover work={item.work} width={COVER_WIDTH} />
        <ThemedText numberOfLines={2} style={styles.title}>
          {item.work.title}
        </ThemedText>
        <ThemedText type="small" themeColor="textSecondary" numberOfLines={1}>
          {item.caption}
        </ThemedText>
      </Pressable>
    </Link>
  );
}

const styles = StyleSheet.create({
  row: {
    gap: Spacing.three,
    paddingVertical: Spacing.one,
  },
  wrap: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.four,
  },
  tile: {
    width: COVER_WIDTH,
    gap: Spacing.one,
  },
  title: {
    fontFamily: Fonts.display,
    fontSize: 16,
    lineHeight: 21,
    marginTop: Spacing.one,
  },
});
