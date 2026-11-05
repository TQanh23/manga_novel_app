import { useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { useTranslation } from 'react-i18next';

import { catalogueListGenres, catalogueListWorks } from '@/api/generated';
import { PAGE_SIZE, useLoad, usePagedWorks } from '@/api/hooks';
import { FilterBar, type Filters, filtersFrom, type FilterParams } from '@/components/filter-bar';
import { Page } from '@/components/page';
import { WorkList } from '@/components/work-list';
import { Spacing } from '@/constants/theme';

/**
 * The catalogue: every work with something published, narrowed by the filters.
 * Links from the homepage open it with a filter already set (`/browse?genre=fantasy`).
 */
export default function BrowseScreen() {
  const { t } = useTranslation();
  const params = useLocalSearchParams<FilterParams>();
  const [filters, setFilters] = useState<Filters>(() => filtersFrom(params));

  const genres = useLoad('genres', () => catalogueListGenres());
  const works = usePagedWorks(JSON.stringify(filters), (offset) =>
    catalogueListWorks({
      query: {
        ...(filters.type && { type: filters.type }),
        ...(filters.status && { status: filters.status }),
        ...(filters.genre && { genre: filters.genre }),
        sort: filters.sort,
        limit: PAGE_SIZE,
        offset,
      },
    }),
  );

  return (
    <Page wide>
      <WorkList
        works={works}
        emptyMessage={t('catalogue.empty')}
        header={
          // The stack header carries the title.
          <View style={styles.header}>
            <FilterBar filters={filters} genres={genres.data ?? []} onChange={setFilters} />
          </View>
        }
      />
    </Page>
  );
}

const styles = StyleSheet.create({
  header: {
    gap: Spacing.three,
    marginBottom: Spacing.four,
  },
});
