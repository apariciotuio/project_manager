# EP-13 — v2 Carveout

**Closed as MVP-complete 2026-04-19** with the following items deliberately punted to v2:

- **React Query adoption** — current impl uses a module-level `Map` cache with equivalent behaviour (1h TTL matches server cache). Migration is a straightforward refactor, not a bug.

MVP scope (outbox + Celery task + suggest debounce + detail-page docs wiring + admin Puppet tab + i18n) shipped and is in production.

Re-open if users hit cache invalidation issues that `useQuery`'s stale-while-revalidate would solve more cleanly.
