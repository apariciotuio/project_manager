export const lock = {
  locked: 'Bloqueado',
  lockedBy: 'Bloqueado por {name}',
  lockedSince: 'Bloqueado desde {time}',
  unlocked: 'Desbloqueado',
  actions: {
    lock: 'Bloquear',
    unlock: 'Desbloquear',
    forceUnlock: 'Forzar desbloqueo',
  },
  banner: {
    youHaveLock: 'Tienes el bloqueo activo',
    othersHaveLock: '{name} tiene este elemento bloqueado',
    readOnly: 'Solo lectura — otro usuario está editando',
  },
  confirmForceUnlock: {
    title: 'Forzar desbloqueo',
    description: 'Vas a quitar el bloqueo de {name}. Sus cambios sin guardar se perderán.',
    checkbox: 'Entiendo que los cambios sin guardar se perderán',
  },
} as const;

export type LockDict = typeof lock;
