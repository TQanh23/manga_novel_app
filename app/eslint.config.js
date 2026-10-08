// https://docs.expo.dev/guides/using-eslint/
const { defineConfig } = require('eslint/config');
const expoConfig = require("eslint-config-expo/flat");
const i18next = require('eslint-plugin-i18next');

module.exports = defineConfig([
  expoConfig,
  {
    // The API client is generated (`npm run gen:api`); it is checked by tsc, not linted.
    ignores: ["dist/*", "src/api/generated/*"],
  },
  {
    // UI copy goes through i18n (EN and VI): no literal text in JSX.
    files: ["src/**/*.tsx"],
    plugins: { i18next },
    rules: {
      "i18next/no-literal-string": ["error", { mode: "jsx-text-only" }],
    },
  },
]);
