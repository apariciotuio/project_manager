/**
 * ESLint rule: no-raw-tailwind-color
 *
 * Forbids raw Tailwind color classes like bg-red-500, text-blue-700, border-green-300 etc.
 * Require semantic tokens instead: bg-primary, text-destructive, etc.
 *
 * Safelist:
 *   - Anything under components/ui/ (shadcn generated, we own it)
 *   - Classes that don't match the <prefix>-<color>-<shade> pattern
 *   - opacity modifiers on semantic tokens (bg-primary/90 is fine)
 */

'use strict';

/** Tailwind named colors (raw palette) */
const RAW_COLORS = new Set([
  'slate', 'gray', 'zinc', 'neutral', 'stone',
  'red', 'orange', 'amber', 'yellow', 'lime',
  'green', 'emerald', 'teal', 'cyan', 'sky',
  'blue', 'indigo', 'violet', 'purple', 'fuchsia',
  'pink', 'rose',
  'black', 'white',
]);

/** Classes like bg-red-500, text-blue-700, border-green-300, fill-amber-100 */
const RAW_COLOR_PATTERN = /\b(bg|text|border|ring|outline|fill|stroke|from|to|via|placeholder|decoration|caret|divide|shadow)-([a-z]+)-(\d{2,3})\b/g;

/** Also catch bg-black / bg-white / text-black / text-white without shade */
const RAW_SIMPLE_PATTERN = /\b(bg|text|border|ring|outline|fill|stroke)-(black|white)\b/g;

function checkClassName(className, report, node) {
  let m;
  RAW_COLOR_PATTERN.lastIndex = 0;
  while ((m = RAW_COLOR_PATTERN.exec(className)) !== null) {
    if (RAW_COLORS.has(m[2])) {
      report({
        node,
        message: `Raw Tailwind color "${m[0]}" is forbidden. Use a semantic token (bg-primary, text-destructive, etc.) instead.`,
      });
    }
  }
  RAW_SIMPLE_PATTERN.lastIndex = 0;
  while ((m = RAW_SIMPLE_PATTERN.exec(className)) !== null) {
    report({
      node,
      message: `Raw Tailwind color "${m[0]}" is forbidden. Use a semantic token instead.`,
    });
  }
}

module.exports = {
  meta: {
    type: 'suggestion',
    docs: {
      description: 'Disallow raw Tailwind color classes; require semantic tokens.',
      category: 'Best Practices',
    },
    schema: [],
  },
  create(context) {
    function checkNode(node) {
      if (node.type === 'Literal' && typeof node.value === 'string') {
        checkClassName(node.value, context.report.bind(context), node);
      }
      if (
        node.type === 'TemplateLiteral' &&
        node.quasis.length > 0
      ) {
        for (const quasi of node.quasis) {
          checkClassName(quasi.value.raw, context.report.bind(context), quasi);
        }
      }
    }

    return {
      JSXAttribute(node) {
        if (
          node.name.name === 'className' ||
          node.name.name === 'class'
        ) {
          if (node.value) checkNode(node.value.type === 'JSXExpressionContainer' ? node.value.expression : node.value);
        }
      },
    };
  },
};
