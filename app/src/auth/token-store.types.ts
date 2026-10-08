export type TokenStore = {
  /** How the refresh token reaches the API: in the JSON body, or as a cookie. */
  transport: 'body' | 'cookie';
  load: () => Promise<string | null>;
  save: (refreshToken: string) => Promise<void>;
  clear: () => Promise<void>;
};
