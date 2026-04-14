
# Mega documento — PRD + especificación funcional + modelo operativo + backlog del MVP

> Documento unificado que consolida visión de producto, PRD, especificación funcional, modelo operativo, capa administrativa, reglas de negocio, experiencia, integraciones y backlog de implementación del MVP.

---

## 0. Control del documento

| Campo | Valor |
|---|---|
| Documento | Mega documento del MVP |
| Naturaleza | PRD formal + alineación interna + especificación funcional + backlog |
| Estado | Borrador consolidado |
| Audiencia | Founders, Product, Design, Engineering, QA, Business, Operaciones |
| Alcance | Todo lo descrito forma parte del MVP |
| Dependencias externas | Google OAuth, Jira, fuentes de contexto de proyecto |
| Principio rector | Claridad, validación y trazabilidad antes de ejecución |

---

## 1. Resumen ejecutivo

Este producto nace para resolver un problema estructural: muchas ideas, bugs, requisitos, iniciativas o cambios de negocio entran demasiado pronto en herramientas de ejecución como Jira, sin pasar por una fase sólida de definición, revisión y validación. El resultado habitual es trabajo mal descrito, ownership difuso, demasiadas conversaciones dispersas, criterios de aceptación pobres, revisiones tardías y retrabajo innecesario.

La propuesta es construir una capa intermedia y autónoma de **maduración del trabajo**. El sistema debe permitir capturar un input ambiguo, aterrizarlo, estructurarlo, revisarlo, validarlo, desglosarlo y llevarlo a un estado `Ready` con control humano explícito. Después, y solo si el equipo lo decide, podrá exportarse a Jira.

El producto no debe entenderse como un simple generador de tareas. Debe ser el lugar donde el trabajo se **define bien** antes de ejecutarse. Por eso el MVP incluye cuatro dimensiones inseparables:

1. **Definición estructurada del trabajo**: transformar inputs vagos en especificaciones y desgloses útiles.
2. **Gobierno del flujo**: ownership único, validaciones, revisiones y paso controlado a `Ready`.
3. **Workspace autónomo**: listados, inbox, dashboards, histórico, búsqueda y trabajo completo sin depender de Jira.
4. **Capa administrativa y operativa**: configuración del workspace, equipos, acceso, reglas, integraciones, plantillas, auditoría y salud del sistema.

El valor diferencial del producto es que separa claramente la fase de **definición** de la fase de **ejecución**, preservando trazabilidad entre ambas.

---

## 2. Tesis del producto

### 2.1 Problema principal

Los equipos reciben trabajo en estados demasiado inmaduros. Una idea verbal, una necesidad del negocio, un bug reportado de forma parcial o un requisito sin criterios claros suele traducirse de forma prematura en un ticket operativo. Eso provoca:

- ambigüedad sobre qué hay que hacer realmente;
- pérdida de contexto entre reuniones, mensajes, documentos y tickets;
- validaciones de negocio, QA o tech que llegan demasiado tarde;
- falta de ownership claro;
- degradación de la calidad del desglose en tareas;
- retrabajo durante la ejecución;
- imposibilidad de reconstruir con claridad cómo se tomó una decisión.

### 2.2 Hipótesis de solución

Si el equipo dispone de una capa intermedia donde el trabajo se captura, aclara, revisa, valida y madura antes de enviarse a ejecución, entonces:

- aumentará la calidad del input operativo;
- se reducirá el retrabajo;
- mejorará la colaboración asíncrona entre perfiles;
- se hará visible qué falta para avanzar;
- se reducirá la dependencia del conocimiento tácito;
- mejorará la trazabilidad entre la idea original y el trabajo ejecutado.

### 2.3 Posicionamiento funcional

El producto debe posicionarse como:

- sistema de definición y maduración del trabajo;
- workspace autónomo previo a ejecución;
- orquestador asíncrono de revisión y validación;
- capa de claridad y trazabilidad antes de Jira.

No debe posicionarse como:

- sustituto completo de toda la operativa de Jira;
- herramienta principal de sprint planning o capacity planning;
- simple interfaz de redacción para tickets.

---

## 3. Objetivos y no objetivos

### 3.1 Objetivo principal

Ayudar a equipos de producto, tecnología, negocio y QA a convertir inputs ambiguos en elementos bien definidos, revisables, validados y listos para ejecución.

### 3.2 Objetivos específicos

- Capturar ideas, bugs, requisitos y cambios desde texto libre.
- Guiar al usuario para aterrizar el contenido mediante preguntas y sugerencias.
- Convertir el input inicial en una especificación estructurada y editable.
- Desglosar la especificación en tareas y subtareas trazables.
- Hacer explícitas las validaciones necesarias y el siguiente paso recomendado.
- Permitir colaboración asíncrona sobre el mismo elemento con histórico completo.
- Garantizar ownership único y responsabilidad clara.
- Permitir operar de extremo a extremo sin Jira.
- Exportar a Jira solo la versión final aprobada y mediante acción explícita.
- Mantener trazabilidad entre origen, decisiones, revisiones y resultado final.
- Proveer una capa administrativa clara para gobernar workspace, personas, equipos, reglas e integraciones.

### 3.3 No objetivos

No son objetivos principales del MVP:

- sustituir toda la ejecución posterior a `Ready`;
- ofrecer edición colaborativa en tiempo real como primera prioridad;
- construir un RBAC complejo basado en roles funcionales tipo producto o QA;
- automatizar completamente el paso a `Ready` sin criterio humano;
- convertirse en una suite generalista de gestión empresarial.

---

## 4. Usuarios, perfiles y audiencias

### 4.1 Usuarios principales

| Perfil | Qué trae al sistema | Qué espera del sistema |
|---|---|---|
| Product Manager | ideas, requisitos, priorización, definiciones | claridad, estructura, revisión, alineación |
| Tech Lead | viabilidad, dependencias, desglose técnico | contexto, riesgos, criterios, ownership |
| Founder | visión, necesidades transversales, decisiones | velocidad de captura, visibilidad global |
| Equipo de producto | refinamiento, coordinación, decisiones | colaboración ordenada y trazable |
| Equipo de tecnología | definición operativa, riesgos, breakdown | menos ambigüedad, mejor calidad de entrada |
| Negocio | cambios, reglas, impacto esperado | visibilidad, feedback, validación funcional |
| QA | validación de testabilidad y completitud | criterios claros, checklist, huecos visibles |

### 4.2 Perfiles operativos adicionales

Para que el sistema funcione de forma realista en un entorno organizativo, el MVP debe contemplar además estos perfiles operativos:

| Perfil operativo | Responsabilidad principal |
|---|---|
| Workspace Admin | gobierno general del workspace, miembros, equipos, reglas e integraciones |
| Project Admin | configuración específica de proyectos, contexto y reglas locales |
| Integration Admin | gestión técnica/funcional de integraciones como Jira |
| Team Lead | coordinación de revisiones, carga del equipo y visibilidad operativa |
| Member | usuario estándar que crea, edita, revisa y colabora |

> Importante: estos perfiles operativos no contradicen la definición previa de que los roles de negocio o contexto en el MVP funcionan como etiquetas. Aquí se distinguen dos capas diferentes: **etiquetas de contexto** y **capacidades administrativas/operativas**.

### 4.3 Audiencias del documento

Este megadocumento está escrito para servir simultáneamente a:

- dirección y founders, para alinear la visión;
- producto y diseño, para definir experiencia y comportamiento;
- ingeniería, para entender el dominio y el backlog;
- QA, para validar reglas y criterios;
- operaciones internas, para gobernar la parte de administración y mantenimiento del sistema.

---

## 5. Principios del producto

1. **Claridad antes que velocidad**  
   La prioridad no es producir tickets rápido, sino producir trabajo bien definido.

2. **Refinamiento progresivo**  
   El sistema asume que la calidad emerge por iteraciones sucesivas.

3. **Control humano en todo momento**  
   El sistema sugiere, estructura y guía, pero no sustituye la decisión final del owner.

4. **Separación entre definición y ejecución**  
   Definir bien el trabajo es una fase propia y diferenciada.

5. **Ownership claro**  
   Cada elemento debe tener una única persona responsable.

6. **Colaboración asíncrona con trazabilidad**  
   Las conversaciones, revisiones y decisiones deben poder recuperarse después.

7. **Máximo detalle razonable antes de exportar**  
   El sistema debe empujar hacia el mayor nivel posible de completitud.

8. **Autonomía sin Jira**  
   El sistema debe ser valioso incluso sin integración externa.

9. **Flujo guiado, no rígido en exceso**  
   Debe existir control, pero sin eliminar capacidad de decisión del owner.

10. **Administración explícita y gobernable**  
    El sistema no debe depender de configuraciones tácitas o de conocimiento informal para funcionar.

---

## 6. Alcance del MVP

Todo lo descrito en este documento entra en el MVP. No se hará una separación formal entre MVP, V1 y V2. El alcance del MVP incluye:

- captura de elementos desde texto libre;
- clarificación guiada;
- especificación estructurada;
- desglose en tareas y subtareas;
- revisiones y validaciones asíncronas;
- ownership único;
- estados de madurez;
- sistema de comentarios, versiones e histórico;
- inbox personal;
- dashboards y listados;
- equipos y asignaciones;
- administración del workspace;
- configuración de reglas y contexto;
- integración opcional con Jira;
- funcionamiento completo sin Jira;
- experiencia responsive y recuperación de conversaciones.

---

## 7. Modelo funcional y de dominio

### 7.1 Entidades principales

| Entidad | Descripción |
|---|---|
| Workspace | contenedor principal donde viven usuarios, equipos, proyectos, reglas e integraciones |
| Proyecto / espacio | ámbito lógico de trabajo dentro del workspace |
| Elemento | unidad principal a madurar: idea, bug, mejora, tarea, iniciativa, spike, cambio de negocio o requisito |
| Especificación | representación estructurada del elemento |
| Tarea | unidad de trabajo derivada del elemento o de su especificación |
| Subtarea | unidad hija de una tarea |
| Revisión | solicitud de feedback o aprobación a una persona o equipo |
| Validación | requisito funcional o de calidad necesario o recomendado para avanzar |
| Conversación | hilo de interacción con el sistema o con personas sobre un elemento |
| Comentario | feedback general o anclado sobre una parte concreta del contenido |
| Versión | snapshot del contenido del elemento en un momento dado |
| Diff | comparación entre dos versiones |
| Equipo | grupo de usuarios que puede recibir revisiones, validaciones o trabajo |
| Notificación | evento interno que requiere atención o informa de un cambio |
| Exportación | snapshot final enviado a Jira |
| Configuración | reglas, plantillas, contexto, integraciones y parámetros del workspace/proyecto |
| Auditoría | registro de acciones administrativas y funcionales relevantes |

### 7.2 Tipos de elemento

El sistema debe soportar, como mínimo:

- Idea
- Bug
- Mejora
- Tarea
- Iniciativa
- Spike / investigación
- Cambio de negocio
- Requisito

Todos comparten un flujo común de maduración. Las diferencias entre tipos afectan sobre todo a:

- la plantilla inicial;
- las sugerencias del sistema;
- las validaciones recomendadas;
- ciertos campos o secciones de la especificación.

### 7.3 Estructura del elemento

Cada elemento debe poder contener:

- identificación básica: ID, título, tipo, owner, estado, creador, fechas;
- input original y notas iniciales;
- especificación estructurada;
- tareas y subtareas derivadas;
- revisiones activas y cerradas;
- checklist de validaciones;
- comentarios y conversaciones;
- versiones y diffs;
- bloqueos y dependencias;
- nivel de completitud;
- siguiente paso recomendado;
- contexto del proyecto;
- información de exportación si existe.

### 7.4 Jerarquía funcional

La jerarquía mínima soportada será:

- Elemento principal
  - Tareas
    - Subtareas

Reglas:

- la jerarquía debe ser visible, navegable y editable;
- toda tarea y subtarea debe mantener vínculo con el elemento origen;
- el usuario debe poder entender de qué parte de la especificación nace el desglose;
- la jerarquía puede reordenarse, dividirse o fusionarse.

### 7.5 Modelo de ownership

- Todo elemento tiene un único owner.
- El owner es la persona responsable de llevar el elemento hasta `Ready`.
- El owner puede cambiarse manualmente.
- Solo el owner puede marcar `Ready`.
- El owner puede forzar `Ready` aunque falten validaciones, dejando justificación trazable.
- Todo feedback vuelve al owner como responsable final.

### 7.6 Colaboración asíncrona

La colaboración del MVP es asíncrona:

- las revisiones no requieren coincidencia temporal;
- el sistema debe preservar el contexto de todas las interacciones;
- el usuario debe poder retomar el trabajo donde lo dejó;
- las decisiones deben quedar ancladas a contenido y versiones concretas.

### 7.7 Revisión vs validación

El sistema debe diferenciar estos conceptos:

- **Revisión**: solicitud de feedback, aprobación o cambios.
- **Validación**: requisito de calidad o madurez que puede bloquear el avance.

Una revisión puede contribuir a cerrar una validación cuando:

- se solicita al perfil o equipo adecuado;
- el revisor emite una respuesta válida;
- el checklist del elemento se actualiza.

### 7.8 Completitud, detalle y madurez

El sistema debe calcular en backend un indicador de completitud. La fórmula exacta puede evolucionar, pero debe contemplar, como mínimo:

- claridad del problema o necesidad;
- objetivo esperado;
- alcance definido;
- criterios de aceptación;
- dependencias y riesgos;
- validaciones relevantes;
- desglose en tareas cuando aplique;
- ownership y siguiente paso.

La UI debe mostrar:

- un nivel visual simple: bajo, medio, alto, o porcentaje;
- los huecos detectados;
- el siguiente paso recomendado.

### 7.9 Bloqueos y dependencias

El sistema debe soportar:

- bloqueos por validaciones pendientes;
- bloqueos por falta de información;
- bloqueos por dependencias funcionales;
- motivo explícito del bloqueo;
- sugerencia clara de desbloqueo.

---

## 8. Estados, ciclo de vida y reglas de transición

### 8.1 Estados principales

| Estado | Significado |
|---|---|
| Borrador | existe el elemento, pero aún no está suficientemente definido |
| En clarificación | se está aterrizando el contenido |
| En revisión | el elemento espera respuesta de revisores o validadores |
| Con cambios solicitados | se han pedido cambios explícitos |
| Validado parcialmente | algunas validaciones se han completado, pero no todas |
| Ready | el owner declara que el trabajo está listo |
| Exportado | la versión final aprobada ha sido enviada a Jira |

### 8.2 Estado operativo derivado

Además del estado principal, el sistema debe mostrar:

| Estado derivado | Regla |
|---|---|
| En progreso | el elemento sigue madurando y no está bloqueado |
| Bloqueado | existe una dependencia o validación pendiente que impide avanzar |
| Ready | el elemento ya está en estado `Ready` |

### 8.3 Reglas de transición

- `Borrador` puede pasar a `En clarificación`.
- `En clarificación` puede pasar a `En revisión`, `Con cambios solicitados`, `Validado parcialmente` o `Ready`.
- `En revisión` puede derivar en `Con cambios solicitados`, `Validado parcialmente` o volver al owner para iterar.
- `Con cambios solicitados` vuelve a clarificación o a revisión.
- `Validado parcialmente` puede continuar revisándose o pasar a `Ready`.
- `Ready` puede pasar a `Exportado` mediante acción explícita.
- Un cambio sustancial sobre un elemento `Ready` antes de exportar puede obligar a recalcular madurez y devolverlo a una fase anterior.
- El sistema debe impedir la transición normal a `Ready` si faltan validaciones obligatorias, salvo override del owner.

### 8.4 Reglas de override

Cuando el owner fuerza `Ready`:

- el sistema debe pedir confirmación explícita;
- debe solicitar un motivo;
- debe dejar trazabilidad visible;
- debe indicar que existe una excepción respecto a validaciones pendientes.

---

## 9. Flujos end-to-end principales

### 9.1 Crear un elemento desde texto libre

1. El usuario inicia creación.
2. Introduce texto libre y selecciona tipo.
3. Añade contexto inicial, notas u objetivo si los tiene.
4. El sistema crea el elemento en `Borrador`.
5. El creador queda como owner por defecto, salvo reasignación.
6. El sistema muestra completitud inicial y siguiente paso recomendado.

### 9.2 Clarificar y estructurar

1. El usuario abre el elemento.
2. Responde preguntas o solicita ayuda al sistema.
3. El sistema detecta huecos y formula preguntas.
4. Propone o actualiza una especificación estructurada.
5. El usuario revisa la propuesta y aplica cambios completos o parciales.
6. Se genera nueva versión.

### 9.3 Desglosar en tareas y subtareas

1. El usuario pide desglose.
2. El sistema genera tareas principales.
3. Donde corresponda, propone subtareas.
4. El usuario edita, divide, fusiona o reordena.
5. Se preserva vínculo entre especificación y desglose.

### 9.4 Solicitar revisión

1. El owner envía el elemento a usuarios o equipos.
2. El sistema crea solicitudes explícitas.
3. Los destinatarios reciben notificación.
4. Revisan, comentan, editan, aprueban o piden cambios.
5. El resultado vuelve al owner.
6. El checklist de validación se actualiza cuando corresponde.

### 9.5 Llegar a `Ready`

1. El owner revisa el estado del elemento.
2. El sistema muestra completitud, bloqueos, validaciones y siguiente paso.
3. Si todo está completo, el owner marca `Ready`.
4. Si faltan validaciones, el sistema bloquea el flujo normal.
5. El owner puede hacer override con justificación.

### 9.6 Exportar a Jira

1. El usuario autorizado pulsa `Enviar a Jira`.
2. El sistema verifica que el elemento está en `Ready`.
3. Exporta el snapshot final aprobado.
4. Guarda la referencia Jira.
5. Muestra la relación entre elemento interno y ticket externo.
6. Sincroniza al menos el estado básico.

### 9.7 Operar sin Jira

1. El equipo crea, refina, revisa y valida dentro del sistema.
2. Usa inbox, listados, vistas detalle, dashboards y búsqueda.
3. El sistema actúa como fuente de verdad de la fase de definición.
4. La exportación a Jira sigue siendo opcional.

---

## 10. Requisitos funcionales detallados del producto

### 10.1 Captura de elementos

El sistema debe:

- permitir crear un elemento desde texto libre;
- permitir elegir tipo de elemento;
- registrar contexto inicial, objetivo y notas;
- guardar borradores aunque falte información;
- conservar el input original;
- asociar owner desde la creación.

**Criterios de aceptación**

- un usuario autenticado puede crear un elemento sin completar todos los campos;
- el elemento queda en `Borrador`;
- el sistema preserva el texto original;
- el owner es visible desde el inicio;
- el elemento aparece en listados internos.

### 10.2 Clarificación guiada

El sistema debe:

- detectar vacíos de información;
- formular preguntas útiles;
- sugerir qué falta antes de avanzar;
- permitir iteraciones sucesivas;
- mantener la conversación asociada al elemento.

**Criterios de aceptación**

- el sistema puede señalar carencias relevantes;
- el usuario puede responder y mejorar el elemento iterativamente;
- la conversación queda guardada;
- el usuario puede retomar más tarde sin perder contexto.

### 10.3 Especificación estructurada

El sistema debe:

- transformar un elemento en una especificación estructurada;
- organizar la información en secciones coherentes;
- permitir edición manual;
- mantener versiones;
- adaptar la estructura al tipo de elemento.

**Criterios de aceptación**

- el usuario puede ver una estructura legible del elemento;
- puede editar sus secciones;
- los cambios generan histórico;
- la especificación sigue siendo consistente entre tipos.

### 10.4 Desglose de trabajo

El sistema debe:

- convertir la especificación en tareas;
- generar subtareas cuando aplique;
- mantener jerarquía y trazabilidad;
- permitir edición manual del breakdown.

**Criterios de aceptación**

- el elemento puede contener tareas y subtareas;
- la jerarquía se ve de forma clara;
- el usuario puede reordenar, dividir o fusionar;
- el origen del desglose sigue siendo rastreable.

### 10.5 Refinamiento iterativo

El sistema debe:

- permitir múltiples iteraciones;
- aceptar propuestas completas o parciales;
- mostrar diff entre versiones;
- mantener histórico comprensible.

**Criterios de aceptación**

- el usuario puede iterar tantas veces como necesite;
- cada cambio relevante queda versionado;
- el diff muestra qué cambió;
- el historial permite entender la evolución.

### 10.6 Gestión de estados

El sistema debe:

- reflejar el estado principal y operativo;
- mostrar bloqueos y dependencias;
- recalcular madurez cuando cambie el contenido;
- mostrar el siguiente paso recomendado.

**Criterios de aceptación**

- el estado es visible siempre;
- el usuario entiende por qué algo está bloqueado;
- el siguiente paso se muestra de forma explícita;
- los cambios de estado se auditan.

### 10.7 Validación de calidad

El sistema debe:

- detectar elementos incompletos o ambiguos;
- señalar ausencia de criterios, contexto o definiciones;
- sugerir validadores;
- controlar el acceso a `Ready`.

**Criterios de aceptación**

- el sistema identifica huecos funcionales;
- muestra validaciones requeridas;
- recomienda perfiles como QA, negocio o tech;
- el owner puede hacer override, pero nunca de forma invisible.

### 10.8 Colaboración y revisión

El sistema debe:

- permitir solicitar revisión a usuarios o equipos;
- permitir aprobación, rechazo o cambios solicitados;
- permitir comentarios generales y anclados;
- permitir edición directa por revisores;
- devolver siempre el resultado al owner.

**Criterios de aceptación**

- un owner puede asignar revisiones explícitas;
- los revisores pueden comentar y editar;
- el resultado queda registrado con actor y fecha;
- si la revisión es a un equipo, todos sus miembros son notificados.

### 10.9 Historial y trazabilidad

El sistema debe:

- registrar versiones y cambios relevantes;
- mantener relación entre input original y contenido final;
- mostrar timeline de decisiones;
- distinguir cambios humanos, sugerencias y exportaciones.

**Criterios de aceptación**

- el usuario puede reconstruir la historia del elemento;
- las versiones son navegables;
- el timeline incluye cambios de estado, revisiones y exportaciones;
- la trazabilidad se mantiene tras exportar a Jira.

### 10.10 Workspace autónomo

El sistema debe incluir:

- listado de elementos;
- vista detalle;
- inbox personal;
- tablero o lista de revisiones;
- dashboard general por estado;
- dashboard por responsable;
- dashboard por equipo;
- búsqueda y filtrado;
- notificaciones internas;
- histórico y trazabilidad completos.

**Criterios de aceptación**

- el flujo completo funciona aunque Jira no esté configurado;
- el usuario puede trabajar de extremo a extremo dentro del sistema;
- la experiencia principal no depende de una herramienta externa.

### 10.11 Exportación a Jira

El sistema debe:

- exportar únicamente mediante acción explícita;
- enviar solo elementos en `Ready`;
- exportar el snapshot final aprobado;
- guardar la referencia Jira;
- reflejar el estado básico del ticket externo;
- no modificar el contenido en Jira de forma automática tras exportar.

**Criterios de aceptación**

- no existe exportación silenciosa ni automática;
- el sistema impide exportar un elemento no `Ready`;
- tras exportar, el usuario ve el ticket vinculado;
- el snapshot exportado queda identificado.

### 10.12 Modos de interacción con el sistema

El MVP debe soportar cuatro modos principales:

1. **Chat general de refinamiento**  
   para aterrizar ideas y recuperar conversaciones.

2. **Mejora contextual sobre un elemento**  
   para pedir reescrituras, concreción o mejora desde la vista detalle.

3. **Revisión asistida**  
   para analizar calidad, completitud y gaps de validación.

4. **Asistencia en definición**  
   para sugerir criterios de aceptación, preguntas pendientes, riesgos y desgloses.

---

## 11. Vistas, navegación y experiencia principal

### 11.1 Vistas mínimas

| Vista | Objetivo |
|---|---|
| Inbox | concentrar la acción pendiente del usuario |
| Dashboard de trabajo | explorar y filtrar elementos |
| Dashboard global | ver estado agregado del sistema |
| Dashboard por equipo | ver carga y pendientes por equipo |
| Dashboard por responsable | ver ownership y carga por persona |
| Vista de flujo | entender el pipeline de maduración |
| Vista detalle de elemento | trabajar el contenido completo |
| Tablero/lista de revisiones | responder revisiones activas |
| Buscador y filtros | recuperar contexto rápidamente |

### 11.2 Inbox

Debe mostrar como mínimo:

- elementos a revisar;
- elementos devueltos al usuario;
- elementos pendientes de decisión;
- bloqueos causados por el usuario;
- prioridad visual para lo más accionable.

### 11.3 Vista detalle de elemento

La vista detalle debe reunir:

- cabecera con tipo, owner, estado y completitud;
- siguiente paso recomendado;
- especificación;
- tareas y subtareas;
- checklist de validación;
- revisiones activas y cerradas;
- comentarios y conversaciones;
- historial y diff;
- referencia Jira si existe.

### 11.4 Experiencia móvil

El sistema debe ser responsive y permitir, como mínimo en móvil:

- revisar el inbox;
- abrir un elemento;
- responder revisiones;
- consultar bloqueos;
- ejecutar acciones críticas.

---

## 12. Parte administrativa y operativa ampliada

> Esta sección amplía de forma explícita la parte de administración para que el producto no dependa de una configuración informal. Aquí se define cómo se gobierna el workspace, quién puede administrar qué, cómo se estructuran personas, equipos, proyectos, reglas, integraciones, auditoría y operaciones de soporte.

### 12.1 Objetivos de la capa de administración

La capa administrativa debe permitir:

- arrancar el sistema en un workspace real;
- gobernar acceso, miembros y equipos;
- definir reglas de validación y routing;
- configurar contexto por proyecto;
- gestionar integraciones externas;
- supervisar salud de uso y de operación;
- auditar acciones sensibles;
- operar incidencias básicas sin intervención técnica ad hoc.

### 12.2 Principios de administración

1. La administración debe ser visible, no implícita.
2. Los permisos operativos deben estar separados de los roles contextuales.
3. Toda acción administrativa relevante debe quedar auditada.
4. El sistema debe ser usable incluso con configuración mínima.
5. La configuración por defecto debe ser segura y razonable.
6. Las reglas del workspace deben poder especializarse por proyecto.
7. La capa admin no debe convertir el sistema en una burocracia compleja.

### 12.3 Modelo administrativo general

Se propone una estructura de administración en tres niveles:

| Nivel | Qué gobierna |
|---|---|
| Workspace | miembros, equipos globales, integraciones, reglas generales, dashboards globales |
| Proyecto / espacio | contexto, validaciones específicas, templates, routing, dashboards locales |
| Elemento | owner, revisores, validaciones concretas, estado y colaboración del caso individual |

### 12.4 Tipos de actores administrativos

#### Workspace Admin

Responsable del gobierno general del entorno. Puede:

- invitar y desactivar miembros;
- crear y gestionar equipos;
- definir reglas generales de validación;
- configurar integraciones;
- acceder a auditoría y dashboards administrativos;
- gestionar configuración base del workspace.

#### Project Admin

Responsable de una porción concreta del sistema. Puede:

- configurar contexto de proyecto;
- ajustar reglas y plantillas locales;
- visualizar métricas del proyecto;
- coordinar equipos asociados al proyecto;
- revisar salud del flujo dentro de su ámbito.

#### Integration Admin

Perfil especializado en integraciones. Puede:

- configurar Jira;
- revisar logs de sincronización;
- forzar reintentos;
- validar mappings y health checks;
- supervisar errores de exportación.

#### Team Lead

Perfil operativo no necesariamente administrador completo. Puede:

- ver carga de su equipo;
- coordinar revisiones;
- detectar cuellos de botella;
- reasignar trabajo dentro del marco permitido;
- impulsar cierres de validación.

#### Member

Usuario estándar. Puede:

- crear elementos;
- editar contenido permitido;
- revisar cuando se le asigna;
- comentar y colaborar;
- usar el sistema sin capacidades administrativas globales.

### 12.5 Etiquetas de contexto vs permisos operativos

El sistema debe separar dos conceptos:

#### Etiquetas de contexto
Son perfiles funcionales como:

- producto,
- desarrollo,
- negocio,
- QA.

Sirven para:

- dar contexto al sistema;
- enrutar sugerencias;
- filtrar vistas;
- sugerir validadores.

#### Permisos operativos
Son capacidades de administración y gobierno como:

- invitar miembros;
- crear equipos;
- configurar reglas;
- conectar Jira;
- ver auditoría;
- gestionar proyectos.

**Regla clave**  
Las etiquetas de contexto no deben convertirse implícitamente en permisos administrativos.

### 12.6 Modelo de permisos operativos del MVP

Aunque el MVP no necesita un RBAC complejo, sí necesita una matriz de capacidades operativas clara.

| Capacidad | Member | Team Lead | Project Admin | Workspace Admin | Integration Admin |
|---|---|---|---|---|---|
| Crear elementos | Sí | Sí | Sí | Sí | Sí |
| Editar elementos propios o asignados | Sí | Sí | Sí | Sí | Sí |
| Solicitar revisiones | Sí | Sí | Sí | Sí | Sí |
| Marcar `Ready` si es owner | Sí | Sí | Sí | Sí | Sí |
| Forzar `Ready` si es owner | Sí | Sí | Sí | Sí | Sí |
| Reasignar owner | Limitado | Limitado | Sí | Sí | No necesariamente |
| Crear equipos | No | No | Opcional según ámbito | Sí | No |
| Gestionar miembros de equipos | No | Parcial | Sí | Sí | No |
| Invitar miembros al workspace | No | No | Opcional | Sí | No |
| Desactivar miembros | No | No | No | Sí | No |
| Configurar reglas de validación globales | No | No | No | Sí | No |
| Configurar reglas por proyecto | No | No | Sí | Sí | No |
| Configurar contexto de proyecto | No | No | Sí | Sí | No |
| Configurar Jira | No | No | Opcional | Sí | Sí |
| Ver logs de integración | No | No | Opcional | Sí | Sí |
| Ver auditoría administrativa | No | No | Parcial | Sí | Parcial |
| Ver dashboards globales admin | No | No | Parcial | Sí | Parcial |

> En implementación, algunas capacidades marcadas como “Opcional” pueden resolverse como permisos delegables dentro del workspace, sin construir un RBAC demasiado sofisticado.

### 12.7 Workspace: ciclo de vida administrativo

El workspace debe soportar al menos:

- creación inicial;
- configuración básica;
- activación operativa;
- mantenimiento;
- archivo o desactivación parcial.

#### Creación inicial
Incluye:

- nombre del workspace;
- dominio de acceso si aplica;
- primer administrador;
- configuración inicial de autenticación;
- primer conjunto de equipos/proyectos si procede.

#### Activación operativa
Debe incluir:

- invitación de miembros;
- definición de equipos;
- configuración mínima de reglas;
- activación del inbox y dashboards;
- configuración opcional de Jira.

#### Mantenimiento
Debe incluir:

- altas y bajas de miembros;
- revisión de equipos;
- actualización de reglas;
- revisión de integraciones;
- seguimiento de cuellos de botella.

#### Archivo o desactivación
Debe contemplar:

- conservación de histórico;
- restricción de cambios;
- mantenimiento de acceso a auditoría;
- tratamiento claro de elementos abiertos.

### 12.8 Gestión de miembros y acceso

La administración de personas debe incluir:

- invitación de nuevos usuarios;
- asociación a uno o varios equipos;
- asignación de etiquetas de contexto;
- asignación de capacidades operativas cuando corresponda;
- activación, suspensión o eliminación lógica.

#### Estados de miembro sugeridos

| Estado | Significado |
|---|---|
| Invitado | existe invitación, pero aún no ha accedido |
| Activo | puede operar normalmente |
| Suspendido | no puede operar, pero su histórico se conserva |
| Eliminado lógicamente | sale del workspace, manteniendo trazabilidad histórica |

#### Reglas de gestión de miembros

- un miembro suspendido no debe recibir nuevas asignaciones;
- un owner suspendido debe disparar una alerta administrativa y requerir reasignación;
- la eliminación lógica no borra auditoría ni participación histórica;
- las invitaciones deben poder reenviarse;
- el sistema debe detectar miembros sin equipo o sin contexto relevante cuando eso afecte al routing.

### 12.9 Gestión de equipos

La administración de equipos debe permitir:

- crear equipos;
- editar nombre y descripción;
- añadir o quitar miembros;
- asociar un líder de equipo si se desea;
- definir si el equipo puede ser destinatario de revisión y validación;
- usar el equipo en dashboards y filtros.

#### Reglas funcionales sobre equipos

- si una revisión se asigna a un equipo, todos sus miembros reciben notificación;
- la revisión debe considerarse respondida cuando un miembro autorizado emite una respuesta final válida;
- el sistema debe dejar trazabilidad de qué miembro respondió en nombre del equipo;
- el equipo no sustituye al owner, solo canaliza trabajo o validación.

### 12.10 Gestión de proyectos o espacios de trabajo

El sistema debe permitir una organización por proyectos o espacios dentro del workspace para:

- agrupar elementos;
- aplicar contexto específico;
- aplicar reglas locales;
- aislar dashboards o filtros;
- asociar equipos habituales.

Cada proyecto o espacio debería poder definir:

- nombre y descripción;
- equipos asociados;
- fuentes de contexto;
- plantillas por defecto;
- validaciones recomendadas u obligatorias;
- reglas de routing;
- configuración Jira si es específica.

### 12.11 Configuración de reglas de validación

La capa admin debe permitir definir reglas como:

- qué validaciones son obligatorias por tipo de elemento;
- qué validaciones son recomendadas;
- en qué orden sugerido deben pedirse;
- qué perfiles o equipos suelen ser validadores adecuados;
- si una validación puede satisfacerse con revisión de un equipo o de una persona concreta.

#### Ejemplos de reglas configurables

- Un bug crítico requiere validación tech y QA.
- Un cambio de negocio requiere validación de negocio.
- Una iniciativa puede requerir validación cruzada de producto y tech antes de `Ready`.
- Un spike puede no requerir desglose fino, pero sí claridad del objetivo y del resultado esperado.

### 12.12 Configuración de routing y sugerencias

Además de las validaciones, el sistema debe permitir definir reglas de routing como:

- equipo sugerido por tipo de elemento;
- validador sugerido por etiqueta de contexto;
- owner sugerido por proyecto;
- plantilla sugerida por combinación de proyecto + tipo.

Estas reglas deben ser guías automáticas, no decisiones irreversibles.

### 12.13 Plantillas y configuración por defecto

La capa administrativa debe permitir definir:

- plantillas por tipo de elemento;
- plantillas por proyecto;
- secciones obligatorias o recomendadas;
- prompts o ayudas contextuales iniciales;
- checklist de validación por defecto;
- estructura de desglose recomendada.

Esto permite estandarizar sin volver rígido el flujo.

### 12.14 Configuración de contexto del proyecto

La administración debe permitir asociar contexto a un proyecto o espacio:

- repositorios relevantes;
- sistemas relacionados;
- documentación de referencia;
- proyectos conectados;
- fuentes de información seleccionadas.

El objetivo no es solo guardar enlaces, sino permitir que el sistema utilice ese contexto para enriquecer sugerencias, revisión y completitud.

### 12.15 Configuración de integraciones

En el MVP la integración prioritaria es Jira. La administración debe cubrir:

- alta de la integración;
- configuración de credenciales;
- asociación con proyectos si aplica;
- definición de mappings básicos;
- health check;
- logs de exportación;
- posibilidad de reintento;
- visibilidad del último estado de sincronización.

### 12.16 Observabilidad administrativa

La administración debe disponer de visibilidad sobre la salud del sistema:

- número de elementos por estado;
- revisiones pendientes envejecidas;
- validaciones bloqueadas;
- owners sobrecargados;
- equipos con exceso de pendientes;
- frecuencia de overrides a `Ready`;
- fallos de exportación a Jira;
- miembros inactivos;
- elementos sin owner válido;
- invitaciones no aceptadas.

### 12.17 Dashboard administrativo

Se recomienda una vista administrativa con, como mínimo, estos bloques:

#### Salud del workspace
- elementos por estado;
- bloqueos críticos;
- tiempo medio hasta `Ready`;
- revisiones pendientes antiguas.

#### Salud organizativa
- miembros activos;
- miembros sin equipo;
- equipos sin líder o sin uso;
- owners con mayor carga.

#### Salud del proceso
- validaciones más incumplidas;
- porcentaje de elementos con override;
- ratio de elementos exportados vs no exportados;
- backlog bloqueado por tipo o equipo.

#### Salud de integraciones
- estado de Jira;
- exportaciones exitosas/fallidas;
- última sincronización;
- errores frecuentes.

### 12.18 Auditoría administrativa

Toda acción administrativa relevante debe quedar auditada, al menos para:

- invitaciones;
- altas/bajas/suspensiones de miembros;
- cambios de permisos operativos;
- creación y edición de equipos;
- cambios de reglas de validación;
- cambios de routing;
- configuración o edición de integraciones;
- cambios de contexto por proyecto;
- reintentos o acciones manuales sobre exportaciones;
- override de operaciones sensibles.

La auditoría debe registrar:

- actor;
- fecha y hora;
- acción;
- entidad afectada;
- valor previo y nuevo cuando aplique;
- contexto de la acción.

### 12.19 Soporte operativo y herramientas administrativas

Aunque no sea una consola avanzada de soporte, el MVP debería permitir ciertas operaciones de mantenimiento sin acudir a ingeniería:

- reasignar owner de elementos huérfanos;
- reactivar o suspender miembros;
- reenviar invitaciones;
- reintentar exportaciones Jira fallidas;
- forzar sincronización básica;
- revisar logs recientes;
- consultar quién cambió una regla;
- detectar elementos bloqueados por configuración.

### 12.20 Casos límite administrativos a contemplar

- El owner es suspendido o eliminado.
- Se borra o desactiva un equipo que tiene revisiones activas.
- Un proyecto cambia sus reglas de validación y hay elementos en curso.
- Jira se desconfigura o falla cuando hay exportaciones pendientes.
- Un usuario tiene varias etiquetas de contexto y varias afiliaciones de equipo.
- Dos admins cambian la misma regla simultáneamente.
- Un workspace no configura equipos, pero sí quiere operar el producto.
- Un elemento pertenece a un proyecto archivado.
- Un revisor responde en nombre de un equipo y otro miembro responde después.
- Un admin cambia el contexto de proyecto y eso altera las sugerencias futuras.

### 12.21 Criterios de aceptación de la capa administrativa

- existe una sección de configuración del workspace;
- existe una gestión de miembros y equipos operable;
- el sistema diferencia perfiles contextuales de capacidades administrativas;
- pueden definirse reglas básicas de validación y routing;
- puede configurarse Jira sin romper el resto del sistema;
- existe auditoría de acciones administrativas;
- el workspace puede operar con configuración mínima y crecer en complejidad después.

---

## 13. Reglas de negocio, permisos y gobierno funcional

### 13.1 Reglas confirmadas

1. Cada elemento tiene un único owner.
2. Solo el owner puede marcar `Ready`.
3. El owner puede forzar `Ready` con justificación.
4. Las validaciones son bloqueantes por defecto.
5. Si una revisión se asigna a un equipo, la notificación llega a todos sus miembros.
6. Los revisores pueden editar el contenido del elemento.
7. Los roles de contexto no gobiernan por sí solos los permisos.
8. La colaboración es asíncrona.
9. Solo la versión final se exporta a Jira.
10. El sistema debe poder funcionar sin Jira.
11. El sistema debe mostrar siempre el siguiente paso recomendado.
12. El usuario debe entender qué falta para llegar a `Ready`.

### 13.2 Reglas adicionales propuestas para cerrar huecos

1. Un elemento nunca puede quedar sin owner operativo.  
   Si el owner se desactiva, debe levantarse alerta y requerirse reasignación.

2. Una revisión asignada a un equipo queda resuelta cuando un miembro autorizado emite una respuesta final válida, manteniendo trazabilidad del respondedor.

3. Una modificación sustancial sobre un elemento `Ready` antes de exportación debe forzar recálculo de completitud y puede revertir el estado.

4. Un elemento `Exportado` mantiene trazabilidad, pero la exportación debe seguir referenciando un snapshot inmutable.

5. Las reglas de validación globales pueden sobreescribirse a nivel de proyecto, pero deben respetar precedencia clara.

---

## 14. Integraciones externas

### 14.1 Google OAuth

El acceso al sistema se realiza con Google OAuth.

### 14.2 Jira

La integración Jira debe cumplir:

- exportación manual y explícita;
- exportación solo de elementos `Ready`;
- envío del snapshot final;
- conservación del vínculo interno/externo;
- sincronización de estado básico;
- no modificación automática del contenido tras exportar en el MVP.

### 14.3 Fuentes de contexto

El sistema debe permitir asociar fuentes relevantes a un proyecto o workspace. En el MVP, estas fuentes se entienden como contexto seleccionado para enriquecer el trabajo. El comportamiento exacto de lectura o explotación dependerá de la implementación final y de las integraciones disponibles.

---

## 15. Requisitos no funcionales

### 15.1 Acceso y autenticación

- autenticación con Google OAuth;
- rutas privadas protegidas;
- gestión adecuada de expiración de sesión.

### 15.2 Responsive

- la aplicación debe ser usable en móvil;
- el inbox debe ser funcional en pantallas pequeñas;
- las acciones críticas deben estar accesibles.

### 15.3 Persistencia del contexto

- el historial conversacional debe persistir;
- las conversaciones deben poder retomarse;
- el sistema debe reducir la necesidad de reconstruir contexto manualmente.

### 15.4 Seguridad

- validación de permisos en backend;
- protección de credenciales e integraciones;
- auditoría de acciones sensibles;
- tratamiento seguro de secretos.

### 15.5 Rendimiento

- listados, búsqueda y detalle deben ser razonablemente rápidos;
- las operaciones largas deben informar de su estado;
- el sistema debe degradar con elegancia ante fallos parciales.

### 15.6 Observabilidad

- logs estructurados;
- eventos de producto;
- trazas o mecanismos de diagnóstico básicos;
- visibilidad de fallos de integración;
- datos para medir adopción y cuellos de botella.

---

## 16. Métricas de éxito

| Métrica | Objetivo |
|---|---|
| Tiempo medio de `Borrador` a `Ready` | reducirlo sin comprometer calidad |
| Porcentaje de elementos con validaciones completas | aumentarlo |
| Porcentaje de elementos con override a `Ready` | mantenerlo controlado |
| Número medio de ciclos de revisión | mantenerlo útil pero no excesivo |
| Porcentaje de elementos exportados sin retrabajo por mala definición | aumentarlo |
| Antigüedad media de bloqueos | reducirla |
| Carga pendiente por equipo y por owner | hacerla visible y equilibrable |
| Uso del sistema sin Jira | demostrar autonomía real |
| Ratio de adopción de inbox y revisiones | validar el modelo de colaboración |
| Fallos de exportación Jira | mantenerlos bajos y diagnosticables |

---

## 17. Riesgos y mitigaciones

| Riesgo | Impacto | Mitigación |
|---|---|---|
| El sistema añade demasiada fricción | baja adopción | override del owner, UX clara, pasos recomendados |
| Se percibe como duplicidad de Jira | resistencia organizativa | reforzar autonomía y valor de definición previa |
| Exceso de notificaciones | fatiga | inbox priorizado y diferenciación entre info y acción |
| Reglas mal configuradas | bloqueos artificiales | defaults simples y auditoría de cambios |
| Sugerencias de baja calidad | pérdida de confianza | preview, aceptación parcial y control humano |
| Administración demasiado compleja | rechazo del equipo | separar mínimo necesario de complejidad opcional |
| Dependencia excesiva del admin | cuello de botella organizativo | configuración razonable por defecto y delegación limitada |
| Fallos de integración Jira | pérdida de confianza | logs, reintentos, health checks y visibilidad clara |

---

## 18. Decisiones pendientes con propuesta recomendada

| Tema | Situación | Propuesta |
|---|---|---|
| Fórmula exacta de “máximo detalle” | abierta | score backend basado en contexto, objetivo, alcance, criterios, dependencias, validaciones, desglose y ownership |
| Quién puede exportar a Jira | no explicitado del todo | por defecto, solo owner; delegable por admin |
| Política tras cambios sobre un elemento exportado | abierta | conservar snapshot exportado y mostrar divergencia si el elemento sigue cambiando |
| Resolución exacta de revisiones de equipo | abierta | un miembro autorizado puede cerrar la revisión, conservando trazabilidad |
| Precedencia entre reglas globales y de proyecto | abierta | proyecto sobreescribe a workspace salvo restricciones globales bloqueantes |
| Nivel de self-service administrativo | abierta | permitir operación razonable sin soporte técnico, sin construir un panel enterprise excesivo |
| Gestión de miembros suspendidos con trabajo activo | abierta | alerta + reasignación obligatoria de ownership antes de suspensión efectiva cuando haya trabajo crítico |

---

## 19. Modelo técnico mínimo recomendado

### 19.1 Entidades principales sugeridas

- `users`
- `workspaces`
- `workspace_memberships`
- `teams`
- `team_members`
- `projects`
- `work_items`
- `work_item_versions`
- `work_item_sections`
- `task_nodes`
- `task_dependencies`
- `review_requests`
- `review_responses`
- `validation_requirements`
- `validation_statuses`
- `comments`
- `comment_anchors`
- `conversation_threads`
- `conversation_messages`
- `assistant_suggestions`
- `notifications`
- `context_sources`
- `context_presets`
- `routing_rules`
- `validation_rules`
- `integration_configs`
- `integration_exports`
- `sync_logs`
- `audit_events`

### 19.2 Servicios lógicos sugeridos

- autenticación y miembros;
- work items y estados;
- especificación y completitud;
- desglose y jerarquía;
- revisiones y validaciones;
- comentarios, versiones y diff;
- notificaciones e inbox;
- búsqueda y dashboards;
- administración y configuración;
- integraciones;
- auditoría y observabilidad.

### 19.3 Reglas técnicas críticas

- el contenido versionado y el estado operativo no deben mezclarse de forma informal;
- las revisiones deben apuntar a una versión concreta;
- la exportación debe apuntar a un snapshot concreto;
- los permisos se validan en backend;
- las notificaciones deben dispararse por eventos de dominio;
- la auditoría debe cubrir tanto capa funcional como administrativa.

---

## 20. Backlog del MVP

### 20.1 Convenciones

- `EP-XX` = épica
- `US-XXX` = historia de usuario

### 20.2 Orden sugerido de implementación

| Orden | Épica |
|---|---|
| 1 | Acceso, identidad y bootstrap |
| 2 | Modelo core, estados y ownership |
| 3 | Captura, borradores y plantillas |
| 4 | Clarificación, conversación y acciones asistidas |
| 5 | Especificación estructurada y motor de calidad |
| 6 | Desglose, jerarquía y dependencias |
| 7 | Revisiones, validaciones y flujo a `Ready` |
| 8 | Comentarios, versiones, diff y trazabilidad |
| 9 | Equipos, asignaciones, notificaciones e inbox |
| 10 | Listados, dashboards, búsqueda y workspace autónomo |
| 11 | Configuración, proyectos, reglas y administración |
| 12 | Exportación y sincronización con Jira |
| 13 | Responsive, seguridad, observabilidad y rendimiento |

---

### EP-00 — Acceso, identidad y bootstrap

**Objetivo**  
Permitir acceso seguro al sistema y resolución de identidad y workspace.

**Historias**
- US-001 Iniciar sesión con Google OAuth.
- US-002 Crear o resolver perfil único del usuario.
- US-003 Gestionar sesión y acceso a rutas protegidas.

**Criterios funcionales**
- login con Google;
- perfil persistido con nombre y email;
- rutas privadas protegidas;
- acceso al workspace resuelto tras autenticación.

**Notas técnicas**
- middleware de auth;
- gestión de sesiones;
- bootstrap inicial del workspace;
- eventos de login y error.

---

### EP-01 — Modelo core, estados y ownership

**Objetivo**  
Definir la entidad principal del sistema y sus reglas básicas.

**Historias**
- US-010 Crear modelo de elemento principal.
- US-011 Implementar máquina de estados.
- US-012 Gestionar owner único y reasignación.
- US-013 Forzar `Ready` con override controlado.

**Criterios funcionales**
- soporte para todos los tipos de elemento;
- estado principal y estado operativo;
- owner único;
- transición controlada a `Ready`.

**Notas técnicas**
- state machine en backend;
- servicios de transición;
- trazabilidad de cambios de owner y estado.

---

### EP-02 — Captura, borradores y plantillas

**Objetivo**  
Capturar trabajo ambiguo sin exigir estructura completa desde el primer momento.

**Historias**
- US-020 Crear elemento desde texto libre.
- US-021 Guardar y retomar borradores.
- US-022 Usar plantillas por tipo.
- US-023 Mostrar cabecera funcional desde el inicio.

**Criterios funcionales**
- creación rápida;
- borradores persistentes;
- input original preservado;
- cabecera con estado, owner y completitud.

**Notas técnicas**
- formularios con guardado parcial;
- plantillas parametrizables;
- eventos de creación y reanudación.

---

### EP-03 — Clarificación, conversación y acciones asistidas

**Objetivo**  
Ayudar a aterrizar el contenido mediante conversación persistente y propuestas revisables.

**Historias**
- US-030 Clarificar mediante preguntas guiadas.
- US-031 Mantener conversación persistente por elemento y general.
- US-032 Proponer mejoras contextuales con preview y aplicación parcial.
- US-033 Ejecutar acciones rápidas de refinamiento.

**Criterios funcionales**
- el usuario puede conversar con el sistema;
- el sistema detecta huecos;
- las propuestas son revisables;
- las conversaciones se recuperan más tarde.

**Notas técnicas**
- threads y mensajes;
- sugerencias versionadas;
- patches parciales aplicables por sección.

---

### EP-04 — Especificación estructurada y motor de calidad

**Objetivo**  
Transformar inputs ambiguos en una especificación clara, editable y medible.

**Historias**
- US-040 Generar especificación estructurada.
- US-041 Editar manualmente la especificación.
- US-042 Ver nivel de completitud y gaps funcionales.
- US-043 Recibir siguiente paso recomendado y validadores sugeridos.

**Criterios funcionales**
- secciones coherentes;
- edición manual;
- score de completitud;
- recomendaciones visibles.

**Notas técnicas**
- contenido estructurado versionable;
- motor de completitud en backend;
- API de gaps y sugerencias.

---

### EP-05 — Desglose, jerarquía y dependencias

**Objetivo**  
Convertir la especificación en unidades ejecutables y relacionarlas entre sí.

**Historias**
- US-050 Generar tareas y subtareas.
- US-051 Editar, dividir, fusionar y reordenar tareas.
- US-052 Mantener trazabilidad entre especificación y desglose.
- US-053 Gestionar dependencias funcionales.
- US-054 Ver vista jerárquica unificada.

**Criterios funcionales**
- árbol editable;
- dependencias visibles;
- origen del desglose rastreable.

**Notas técnicas**
- modelo de árbol;
- validación anti-ciclos;
- relaciones entre secciones y tareas.

---

### EP-06 — Revisiones, validaciones y flujo a `Ready`

**Objetivo**  
Coordinar la revisión asíncrona y controlar el avance de madurez.

**Historias**
- US-060 Solicitar revisión a usuarios o equipos.
- US-061 Responder revisión con aprobar, rechazar o pedir cambios.
- US-062 Gestionar checklist de validación.
- US-063 Soportar flujo iterativo de ida y vuelta al owner.
- US-064 Aplicar flujo normal y override hacia `Ready`.

**Criterios funcionales**
- revisiones explícitas;
- validaciones visibles;
- iteración múltiple;
- owner como decisor final.

**Notas técnicas**
- entidades de review y validation;
- fan-out de notificaciones;
- control de versionado por revisión.

---

### EP-07 — Comentarios, versiones, diff y trazabilidad

**Objetivo**  
Hacer visible cómo cambió el elemento y por qué.

**Historias**
- US-070 Añadir comentarios anclados.
- US-071 Versionar cambios relevantes.
- US-072 Comparar versiones y propuestas con diff.
- US-073 Consultar timeline completo del elemento.

**Criterios funcionales**
- comentarios generales y anclados;
- versiones navegables;
- diff legible;
- timeline completo.

**Notas técnicas**
- snapshots o change sets;
- anchors estables;
- servicio de diff;
- auditoría inmutable.

---

### EP-08 — Equipos, asignaciones, notificaciones e inbox

**Objetivo**  
Permitir colaboración distribuida y priorizada.

**Historias**
- US-080 Crear y gestionar equipos.
- US-081 Asignar trabajo manualmente y sugerir asignaciones.
- US-082 Enviar notificaciones internas por eventos relevantes.
- US-083 Mostrar inbox personal priorizado.
- US-084 Ejecutar acciones rápidas desde notificaciones e inbox.

**Criterios funcionales**
- equipos utilizables en revisiones;
- notificaciones internas;
- inbox centrado en acción;
- deeplinks al contexto exacto.

**Notas técnicas**
- fan-out de notificaciones;
- queries agregadas por usuario;
- estados de notificación;
- heurísticas simples de asignación sugerida.

---

### EP-09 — Listados, dashboards, búsqueda y workspace autónomo

**Objetivo**  
Hacer operable el sistema como fuente de verdad de la definición.

**Historias**
- US-090 Listar elementos con filtros y vistas rápidas.
- US-091 Consultar dashboard global.
- US-092 Consultar dashboards por responsable y por equipo.
- US-093 Ver flujo de trabajo en pipeline.
- US-094 Buscar y recuperar contexto.
- US-095 Ver una vista unificada de trabajo.

**Criterios funcionales**
- filtros por estado, owner, tipo y equipo;
- dashboards agregados;
- pipeline visible;
- búsqueda full-text básica;
- vista detalle integrada.

**Notas técnicas**
- APIs optimizadas para listados y métricas;
- agregaciones reutilizables;
- búsqueda indexada;
- funcionamiento completo sin Jira.

---

### EP-10 — Configuración, proyectos, reglas y administración

**Objetivo**  
Dar gobierno real al sistema y permitir adaptación por workspace y proyecto.

**Historias**
- US-100 Seleccionar fuentes de contexto relevantes.
- US-101 Guardar configuraciones reutilizables de contexto.
- US-102 Configurar participantes, equipos y reglas de validación.
- US-103 Usar roles como etiquetas contextuales y de routing.
- US-104 Configurar integración con Jira.
- US-105 Gestionar miembros del workspace.
- US-106 Gestionar capacidades operativas y ámbito administrativo.
- US-107 Consultar auditoría administrativa.
- US-108 Ver dashboard administrativo de salud del sistema.
- US-109 Operar herramientas de soporte básicas.

**Criterios funcionales**
- existe una sección admin usable;
- miembros, equipos y reglas son configurables;
- la administración está separada de las etiquetas de contexto;
- el sistema puede crecer sin depender de ingeniería para cada cambio menor.

**Notas técnicas**
- entidades de configuración;
- scopes de permisos;
- auditoría de cambios;
- health checks de integraciones;
- reintentos y logs operativos.

---

### EP-11 — Exportación y sincronización con Jira

**Objetivo**  
Enviar solo la versión final aprobada y mantener relación coherente con Jira.

**Historias**
- US-110 Enviar a Jira mediante acción explícita.
- US-111 Construir y enviar snapshot final.
- US-112 Guardar referencia Jira y mostrar relación interna/externa.
- US-113 Sincronizar estado básico desde Jira.
- US-114 Mantener comportamiento controlado tras exportación.

**Criterios funcionales**
- exportación solo desde `Ready`;
- snapshot exportado identificado;
- vínculo con Jira visible;
- sincronización básica de estado.

**Notas técnicas**
- integración desacoplada con jobs;
- idempotencia;
- logs y retries;
- separación clara entre modelo interno y payload externo.

---

### EP-12 — Responsive, seguridad, rendimiento y observabilidad

**Objetivo**  
Asegurar robustez operativa y una experiencia usable.

**Historias**
- US-120 Soportar uso responsive y acciones críticas en móvil.
- US-121 Cubrir accesibilidad y estados de interfaz.
- US-122 Proteger permisos, auditoría y seguridad operativa.
- US-123 Mantener rendimiento y fiabilidad mínimos.
- US-124 Instrumentar monitorización y analítica de producto.

**Criterios funcionales**
- uso razonable en móvil;
- feedback claro en la UI;
- permisos backend;
- visibilidad de errores y métricas.

**Notas técnicas**
- responsive desde inicio;
- logs estructurados;
- error tracking;
- analítica de uso;
- controles básicos de seguridad.

---

## 21. Dependencias entre épicas

| Épica | Depende de |
|---|---|
| EP-00 | — |
| EP-01 | EP-00 |
| EP-02 | EP-00, EP-01 |
| EP-03 | EP-02 |
| EP-04 | EP-01, EP-02, EP-03 |
| EP-05 | EP-04 |
| EP-06 | EP-01, EP-04, EP-05, EP-08 |
| EP-07 | EP-01, EP-04, EP-05, EP-06 |
| EP-08 | EP-00, EP-01 |
| EP-09 | EP-01, EP-02, EP-06, EP-08 |
| EP-10 | EP-00, EP-08 |
| EP-11 | EP-01, EP-04, EP-06, EP-10 |
| EP-12 | transversal a todas |

---

## 22. Definition of Done transversal

Una historia no se considera cerrada si no cumple:

- criterios funcionales aceptados;
- permisos validados en backend;
- auditoría registrada donde aplique;
- estados de loading, vacío y error cubiertos;
- comportamiento responsive revisado;
- eventos de producto y errores principales instrumentados;
- pruebas del happy path y edge cases relevantes.

---

## 23. Resumen final

Este MVP define un sistema completo para capturar, clarificar, estructurar, revisar, validar y preparar trabajo antes de ejecución. El sistema debe funcionar como una capa de maduración autónoma, con ownership claro, colaboración asíncrona, trazabilidad total, administración explícita y exportación opcional a Jira.

La parte administrativa no es un añadido secundario: es la capa que hace posible que el producto opere con coherencia en un entorno real. Por eso el MVP incluye también gobierno de workspace, miembros, equipos, proyectos, reglas, contexto, integraciones, auditoría y supervisión operativa.

La idea central del producto se mantiene estable en todo el documento: **antes de ejecutar, hay que definir bien**.
