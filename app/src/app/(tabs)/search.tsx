import { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { useTranslation } from 'react-i18next';

import { catalogueSearchWorks } from '@/api/generated';
import { PAGE_SIZE, usePagedWorks } from '@/api/hooks';
import { TextField } from '@/components/form';
import { Page } from '@/components/page';
import { ThemedText } from '@/components/themed-text';
import { WorkList } from '@/components/work-list';
import { Spacing } from '@/constants/theme';
import { useDebounced } from '@/hooks/use-debounced';

const DEBOUNCE_MS = 300;

/** Search by title, author or tag. The API matches with or without diacritics. */
export default function SearchScreen() {
  const { t } = useTranslation();
  const [text, setText] = useState('');
  // Sent as typed: the API does the normalising, so nothing is stripped here.
  const query = useDebounced(text.trim(), DEBOUNCE_MS);

  const works = usePagedWorks(query ? `search:${query}` : null, (offset) =>
    catalogueSearchWorks({ query: { q: query, limit: PAGE_SIZE, offset } }),
  );

  return (
    <Page>
      <WorkList
        works={works}
        emptyMessage={query ? t('search.empty', { query }) : t('search.hint')}
        header={
          <View style={styles.header}>
            <ThemedText type="subtitle">{t('search.title')}</ThemedText>
            <TextField
              label={t('search.title')}
              placeholder={t('search.placeholder')}
              value={text}
              onChangeText={setText}
              autoCapitalize="none"
              autoCorrect={false}
              inputMode="search"
              returnKeyType="search"
            />
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
