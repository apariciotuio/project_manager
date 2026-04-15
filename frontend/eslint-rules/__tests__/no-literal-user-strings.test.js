'use strict';

const { RuleTester } = require('eslint');
const rule = require('../no-literal-user-strings');

const tester = new RuleTester({
  parser: require.resolve('@babel/eslint-parser'),
  parserOptions: {
    requireConfigFile: false,
    babelOptions: { presets: ['@babel/preset-react'] },
    ecmaVersion: 2020,
    ecmaFeatures: { jsx: true },
  },
});

tester.run('no-literal-user-strings', rule, {
  valid: [
    // i18n call in JSX expression — ok
    { code: '<div>{t("auth.signIn")}</div>' },
    // Empty string — ok
    { code: '<input placeholder="" />' },
    // Single char — ok
    { code: '<span>/</span>' },
    // Pure whitespace in JSX — ok
    { code: '<div>  </div>' },
    // Non-user-facing prop — ok
    { code: '<div data-testid="login-button" />' },
  ],
  invalid: [
    {
      code: '<button>Iniciar sesión</button>',
      errors: [{ message: /User-facing string "Iniciar sesión" must be wrapped/ }],
    },
    {
      code: '<input placeholder="Escribe tu nombre" />',
      errors: [{ message: /User-facing string.*placeholder/ }],
    },
    {
      code: '<img alt="Logo de la empresa" />',
      errors: [{ message: /User-facing string.*alt/ }],
    },
    {
      code: '<div aria-label="Abrir menú" />',
      errors: [{ message: /User-facing string.*aria-label/ }],
    },
  ],
});

console.log('no-literal-user-strings: all tests passed');
