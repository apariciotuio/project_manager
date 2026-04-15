'use strict';

const { RuleTester } = require('eslint');
const rule = require('../no-raw-text-size');

const tester = new RuleTester({
  parser: require.resolve('@babel/eslint-parser'),
  parserOptions: {
    requireConfigFile: false,
    babelOptions: { presets: ['@babel/preset-react'] },
    ecmaVersion: 2020,
    ecmaFeatures: { jsx: true },
  },
});

tester.run('no-raw-text-size', rule, {
  valid: [
    { code: '<div className="text-display font-bold" />' },
    { code: '<div className="text-h1" />' },
    { code: '<div className="text-body text-muted-foreground" />' },
    { code: '<div className="text-caption" />' },
    { code: '<div className="text-code" />' },
  ],
  invalid: [
    {
      code: '<div className="text-xs" />',
      errors: [{ message: /Raw text size "text-xs"/ }],
    },
    {
      code: '<div className="text-sm font-medium" />',
      errors: [{ message: /Raw text size "text-sm"/ }],
    },
    {
      code: '<div className="text-2xl" />',
      errors: [{ message: /Raw text size "text-2xl"/ }],
    },
    {
      code: '<div className="text-3xl text-foreground" />',
      errors: [{ message: /Raw text size "text-3xl"/ }],
    },
  ],
});

console.log('no-raw-text-size: all tests passed');
