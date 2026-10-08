import { Platform } from 'react-native';

import { tokenStore } from '@/auth/token-store';

import { authRefreshToken, type ErrorResponse, type TokenResponse } from './generated';
import { client } from './generated/client.gen';

// The Android emulator reaches the host machine at 10.0.2.2.
const DEFAULT_API_URL = Platform.OS === 'android' ? 'http://10.0.2.2:8000' : 'http://localhost:8000';

export const API_URL = process.env.EXPO_PUBLIC_API_URL ?? DEFAULT_API_URL;

// The access token lives in memory only. It is short-lived and re-issued from
// the refresh token whenever the app starts or the API answers 401.
let accessToken: string | null = null;
let refreshInFlight: Promise<TokenResponse | null> | null = null;

/** Error code from the API's envelope, or `network_error` when no response arrived. */
export function errorCode(error: unknown): string {
  const code = (error as Partial<ErrorResponse> | undefined)?.error?.code;
  return typeof code === 'string' ? code : 'network_error';
}

export async function storeTokens(tokens: TokenResponse): Promise<void> {
  accessToken = tokens.access_token;
  if (tokens.refresh_token) {
    await tokenStore.save(tokens.refresh_token);
  }
}

export async function forgetTokens(): Promise<void> {
  accessToken = null;
  await tokenStore.clear();
}

/** The stored refresh token, for calls that must send it in the body (sign-out on native). */
export function storedRefreshToken(): Promise<string | null> {
  return tokenStore.load();
}

async function requestNewTokens(): Promise<TokenResponse | null> {
  const stored = await tokenStore.load();
  if (tokenStore.transport === 'body' && !stored) {
    return null;
  }
  const body = tokenStore.transport === 'body' ? { refresh_token: stored } : undefined;

  let result = await authRefreshToken({ body });
  if (result.response?.status === 409) {
    // Another tab refreshed with the same cookie a moment ago. The browser now
    // holds the cookie that tab was given, so one more try succeeds.
    await new Promise((resolve) => setTimeout(resolve, 300));
    result = await authRefreshToken({ body });
  }

  if (result.data) {
    await storeTokens(result.data);
    return result.data;
  }
  if (result.response) {
    // The API refused the token: the session is over.
    await forgetTokens();
  }
  // No response at all means offline; keep the token for the next attempt.
  return null;
}

/** Trade the refresh token for a new pair. Concurrent callers share one request. */
export function refreshSession(): Promise<TokenResponse | null> {
  refreshInFlight ??= requestNewTokens().finally(() => {
    refreshInFlight = null;
  });
  return refreshInFlight;
}

const authFetch: typeof fetch = async (input, init) => {
  const request = new Request(input, init);
  const retry = request.clone();

  const response = await fetch(request);
  const hadToken = request.headers.has('Authorization');
  if (response.status !== 401 || !hadToken || request.url.includes('/v1/auth/')) {
    return response;
  }

  // The access token expired: get a new one and replay the request once.
  const tokens = await refreshSession();
  if (!tokens) {
    return response;
  }
  retry.headers.set('Authorization', `Bearer ${tokens.access_token}`);
  return fetch(retry);
};

client.setConfig({
  baseUrl: API_URL,
  // Lets the browser send and store the refresh cookie. Native has no cookie to send.
  credentials: Platform.OS === 'web' ? 'include' : 'omit',
  auth: () => accessToken ?? undefined,
  fetch: authFetch,
});
