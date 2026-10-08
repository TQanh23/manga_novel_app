import { createContext, type PropsWithChildren, use, useEffect, useMemo, useState } from 'react';

import { errorCode, forgetTokens, refreshSession, storedRefreshToken, storeTokens } from '@/api/client';
import {
  authAddAuthorRole,
  authLogin,
  authLogout,
  authRegisterUser,
  type Locale,
  type UserResponse,
} from '@/api/generated';

import { tokenStore } from './token-store';

type Credentials = { email: string; password: string };
type Registration = Credentials & { displayName: string; locale: Locale };

/** Each action resolves to an API error code, or null when it worked. */
type Session = {
  user: UserResponse | null;
  /** True until the first silent refresh has finished. */
  isLoading: boolean;
  signIn: (credentials: Credentials) => Promise<string | null>;
  register: (registration: Registration) => Promise<string | null>;
  becomeAuthor: () => Promise<string | null>;
  signOut: () => Promise<void>;
};

const SessionContext = createContext<Session | null>(null);

export function useSession(): Session {
  const session = use(SessionContext);
  if (!session) {
    throw new Error('useSession must be used inside <SessionProvider>');
  }
  return session;
}

export function SessionProvider({ children }: PropsWithChildren) {
  const [user, setUser] = useState<UserResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Silent sign-in: a stored refresh token (or the browser's cookie) brings
    // the session back after a restart or a page reload.
    let cancelled = false;
    refreshSession().then((tokens) => {
      if (!cancelled) {
        setUser(tokens?.user ?? null);
        setIsLoading(false);
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const session = useMemo<Session>(() => {
    const signIn = async ({ email, password }: Credentials) => {
      const { data, error } = await authLogin({
        body: { email, password, token_transport: tokenStore.transport },
      });
      if (!data) {
        return errorCode(error);
      }
      await storeTokens(data);
      setUser(data.user);
      return null;
    };

    return {
      user,
      isLoading,
      signIn,
      register: async ({ email, password, displayName, locale }) => {
        const { data, error } = await authRegisterUser({
          body: { email, password, display_name: displayName, locale },
        });
        return data ? signIn({ email, password }) : errorCode(error);
      },
      becomeAuthor: async () => {
        const { data, error } = await authAddAuthorRole();
        if (!data) {
          return errorCode(error);
        }
        setUser(data);
        return null;
      },
      signOut: async () => {
        // Best effort: the local session ends even if the API cannot be reached.
        const refreshToken = await storedRefreshToken();
        await authLogout({ body: refreshToken ? { refresh_token: refreshToken } : undefined });
        await forgetTokens();
        setUser(null);
      },
    };
  }, [user, isLoading]);

  return <SessionContext value={session}>{children}</SessionContext>;
}
