Qué queda por delante                                                                                                                          
                                                                                                                                                 
  ┌─────────────────────────────────────┬───────────────────────────────────────┐
  │                Track                │                Estado                 │
  ├─────────────────────────────────────┼───────────────────────────────────────┤
  │ Track 2 — decisiones técnicas       │ ✅ Cerrado (32 decisiones)            │
  ├─────────────────────────────────────┼───────────────────────────────────────┤
  │ Track 1 — propagación a EP docs     │ 🔴 Pendiente — afecta ~35 archivos    │
  ├─────────────────────────────────────┼───────────────────────────────────────┤
  │ Track 3 — 20 issues de consistencia │ 🔴 Pendiente — schema fixes mecánicos │
  └─────────────────────────────────────┴───────────────────────────────────────┘

  Track 1 se complica ahora con dundun — muchas épicas cambian más de lo que parecía:
  - EP-03 (conversation) se simplifica mucho → proxy a dundun
  - EP-04 (completeness) → spec gen delegada
  - EP-05 (breakdown) → delegado
  - EP-13 (search) → reescritura: PuppetClient directo, no RAG interno
  - EP-12 (observability) → reducido
  - EP-11 (Jira) → reescritura completa (import + upsert)
  - EP-17 (locks) → añade presence
  - EP-10 (admin) → añade superadmin cross-workspace
  - EP-00 (auth) → no auto-create, workspace picker
  - EP-02 (templates) → JSON-schema tipado
  - EP-16 (attachments) → sin ClamAV, sin signed URLs

  Propuesta: arranco track 1 en bloque con un agente dedicado (como hice con el barrido MVP), con briefing preciso de qué cambia por épica.
  Reviso cada épica tras el barrido.

  ¿Lanzo track 1?