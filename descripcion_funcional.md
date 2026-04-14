# Descripción funcional — Plataforma de Maduración del Trabajo

## 1. A alto nivel

### Qué es el producto

Una plataforma de **maduración del trabajo**: capa intermedia y autónoma donde ideas, bugs, requisitos, iniciativas y cambios de negocio se capturan, clarifican, estructuran, revisan, validan y desglosan antes de ejecutarse. Cuando el trabajo está listo, se exporta de forma explícita a Jira. Mientras tanto, el sistema es la fuente de verdad de la fase de definición.

### Qué problema resuelve

El trabajo suele entrar en Jira demasiado pronto: enunciados vagos, ownership difuso, criterios pobres, validaciones tardías, retrabajo. La plataforma separa **definición** de **ejecución** y hace explícito lo que hoy ocurre de forma informal: conversaciones dispersas, decisiones sin registrar, supuestos no escritos.

### A quién sirve

| Perfil | Qué espera del sistema |
|---|---|
| Product Manager | estructura, alineación, revisión |
| Tech Lead | contexto claro, criterios, ownership |
| Founder | captura rápida, visibilidad global |
| Negocio | feedback trazable, validación funcional |
| QA | checklist explícito, huecos visibles |
| Team Lead | dashboards por equipo, cuellos de botella |
| Workspace/Project Admin | configuración, reglas, auditoría |
| Superadmin | creación de workspaces, auditoría cruzada |

### Principios rectores

1. **Antes de ejecutar, definir bien.** El producto no genera tickets: madura trabajo.
2. **Asincronía como base, tiempo real donde aporta.** Revisiones, versiones y comentarios sin coincidencia temporal; presencia y locks para evitar pisarse.
3. **Trazabilidad total.** Toda decisión queda anclada a versión, autor y momento.
4. **Ownership único.** Un responsable por elemento. Solo el owner marca `Ready`.
5. **Control humano.** El sistema sugiere; la persona decide. El override siempre existe y queda registrado.
6. **Autonomía sin Jira.** El flujo completo funciona sin integración externa.

### Qué NO es

- Sustituto de Jira en ejecución, sprint planning o capacity planning.
- Editor colaborativo en tiempo real sobre el mismo campo (no hay CRDT/OT).
- Generador automático de `Ready` sin criterio humano.
- Suite generalista de gestión empresarial.

### Resumen de capacidades

- Captura desde texto libre con borradores persistentes y plantillas por tipo.
- Clarificación guiada por chat asistido con detección de huecos y propuestas aceptables por tramos.
- Especificación estructurada versionada con motor de completitud y siguiente paso recomendado.
- Desglose jerárquico en tareas/subtareas con dependencias y validación anti-ciclos.
- Revisiones y validaciones asíncronas a personas o equipos, con iteración hasta `Ready`.
- Comentarios anclados, versiones navegables, diff legible y timeline completo.
- Presencia en tiempo real y locks de edición para prevenir conflictos.
- Workspace autónomo con listados, filtros, dashboards, búsqueda e inbox priorizado.
- Tags, adjuntos (imágenes y PDF) y búsqueda semántica sobre contenido interno y documentación Tuio.
- Exportación e importación explícitas con Jira y administración completa del workspace.
- **Acceso programático de solo lectura vía MCP** para agentes externos (Claude Code, copilotos, CLIs), con tokens emitidos por admin, aislamiento por workspace y auditoría completa.

---

## 2. Glosario

| Término | Definición |
|---|---|
| **Workspace** | Contenedor principal: usuarios, equipos, proyectos, reglas e integraciones. Unidad de aislamiento de datos y permisos. |
| **Proyecto** | Ámbito lógico dentro del workspace que agrupa elementos y aplica contexto y reglas locales. |
| **Work item (elemento)** | Unidad que se madura: idea, bug, mejora, tarea, iniciativa, spike, cambio de negocio, requisito, milestone o story. |
| **Owner** | Única persona responsable de un elemento; el único que puede marcar `Ready`. |
| **Ready** | Estado que declara el elemento listo para ejecutarse. Requiere validaciones o override justificado. |
| **Override** | Acto del owner de forzar `Ready` con validaciones pendientes, dejando motivo trazable. |
| **Revisión** | Solicitud explícita de feedback, aprobación o cambios a persona o equipo. |
| **Validación** | Requisito de calidad o madurez que bloquea el avance hasta cumplirse. |
| **Spec** | Representación estructurada del elemento en secciones coherentes. |
| **Versión** | Snapshot del contenido en un momento dado; base del diff y del histórico. |
| **Inbox** | Vista personal priorizada con lo que requiere acción del usuario ahora. |
| **Thread** | Conversación persistente asociada a un elemento o general. |
| **Milestone** | Objetivo temporal de entrega (p. ej. "Lanzamiento Q2"). |
| **Story** | Feature visible al usuario dentro de una iniciativa/épica. |
| **Tag** | Etiqueta libre scoped al workspace, para agrupar y filtrar. |
| **Lock de edición** | Reserva temporal al editar; impide que otros guarden cambios simultáneos. |
| **Snapshot de exportación** | Copia inmutable del elemento al enviarlo a Jira; base para detectar divergencia. |
| **Dundun** | Capa interna de inteligencia que el producto integra para chat, detección de huecos, generación y sugerencias. Para el usuario es "el asistente". |
| **Puppet** | Plataforma interna Tuio de búsqueda semántica sobre contenido del workspace y documentación externa. |
| **Capability** | Capacidad operativa concreta (invitar, configurar Jira, force-unlock, etc.), separada de las etiquetas de contexto. |
| **MCP (Model Context Protocol)** | Protocolo abierto que permite a agentes externos (IDE copilots, CLIs, otros LLMs) consultar la plataforma mediante *tools* y *resources* tipados, sin tocar la API REST ni la base de datos. |
| **MCP token** | Credencial emitida por un admin del workspace que vincula a un usuario con **un único workspace** y el alcance `mcp:read`. Se muestra en claro **una sola vez** al crearla; el hash se guarda con argon2id. TTL por defecto 30 días, máximo 90. |

---

## 3. En detalle

### 3.1 Acceso e identidad

El usuario entra con Google OAuth. El sistema mantiene un perfil único por persona y resuelve tras el login a qué workspaces pertenece: si es uno, entra directo; si son varios, un selector permite elegir. Las rutas privadas están protegidas y la sesión expira de forma controlada.

La pertenencia al workspace se gestiona por invitación. Cada usuario lleva asociadas **etiquetas de contexto** (producto, tecnología, negocio, QA…) y **capacidades operativas** (invitar, configurar reglas, conectar Jira, forzar unlock…). Las dos capas son independientes: ser de "negocio" no implica ser admin, y al revés.

### 3.2 Captura y clarificación

Crear un elemento es barato y rápido: el usuario pulsa crear, escribe texto libre, elige tipo (idea, bug, mejora, tarea, iniciativa, spike, cambio, requisito, milestone o story) y el sistema crea el elemento en `Borrador`, guarda el **input original** inmutable, asigna al creador como owner, aplica plantilla si existe para ese tipo/proyecto, muestra la cabecera funcional (tipo, owner, estado, completitud) y persiste el borrador aunque la información sea parcial.

La clarificación ocurre en un **chat asistido** persistente por elemento. El asistente detecta huecos (falta objetivo, no hay criterios, alcance ambiguo, dependencias no vistas) y formula preguntas. El usuario responde y el sistema propone mejoras por sección con preview; el usuario acepta entera, por tramos o rechaza, y cada aceptación genera versión. La UI es vista dividida (chat a la izquierda, contenido a la derecha) con sincronización bidireccional y paneles colapsables. Existe además un **chat general** del workspace, no ligado a un elemento, desde el que se puede decidir crear uno cuando la conversación ha madurado.

### 3.3 Especificación estructurada

Cada elemento se proyecta en una **especificación** con secciones coherentes según su tipo: contexto, objetivo, alcance, criterios de aceptación, dependencias, validaciones, desglose, ownership. El usuario edita cada sección manualmente o pide al asistente que la genere o reescriba con preview, aceptando o rechazando por sección.

Un motor de completitud evalúa el grado de definición del elemento y la UI muestra indicador visual de madurez (bajo / medio / alto o porcentaje), los **huecos detectados** con enlace directo a la sección, y el **siguiente paso recomendado** explícito ("faltan criterios de aceptación", "falta validación QA", "conviene desglosar en tareas").

El sistema sugiere además **validadores** plausibles según tipo, etiquetas de contexto del elemento y reglas del proyecto.

### 3.4 Desglose y dependencias

Desde la especificación, el elemento se desglosa en un **árbol editable** de tareas y subtareas. El sistema puede proponer un desglose inicial que el usuario refina: añadir, renombrar, dividir, fusionar, reordenar por drag-and-drop, cambiar de padre. Se definen **dependencias funcionales** entre tareas y entre elementos distintos del workspace, con validación anti-ciclos. Cada tarea preserva el vínculo con la sección de la spec de la que nace. La jerarquía superior (milestone → épica → story → tarea → subtarea) se describe en §3.9.

### 3.5 Revisión y validación

El owner envía el elemento a revisión a personas o equipos. El sistema crea una solicitud vinculada a la **versión actual**, notifica a los destinatarios (si es equipo, a todos sus miembros) y registra quién responde en nombre del equipo. El revisor lee, comenta (general o anclado), puede editar directamente y responde con **aprobar**, **rechazar** o **pedir cambios**. El resultado vuelve al owner y puede haber múltiples ciclos.

En paralelo, el elemento tiene un **checklist de validación** con reglas obligatorias y recomendadas definidas a nivel workspace o proyecto. Cuando una revisión del perfil adecuado se cierra con aprobación, la validación correspondiente se marca cumplida.

Transición a `Ready`: con validaciones obligatorias cumplidas, el owner marca `Ready`. Con validaciones pendientes, la transición normal está bloqueada y el owner puede hacer **override** con justificación trazable, visible en el histórico y contabilizado en los dashboards administrativos.

### 3.6 Trazabilidad

La historia del elemento se reconstruye siempre:

- **Versiones** automáticas en cada cambio relevante, navegables y abribles en lectura.
- **Diff visual** legible entre dos versiones, con aceptación por segmento al comparar una propuesta del asistente con el contenido actual.
- **Tags de versión** para marcar hitos ("revisión inicial", "aprobada por negocio").
- **Timeline** cronológico: creación, cambios de estado, revisiones, validaciones cumplidas, comentarios, exportaciones. Distingue actor: humano, asistente o sistema.
- **Comentarios** generales o anclados a sección (o a un rango de texto). Soportan respuestas en hilo, reacciones, menciones y marcan si fueron editados. Si el texto anclado cambia, el sistema reubica el anclaje; si no lo encuentra, marca el comentario "huérfano" sin borrarlo.

Las acciones administrativas se auditan aparte (ver §3.13).

### 3.7 Colaboración asíncrona + presencia tiempo real

La colaboración es **primariamente asíncrona**: revisiones, validaciones y comentarios no requieren coincidencia temporal. Sobre esa base, señales de tiempo real:

- Indicadores **"X está editando"** / **"N personas viendo"** en detalle y listados, y typing indicators en chats y comentarios.
- **Locks de edición** por elemento: al entrar en modo edición se adquiere un lock. Otros ven "María está editando" y el botón queda inhabilitado. El lock se extiende con la actividad y expira tras inactividad (~5 min).
- El usuario puede **pedir unlock** al titular con motivo; el titular libera o ignora, y pasado un tiempo se libera solo.
- Un workspace admin o superadmin puede ejecutar **force-unlock** con motivo obligatorio; queda auditado y el titular anterior es notificado.

### 3.8 Workspace autónomo

El sistema se usa de extremo a extremo sin Jira.

- **Listados** con filtros combinables (estado, tipo, owner, equipo, tags, archivado), presets guardados y quick filters "My Items" (como owner, creador o revisor).
- **Dashboards**: global por estado, por responsable, por equipo, y vista **pipeline** del flujo.
- **Kanban** con drag-and-drop que dispara transiciones de estado (errores inline si la transición no es válida).
- **Búsqueda** combinada keyword + semántica (§3.15) y **búsquedas guardadas** por usuario.
- **Inbox personal** priorizado (revisiones pendientes > elementos devueltos > bloqueos que le afectan > decisiones pendientes) con enlace al contexto exacto y acciones rápidas sin salir.
- **Vista detalle**: cabecera, siguiente paso, spec, desglose, validaciones, revisiones, comentarios, historial, adjuntos, referencia Jira y estado de lock.

Las vistas principales son responsive; en móvil funcionan inbox y acciones críticas.

### 3.9 Jerarquía

El producto soporta una jerarquía funcional que va desde lo estratégico a lo ejecutivo:

```
Workspace → Proyecto → Milestone → Iniciativa/Épica → Story → Tarea → Subtarea
```

Cada nivel es un work item con su propio tipo. Reglas de compatibilidad padre-hijo aseguran que, p. ej., un milestone no puede colgar de una story. Elementos sin padre cuelgan directamente del proyecto.

- Vista árbol navegable por proyecto, colapsable por nivel.
- Breadcrumb de ancestros desde cualquier elemento y selector de padre en creación.
- **Roll-up de completitud**: el avance de un padre se calcula a partir del estado de sus hijos; al pasar una story a `Ready`, la épica y el milestone se recalculan.
- Filtros por ancestro ("todas las stories de la épica X").

### 3.10 Tags y etiquetado

Cada workspace tiene un **catálogo de tags** propio. Los admins pueden sembrar un conjunto inicial; los miembros añaden más al aplicarlos. Un elemento lleva múltiples tags (tope razonable, ~20), cada uno con color y opcionalmente icono. Al escribir, el sistema autocompleta para evitar variantes y typos. Filtros en listados, dashboards y búsqueda soportan lógica **AND** y **OR**.

Gobierno desde administración: renombrar, **fusionar** un tag dentro de otro (los elementos heredan el destino, operación auditada) y **archivar** un tag (desaparece de autocompletado y creación, permanece en los elementos que ya lo llevaban).

### 3.11 Adjuntos

Los elementos y los comentarios soportan adjuntos de **imágenes** (PNG, JPG, GIF, WebP) y **documentos PDF**. Subida por drag-and-drop o selector con barra de progreso, y **pegado inline** de imágenes en comentarios desde portapapeles o drag. Thumbnails de imágenes y de la primera página de los PDF en la **galería** del elemento, con previsualización en modal y descarga. Validación de tipo y tamaño (configurable por workspace; p. ej. 10 MB por archivo). Los adjuntos se liberan al eliminar el elemento padre; solo el autor del adjunto o el owner del elemento pueden borrarlos.

### 3.12 Exportación e importación Jira

La integración con Jira es **opcional y explícita**. No hay sincronización automática ni bidireccional: Jira nunca modifica contenido de la plataforma por sí solo.

- **Exportar a Jira**: acción manual del owner (o delegado) sobre un elemento en `Ready`. Envía snapshot inmutable, guarda la referencia del issue y muestra el vínculo en detalle.
- **Re-exportar** el mismo elemento hace **upsert por clave**. Antes de sobrescribir, avisa si hay edición manual en Jira desde la última exportación.
- **Importar** desde Jira: acción iniciada por el usuario que crea un elemento en `Borrador` marcado como importado. Si ese elemento madura y se exporta, actualiza el issue original.
- **Sincronización de estado básico** del issue externo para reflejar progreso, con reintentos e idempotencia.
- Indicador de **divergencia** si el elemento sigue cambiando y el snapshot de Jira queda atrás.

### 3.13 Administración

La capa administrativa gobierna el workspace en tres niveles: workspace, proyecto y elemento.

**Personas**: invitar, activar, suspender y eliminar lógicamente; asignar etiquetas de contexto y capacidades operativas. Estados: invitado, activo, suspendido, eliminado lógico. Suspender a un owner con trabajo activo dispara alerta y exige reasignación.

**Equipos**: crear, mover miembros, asignar lead opcional, declarar si reciben revisiones/validaciones. Una revisión a equipo notifica a todos sus miembros y se cierra cuando uno autorizado responde.

**Proyectos**: agrupan elementos y definen contexto (repositorios, documentación, sistemas relacionados), plantillas, reglas locales y configuración Jira específica si aplica.

**Reglas de validación y routing**: qué validaciones son obligatorias o recomendadas por tipo; qué perfiles/equipos suelen validar; equipo, owner y plantilla sugeridos por tipo + proyecto. Proyecto sobreescribe a workspace salvo restricciones globales bloqueantes.

**Integraciones y plantillas**: alta y configuración de Jira y Puppet con credenciales cifradas, health checks, logs y reintentos manuales. Plantillas por tipo o proyecto, con secciones obligatorias, ayudas contextuales y checklist por defecto.

**Superadmin de plataforma**: crea workspaces, arranca organizaciones nuevas, audita acciones cross-workspace y ejecuta force-unlock.

**Dashboard de salud** en cuatro bloques: workspace (estados, bloqueos, tiempo a `Ready`, revisiones envejecidas), organizativa (miembros sin equipo, owners sobrecargados), proceso (validaciones incumplidas, % overrides, backlog bloqueado) e integraciones (estado de Jira y Puppet, exportaciones fallidas).

**Auditoría** inmutable de acciones sensibles con actor, fecha, entidad y valor previo/nuevo. **Soporte operativo básico**: reasignar owner huérfano, reenviar invitaciones, reintentar exportaciones, consultar quién cambió una regla, detectar elementos bloqueados por configuración.

### 3.14 Capa de inteligencia (Dundun)

La plataforma delega en **Dundun** —capa interna de inteligencia— las tareas que requieren comprensión del lenguaje: chat general del workspace y por elemento, detección de huecos en la especificación, generación y reescritura de secciones con preview, propuesta inicial de desglose, sugerencia de validadores plausibles y de siguiente paso, y asistencia en revisión.

Para el usuario, Dundun es simplemente "el asistente": una presencia integrada en clarificación, chat general y propuestas contextuales. El usuario no configura modelos ni parámetros. Todas las propuestas son **previsibles, aceptables por tramos y reversibles**: nada se aplica sin acción explícita, y toda aceptación genera versión con autor diferenciable en el timeline.

### 3.15 Búsqueda semántica (Puppet)

La búsqueda se apoya en **Puppet**, plataforma interna Tuio de búsqueda semántica. Desde la perspectiva del usuario:

- La barra combina **keyword y semántica** en un resultado único ordenado por relevancia, con **type-ahead** desde el segundo carácter.
- Filtros faceteados: estado, tipo, equipo, owner, tags, archivado.
- Los resultados incluyen snippets que resaltan por qué coincide cada elemento.
- Cubre work items, secciones de especificación y comentarios del workspace actual.
- Desde la misma barra se busca **documentación externa de Tuio** (READMEs, ADRs, docs de proyectos), con resultados diferenciados y trazabilidad de fuente.
- Cada usuario puede **guardar búsquedas** (query + filtros).
- Aislamiento estricto por workspace: un usuario no ve resultados de otro.

El indexado es asíncrono con lag asumido de hasta ~3 segundos. Si Puppet está caído, la búsqueda devuelve error explícito en lugar de fallback silencioso.

### 3.16 Acceso programático (MCP)

La plataforma expone su superficie de **lectura** a agentes externos mediante un servidor **MCP (Model Context Protocol)**. Cualquier cliente MCP estándar —Claude Code, Claude Desktop, copilotos de IDE, CLIs, scripts de reporting u otros agentes— puede consultar el estado del workspace sin tocar la API REST ni la base de datos, con el mismo modelo de permisos que la interfaz web.

**Qué expone**. Un catálogo de ~20 *tools* tipados y 4 *resources* suscribibles, entre otros: detalle y búsqueda de elementos, jerarquía (proyecto → milestone → épica → story → tarea), historial de versiones y diffs, comentarios anclados, revisiones y validaciones, threads del asistente (Dundun), búsqueda semántica (Puppet), tags y labels, metadatos de adjuntos, inbox priorizado, dashboards del workspace, y estado de exportación Jira con indicador de divergencia. Los *resources* `workitem://<id>`, `epic://<id>/tree`, `workspace://<id>/dashboard` y `user://me/inbox` permiten **suscripción en tiempo real**: cambios relevantes llegan al cliente en menos de 2 segundos sobre el mismo bus SSE que usa la UI.

**Qué NO expone** (MVP). No hay *tools* de escritura: ni crear, ni transicionar, ni comentar, ni exportar a Jira, ni aplicar sugerencias de Dundun, ni acciones administrativas. Las operaciones de escritura llegarán en un épico posterior con un modelo de autenticación más estricto y revisión de seguridad dedicada.

**Autenticación y autorización**. El acceso se gobierna con **MCP tokens** emitidos por admins del workspace (capacidad `mcp:issue`). Cada token está vinculado a un **único workspace** (aislamiento estricto, coherente con §3.15), lleva el alcance `mcp:read`, tiene TTL máximo de 90 días (30 por defecto) y puede rotarse o revocarse en cualquier momento. El plaintext del token se muestra **una sola vez** al crearlo; se guarda con argon2id. Un usuario puede tener hasta 10 tokens activos por workspace. Revocar un token surte efecto en ≤ 5 segundos.

La autorización **delega por completo en la capa de aplicación**: el servidor MCP no implementa reglas paralelas; cada *tool* llama al mismo servicio que usa la API REST, con el `actor_id` y `workspace_id` del token. Esto garantiza que cualquier cambio de permisos en la web se refleja automáticamente en MCP.

**Administración**. Desde el panel de administración (ver §3.13) los admins gestionan los tokens MCP de su workspace:

- Emitir un token para un usuario (elige nombre, duración y ve el plaintext una única vez con un diálogo que exige copia o descarga explícita antes de cerrar).
- Listar tokens activos y revocados, con `last_used_at` y `last_used_ip` para detectar uso indebido.
- Rotar un token (invalida el anterior y emite uno nuevo).
- Revocar con confirmación tipeada del nombre.
- Consultar la **auditoría de invocaciones** por token: herramienta llamada, latencia, resultado, código de error, cliente MCP (nombre y versión). Cada invocación MCP se registra en la misma cola de auditoría que el tráfico REST.

Los usuarios finales disponen además de una vista `/settings/mcp-tokens` para ver sus propios tokens y revocarlos sin necesidad de capacidad administrativa.

**Garantías de seguridad**:

- **Aislamiento por workspace**: un token de W nunca devuelve datos de W'. El `workspace_id` proviene exclusivamente del token; los parámetros que lo contradigan devuelven `forbidden`.
- **Política de no-enumeración**: las respuestas no distinguen "no existe" de "no puedes verlo" salvo en el caso seguro de elementos borrados lógicamente en el propio workspace.
- **Rate limiting compartido con REST**: no es una puerta trasera que evite los límites globales.
- **Auditoría inmutable** de cada invocación con hash de parámetros (nunca el cuerpo en claro).
- **Puppet sin fallback silencioso**: si la búsqueda semántica no está disponible, el agente recibe un error explícito.
- **Adjuntos**: MCP devuelve metadatos, nunca el binario; la descarga se obtiene bajo URL firmada de corta duración (≤ 5 min) y vinculada al mismo token.

**Transportes**. El servidor soporta `stdio` (para agentes locales como Claude Code) y HTTP/SSE (para clientes remotos). Ambos activos desde el primer día.

**Para el usuario**, el MCP es simplemente "la forma de dejar que otros agentes lean lo que ya está en la plataforma, con las mismas reglas de permisos y trazabilidad, sin copiar datos a ningún sitio".
