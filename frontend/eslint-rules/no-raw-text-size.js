/**
 * ESLint rule: no-raw-text-size
 *
 * Forbids raw Tailwind text-size classes like text-xs, text-sm, text-2xl
 * outside of the approved semantic list. Use text-display, text-h1, text-body, etc.
 *
 * Approved classes (from semantic system + necessary raw sizes within that system):
 *   text-display, text-h1, text-h2, text-h3, text-body, text-body-sm, text-caption, text-code
 */

'use strict';

/** Raw Tailwind text size classes */
const RAW_TEXT_SIZES = new Set([
  'text-xs', 'text-sm', 'text-base', 'text-lg',
  'text-xl', 'text-2xl', 'text-3xl', 'text-4xl',
  'text-5xl', 'text-6xl', 'text-7xl', 'text-8xl', 'text-9xl',
]);

/** Semantic replacements (allowed) */
// text-display, text-h1 ... text-code — all defined in globals.css @layer utilities

function checkClassName(className, report, node) {
  // Split on whitespace to get individual classes
  const classes = className.split(/\s+/);
  for (const cls of classes) {
    if (RAW_TEXT_SIZES.has(cls)) {
      report({
        node,
        message: `Raw text size "${cls}" is forbidden. Use a semantic class (text-display, text-h1, text-h2, text-h3, text-body, text-body-sm, text-caption, text-code) instead.`,
      });
    }
  }
}

module.exports = {
  meta: {
    type: 'suggestion',
    docs: {
      description: 'Disallow raw Tailwind text-size classes; require semantic typography classes.',
      category: 'Best Practices',
    },
    schema: [],
  },
  create(context) {
    function checkNode(node) {
      if (node.type === 'Literal' && typeof node.value === 'string') {
        checkClassName(node.value, context.report.bind(context), node);
      }
      if (node.type === 'TemplateLiteral') {
        for (const quasi of node.quasis) {
          checkClassName(quasi.value.raw, context.report.bind(context), quasi);
        }
      }
    }

    return {
      JSXAttribute(node) {
        if (node.name.name === 'className' || node.name.name === 'class') {
          if (node.value) {
            checkNode(
              node.value.type === 'JSXExpressionContainer'
                ? node.value.expression
                : node.value
            );
          }
        }
      },
    };
  },
};
