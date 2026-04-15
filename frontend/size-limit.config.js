// size-limit configuration
// Per-route budget: 200 KB gzipped.
// Run: npx size-limit (after next build)
// CI fails when any route exceeds the limit.

/** @type {import('size-limit').SizeLimitConfig} */
module.exports = [
  {
    name: 'Login page',
    path: '.next/static/chunks/app/login/page*.js',
    limit: '200 kB',
    gzip: true,
  },
  {
    name: 'Workspace select page',
    path: '.next/static/chunks/app/workspace/select/page*.js',
    limit: '200 kB',
    gzip: true,
  },
  {
    name: 'Workspace shell page',
    path: '.next/static/chunks/app/workspace/[slug]/page*.js',
    limit: '200 kB',
    gzip: true,
  },
  {
    name: 'Shared chunks (framework)',
    path: '.next/static/chunks/framework*.js',
    limit: '200 kB',
    gzip: true,
  },
];
