export const errors = {
  generic: 'Algo salió mal. Inténtalo de nuevo.',
  network: 'No pudimos conectarnos. Comprueba tu conexión.',
  notFound: 'No encontramos lo que buscabas.',
  forbidden: 'No tienes permiso para hacer esto.',
  unauthorized: 'Inicia sesión para continuar.',
  timeout: 'La operación tardó demasiado. Inténtalo de nuevo.',
  validationFailed: 'Revisa los datos e inténtalo de nuevo.',
  auth: {
    oauth_failed: 'No pudimos completar el inicio de sesión. Inténtalo de nuevo.',
    session_expired: 'Tu sesión expiró. Inicia sesión de nuevo.',
    invalid_state: 'Solicitud inválida. Inténtalo de nuevo.',
    cancelled: 'Cancelaste el inicio de sesión.',
    no_workspace: 'Tu cuenta no tiene acceso a ningún workspace.',
  },
  workitem: {
    notFound: 'No encontramos este elemento de trabajo.',
    locked: 'Este elemento está bloqueado y no puede editarse.',
    staleVersion: 'Otra persona hizo cambios. Recarga para continuar.',
    invalidTransition: 'No puedes cambiar a ese estado desde el estado actual.',
  },
  review: {
    notFound: 'No encontramos esta revisión.',
    alreadyClosed: 'Esta revisión ya está cerrada.',
  },
  hierarchy: {
    circularDependency: 'Este cambio crearía una dependencia circular.',
  },
  mcp: {
    tokenExpired: 'La clave expiró.',
    tokenRevoked: 'La clave fue revocada.',
    quotaExceeded: 'Se alcanzó el límite de peticiones.',
  },
} as const;

export type ErrorsDict = typeof errors;
