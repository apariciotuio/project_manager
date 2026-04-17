/** @type {import('eslint').Linter.Config} */
module.exports = {
  extends: ['next/core-web-vitals', 'plugin:security/recommended-legacy'],
  plugins: ['security'],
  rules: {},
};
