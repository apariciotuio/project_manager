# EP-11 Sync Spec — DEPRECATED

> **Resolved 2026-04-14 (decisions_pending.md #5, #12, #26)**: This spec is gutted. Jira polling, status sync, webhooks, and the `sync_logs` table are all **removed from scope**. Re-introducing automated sync requires a new decision recorded in `decisions_pending.md`.
>
> The inbound counterpart of export is now **user-initiated import**: see `../import/spec.md`.
>
> Export re-runs UPDATE the same Jira issue via upsert-by-key; see `../export/spec.md`.

(File preserved as a redirect per propagation brief; do not delete.)
