import { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { useTranslation } from 'react-i18next';

import type {
  ContentLanguage,
  GlossaryEntryResponse,
  GlossaryEntryUpdate,
  GlossaryKind,
} from '@/api/generated';
import { ChipGroup } from '@/components/chip';
import { Button, ErrorText, TextField } from '@/components/form';
import { ThemedText } from '@/components/themed-text';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { errorMessageKey } from '@/i18n';

import { parseList } from './work-form';

// The API's limits, so the form says no before the request does.
const MAX_NAME = 100;
const MAX_ALIASES = 20;
const MAX_ATTRIBUTES = 30;
const MAX_ATTRIBUTE_KEY = 50;
const LANGUAGES: readonly ContentLanguage[] = ['ko', 'ja', 'en', 'vi'];
export const GLOSSARY_KINDS: readonly GlossaryKind[] = ['character', 'place', 'term'];
// A value typed as a plain number is kept as one, like "tuổi" = 17 in the seed.
const NUMBER = /^-?(0|[1-9]\d*)(\.\d+)?$/;

/** One fact of an entry as the form edits it. `original` is the value the API holds. */
export type FactRow = { id: number; key: string; value: string; original?: unknown };

export type GlossaryFormValues = {
  kind: GlossaryKind;
  name: string;
  /** The other names as typed, separated by commas. */
  aliases: string;
  translations: Partial<Record<ContentLanguage, string>>;
  facts: FactRow[];
};

/** The entry the form sends, ready for the API. */
export type GlossaryEntryFields = {
  kind: GlossaryKind;
  name: string;
  aliases: string[];
  attributes: Record<string, unknown>;
  translations: Partial<Record<ContentLanguage, string>>;
};

/** How a value the API holds is shown: text as it is, anything else as JSON. */
export function shownValue(value: unknown): string {
  return typeof value === 'string' ? value : JSON.stringify(value);
}

/** What the form starts with: an existing entry, or an empty one of `kind`. */
export function glossaryValues(
  entry: GlossaryEntryResponse | null,
  kind: GlossaryKind = 'character',
): GlossaryFormValues {
  if (!entry) {
    return { kind, name: '', aliases: '', translations: {}, facts: [] };
  }
  return {
    kind: entry.kind,
    name: entry.name,
    aliases: entry.aliases.join(', '),
    translations: entry.translations as Partial<Record<ContentLanguage, string>>,
    facts: Object.entries(entry.attributes).map(([key, value], index) => ({
      id: index,
      key,
      value: shownValue(value),
      original: value,
    })),
  };
}

/** A fact's value as it goes to the API. One the author did not touch keeps its type. */
export function factValue(row: FactRow): unknown {
  if (row.original !== undefined && row.value === shownValue(row.original)) {
    return row.original;
  }
  const value = row.value.trim();
  return NUMBER.test(value) ? Number(value) : value;
}

const characters = (text: string) => Array.from(text).length;

/** What can be wrong with an entry before it is sent, by its message in `studio.glossary.form`. */
export type GlossaryProblem =
  | 'nameRequired'
  | 'tooManyAliases'
  | 'aliasTooLong'
  | 'attributeKeyRequired'
  | 'attributeKeyTooLong'
  | 'duplicateKey'
  | 'tooManyAttributes';

/**
 * The entry as the API takes it, or what is wrong with it. Lengths are
 * counted in characters, as the API counts them.
 */
export function glossaryFields(
  values: GlossaryFormValues,
): { fields: GlossaryEntryFields } | { problem: GlossaryProblem; key?: string } {
  const name = values.name.trim();
  if (!name) {
    return { problem: 'nameRequired' };
  }
  const aliases = parseList(values.aliases);
  if (aliases.length > MAX_ALIASES) {
    return { problem: 'tooManyAliases' };
  }
  if (aliases.some((alias) => characters(alias) > MAX_NAME)) {
    return { problem: 'aliasTooLong' };
  }

  const attributes: Record<string, unknown> = {};
  for (const row of values.facts) {
    const key = row.key.trim();
    if (!key && !row.value.trim()) {
      continue;
    }
    if (!key) {
      return { problem: 'attributeKeyRequired' };
    }
    if (characters(key) > MAX_ATTRIBUTE_KEY) {
      return { problem: 'attributeKeyTooLong' };
    }
    if (key in attributes) {
      return { problem: 'duplicateKey', key };
    }
    attributes[key] = factValue(row);
  }
  if (Object.keys(attributes).length > MAX_ATTRIBUTES) {
    return { problem: 'tooManyAttributes' };
  }

  const translations: Partial<Record<ContentLanguage, string>> = {};
  for (const language of LANGUAGES) {
    const text = values.translations[language]?.trim();
    if (text) {
      translations[language] = text;
    }
  }
  return { fields: { kind: values.kind, name, aliases, attributes, translations } };
}

const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);

function sameRecord(a: Record<string, unknown>, b: Record<string, unknown>): boolean {
  const keys = Object.keys(a);
  return (
    keys.length === Object.keys(b).length && keys.every((key) => key in b && same(a[key], b[key]))
  );
}

/** What changed in an existing entry, and nothing else. */
export function glossaryChanges(
  entry: GlossaryEntryResponse,
  fields: GlossaryEntryFields,
): GlossaryEntryUpdate {
  const changes: GlossaryEntryUpdate = {};
  if (fields.kind !== entry.kind) changes.kind = fields.kind;
  if (fields.name !== entry.name) changes.name = fields.name;
  if (!same(fields.aliases, entry.aliases)) changes.aliases = fields.aliases;
  if (!sameRecord(fields.attributes, entry.attributes)) changes.attributes = fields.attributes;
  if (!sameRecord(fields.translations, entry.translations)) {
    changes.translations = fields.translations;
  }
  return changes;
}

type GlossaryFormProps = {
  initial: GlossaryFormValues;
  /** The work's own language: its name there is the entry's name, so it has no field. */
  language: ContentLanguage;
  mode: 'create' | 'edit';
  /** Resolves to an API error code, or null when it was saved. */
  onSubmit: (fields: GlossaryEntryFields) => Promise<string | null>;
  onCancel: () => void;
  /** For an entry that exists. Resolves to an API error code, or null when it was deleted. */
  onDelete?: () => Promise<string | null>;
};

/** A character, place or term: its names in each language, and what is true of it (FR-NV-03). */
export function GlossaryForm({
  initial,
  language,
  mode,
  onSubmit,
  onCancel,
  onDelete,
}: GlossaryFormProps) {
  const { t } = useTranslation();
  const [values, setValues] = useState(initial);
  const [nextId, setNextId] = useState(initial.facts.length);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  const change = (next: Partial<GlossaryFormValues>) =>
    setValues((current) => ({ ...current, ...next }));
  const changeFact = (id: number, next: Partial<FactRow>) =>
    change({ facts: values.facts.map((row) => (row.id === id ? { ...row, ...next } : row)) });

  const submit = async () => {
    const result = glossaryFields(values);
    if ('problem' in result) {
      setProblem(t(`studio.glossary.form.${result.problem}`, { key: result.key }));
      return;
    }
    setProblem(null);
    setBusy(true);
    const failure = await onSubmit(result.fields);
    setBusy(false);
    if (failure) {
      setProblem(t(errorMessageKey(failure)));
    }
  };

  return (
    <View style={styles.form}>
      <ChipGroup<GlossaryKind>
        label={t('studio.glossary.form.kind')}
        value={values.kind}
        options={GLOSSARY_KINDS.map((kind) => ({
          value: kind,
          label: t(`studio.glossary.kind.${kind}`),
        }))}
        onChange={(kind) => change({ kind })}
      />
      <TextField
        label={t('studio.glossary.form.name')}
        value={values.name}
        maxLength={MAX_NAME}
        onChangeText={(name) => change({ name })}
      />
      <TextField
        label={t('studio.glossary.form.aliases')}
        hint={t('studio.glossary.form.aliasesHint')}
        value={values.aliases}
        onChangeText={(aliases) => change({ aliases })}
      />

      <View style={styles.group}>
        <ThemedText type="smallBold">{t('studio.glossary.form.translations')}</ThemedText>
        {LANGUAGES.filter((other) => other !== language).map((other) => (
          <TextField
            key={other}
            label={t(`contentLanguage.${other}`)}
            value={values.translations[other] ?? ''}
            maxLength={MAX_NAME}
            onChangeText={(text) =>
              change({ translations: { ...values.translations, [other]: text } })
            }
          />
        ))}
      </View>

      <View style={styles.group}>
        <ThemedText type="smallBold">{t('studio.glossary.form.attributes')}</ThemedText>
        <ThemedText type="small" themeColor="textSecondary">
          {t('studio.glossary.form.attributesHint')}
        </ThemedText>
        {values.facts.map((row, index) => (
          <FactFields
            key={row.id}
            row={row}
            number={index + 1}
            onChange={(next) => changeFact(row.id, next)}
            onRemove={() => change({ facts: values.facts.filter((other) => other.id !== row.id) })}
          />
        ))}
        {values.facts.length < MAX_ATTRIBUTES ? (
          <Button
            label={t('studio.glossary.form.addAttribute')}
            variant="secondary"
            onPress={() => {
              change({ facts: [...values.facts, { id: nextId, key: '', value: '' }] });
              setNextId((id) => id + 1);
            }}
          />
        ) : null}
      </View>

      {problem ? <ErrorText>{problem}</ErrorText> : null}
      <Button
        label={mode === 'create' ? t('studio.glossary.form.create') : t('studio.glossary.form.save')}
        busy={busy}
        onPress={() => void submit()}
      />
      <Button label={t('studio.glossary.form.cancel')} variant="secondary" onPress={onCancel} />
      {onDelete ? <DeleteEntry name={initial.name} onDelete={onDelete} /> : null}
    </View>
  );
}

/**
 * Deleting takes two presses: the first asks, the second deletes. Written out
 * here rather than as an Alert, which react-native-web does not show.
 */
function DeleteEntry({
  name,
  onDelete,
}: {
  name: string;
  onDelete: () => Promise<string | null>;
}) {
  const { t } = useTranslation();
  const [asking, setAsking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const confirm = async () => {
    setBusy(true);
    setError(null);
    const failure = await onDelete();
    // Deleted: the screen goes back to the list and this form is gone.
    if (failure) {
      setBusy(false);
      setError(failure);
    }
  };

  if (!asking) {
    return (
      <Button
        label={t('studio.glossary.form.delete')}
        variant="secondary"
        onPress={() => setAsking(true)}
      />
    );
  }
  return (
    <View style={styles.group}>
      <ThemedText accessibilityRole="alert">
        {t('studio.glossary.form.confirmDelete', { name })}
      </ThemedText>
      {error ? <ErrorText>{t(errorMessageKey(error))}</ErrorText> : null}
      <Button label={t('studio.glossary.form.confirm')} busy={busy} onPress={() => void confirm()} />
      <Button
        label={t('studio.glossary.form.keep')}
        variant="secondary"
        disabled={busy}
        onPress={() => setAsking(false)}
      />
    </View>
  );
}

function FactFields({
  row,
  number,
  onChange,
  onRemove,
}: {
  row: FactRow;
  number: number;
  onChange: (next: Partial<FactRow>) => void;
  onRemove: () => void;
}) {
  const { t } = useTranslation();
  const theme = useTheme();
  const keyLabel = `${t('studio.glossary.form.attributeKey')} ${number}`;
  return (
    <View style={[styles.fact, { borderColor: theme.backgroundElement }]}>
      <TextField
        label={keyLabel}
        value={row.key}
        maxLength={MAX_ATTRIBUTE_KEY}
        onChangeText={(key) => onChange({ key })}
      />
      <TextField
        label={`${t('studio.glossary.form.attributeValue')} ${number}`}
        value={row.value}
        multiline
        onChangeText={(value) => onChange({ value })}
      />
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`${t('studio.glossary.form.removeAttribute')}: ${row.key || keyLabel}`}
        onPress={onRemove}
        style={styles.remove}>
        <ThemedText type="linkPrimary">{t('studio.glossary.form.removeAttribute')}</ThemedText>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  form: {
    gap: Spacing.four,
  },
  group: {
    gap: Spacing.two,
  },
  fact: {
    borderWidth: 1,
    borderRadius: Spacing.two,
    padding: Spacing.three,
    gap: Spacing.two,
  },
  remove: {
    alignSelf: 'flex-start',
  },
});
