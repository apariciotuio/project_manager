/**
 * ESLint rule: tone-jargon
 *
 * Rejects strings containing jargon/tone violations from tone-jargon.json.
 * Checks JSX text and string literals in user-facing prop positions.
 *
 * Inline-disable: // eslint-disable-next-line tone-jargon
 */

'use strict';

const { forbidden } = require('./tone-jargon.json');

function containsJargon(str) {
  for (const term of forbidden) {
    if (str.includes(term)) return term;
  }
  return null;
}

module.exports = {
  meta: {
    type: 'suggestion',
    docs: {
      description: 'Disallow jargon and tone violations in user-facing strings.',
      category: 'Best Practices',
    },
    schema: [],
  },
  create(context) {
    return {
      JSXText(node) {
        const text = node.value;
        const jargon = containsJargon(text);
        if (jargon) {
          context.report({
            node,
            message: `Tone jargon "${jargon}" found in JSX text. Rephrase in plain ES tuteo.`,
          });
        }
      },
      JSXAttribute(node) {
        const val = node.value;
        if (!val) return;
        let str = null;
        if (val.type === 'Literal' && typeof val.value === 'string') {
          str = val.value;
        }
        if (!str) return;
        const jargon = containsJargon(str);
        if (jargon) {
          context.report({
            node: val,
            message: `Tone jargon "${jargon}" in attribute "${node.name.name}". Rephrase in plain ES tuteo.`,
          });
        }
      },
    };
  },
};
