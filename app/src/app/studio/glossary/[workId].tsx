import { Stack, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { useTranslation } from 'react-i18next';

import { errorCode } from '@/api/client';
import {
  authorCreateGlossaryEntry,
  authorGetWork,
  authorListGlossary,
  authorUpdateGlossaryEntry,
  type GlossaryEntryResponse,
} from '@/api/generated';
import { useLoad } from '@/api/hooks';
import { Button } from '@/components/form';
import { Page } from '@/components/page';
import { EmptyState, ErrorState, LoadingState } from '@/components/state-views';
import { ThemedText } from '@/components/themed-text';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import {
  GLOSSARY_KINDS,
  type GlossaryEntryFields,
  GlossaryForm,
  glossaryChanges,
  glossaryValues,
} from '@/studio/glossary-form';

/** A work's glossary: its characters, places and terms (FR-NV-03). */
export default function GlossaryScreen() {
  const { t } = useTranslation();
  const { workId } = useLocalSearchParams<{ workId: string }>();
  const work = useLoad(`author-work:${workId}`, () => authorGetWork({ path: { work_id: workId } }));
  const entries = useLoad(`glossary:${workId}`, () =>
    authorListGlossary({ path: { work_id: workId } }),
  );
  // The entry being edited, a new one, or none: the list is shown.
  const [editing, setEditing] = useState<GlossaryEntryResponse | 'new' | null>(null);

  const save = async (fields: GlossaryEntryFields) => {
    const result =
      editing === 'new'
        ? await authorCreateGlossaryEntry({ path: { work_id: workId }, body: fields }).catch(
            () => null,
          )
        : editing
          ? await authorUpdateGlossaryEntry({
              path: { work_id: workId, entry_id: editing.id },
              body: glossaryChanges(editing, fields),
            }).catch(() => null)
          : null;
    if (!result?.data) {
      return result ? errorCode(result.error) : 'network_error';
    }
    setEditing(null);
    entries.reload();
    return null;
  };

  const body = () => {
    if (work.isLoading || entries.isLoading) {
      return <LoadingState />;
    }
    if (work.error === 'work_not_found') {
      return <EmptyState message={t('studio.notFound')} />;
    }
    if (work.error || entries.error || !work.data || !entries.data) {
      return (
        <ErrorState
          code={work.error ?? entries.error ?? 'unknown'}
          onRetry={() => {
            work.reload();
            entries.reload();
          }}
        />
      );
    }
    if (editing) {
      return (
        <GlossaryForm
          key={editing === 'new' ? 'new' : editing.id}
          mode={editing === 'new' ? 'create' : 'edit'}
          initial={glossaryValues(editing === 'new' ? null : editing)}
          language={work.data.language}
          onSubmit={save}
          onCancel={() => setEditing(null)}
        />
      );
    }
    return (
      <Entries entries={entries.data} onChoose={setEditing} />
    );
  };

  return (
    <Page>
      <Stack.Screen options={{ title: t('studio.glossary.title') }} />
      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        {body()}
      </ScrollView>
    </Page>
  );
}

function Entries({
  entries,
  onChoose,
}: {
  entries: GlossaryEntryResponse[];
  onChoose: (entry: GlossaryEntryResponse | 'new') => void;
}) {
  const { t } = useTranslation();
  return (
    <View style={styles.sections}>
      <ThemedText themeColor="textSecondary">{t('studio.glossary.hint')}</ThemedText>
      <Button label={t('studio.glossary.newEntry')} onPress={() => onChoose('new')} />
      {entries.length === 0 ? <EmptyState message={t('studio.glossary.empty')} /> : null}
      {GLOSSARY_KINDS.map((kind) => {
        const ofKind = entries.filter((entry) => entry.kind === kind);
        return ofKind.length === 0 ? null : (
          <View key={kind} style={styles.section}>
            <ThemedText type="smallBold" accessibilityRole="header">
              {t(`studio.glossary.section.${kind}`)}
            </ThemedText>
            {ofKind.map((entry) => (
              <EntryRow key={entry.id} entry={entry} onPress={() => onChoose(entry)} />
            ))}
          </View>
        );
      })}
    </View>
  );
}

function EntryRow({ entry, onPress }: { entry: GlossaryEntryResponse; onPress: () => void }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const facts = Object.keys(entry.attributes).length;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={entry.name}
      onPress={onPress}
      style={({ pressed }) => [
        styles.row,
        { backgroundColor: theme.backgroundElement },
        pressed && styles.pressed,
      ]}>
      <ThemedText style={styles.name}>{entry.name}</ThemedText>
      {entry.aliases.length > 0 ? (
        <ThemedText type="small">{entry.aliases.join(', ')}</ThemedText>
      ) : null}
      {facts > 0 ? (
        <ThemedText type="small" themeColor="textSecondary">
          {t('studio.glossary.facts', { count: facts })}
        </ThemedText>
      ) : null}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  content: {
    padding: Spacing.three,
    paddingBottom: Spacing.five,
  },
  sections: {
    gap: Spacing.four,
  },
  section: {
    gap: Spacing.two,
  },
  row: {
    borderRadius: Spacing.two,
    padding: Spacing.three,
    gap: Spacing.half,
  },
  name: {
    fontWeight: 700,
  },
  pressed: {
    opacity: 0.7,
  },
});
