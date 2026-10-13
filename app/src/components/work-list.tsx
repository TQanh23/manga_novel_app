import type { ReactElement } from 'react';
import { ActivityIndicator, FlatList, StyleSheet, View } from 'react-native';
import { useTranslation } from 'react-i18next';

import type { PagedWorks } from '@/api/hooks';
import { Button, ErrorText } from '@/components/form';
import { EmptyState, ErrorState, LoadingState } from '@/components/state-views';
import { WorkCard } from '@/components/work-card';
import { Spacing } from '@/constants/theme';
import { errorMessageKey } from '@/i18n';

type WorkListProps = {
  works: PagedWorks;
  /** Shown above the list and scrolled with it: a title, the filters, a search box. */
  header?: ReactElement;
  /** What to say when the list has loaded and is empty. */
  emptyMessage: string;
};

/** A paged list of works with its loading, empty and error states. */
export function WorkList({ works, header, emptyMessage }: WorkListProps) {
  const { t } = useTranslation();
  const { items, error, isLoading, isLoadingMore, hasMore, loadMore, reload } = works;

  const body = () => {
    if (isLoading) {
      return <LoadingState />;
    }
    if (error && items.length === 0) {
      return <ErrorState code={error} onRetry={reload} />;
    }
    return <EmptyState message={emptyMessage} />;
  };

  const footer = () => {
    if (isLoadingMore) {
      return <ActivityIndicator accessibilityLabel={t('common.loading')} />;
    }
    if (items.length === 0 || !hasMore) {
      return null;
    }
    return (
      <View style={styles.footer}>
        {error ? <ErrorText>{t(errorMessageKey(error))}</ErrorText> : null}
        <Button label={t('catalogue.loadMore')} variant="secondary" onPress={loadMore} />
      </View>
    );
  };

  return (
    <FlatList
      data={items}
      keyExtractor={(work) => work.id}
      renderItem={({ item }) => <WorkCard work={item} />}
      ListHeaderComponent={header}
      ListEmptyComponent={body}
      ListFooterComponent={footer}
      // Scrolling near the end loads the next page; the button is there for
      // screens tall enough that the list never scrolls.
      onEndReached={error ? undefined : loadMore}
      onEndReachedThreshold={0.5}
      contentContainerStyle={styles.content}
      ItemSeparatorComponent={Separator}
      keyboardShouldPersistTaps="handled"
    />
  );
}

function Separator() {
  return <View style={styles.separator} />;
}

const styles = StyleSheet.create({
  content: {
    padding: Spacing.three,
    paddingBottom: Spacing.five,
  },
  separator: {
    height: Spacing.three,
  },
  footer: {
    alignItems: 'center',
    gap: Spacing.two,
    marginTop: Spacing.three,
  },
});
