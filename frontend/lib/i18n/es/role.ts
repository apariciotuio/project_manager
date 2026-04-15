export const role = {
  names: {
    superadmin: 'Superadmin',
    workspaceAdmin: 'Admin del workspace',
    projectAdmin: 'Admin del proyecto',
    techLead: 'Tech Lead',
    productManager: 'Product Manager',
    teamLead: 'Team Lead',
    developer: 'Desarrollador',
    qa: 'QA',
    viewer: 'Lector',
  },
  descriptions: {
    superadmin: 'Acceso total a la plataforma',
    workspaceAdmin: 'Administra el workspace y sus miembros',
    projectAdmin: 'Administra proyectos y miembros del proyecto',
    techLead: 'Lidera el equipo técnico',
    productManager: 'Gestiona el backlog y prioridades',
    teamLead: 'Lidera el equipo de trabajo',
    developer: 'Implementa y entrega funcionalidades',
    qa: 'Verifica la calidad del software',
    viewer: 'Solo puede ver contenido',
  },
  actions: {
    assign: 'Asignar rol',
    remove: 'Quitar rol',
    change: 'Cambiar rol',
  },
} as const;

export type RoleDict = typeof role;
