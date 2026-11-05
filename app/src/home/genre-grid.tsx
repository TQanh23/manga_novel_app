import { Link } from 'expo-router';
import { Pressable, StyleSheet, View } from 'react-native';

import type { GenreResponse } from '@/api/generated';
import { OrnateFrame } from '@/components/ornaments';
import { ThemedText } from '@/components/themed-text';
import { Fonts, Spacing } from '@/constants/theme';
import { useLayout } from '@/hooks/use-layout';
import { genreName } from '@/i18n';

const GUTTER = Spacing.two - Spacing.half;

/** Every genre as a framed tile; a tile opens the catalogue filtered to it. */
export function GenreGrid({ genres }: { genres: GenreResponse[] }) {
  const { isWide, columns } = useLayout();
  // Two tiles a row on a phone, three on a tablet, four on a wide window.
  const perRow = isWide ? 4 : columns + 1;
  return (
    <View style={styles.grid}>
      {genres.map((genre) => {
        const name = genreName(genre.slug, genre.name);
        return (
          <Link key={genre.slug} href={{ pathname: '/browse', params: { genre: genre.slug } }} asChild>
            <Pressable
              accessibilityRole="link"
              accessibilityLabel={name}
              // One flat style: <Link asChild> refuses an array, and drops a function on web.
              style={StyleSheet.flatten([styles.cell, { width: `${100 / perRow}%` }])}>
              <OrnateFrame style={styles.tile}>
                <ThemedText numberOfLines={1} style={styles.name}>
                  {name}
                </ThemedText>
              </OrnateFrame>
            </Pressable>
          </Link>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  // Gutters as padding inside each cell, taken back by the grid's margin, so
  // percentage widths add up and a short last row keeps the same tile size.
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginHorizontal: -GUTTER,
  },
  cell: {
    paddingHorizontal: GUTTER,
    paddingBottom: GUTTER * 2,
  },
  tile: {
    paddingVertical: Spacing.four,
    paddingHorizontal: Spacing.three,
    alignItems: 'center',
  },
  name: {
    fontFamily: Fonts.display,
    fontSize: 18,
    lineHeight: 24,
    textAlign: 'center',
  },
});
