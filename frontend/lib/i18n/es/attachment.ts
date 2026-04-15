export const attachment = {
  actions: {
    upload: 'Subir archivo',
    download: 'Descargar',
    delete: 'Eliminar archivo',
    preview: 'Vista previa',
  },
  fields: {
    name: 'Nombre del archivo',
    size: 'Tamaño',
    type: 'Tipo',
    uploadedBy: 'Subido por',
    uploadedAt: 'Subido el',
  },
  confirmDelete: {
    title: 'Eliminar archivo',
    description: 'Esta acción no se puede deshacer.',
    checkbox: 'Entiendo que esta acción no se puede deshacer',
  },
  noAttachments: 'Sin archivos adjuntos',
  dropzone: 'Arrastra archivos aquí o pulsa para seleccionar',
} as const;

export type AttachmentDict = typeof attachment;
