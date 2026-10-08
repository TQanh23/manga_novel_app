import type { TokenStore } from './token-store.types';

// Web: the refresh token is an httpOnly cookie the API sets and the browser
// sends back. Page scripts never see it, so there is nothing to store here.
export const tokenStore: TokenStore = {
  transport: 'cookie',
  load: async () => null,
  save: async () => {},
  clear: async () => {},
};
