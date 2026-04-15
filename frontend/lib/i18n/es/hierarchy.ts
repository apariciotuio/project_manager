export const hierarchy = {
  actions: {
    addChild: 'Añadir hijo',
    addParent: 'Asignar padre',
    removeChild: 'Quitar hijo',
    removeParent: 'Quitar padre',
    move: 'Mover',
  },
  fields: {
    parent: 'Padre',
    children: 'Hijos',
    depth: 'Nivel',
    path: 'Ruta',
  },
  rollup: {
    total: '{count} elementos',
    ready: '{count} listos',
    blocked: '{count} bloqueados',
  },
} as const;

export type HierarchyDict = typeof hierarchy;
