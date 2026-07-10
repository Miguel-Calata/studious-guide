# 01 — Requisitos

## 🎭 Roles de Usuario

| Rol | Descripción | Permisos |
|-----|-------------|----------|
| **Público** (sin auth) | Cualquier visitante | Ver compendios publicados, descargar .md, abrir en Notion |
| **Creator** (auth) | Médico/editor | Todo lo del público + crear proyectos, subir PDFs, generar compendios |
| **Admin** (auth, Fase 2) | Superusuario | Todo lo del creator + gestionar prompts, ver métricas globales |

---

## Requisitos Funcionales

### RF-01: Gestión de Proyectos (Patologías)

| ID | Requisito | Prioridad |
|----|-----------|-----------|
| RF-01.1 | Crear un nuevo proyecto (patología) con nombre y descripción | 🔴 MVP |
| RF-01.2 | Listar proyectos del usuario con estado (activo, completado, archivado) | 🔴 MVP |
| RF-01.3 | Ver detalle de un proyecto con todas sus fuentes, extracciones y secciones | 🔴 MVP |
| RF-01.4 | Archivar / eliminar proyectos | 🟡 Fase 2 |
| RF-01.5 | Publicar compendio → sube a S3 y lo hace accesible públicamente | 🔴 MVP |

### RF-02: Gestión de PDFs Fuente

| ID | Requisito | Prioridad |
|----|-----------|-----------|
| RF-02.1 | Subir PDFs a un proyecto (drag & drop / file picker) | 🔴 MVP |
| RF-02.2 | Clasificar cada PDF: BMJ Best Practice, Guía completa, Artículo de revista | 🔴 MVP |
| RF-02.3 | Previsualizar PDF (visor embebido) | 🟡 Fase 2 |
| RF-02.4 | Eliminar / reemplazar PDFs | 🔴 MVP |

### RF-03: Extracción de Contenido (OpenRouter API)

| ID | Requisito | Prioridad |
|----|-----------|-----------|
| RF-03.1 | Ejecutar extracción de un PDF con el prompt + modelo correspondiente vía OpenRouter | 🔴 MVP |
| RF-03.2 | Manejar continuaciones automáticas cuando el modelo alcanza su límite de output | 🔴 MVP |
| RF-03.3 | Ejecutar auditoría automática post-extracción (comparar contra PDF) | 🔴 MVP |
| RF-03.4 | Unir todas las extracciones de un proyecto en un solo documento Markdown | 🔴 MVP |
| RF-03.5 | Mostrar progreso de extracción (cola de jobs, estado, tokens consumidos, costo) | 🔴 MVP |
| RF-03.6 | Re-ejecutar extracción de un solo PDF | 🟡 Fase 2 |

### RF-04: Generación del Compendio (11 secciones)

| ID | Requisito | Prioridad |
|----|-----------|-----------|
| RF-04.1 | Generar los 11 prompts especializados usando el motor SAM v9 | 🔴 MVP |
| RF-04.2 | Enviar cada prompt al modelo óptimo vía OpenRouter (Gemini para 🟢🟡, Claude para 🔴) | 🔴 MVP |
| RF-04.3 | Respetar MAPA_ECOS (cada sección recibe solo lo que no debe repetir) | 🔴 MVP |
| RF-04.4 | Aplicar dosificación de razonamiento por sección (🔴 MAX / 🟡 ALTO / 🟢 ESTÁNDAR) | 🔴 MVP |
| RF-04.5 | Trackear costo por sección y total del compendio (OpenRouter devuelve pricing) | 🔴 MVP |
| RF-04.6 | Re-generar secciones individuales sin rehacer todo el compendio | 🟡 Fase 2 |
| RF-04.7 | Vista previa de cada sección generada con editor Markdown | 🟡 Fase 2 |

### RF-05: Motor de Prompts

| ID | Requisito | Prioridad |
|----|-----------|-----------|
| RF-05.1 | Almacenar y versionar System Prompts (Pilares, Leyes, reglas) | 🔴 MVP |
| RF-05.2 | Almacenar y versionar Prompts de Extracción (v3, v5, artículos) | 🔴 MVP |
| RF-05.3 | Almacenar y versionar Prompt de Auditoría | 🔴 MVP |
| RF-05.4 | Almacenar y versionar Parche Gemini (densidad de citas, divergencias) | 🔴 MVP |
| RF-05.5 | Permitir edición de prompts por el usuario administrador | 🟡 Fase 2 |
| RF-05.6 | Sistema de versionado de prompts (track changes, revertir) | 🟢 Futuro |

### RF-06: Integración con Notion

| ID | Requisito | Prioridad |
|----|-----------|-----------|
| RF-06.1 | Conectar cuenta de Notion vía OAuth (Public Integration) | 🔴 MVP |
| RF-06.2 | Seleccionar página/base de datos de destino en Notion | 🔴 MVP |
| RF-06.3 | Publicar secciones individuales como páginas en Notion | 🔴 MVP |
| RF-06.4 | Publicar compendio completo con estructura jerárquica automática | 🔴 MVP |
| RF-06.5 | Sincronizar cambios (si se re-genera una sección, actualizar en Notion) | 🟡 Fase 2 |

### RF-07: Autenticación y Usuarios

| ID | Requisito | Prioridad |
|----|-----------|-----------|
| RF-07.1 | Registro con email y contraseña | 🔴 MVP |
| RF-07.2 | Login con email y contraseña (JWT) | 🔴 MVP |
| RF-07.3 | Recuperación de contraseña | 🟡 Fase 2 |
| RF-07.4 | Login con Google OAuth | 🟢 Futuro |
| RF-07.5 | Roles: admin (edita prompts), médico (crea proyectos) | 🟢 Futuro |

### RF-08: Visor Público y Exportación

| ID | Requisito | Prioridad |
|----|-----------|-----------|
| RF-08.1 | Visor público minimalista: renderiza Markdown con marked.js, sin auth | 🔴 MVP |
| RF-08.2 | Listado público de compendios publicados (nombre de patología, fecha, nº secciones) | 🔴 MVP |
| RF-08.3 | Descargar compendio completo como .md (desde S3) | 🔴 MVP |
| RF-08.4 | Botón "Abrir en Notion" con deep link a la página publicada | 🔴 MVP |
| RF-08.5 | Subir compendio final a bucket S3 al publicar | 🔴 MVP |
| RF-08.6 | Servir archivos .md desde S3 (con cache headers para rendimiento) | 🔴 MVP |

---

## Requisitos No Funcionales

### RNF-01: Rendimiento

| ID | Requisito | Meta |
|----|-----------|------|
| RNF-01.1 | Tiempo de extracción por PDF (OpenRouter/Gemini) | < 2 min para PDF de 150k tokens |
| RNF-01.2 | Tiempo de generación de las 11 secciones | < 10 min total (con caching) |
| RNF-01.3 | Respuesta de la API para operaciones CRUD | < 500ms |
| RNF-01.4 | Upload de PDFs | Soportar hasta 50MB |

### RNF-02: Seguridad

| ID | Requisito |
|----|-----------|
| RNF-02.1 | Todas las comunicaciones sobre HTTPS |
| RNF-02.2 | API keys de OpenRouter/Notion protegidas en `.env` (nunca en logs o código fuente) |
| RNF-02.3 | Contraseñas hasheadas (bcrypt) |
| RNF-02.4 | PDFs almacenados con acceso restringido (no servidos públicamente) |
| RNF-02.5 | Rate limiting en endpoints de autenticación |

### RNF-03: Mantenibilidad

| ID | Requisito |
|----|-----------|
| RNF-03.1 | Código backend modular con separación clara de responsabilidades |
| RNF-03.2 | Tests unitarios para lógica de negocio (prompt engine, merge, etc.) |
| RNF-03.3 | Tests de integración para flujos de API |
| RNF-03.4 | Documentación de API (OpenAPI/Swagger) |

### RNF-04: Observabilidad y Control de Costos

| ID | Requisito |
|----|-----------|
| RNF-04.1 | Logs estructurados (JSON) de cada paso del pipeline |
| RNF-04.2 | Métricas de consumo de tokens y COSTO USD por proyecto y por sección |
| RNF-04.3 | Trazabilidad: cada sección generada referencia su prompt, modelo (vía OpenRouter) y PDFs fuente |
| RNF-04.4 | Dashboard de costos: total gastado por mes, por proyecto, por modelo |
| RNF-04.5 | Alerta si el costo estimado de un proyecto excede un umbral configurable |

### RNF-05: Despliegue

| ID | Requisito |
|----|-----------|
| RNF-05.1 | `docker compose up` levanta todo el stack (app, DB, Redis, workers) |
| RNF-05.2 | Configuración vía variables de entorno (.env) |
| RNF-05.3 | Health checks en todos los servicios |
| RNF-05.4 | Backup automático de base de datos |

---

> **Nota:** Los RF marcados como 🔴 MVP son el alcance mínimo de la Fase 1.
