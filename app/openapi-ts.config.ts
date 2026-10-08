import { defineConfig } from '@hey-api/openapi-ts';

// The API client is generated, never written by hand: `npm run gen:api`.
export default defineConfig({
  input: './openapi.json',
  output: { path: './src/api/generated' },
  plugins: ['@hey-api/client-fetch', '@hey-api/typescript', '@hey-api/sdk'],
});
