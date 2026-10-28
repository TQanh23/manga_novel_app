import { useTranslation } from 'react-i18next';

import { useTheme } from '@/hooks/use-theme';

import { EDITOR_COMMANDS, type EditorAppearance, type EditorCommand } from './editor-page';

export type RichTextEditorProps = {
  /** The newest saved text, as the API stores it. Read once, when the editor opens. */
  initialHtml: string;
  /** Called with the text whenever the author has changed it and paused. */
  onChange: (html: string) => void;
};

/** What the editor page is built with besides the text: its colours and words. */
export function useEditorPage(): {
  appearance: EditorAppearance;
  labels: Record<EditorCommand, string>;
  placeholder: string;
  label: string;
} {
  const { t } = useTranslation();
  const theme = useTheme();
  return {
    appearance: {
      text: theme.text,
      background: theme.background,
      muted: theme.textSecondary,
      toolbar: theme.backgroundElement,
    },
    labels: Object.fromEntries(
      EDITOR_COMMANDS.map((command) => [command, t(`studio.editor.${command}`)]),
    ) as Record<EditorCommand, string>,
    placeholder: t('studio.episode.placeholder'),
    label: t('studio.episode.text'),
  };
}
