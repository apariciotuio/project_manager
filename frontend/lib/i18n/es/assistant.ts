export const assistant = {
  title: 'Asistente',
  placeholder: 'Escribe tu pregunta…',
  actions: {
    send: 'Enviar',
    copy: 'Copiar respuesta',
    clear: 'Borrar conversación',
    regenerate: 'Regenerar respuesta',
  },
  status: {
    thinking: 'Pensando…',
    typing: 'Escribiendo…',
    error: 'No pude generar una respuesta. Inténtalo de nuevo.',
    offline: 'El asistente no está disponible. Inténtalo más tarde.',
  },
  emptyState: {
    title: 'Pregúntame lo que quieras',
    description: 'Puedo ayudarte con este elemento de trabajo, resumir revisiones o buscar información en el proyecto.',
  },
} as const;

export type AssistantDict = typeof assistant;
