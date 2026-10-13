import { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { useTranslation } from 'react-i18next';

import { catalogueListGenres, catalogueListWorks } from '@/api/generated';
import { PAGE_SIZE, useLoad, usePagedWorks } from '@/api/hooks';
import { FilterBar, type Filters, NO_FILTERS } from '@/components/filter-bar';
import { Page } from '@/components/page';
import { ThemedText } from '@/components/themed-text';
import { WorkList } from '@/components/work-list';
import { Spacing } from '@/constants/theme';

/** The catalogue: every work with something published, narrowed by the filters. */
export default function HomeScreen() {
  const { t } = useTranslation();
  const [filters, setFilters] = useState<Filters>(NO_FILTERS);

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
    <Page>
      <WorkList
        works={works}
        emptyMessage={t('catalogue.empty')}
        header={
          <View style={styles.header}>
            <ThemedText type="subtitle">{t('catalogue.title')}</ThemedText>
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
