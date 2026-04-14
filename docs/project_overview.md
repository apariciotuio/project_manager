# Project Overview — Plataforma de Maduración del Trabajo

## Propósito

Construir una **capa intermedia y autónoma de maduración del trabajo** que separa la fase de **definición** de la fase de **ejecución**. El sistema captura inputs ambiguos (ideas, bugs, requisitos, cambios de negocio), los aterriza mediante clarificación guiada, los estructura en especificaciones revisables, los desglosa en tareas, coordina revisiones y validaciones asíncronas, y los lleva a estado `Ready` bajo control humano explícito. Solo entonces, y mediante acción explícita, se exporta a Jira.

**Principio rector**: antes de ejecutar, hay que definir bien. El producto no es un generador de tickets: es el lugar donde el trabajo se define bien antes de ejecutarse.

**No objetivos**: sustituir Jira en ejecución, co-edición simultánea del mismo campo (CRDT/OT), automatizar `Ready` sin criterio humano.

**Sí objetivos en colaboración**: base asíncrona (revisiones, versiones, comentarios, validaciones sin coincidencia temporal) + **presencia en tiempo real** (indicadores "X está editando/viendo", typing en chat/comentarios, contador "N viewing") + locks de edición (EP-17) para prevenir write conflicts.

---

## Dimensiones del producto

1. **Definición estructurada** — transformar inputs vagos en especificaciones y desgloses útiles.
2. **Gobierno del flujo** — ownership único, validaciones, revisiones, paso controlado a `Ready`.
3. **Workspace autónomo** — listados, inbox, dashboards, histórico, búsqueda y trabajo completo sin Jira.
4. **Capa administrativa y operativa** — workspace, equipos, reglas, integraciones, plantillas, auditoría, salud.

---

## Usuarios

**Principales**: Product Manager, Tech Lead, Founder, Producto, Tecnología, Negocio, QA.
**Operativos**: Workspace Admin, Project Admin, Integration Admin, Team Lead, Member, Superadmin (plataforma).

Separación estricta entre **etiquetas de contexto** (producto, desarrollo, negocio, QA — enrutan sugerencias) y **permisos operativos** (invitar, configurar, auditar — gobiernan el sistema).

---

## Modelo de dominio

### Entidades principales

Workspace · Proyecto · Elemento (work_item) · Especificación · Tarea · Subtarea · Revisión · Validación · Conversación · Comentario · Versión · Diff · Equipo · Notificación · Exportación · Configuración · Auditoría · Tag · Attachment · Lock.

### Tipos de elemento

Idea · Bug · Mejora · Tarea · Iniciativa · Spike · Cambio de negocio · Requisito · **Milestone** · **Story** (añadidos por EP-14).

### Jerarquía

`Workspace → Project → Milestone → Epic/Initiative → Story → Task → Subtask`. Jerarquía navegable, editable, con reglas de compatibilidad padre-hijo por tipo.

### Ownership

Único por elemento. Solo el owner puede marcar `Ready`. Puede forzar `Ready` con justificación trazable. Feedback siempre vuelve al owner.

---

## Estados y ciclo de vida

| Estado principal | Significado |
|---|---|
| Borrador | Elemento creado, aún no definido |
| En clarificación | Se está aterrizando el contenido |
| En revisión | Esperando respuesta de revisores/validadores |
| Con cambios solicitados | Cambios explícitos pedidos |
| Validado parcialmente | Algunas validaciones completas |
| Ready | Owner declara listo |
| Exportado | Snapshot final enviado a Jira |

**Estado operativo derivado**: En progreso · Bloqueado · Ready.

**Reglas clave**: validaciones bloqueantes por defecto; override del owner requiere motivo trazable; modificación sustancial sobre `Ready` recalcula madurez.

---

## Flujos end-to-end

1. **Captura** desde texto libre → Borrador con owner por defecto.
2. **Clarificación** guiada con preguntas y detección de huecos.
3. **Especificación** estructurada versionada, editable.
4. **Desglose** en tareas/subtareas con trazabilidad a spec.
5. **Revisión** explícita a usuarios o equipos, asíncrona.
6. **Ready** con checklist de validación o override justificado.
7. **Exportación** explícita a Jira (snapshot inmutable).
8. **Operación sin Jira** como fuente de verdad de la fase de definición.

---

## Funcionalidades por épica

### EP-00 — Acceso, Identidad y Bootstrap
Google OAuth · perfil único · rutas protegidas · resolución de workspace tras login · gestión de sesión.

### EP-01 — Modelo Core, Estados y Ownership
Entidad `work_item` con todos los tipos · state machine con transiciones auditadas · owner único y reasignación · override de `Ready` con justificación · **`parent_work_item_id` + materialized path (ext. EP-14)** · **`attachment_count` denormalizado (ext. EP-16)**.

### EP-02 — Captura, Borradores y Plantillas
Creación desde texto libre · borradores persistentes con guardado parcial · plantillas parametrizables por tipo · cabecera funcional (estado, owner, completitud) desde el inicio · preservación del input original.

### EP-03 — Clarificación, Conversación y Acciones Asistidas
Conversación persistente por elemento y general · detección de huecos · propuestas con preview y aplicación parcial por sección · acciones rápidas de refinamiento · **split-view UX (chat izquierda / contenido derecha, colapsable, con sync bidireccional — ext.)**.

### EP-04 — Especificación Estructurada y Motor de Calidad
Generación de especificación con secciones coherentes por tipo · edición manual · motor de completitud en backend (contexto, objetivo, alcance, criterios, dependencias, validaciones, desglose, ownership) · API de gaps · siguiente paso recomendado · sugerencia de validadores.

### EP-05 — Desglose, Jerarquía y Dependencias
Árbol editable de tareas/subtareas · dividir, fusionar, reordenar · dependencias funcionales con validación anti-ciclos · trazabilidad spec ↔ desglose · vista jerárquica unificada.

### EP-06 — Revisiones, Validaciones y Flujo a `Ready`
Solicitud de revisión a usuarios o equipos (fan-out de notificaciones) · respuestas: aprobar / rechazar / pedir cambios · checklist de validación · iteración múltiple ida-vuelta al owner · override controlado a `Ready` · revisión vinculada a versión concreta.

### EP-07 — Comentarios, Versiones, Diff y Trazabilidad
Comentarios generales y anclados · versionado con snapshots/change sets · servicio de diff legible · timeline completo de decisiones · auditoría inmutable · **imágenes inline en comentarios vía paste/drag (ext. EP-16)**.

### EP-08 — Equipos, Asignaciones, Notificaciones e Inbox
CRUD de equipos · asignación manual y sugerencias heurísticas · notificaciones internas por eventos de dominio · inbox personal priorizado · deeplinks al contexto exacto · acciones rápidas desde inbox.

### EP-09 — Listados, Dashboards, Búsqueda y Workspace Autónomo
Listados con filtros (estado, owner, tipo, equipo) · dashboard global, por responsable, por equipo · pipeline de flujo · búsqueda full-text · vista detalle integrada · **quick filters "My Items" (owner/creador/revisor) + presets guardados (ext.)** · **Kanban drag-drop con transición de estado y errores inline (ext.)** · autonomía total sin Jira.

### EP-10 — Configuración, Proyectos, Reglas y Administración
Gestión de miembros (invitar, suspender, eliminar lógico) · gestión de equipos · gestión de proyectos y contexto · reglas de validación (global / proyecto, con precedencia) · routing y plantillas · configuración Jira · auditoría administrativa · dashboard admin (salud workspace, organizativa, proceso, integraciones) · soporte operativo básico · **superadmin (flag global en users, bootstrap vía CLI/env, crear usuarios, cross-workspace audit) (ext.)** · **admin de tags: CRUD, merge, archive (ext. EP-15)** · **config integración Puppet (ext. EP-13)**.

### EP-11 — Exportación y Sincronización con Jira
Exportación manual y explícita desde `Ready` · snapshot inmutable · referencia interna/externa · sincronización de estado básico · jobs desacoplados con idempotencia, reintentos y logs.

### EP-12 — Responsive, Seguridad, Rendimiento y Observabilidad
Responsive (inbox y acciones críticas en móvil) · accesibilidad y estados UI (loading/empty/error) · permisos validados en backend · auditoría de acciones sensibles · logs estructurados · error tracking · analítica de producto · health checks.

### EP-13 — Búsqueda Semántica + Integración Puppet (nueva)
Integración con Puppet (plataforma interna Tuio de búsqueda semántica) · indexación push de work items, specs y comentarios · búsqueda semántica sobre work items · búsqueda sobre documentación externa Tuio (READMEs, ADRs) · resultados híbridos (keyword PG FTS + semántico Puppet) con provenance · browser de documentación · aislamiento por workspace.

### EP-14 — Jerarquía: Milestones, Épicas, Stories (nueva)
Tipos nuevos `milestone` y `story` · `parent_work_item_id` con reglas de compatibilidad · vista árbol jerárquico por proyecto (Milestones → Epics → Stories → Tasks) · roll-up de completitud de hijos a padre.

### EP-15 — Tags + Labels (nueva)
Catálogo de tags a nivel workspace (admin + user-created) · asignación múltiple a work items · filtros AND/OR en listados, dashboards, búsqueda · autocompletado anti-typos · governance: rename, merge, archive · color e icono por tag.

### EP-16 — Attachments + Media (nueva)
Upload de imágenes (PNG/JPG/GIF/WebP) y documentos (PDF) a work items o comentarios · object storage S3-compatible · thumbnails asíncronos vía Celery · validación de tipo/tamaño + virus scan · galería en detalle · signed URLs autenticadas · cleanup al borrar padre.

### EP-17 — Edit Locking + Control de Colaboración (nueva)
Lock de edición al entrar en modo edición · indicador "X está editando" · enforcement server-side al guardar · expiración por inactividad (~5 min) · request de unlock (notifica al lock holder) · force unlock por superadmin/workspace admin con auditoría.

---

## Integraciones externas

| Integración | Rol |
|---|---|
| Google OAuth | Autenticación única |
| Jira | Exportación manual opcional de `Ready` + sync de estado básico |
| Puppet | Búsqueda semántica y documentación externa Tuio (EP-13) |
| Object Storage (S3-compatible) | Attachments y media (EP-16) |
| Fuentes de contexto | Repos, docs, sistemas relacionados asociados por proyecto |

---

## Requisitos no funcionales

- **Autenticación**: Google OAuth, rutas privadas, gestión de expiración.
- **Responsive**: móvil usable, inbox y acciones críticas accesibles.
- **Persistencia**: historial conversacional y contexto recuperables.
- **Seguridad**: permisos en backend, secretos cifrados (Fernet en integrations), auditoría de acciones sensibles.
- **Rendimiento**: listados, búsqueda y detalle rápidos; operaciones largas con feedback; degradación elegante.
- **Observabilidad**: logs estructurados, eventos de producto, trazas, visibilidad de fallos de integración, métricas de adopción y cuellos de botella.

---

## Métricas de éxito

- Tiempo medio `Borrador → Ready` (reducir sin comprometer calidad).
- % elementos con validaciones completas (subir).
- % elementos con override a `Ready` (mantener controlado).
- Número medio de ciclos de revisión (útil, no excesivo).
- % elementos exportados sin retrabajo por mala definición (subir).
- Antigüedad media de bloqueos (reducir).
- Carga por equipo y owner (visible y equilibrable).
- Uso del sistema sin Jira (autonomía real).
- Ratio adopción de inbox y revisiones.
- Fallos de exportación Jira (bajos y diagnosticables).

---

## Orden de implementación

```
EP-00 → EP-01 → EP-02 → EP-03 → EP-04 → EP-05 → EP-06 → EP-07
                                        EP-08 → EP-09
                                        EP-10 → EP-11
                                        EP-12 (transversal)
                                        EP-13..EP-17 (extensiones nuevas)
```

**Camino crítico**: EP-00 → EP-01 → EP-02 → EP-03 → EP-04 → EP-05 → EP-06 → EP-07.
**Paralelo**: EP-08 tras EP-01; EP-10 tras EP-08.

---

## Definition of Done transversal

Criterios funcionales aceptados · permisos validados en backend · auditoría registrada donde aplique · estados loading/vacío/error cubiertos · responsive revisado · eventos de producto e instrumentación · happy path + edge cases relevantes con tests.
