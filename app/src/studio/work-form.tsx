import { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { useTranslation } from 'react-i18next';

import {
  authorListWufPresets,
  catalogueListGenres,
  type ContentLanguage,
  type WorkResponse,
  type WorkStatus,
  type WorkType,
  type WorkUpdate,
} from '@/api/generated';
import { useLoad } from '@/api/hooks';
import { ChipGroup, ChipSet } from '@/components/chip';
import { Button, ErrorText, TextField } from '@/components/form';
import { ErrorState, LoadingState } from '@/components/state-views';
import { ThemedText } from '@/components/themed-text';
import { Spacing } from '@/constants/theme';
import { errorMessageKey, formatPeriod, genreName } from '@/i18n';

// The API's limits, so the form says no before the request does.
const MAX_TITLE = 200;
const MAX_SYNOPSIS = 5_000;
const MAX_GENRES = 3;
const MAX_TAGS = 10;
const MAX_TAG_LENGTH = 30;
// Lists are split on the comma of each content language, not on spaces.
const LIST_SEPARATORS = /[,，、]/;
const LANGUAGES: readonly ContentLanguage[] = ['ko', 'ja', 'en', 'vi'];
// Chips need a string for "no wait-until-free"; no preset id is empty.
const OFF = '';

export type WorkFormValues = {
  type: WorkType;
  title: string;
  synopsis: string;
  language: ContentLanguage;
  status: WorkStatus;
  wufPresetId: string | null;
  genres: string[];
  tags: string[];
};

/** What the form starts with for a work that already exists. */
export function formValues(work: WorkResponse): WorkFormValues {
  return {
    type: work.type,
    title: work.title,
    synopsis: work.synopsis,
    language: work.language,
    status: work.status,
    wufPresetId: work.wuf_preset_id,
    genres: work.genres,
    tags: work.tags,
  };
}

function sameSet(a: readonly string[], b: readonly string[]): boolean {
  return a.length === b.length && a.every((item) => b.includes(item));
}

/**
 * What the author changed, and nothing else. The API checks every field it is
 * sent, so resending a wait-until-free period that is no longer offered would
 * refuse a change to the title.
 */
export function changedFields(before: WorkFormValues, after: WorkFormValues): WorkUpdate {
  const changes: WorkUpdate = {};
  if (after.title !== before.title) changes.title = after.title;
  if (after.synopsis !== before.synopsis) changes.synopsis = after.synopsis;
  if (after.language !== before.language) changes.language = after.language;
  if (after.status !== before.status) changes.status = after.status;
  if (after.wufPresetId !== before.wufPresetId) changes.wuf_preset_id = after.wufPresetId;
  if (!sameSet(after.genres, before.genres)) changes.genres = after.genres;
  if (!sameSet(after.tags, before.tags)) changes.tags = after.tags;
  return changes;
}

/** The items of a list the author typed (tags, other names), each once, in the order typed. */
export function parseList(text: string): string[] {
  const items = text
    .split(LIST_SEPARATORS)
    .map((item) => item.trim())
    .filter((item) => item.length > 0);
  return [...new Set(items)];
}

type WorkFormProps = {
  initial: WorkFormValues;
  /** A new work picks its format; an existing one has a status instead. */
  mode: 'create' | 'edit';
  /** Resolves to an API error code, or null when it was saved. */
  onSubmit: (values: WorkFormValues) => Promise<string | null>;
};

/** A work's details: what readers see on its page, and its wait-until-free period. */
export function WorkForm({ initial, mode, onSubmit }: WorkFormProps) {
  const { t } = useTranslation();
  const genres = useLoad('genres', () => catalogueListGenres());
  const presets = useLoad('wuf-presets', () => authorListWufPresets());

  const [values, setValues] = useState(initial);
  const [tagText, setTagText] = useState(initial.tags.join(', '));
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  if (genres.isLoading || presets.isLoading) {
    return <LoadingState />;
  }
  if (!genres.data || !presets.data) {
    return (
      <ErrorState
        code={genres.error ?? presets.error ?? 'unknown'}
        onRetry={() => {
          genres.reload();
          presets.reload();
        }}
      />
    );
  }

  const change = (next: Partial<WorkFormValues>) => {
    setValues((current) => ({ ...current, ...next }));
    setSaved(false);
  };

  const submit = async () => {
    const tags = parseList(tagText);
    const invalid = !values.title.trim()
      ? t('studio.form.titleRequired')
      : tags.length > MAX_TAGS
        ? t('studio.form.tooManyTags')
        : // Counted in characters, as the API counts them, not in UTF-16 units.
          tags.some((tag) => Array.from(tag).length > MAX_TAG_LENGTH)
          ? t('studio.form.tagTooLong')
          : null;
    setSaved(false);
    setProblem(invalid);
    if (invalid) {
      return;
    }
    setBusy(true);
    const failure = await onSubmit({
      ...values,
      title: values.title.trim(),
      tags,
    });
    setBusy(false);
    if (failure) {
      setProblem(t(errorMessageKey(failure)));
    } else {
      setSaved(mode === 'edit');
    }
  };

  const periods = [...presets.data].sort((a, b) => a.seconds - b.seconds);

  return (
    <View style={styles.form}>
      {mode === 'create' ? (
        <View style={styles.field}>
          <ChipGroup<WorkType>
            label={t('studio.form.type')}
            value={values.type}
            options={[
              { value: 'novel', label: t('workType.novel') },
              { value: 'manga', label: t('workType.manga') },
            ]}
            onChange={(type) => change({ type })}
          />
          <ThemedText type="small" themeColor="textSecondary">
            {t('studio.form.typeHint')}
          </ThemedText>
        </View>
      ) : (
        <ChipGroup<WorkStatus>
          label={t('studio.form.status')}
          value={values.status}
          options={[
            { value: 'ongoing', label: t('workStatus.ongoing') },
            { value: 'completed', label: t('workStatus.completed') },
          ]}
          onChange={(status) => change({ status })}
        />
      )}

      <TextField
        label={t('studio.form.title')}
        value={values.title}
        maxLength={MAX_TITLE}
        onChangeText={(title) => change({ title })}
      />
      <TextField
        label={t('studio.form.synopsis')}
        value={values.synopsis}
        maxLength={MAX_SYNOPSIS}
        multiline
        style={styles.synopsis}
        onChangeText={(synopsis) => change({ synopsis })}
      />

      <ChipGroup<ContentLanguage>
        label={t('studio.form.language')}
        value={values.language}
        options={LANGUAGES.map((language) => ({
          value: language,
          label: t(`contentLanguage.${language}`),
        }))}
        onChange={(language) => change({ language })}
      />

      <ChipSet
        label={t('studio.form.genres')}
        values={values.genres}
        max={MAX_GENRES}
        options={genres.data.map((genre) => ({
          value: genre.slug,
          label: genreName(genre.slug, genre.name),
        }))}
        onChange={(chosen) => change({ genres: chosen })}
      />
      <TextField
        label={t('studio.form.tags')}
        hint={t('studio.form.tagsHint')}
        value={tagText}
        onChangeText={(text) => {
          setTagText(text);
          setSaved(false);
        }}
      />

      <View style={styles.field}>
        <ChipGroup
          label={t('studio.form.wuf')}
          value={values.wufPresetId ?? OFF}
          options={[
            { value: OFF, label: t('studio.form.wufOff') },
            ...periods.map((preset) => ({
              value: preset.id,
              label: formatPeriod(preset.seconds),
            })),
          ]}
          onChange={(id) => change({ wufPresetId: id === OFF ? null : id })}
        />
        <ThemedText type="small" themeColor="textSecondary">
          {t('studio.form.wufHint')}
        </ThemedText>
      </View>

      {problem ? <ErrorText>{problem}</ErrorText> : null}
      {saved ? <ThemedText type="small">{t('studio.form.saved')}</ThemedText> : null}
      <Button
        label={mode === 'create' ? t('studio.form.create') : t('studio.form.save')}
        busy={busy}
        onPress={() => void submit()}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  form: {
    gap: Spacing.four,
  },
  field: {
    gap: Spacing.one,
  },
  synopsis: {
    minHeight: 120,
    textAlignVertical: 'top',
  },
});
