import { Stack, useLocalSearchParams, useRouter } from 'expo-router';
import { useState } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import { useTranslation } from 'react-i18next';

import { errorCode } from '@/api/client';
import { authorGetWork, authorUpdateWork, type WorkResponse } from '@/api/generated';
import { useLoad } from '@/api/hooks';
import { Button } from '@/components/form';
import { Page } from '@/components/page';
import { EmptyState, ErrorState, LoadingState } from '@/components/state-views';
import { ThemedText } from '@/components/themed-text';
import { Spacing } from '@/constants/theme';
import { EpisodeList } from '@/studio/episode-list';
import { changedFields, formValues, WorkForm, type WorkFormValues } from '@/studio/work-form';

/** A work in the studio: its episodes, then its details (FR-NV-01). */
export default function EditWorkScreen() {
  const { t } = useTranslation();
  const router = useRouter();
  const { workId } = useLocalSearchParams<{ workId: string }>();
  const work = useLoad(`author-work:${workId}`, () => authorGetWork({ path: { work_id: workId } }));
  // The work as last saved here; the form compares against it.
  const [saved, setSaved] = useState<WorkResponse | null>(null);
  const current = saved ?? work.data;

  const save = async (values: WorkFormValues) => {
    if (!current) {
      return 'unknown';
    }
    const body = changedFields(formValues(current), values);
    if (Object.keys(body).length === 0) {
      return null;
    }
    const result = await authorUpdateWork({
      path: { work_id: workId },
      body,
    }).catch(() => null);
    if (!result?.data) {
      return result ? errorCode(result.error) : 'network_error';
    }
    setSaved(result.data);
    return null;
  };

  const body = () => {
    if (work.isLoading) {
      return <LoadingState />;
    }
    // Another author's work answers exactly like one that does not exist.
    if (work.error === 'work_not_found') {
      return <EmptyState message={t('studio.notFound')} />;
    }
    if (work.error || !current) {
      return <ErrorState code={work.error ?? 'unknown'} onRetry={work.reload} />;
    }
    return (
      <View style={styles.sections}>
        <EpisodeList workId={workId} />
        <View style={styles.section}>
          <ThemedText type="smallBold" accessibilityRole="header">
            {t('studio.glossary.title')}
          </ThemedText>
          <ThemedText type="small" themeColor="textSecondary">
            {t('studio.glossary.hint')}
          </ThemedText>
          <Button
            label={t('studio.glossary.open')}
            variant="secondary"
            onPress={() =>
              router.push({ pathname: '/studio/glossary/[workId]', params: { workId } })
            }
          />
        </View>
        <View style={styles.section}>
          <ThemedText type="smallBold" accessibilityRole="header">
            {t('studio.details')}
          </ThemedText>
          <WorkForm mode="edit" initial={formValues(current)} onSubmit={save} />
        </View>
      </View>
    );
  };

  return (
    <Page>
      <Stack.Screen options={{ title: current?.title ?? t('studio.editTitle') }} />
      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        {body()}
      </ScrollView>
    </Page>
  );
}

const styles = StyleSheet.create({
  content: {
    padding: Spacing.three,
    paddingBottom: Spacing.five,
  },
  sections: {
    gap: Spacing.five,
  },
  section: {
    gap: Spacing.three,
  },
});
