export const review = {
  state: {
    open: 'Abierta',
    approved: 'Aprobada',
    rejected: 'Rechazada',
    closed: 'Cerrada',
  },
  actions: {
    open: 'Abrir revisión',
    approve: 'Aprobar',
    reject: 'Rechazar',
    close: 'Cerrar revisión',
    addComment: 'Añadir comentario',
    override: 'Forzar aprobación',
  },
  fields: {
    reviewer: 'Revisor',
    decision: 'Decisión',
    comment: 'Comentario',
    createdAt: 'Abierta el',
    resolvedAt: 'Resuelta el',
  },
  confirmOverride: {
    title: 'Forzar aprobación',
    description: 'Vas a aprobar este elemento sin consenso del equipo. Esta acción queda registrada.',
    checkbox: 'Entiendo que esta acción queda registrada y no se puede deshacer',
  },
} as const;

export type ReviewDict = typeof review;
