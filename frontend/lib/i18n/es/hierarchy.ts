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
    recalculating: 'Recalculando',
    percent: '{percent}% completado',
    noData: 'Sin datos',
  },
  tree: {
    empty: 'No hay elementos en este proyecto',
    loadMore: 'Cargar más',
    unparented: 'Sin padre',
    expand: 'Expandir',
    collapse: 'Colapsar',
  },
  parentPicker: {
    label: 'Padre',
    placeholder: 'Buscar padre...',
    noResults: 'No se encontraron padres válidos',
    clear: 'Quitar selección',
    error: 'Error al cargar opciones',
  },
  breadcrumb: {
    aria: 'Ruta de navegación',
  },
} as const;

export type HierarchyDict = typeof hierarchy;
