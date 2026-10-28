import { Link, useRouter } from 'expo-router';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { useTranslation } from 'react-i18next';

import { authorListWorks, type UserResponse, type WorkResponse } from '@/api/generated';
import { useLoad } from '@/api/hooks';
import { useSession } from '@/auth/session';
import { Button, Screen } from '@/components/form';
import { Page } from '@/components/page';
import { EmptyState, ErrorState, LoadingState } from '@/components/state-views';
import { ThemedText } from '@/components/themed-text';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { useVisit } from '@/hooks/use-visit';
import { formatDate } from '@/i18n';

const SEPARATOR = ' · ';

/** An author's works, drafts and all (FR-NV-01). */
export default function StudioScreen() {
  const { t } = useTranslation();
  const { user } = useSession();

  // The tab is hidden from everyone else; this is for a link that leads here anyway.
  if (!user?.roles.includes('author')) {
    return (
      <Screen>
        <ThemedText type="subtitle">{t('studio.title')}</ThemedText>
        <ThemedText themeColor="textSecondary">{t('studio.notAuthor')}</ThemedText>
      </Screen>
    );
  }
  return <AuthorWorks user={user} />;
}

function AuthorWorks({ user }: { user: UserResponse }) {
  const { t } = useTranslation();
  const router = useRouter();
  // Coming back from editing a work shows what was saved.
  const visit = useVisit();
  const works = useLoad(`author-works:${user.id}:${visit}`, () => authorListWorks());

  const body = () => {
    if (works.isLoading) {
      return <LoadingState />;
    }
    if (works.error || !works.data) {
      return <ErrorState code={works.error ?? 'unknown'} onRetry={works.reload} />;
    }
    if (works.data.length === 0) {
      return <EmptyState message={t('studio.empty')} />;
    }
    return works.data.map((work) => <WorkRow key={work.id} work={work} />);
  };

  return (
    <Page>
      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.heading}>
          <ThemedText type="subtitle">{t('studio.title')}</ThemedText>
          <Button label={t('studio.newWork')} onPress={() => router.push('/studio/new')} />
        </View>
        {body()}
      </ScrollView>
    </Page>
  );
}

function WorkRow({ work }: { work: WorkResponse }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const kind = [t(`workType.${work.type}`), t(`workStatus.${work.status}`)];
  return (
    <Link href={{ pathname: '/studio/[workId]', params: { workId: work.id } }} asChild>
      <Pressable
        accessibilityRole="link"
        accessibilityLabel={work.title}
        style={({ pressed }) => [
          styles.row,
          { backgroundColor: theme.backgroundElement },
          pressed && styles.pressed,
        ]}>
        <ThemedText style={styles.title}>{work.title}</ThemedText>
        <ThemedText type="small" themeColor="textSecondary">
          {(work.is_sample ? [...kind, t('studio.sample')] : kind).join(SEPARATOR)}
        </ThemedText>
        <ThemedText type="small" themeColor="textSecondary">
          {t('catalogue.updated', { date: formatDate(work.updated_at) })}
        </ThemedText>
      </Pressable>
    </Link>
  );
}

const styles = StyleSheet.create({
  content: {
    padding: Spacing.three,
    paddingBottom: Spacing.five,
    gap: Spacing.three,
  },
  heading: {
    gap: Spacing.three,
  },
  row: {
    borderRadius: Spacing.two,
    padding: Spacing.three,
    gap: Spacing.half,
  },
  title: {
    fontWeight: 700,
  },
  pressed: {
    opacity: 0.7,
  },
});
