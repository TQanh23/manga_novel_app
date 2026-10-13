import { StyleSheet, View } from 'react-native';
import { useTranslation } from 'react-i18next';

import type { GenreResponse, WorkSort, WorkStatus, WorkType } from '@/api/generated';
import { ChipGroup } from '@/components/chip';
import { Spacing } from '@/constants/theme';
import { genreName } from '@/i18n';

/** What the catalogue is narrowed to. `null` means no filter on that axis. */
export type Filters = {
  type: WorkType | null;
  status: WorkStatus | null;
  genre: string | null;
  sort: WorkSort;
};

export const NO_FILTERS: Filters = { type: null, status: null, genre: null, sort: 'newest' };

// Chips need a string for "no filter"; no genre, type or status is called this.
const ALL = '';

type FilterBarProps = {
  filters: Filters;
  /** The genres the API offers. Empty until they have loaded. */
  genres: readonly GenreResponse[];
  onChange: (filters: Filters) => void;
};

export function FilterBar({ filters, genres, onChange }: FilterBarProps) {
  const { t } = useTranslation();
  const all = { value: ALL, label: t('catalogue.all') };

  return (
    <View style={styles.bar}>
      <ChipGroup
        label={t('catalogue.filterType')}
        value={filters.type ?? ALL}
        options={[
          all,
          { value: 'novel', label: t('workType.novel') },
          { value: 'manga', label: t('workType.manga') },
        ]}
        onChange={(type) => onChange({ ...filters, type: type === ALL ? null : (type as WorkType) })}
      />
      <ChipGroup
        label={t('catalogue.filterStatus')}
        value={filters.status ?? ALL}
        options={[
          all,
          { value: 'ongoing', label: t('workStatus.ongoing') },
          { value: 'completed', label: t('workStatus.completed') },
        ]}
        onChange={(status) =>
          onChange({ ...filters, status: status === ALL ? null : (status as WorkStatus) })
        }
      />
      <ChipGroup
        label={t('catalogue.filterGenre')}
        value={filters.genre ?? ALL}
        options={[
          all,
          ...genres.map((genre) => ({ value: genre.slug, label: genreName(genre.slug, genre.name) })),
        ]}
        onChange={(genre) => onChange({ ...filters, genre: genre === ALL ? null : genre })}
      />
      <ChipGroup<WorkSort>
        label={t('catalogue.filterSort')}
        value={filters.sort}
        options={[
          { value: 'newest', label: t('catalogue.sort.newest') },
          { value: 'popular', label: t('catalogue.sort.popular') },
        ]}
        onChange={(sort) => onChange({ ...filters, sort })}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  bar: {
    gap: Spacing.three,
  },
});
