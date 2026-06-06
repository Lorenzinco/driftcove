import vuetify from "eslint-config-vuetify";

const vuetifyConfig = await vuetify();
const baseConfig = Array.isArray(vuetifyConfig)
  ? vuetifyConfig
  : [vuetifyConfig];

export default [
  ...baseConfig,
  {
    rules: {
      // Keep ESLint focused on maintainability issues instead of formatter noise.
      "@stylistic/semi": "off",
      "@stylistic/quotes": "off",
      "@stylistic/max-statements-per-line": "off",
      "@stylistic/member-delimiter-style": "off",
      "@stylistic/indent-binary-ops": "off",
      "vue/script-indent": "off",

      // These are useful during a deliberate cleanup, but too noisy for day-to-day work
      // in the current codebase and create thousands of language-server diagnostics.
      "complexity": "off",
      "no-empty": "off",
      "import/no-duplicates": "off",
      "@typescript-eslint/no-unused-vars": "off",
      "@typescript-eslint/triple-slash-reference": "off",
      "@typescript-eslint/unified-signatures": "off",
      "unicorn/prefer-add-event-listener": "off",
      "unicorn/prefer-array-some": "off",
      "unicorn/prefer-blob-reading-methods": "off",
      "unicorn/prefer-includes": "off",
      "unicorn/prefer-math-min-max": "off",
      "unicorn/prefer-number-properties": "off",
      "vue/no-required-prop-with-default": "off",
    },
  },
];
