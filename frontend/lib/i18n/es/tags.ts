export const tags = {
  actions: {
    add: 'Añadir etiqueta',
    remove: 'Quitar etiqueta',
    create: 'Crear etiqueta',
    edit: 'Editar etiqueta',
    delete: 'Eliminar etiqueta',
  },
  fields: {
    name: 'Nombre',
    color: 'Color',
  },
  overflow: '+{count} más',
  noTags: 'Sin etiquetas',
} as const;

export type TagsDict = typeof tags;
