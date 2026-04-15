export const mcp = {
  title: 'Claves de acceso',
  description: 'Gestiona las claves para conectar herramientas externas.',
  actions: {
    create: 'Crear clave',
    revoke: 'Revocar clave',
    reveal: 'Mostrar clave',
    copy: 'Copiar clave',
    regenerate: 'Regenerar clave',
  },
  fields: {
    name: 'Nombre',
    prefix: 'Prefijo',
    createdAt: 'Creada el',
    expiresAt: 'Expira el',
    lastUsedAt: 'Último uso',
    status: 'Estado',
    scopes: 'Permisos',
  },
  status: {
    active: 'Activa',
    expired: 'Expirada',
    revoked: 'Revocada',
  },
  reveal: {
    title: 'Clave de acceso',
    warning: 'Esta clave solo se muestra una vez. Cópiala ahora y guárdala en un lugar seguro.',
    autoClose: 'Se oculta automáticamente en {seconds} segundos',
    gate: 'Muestra la clave',
  },
  confirmRevoke: {
    title: 'Revocar clave',
    description: 'Las integraciones que usan esta clave dejarán de funcionar. Escribe el nombre de la clave para confirmar.',
    typeToConfirm: 'Escribe "{name}" para confirmar',
  },
  noTokens: 'Sin claves de acceso',
  createFirst: 'Crea tu primera clave para conectar herramientas externas',
} as const;

export type McpDict = typeof mcp;
