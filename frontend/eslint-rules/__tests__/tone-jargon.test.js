'use strict';

const { RuleTester } = require('eslint');
const rule = require('../tone-jargon');

const tester = new RuleTester({
  parser: require.resolve('@babel/eslint-parser'),
  parserOptions: {
    requireConfigFile: false,
    babelOptions: { presets: ['@babel/preset-react'] },
    ecmaVersion: 2020,
    ecmaFeatures: { jsx: true },
  },
});

tester.run('tone-jargon', rule, {
  valid: [
    { code: '<button>Guardar cambios</button>' },
    { code: '<button>Confirmar</button>' },
    { code: '<p>Todo listo</p>' },
    { code: '<input placeholder={t("common.search")} />' },
  ],
  invalid: [
    {
      code: '<button>submit</button>',
      errors: [{ message: /Tone jargon "submit"/ }],
    },
    {
      code: '<p>Are you sure?</p>',
      errors: [{ message: /Tone jargon "Are you sure"/ }],
    },
    {
      code: '<span>Draft</span>',
      errors: [{ message: /Tone jargon "Draft"/ }],
    },
    {
      code: '<span>Ready</span>',
      errors: [{ message: /Tone jargon "Ready"/ }],
    },
    {
      code: '<p>Dirígete con usted</p>',
      errors: [{ message: /Tone jargon "usted"/ }],
    },
    {
      code: '<button aria-label="click here">Ir</button>',
      errors: [{ message: /Tone jargon "click here"/ }],
    },
  ],
});

console.log('tone-jargon: all tests passed');
