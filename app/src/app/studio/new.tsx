import { Stack, useRouter } from 'expo-router';
import { ScrollView, StyleSheet } from 'react-native';
import { useTranslation } from 'react-i18next';

import { errorCode } from '@/api/client';
import { authorCreateWork } from '@/api/generated';
import { Page } from '@/components/page';
import { Spacing } from '@/constants/theme';
import { currentLocale } from '@/i18n';
import { WorkForm, type WorkFormValues } from '@/studio/work-form';

/** Start a new work (FR-NV-01). Its episodes are added once it exists. */
export default function NewWorkScreen() {
  const { t } = useTranslation();
  const router = useRouter();

  // Most authors write in the language they use the app in.
  const initial: WorkFormValues = {
    type: 'novel',
    title: '',
    synopsis: '',
    language: currentLocale(),
    status: 'ongoing',
    wufPresetId: null,
    genres: [],
    tags: [],
  };

  const create = async (values: WorkFormValues) => {
    const result = await authorCreateWork({
      body: {
        type: values.type,
        title: values.title,
        synopsis: values.synopsis,
        language: values.language,
        wuf_preset_id: values.wufPresetId,
        genres: values.genres,
        tags: values.tags,
      },
    }).catch(() => null);
    if (!result?.data) {
      return result ? errorCode(result.error) : 'network_error';
    }
    // The new work's page replaces this form, so going back leads to the list.
    router.replace({
      pathname: '/studio/[workId]',
      params: { workId: result.data.id },
    });
    return null;
  };

  return (
    <Page>
      <Stack.Screen options={{ title: t('studio.newTitle') }} />
      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        <WorkForm mode="create" initial={initial} onSubmit={create} />
      </ScrollView>
    </Page>
  );
}

const styles = StyleSheet.create({
  content: {
    padding: Spacing.three,
    paddingBottom: Spacing.five,
  },
});
