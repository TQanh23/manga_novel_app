import { StyleSheet, View } from 'react-native';
import { useTranslation } from 'react-i18next';

import { catalogueListWorks, type WorkDetail } from '@/api/generated';
import { useLoad } from '@/api/hooks';
import { SectionHeader } from '@/components/section-header';
import { Loaded } from '@/home/loaded';
import { Shelf, type ShelfItem } from '@/home/shelf';
import { Spacing } from '@/constants/theme';
import { formatDate } from '@/i18n';

const SHOWN = 6;

/** Other works in this one's first genre. Left out when there are none. */
export function MoreLikeThis({ work }: { work: WorkDetail }) {
  const genre = work.genres[0];
  if (!genre) {
    return null;
  }
  return <Similar workId={work.id} genre={genre} />;
}

function Similar({ workId, genre }: { workId: string; genre: string }) {
  const { t } = useTranslation();
  // One more than shown, as this work is likely among them.
  const similar = useLoad(`similar:${genre}`, () =>
    catalogueListWorks({ query: { genre, sort: 'popular', limit: SHOWN + 1 } }),
  );
  const others = (similar.data?.items ?? []).filter((item) => item.id !== workId).slice(0, SHOWN);
  if (!similar.isLoading && !similar.error && others.length === 0) {
    return null;
  }
  return (
    <View style={styles.section}>
      <SectionHeader
        title={t('work.moreLikeThis')}
        seeAll={{ pathname: '/browse', params: { genre } }}
      />
      <Loaded load={similar} placeholderHeight={220}>
        {() => (
          <Shelf
            items={others.map(
              (item): ShelfItem => ({
                key: item.id,
                work: item,
                label: item.title,
                href: { pathname: '/works/[workId]', params: { workId: item.id } },
                caption: t('catalogue.updated', { date: formatDate(item.last_published_at) }),
              }),
            )}
          />
        )}
      </Loaded>
    </View>
  );
}

const styles = StyleSheet.create({
  section: {
    gap: Spacing.three,
  },
});
