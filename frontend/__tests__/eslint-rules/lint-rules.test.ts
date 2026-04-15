/**
 * Smoke test: verifies all 4 custom ESLint rule test suites pass.
 * The actual RuleTester assertions live in eslint-rules/__tests__/*.test.js —
 * we exec them as Node scripts and assert exit code 0.
 */
import { execSync } from 'node:child_process';
import { join } from 'node:path';
import { describe, it } from 'vitest';

const root = join(process.cwd());

function runRuleTest(file: string) {
  execSync(`node ${join(root, 'eslint-rules/__tests__', file)}`, { stdio: 'inherit' });
}

describe('Custom ESLint rules', () => {
  it('no-raw-tailwind-color — all cases pass', () => {
    runRuleTest('no-raw-tailwind-color.test.js');
  });

  it('no-raw-text-size — all cases pass', () => {
    runRuleTest('no-raw-text-size.test.js');
  });

  it('no-literal-user-strings — all cases pass', () => {
    runRuleTest('no-literal-user-strings.test.js');
  });

  it('tone-jargon — all cases pass', () => {
    runRuleTest('tone-jargon.test.js');
  });
});
