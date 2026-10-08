import * as SecureStore from 'expo-secure-store';

import type { TokenStore } from './token-store.types';

const KEY = 'refresh_token';

// Android and iOS: the refresh token travels in request and response bodies
// and rests in the platform keystore.
export const tokenStore: TokenStore = {
  transport: 'body',
  load: () => SecureStore.getItemAsync(KEY),
  save: (refreshToken) => SecureStore.setItemAsync(KEY, refreshToken),
  clear: () => SecureStore.deleteItemAsync(KEY),
};
