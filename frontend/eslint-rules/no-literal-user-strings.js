/**
 * ESLint rule: no-literal-user-strings
 *
 * Forbids string literals in JSX children and common user-facing props
 * (placeholder, label, aria-label, title, alt) that are not empty strings
 * or single whitespace / punctuation.
 *
 * Exemptions:
 *   - Empty strings: ""
 *   - Single characters (e.g., "/" separator)
 *   - Strings that look like i18n keys ("auth.signIn")
 *   - SR-only technical strings in aria-hidden contexts
 *   - Inline-disable comment: // eslint-disable-next-line no-literal-user-strings
 */

'use strict';

const USER_FACING_PROPS = new Set([
  'placeholder',
  'label',
  'aria-label',
  'aria-description',
  'title',
  'alt',
]);

function isI18nKey(str) {
  // Looks like a dotted key or curly-brace interpolation — not user-facing
  return /^\{/.test(str) || /^[a-z][a-zA-Z0-9]*(\.[a-zA-Z0-9]+)+$/.test(str);
}

function isExempt(str) {
  if (!str || str.trim() === '') return true;
  if (str.length <= 2) return true;
  if (isI18nKey(str)) return true;
  return false;
}

module.exports = {
  meta: {
    type: 'suggestion',
    docs: {
      description: 'Require i18n t() for user-facing strings instead of hardcoded literals.',
      category: 'Best Practices',
    },
    schema: [],
  },
  create(context) {
    return {
      JSXElement(node) {
        for (const child of node.children) {
          if (
            child.type === 'JSXText' &&
            child.value.trim().length > 0 &&
            !isExempt(child.value.trim())
          ) {
            context.report({
              node: child,
              message: `User-facing string "${child.value.trim()}" must be wrapped in t(). Use next-intl useTranslations() instead.`,
            });
          }
        }
      },
      JSXAttribute(node) {
        if (!USER_FACING_PROPS.has(node.name.name)) return;
        const val = node.value;
        if (!val) return;
        if (val.type === 'Literal' && typeof val.value === 'string') {
          if (!isExempt(val.value)) {
            context.report({
              node: val,
              message: `User-facing string in "${node.name.name}" must use t(). Hardcoded: "${val.value}".`,
            });
          }
        }
      },
    };
  },
};
