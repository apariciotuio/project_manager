/**
 * Tests for no-raw-tailwind-color ESLint rule.
 * Uses ESLint's built-in RuleTester.
 */
'use strict';

const { RuleTester } = require('eslint');
const rule = require('../no-raw-tailwind-color');

const tester = new RuleTester({
  parser: require.resolve('@babel/eslint-parser'),
  parserOptions: {
    requireConfigFile: false,
    babelOptions: { presets: ['@babel/preset-react'] },
    ecmaVersion: 2020,
    ecmaFeatures: { jsx: true },
  },
});

tester.run('no-raw-tailwind-color', rule, {
  valid: [
    // Semantic tokens — should pass
    { code: '<div className="bg-primary text-foreground border-border" />' },
    { code: '<div className="bg-destructive text-primary-foreground" />' },
    { code: '<div className="bg-success text-warning" />' },
    { code: '<div className="bg-muted text-muted-foreground" />' },
    // No className — should pass
    { code: '<div id="test" />' },
  ],
  invalid: [
    {
      code: '<div className="bg-red-500" />',
      errors: [{ message: /Raw Tailwind color "bg-red-500"/ }],
    },
    {
      code: '<div className="text-blue-700" />',
      errors: [{ message: /Raw Tailwind color "text-blue-700"/ }],
    },
    {
      code: '<div className="border-green-300" />',
      errors: [{ message: /Raw Tailwind color "border-green-300"/ }],
    },
    {
      code: '<div className="bg-zinc-100" />',
      errors: [{ message: /Raw Tailwind color "bg-zinc-100"/ }],
    },
    {
      code: '<div className="bg-black" />',
      errors: [{ message: /Raw Tailwind color "bg-black"/ }],
    },
    {
      code: '<div className="text-white" />',
      errors: [{ message: /Raw Tailwind color "text-white"/ }],
    },
  ],
});

console.log('no-raw-tailwind-color: all tests passed');
