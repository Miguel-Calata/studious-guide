# 11 — Changelog / Bitácora de Decisiones

Registro cronológico de decisiones arquitectónicas, cambios de diseño y desviaciones del plan original.

---

## 2026-07-08 — Sprint 10: Pipeline UI (frontend)

### Alcance
Conexión completa del pipeline backend (extracciones, merge, generación, secciones) en la UI de detalle de proyecto. Sin cambios en el backend (todos los endpoints ya existían).

### Nuevas dependencias (frontend)
- `sonner@^2.0.7` → toasts de feedback (errores 409 y confirmaciones async).
- `@uiw/react-md-editor@^4.0.7` → editor Markdown del panel de revisión de secciones (import diferido vía `React.lazy`).

### Componentes nuevos
- `pages/ProjectDetailPage.tsx` (refactor): usa `useProjectPolling` para refrescar proyecto y documentos con `refreshInterval` condicional (3s solo en `extracting`/`generating`).
- `components/pipeline/ExtractionCard.tsx`: "Extraer todo" + "Reintentar fallidos" + barra de progreso de documentos.
- `components/pipeline/CompendiumCard.tsx`: "Fusionar extracciones" + "Generar compendio" + progreso "N/11" + lista de secciones.
- `components/pipeline/ProgressBar.tsx`: barra reutilizable.
- `components/sections/SectionList.tsx` + `SectionEditor.tsx`: lista de 11 secciones y editor Markdown (PUT `/sections/{id}`, regenerate POST `/sections/{id}/regenerate`).
- `hooks/useProjectPolling.ts`: polling condicional.
- `lib/pipeline.ts`: mapeos de estado→label/variant (extracción, documento, sección) y helpers de polling.
- `lib/notify.ts`: `notifyError`/`notifySuccess` (sonner) que extraen el `detail` del backend.
- `types/extraction.ts`, `types/compendium.ts`, `api/extractions.ts`, `api/compendiums.ts`.

### Decisiones
- **F-13**: editor `@uiw/react-md-editor` con import diferido (no infla el bundle del panel).
- **F-14**: actualización async vía `useSWR` `refreshInterval` condicional (no SSE/WebSockets).
- **F-15**: merge y generate como dos acciones explícitas separadas, respetando la máquina de estados.
- **F-16**: feedback con `sonner`, mapeando el `detail` de los 409 del backend a toasts legibles en español.

### Notas
- Los botones respetan la máquina de estados del backend: "Extraer todo" habilitado solo en `draft`/`extracting`; "Generar compendio" solo con `merged_content` y en `draft`/`review`.
- "Reintentar fallidos" reusa `extract-all` (el backend re-encola docs en estado `error`).
- Tests Vitest: 39 en total (incluye `pipeline`, `api/extractions`, `api/compendiums`, `SectionList`, `ProjectDetailPage`, `useProjectPolling`). `tsc -b` y `oxlint` limpios.

---

## 2026-07-08 — Incidente: "Not authenticated" al iniciar sesión (Docker)

### Síntoma
Al iniciar sesión en el frontend aparecía siempre "Not authenticated" y `GET /auth/me` devolvía 401.

### Causa raíz
**No fue un bug de código.** El contenedor `docker-backend` estaba corriendo con una imagen construida ~2 horas antes, correspondiente a una versión del backend **anterior al Sprint 8** (antes de implementar cookies httpOnly, `/auth/logout` y `/auth/refresh`). El endpoint `/auth/login` de esa imagen vieja respondía 200 pero **sin `Set-Cookie`**, por lo que el navegador nunca guardaba la sesión. Confirmado con `docker exec ... cat /app/app/modules/auth/router.py` (solo tenía `def login`).

### Resolución
- `docker compose build backend worker` + `up -d backend worker` para reconstruir con el código actual.
- Verificado: `POST /auth/login` ahora devuelve `Set-Cookie: access_token=...; HttpOnly; SameSite=lax` y `refresh_token=...; HttpOnly`. `GET /auth/me` con esas cookies → 200. Flujo validado también a través del proxy nginx del servicio `frontend` (puerto 5173).

### Lección / nota operativa
> Tras cualquier cambio en `backend/`, reconstruir la imagen (`docker compose up --build` o `build backend worker`). El `docker ps` mostraba el contenedor "Up 2 hours" pero con binario viejo. Ver `README.md` (Inicio Rápido, Opción A).

### UX de registro
- Se mantuvo el **autologin** tras registro (register → login → cookie → navega a `/`), que es el flujo más ágil para el usuario. No se requirieron cambios de código en frontend; el fallo previo era exclusivamente la imagen de backend desactualizada.

---

## 2026-07-08 — Fix: "No se pudieron cargar los proyectos" / "No se pudo crear el proyecto"

### Síntoma
Tras login correcto, el dashboard mostraba "No se pudieron cargar los proyectos. Intenta de nuevo." y el modal "Nuevo proyecto" mostraba "No se pudo crear el proyecto".

### Causa raíz
Doble problema en el flujo `/api/v1/projects` (ruta de colección):
1. **FastAPI `redirect_slashes=True`** (default) redirigía `GET /projects` → `GET /projects/` (307). El frontend siempre llama sin slash (claves SWR `/projects`).
2. **nginx del frontend** usaba `proxy_set_header Host $host;` — `$host` descarta el puerto, así que el `Location` del 307 salía como `http://localhost/api/v1/projects/` (sin `:5173`). El navegador intentaba esa URL en puerto 80 → error de red/CORS → SWR `onError`. Lo mismo rompía el `POST /projects` (307 en medio del alta).

### Resolución
- `backend/app/main.py`: `FastAPI(..., redirect_slashes=False)`.
- `backend/app/modules/projects/router.py`: rutas de colección `@router.get("/")` / `@router.post("/")` → `""` (ruta `/projects` exacta, sin slash).
- `docker/nginx.frontend.conf`: `proxy_set_header Host $http_host;` (preserva el puerto en cualquier redirect residual).
- Rebuild de `backend`, `worker` y `frontend`.

### Verificación
- `GET /api/v1/projects` (nginx, sin slash) → **200** (sin 307).
- `POST /api/v1/projects` (nginx) → **201**.
- `GET /api/v1/projects/{id}/documents` (nginx) → **200**.
- Login → dashboard carga proyectos; "Nuevo proyecto" crea y aparece en la lista.

> Nota: el router `documents` no usaba paths raíz (`/`), así que no requirió cambio. Los demás routers (extractions, compendiums, etc.) se ajustarán al construir su UI; con `redirect_slashes=False` basta llamarlos con la ruta exacta que defina cada endpoint.

---

## 2026-07-08 — Sprint 9: Dashboard de proyectos

### Decisiones

| # | Decisión | Justificación | Alternativas |
|---|----------|---------------|-------------|
| F-7 | **Tipo de documento implícito** | El usuario no elige tipo; se infiere del nombre del archivo y se sube agrupado por tipo. Reduce fricción | Selector manual de tipo (el backend lo requería antes, ahora es opcional) |
| F-8 | **Crear proyecto en modal** | Acceso rápido desde el dashboard sin navegación extra | Página separada `/projects/new` |
| F-9 | **Drag & drop + botón** | Cubre usuarios que arrastran y los que prefieren el file picker | Solo botón (menos ergonómico) |
| F-10 | **Badges de estado con color, sin barra de progreso** | Información suficiente para el MVP del dashboard | Barra de progreso del pipeline (Sprint 10+) |
| F-11 | **UI en español** | La plataforma está orientada al mercado hispanohablante (Dr. Jorge) | Inglés (inconsistente con el resto de la app) |

### Implementado

- [x] Tipos `Project`, `ProjectCreateRequest`, `SourceDocument`, `DocumentType`.
- [x] Schemas: `projectCreateSchema` (zod).
- [x] API: `api/projects.ts` (getProjects, getProject, createProject, archiveProject), `api/documents.ts` (getDocuments, uploadDocuments, deleteDocument).
- [x] `api/client.ts`: helper `uploadFile()` para multipart con cookies.
- [x] Componentes UI shadcn: `dialog`, `badge` (variantes por estado), `table`, `skeleton`, `textarea`, `separator`, `dropdown-menu`.
- [x] `lib/projects.ts`: `statusLabel`, `statusVariant`, `documentTypeLabel`, `inferDocumentType`.
- [x] `components/projects/`: `ProjectList`, `ProjectCard`, `CreateProjectDialog`.
- [x] `components/documents/`: `DocumentUploader` (react-dropzone), `DocumentList`.
- [x] `pages/DashboardPage.tsx` reescrito; nuevo `pages/ProjectDetailPage.tsx`.
- [x] `routes/AppRouter.tsx`: ruta `/projects/:id`.
- [x] Dependencias: `react-dropzone`, `@radix-ui/react-dialog`, `@radix-ui/react-dropdown-menu`, `@radix-ui/react-separator`.
- [x] Tests (Vitest): `projects.test.ts` (lib), `projects.ui.test.tsx`, `documents.test.tsx` (16 tests total, todos pasando).

### Archivos nuevos

- `frontend/src/types/project.ts`, `frontend/src/types/document.ts`
- `frontend/src/schemas/project.ts`
- `frontend/src/api/projects.ts`, `frontend/src/api/documents.ts`
- `frontend/src/lib/projects.ts`
- `frontend/src/components/ui/{dialog,badge,table,skeleton,textarea,separator,dropdown-menu}.tsx`
- `frontend/src/components/projects/{ProjectList,ProjectCard,CreateProjectDialog}.tsx`
- `frontend/src/components/documents/{DocumentUploader,DocumentList}.tsx`
- `frontend/src/pages/ProjectDetailPage.tsx`
- `frontend/src/test/{projects.test.ts,projects.ui.test.tsx,documents.test.tsx}`

### Archivos modificados

- `frontend/src/api/client.ts` — +`uploadFile`
- `frontend/src/pages/DashboardPage.tsx` — reescrito con SWR + modal
- `frontend/src/routes/AppRouter.tsx` — +ruta `/projects/:id`
- `frontend/package.json` — +dependencias
- `docs/12_roadmap_sprints.md` — Sprint 9 completado + backlog archivar proyecto

### Backlog documentado

- **Archivar/eliminar proyectos desde UI** → Sprint 12. El endpoint backend ya existe.

### Infraestructura (Docker / Coolify)

- [x] **Servicio `frontend` en `docker-compose.yml`** que construye la SPA (multi-stage: `npm ci` + `npm run build`) y la sirve con nginx.
- [x] `docker/Dockerfile.frontend` (context raíz, build en `frontend/`, nginx final).
- [x] `docker/nginx.frontend.conf`: proxy de `/api/v1` → `backend:8000` (mismo origen, cookies httpOnly sin CORS) + SPA fallback a `index.html`.
- [x] Variable `FRONTEND_PORT` (default 5173) en `.env.docker.example`.
- [x] Verificado: `GET /` → 200, `GET /api/v1/health` → healthy, `GET /projects/x` → 200 (SPA fallback).

> **Decisión F-12:** El frontend se despliega como build estático en nginx dentro del compose, no con el dev server de Vite. Esto es requisito para Coolify (un solo `docker-compose` up levanta todo). El proxy de nginx al backend elimina la dependencia de CORS en producción.

---

## 2026-07-08 — Sprint 8: Frontend Scaffold

### Decisiones

| # | Decisión | Justificación | Alternativas |
|---|----------|---------------|-------------|
| F-1 | **Auth con cookies httpOnly** | Mitiga robo de JWT vía XSS (JS no accede a `document.cookie`). El frontend no maneja tokens directamente | localStorage (simple pero vulnerable a XSS), cookies firmadas por el cliente |
| F-2 | **`get_current_user` lee cookie con fallback a Bearer** | Compatibilidad total: el frontend usa cookies, Swagger/clientes no-browser siguen usando `Authorization: Bearer` | Romper el header Bearer (rompería Swagger y tests existentes) |
| F-3 | **`/auth/refresh` prioriza cookie, fallback a body** | El cliente browser envía solo cookies (`credentials: include`, sin body); clientes no-browser pueden seguir enviando `refresh_token` en JSON | Solo cookie (rompe compatibilidad), solo body (no sirve al flujo browser) |
| F-4 | **`/auth/logout` nuevo endpoint** | Limpia ambas cookies (access + refresh) en el browser | Reutilizar refresh con token vacío (sucio) |
| F-5 | **React Router v6 + SWR** | Estándar documentado en `03_stack_tecnologico.md` | v7 (más nuevo pero no documentado), TanStack Query |
| F-6 | **Dominio de cookie configurable** | `api.astreo.space`, `coolify.astreo.space`, etc. conviven; con `COOKIE_DOMAIN=.astreo.space` la cookie se comparte entre subdominios del mismo padre | Cookie por host (no funcionaría cross-subdominio) |

### Implementado

- [x] Scaffold frontend: Vite + React 19 + TS, Tailwind, shadcn/ui, react-hook-form + zod, SWR, Vitest.
- [x] `frontend/src/api/client.ts`: `request<T>` con `credentials: include` + refresh automático ante 401 (cola de peticiones en vuelo).
- [x] `frontend/src/contexts/AuthContext.tsx`: login/register/logout + `me` al montar.
- [x] `frontend/src/routes/`: `AppRouter` (v6), `ProtectedRoute`.
- [x] `frontend/src/components/layout/`: `AppShell` + `Header` (usuario + logout).
- [x] Páginas: `LoginPage`, `RegisterPage`, `DashboardPage` (placeholder).
- [x] Backend `auth/service.py`: `set_auth_cookies`, `clear_auth_cookies`, config `cookie_secure`/`cookie_samesite`/`cookie_domain`.
- [x] Backend `auth/router.py`: `login`/`refresh` setean cookies; nuevo `POST /auth/logout`; `me` sin cambios.
- [x] Backend `auth/dependencies.py`: `get_current_user` lee cookie `access_token` con fallback a Bearer.
- [x] Tests frontend (5): AuthContext, ProtectedRoute, client.

### Archivos nuevos

- `frontend/` (scaffold completo).
- `backend/app/modules/auth/dependencies.py` — modificado para leer cookie.
- `backend/app/modules/auth/router.py` — modificado (cookies + logout).
- `backend/app/modules/auth/service.py` — + helpers de cookies.
- `backend/app/config.py` — + `cookie_secure`, `cookie_samesite`, `cookie_domain`.

### ⚠️ Mejoras de seguridad pendientes (documentadas para Fase 2+)

1. **Denylist de refresh tokens:** el logout solo borra la cookie en el browser; el refresh token sigue siendo válido en el backend hasta su expiración. Mejora: almacenar `jti` en la DB y validarlo en `/auth/refresh` y `/auth/logout` (revocar).
2. **`secure=true` en producción:** setear `COOKIE_SECURE=true` (HTTPS obligatorio) antes de deploy real. En dev (`localhost`) debe quedar `false`.
3. **`samesite` estricto / protección CSRF:** `lax` es suficiente para el flujo actual (POST con cookies solo desde mismo sitio en navegación top-level). Si se añaden formularios cross-site, evaluar `strict` o token double-submit.
4. **`domain` en producción:** configurar `COOKIE_DOMAIN=.astreo.space` para compartir entre subdominios; en `localhost` debe quedar vacío (`None`).
5. **Rotación de refresh:** opcional, reemplazar refresh token en cada uso (ya se hace en el endpoint, pero el anterior sigue válido sin denylist).
6. **Rate limiting en `/auth/login` y `/auth/register`** (RNF-02.5 del `01_requisitos.md`) aún no implementado.

---


## 2026-07-08 — Sprint 7: Notion Integration

### Decisiones

| # | Decisión | Justificación | Alternativas |
|---|----------|---------------|-------------|
| N-1 | **API key encriptada con `cryptography.fernet`** | Key derivada del JWT secret (SHA-256). La API key nunca se almacena en texto plano. Evita migración posterior | Texto plano (requiere migración después) |
| N-2 | **Publish síncrono** | `POST /projects/{id}/publish/notion` bloquea hasta crear las 12 páginas (~15-30s). Resultado inmediato para el usuario | ARQ worker asíncrono (más complejo, estado intermedio) |
| N-3 | **Re-publish actualiza páginas existentes** | Si `notion_page_id` existe en la sección, `update_page()` en vez de `create_page()`. No rompe links en Notion | Borrar y recrear (pierde bookmarks) |
| N-4 | **`PUT /notion/config` separado del connect** | Setea `default_parent_page_id` después de connect. Más explícito | Incluir en connect (mezcla responsabilidades) |
| N-5 | **Override de `parent_page_id` en publish** | `POST` acepta `parent_page_id` opcional; si no, usa `default_parent_page_id` | Solo default (menos flexible) |
| N-6 | **Página raíz con resumen + índice** | La página raíz del compendio incluye fecha, descripción y lista de links a las 11 secciones hijas | Vacía (solo contenedora) |

### Implementado

- [x] Modelo `NotionConfig` + migración `008_create_notion_configs_table.py`
- [x] Campos: user_id (UNIQUE FK), api_key_encrypted (TEXT), workspace_name, default_parent_page_id, is_connected
- [x] Encrypt/decrypt helpers con Fernet (property `api_key`)
- [x] `NotionClientWrapper` usando `notion-client` SDK AsyncClient
- [x] Conversor `_md_to_notion_blocks()`: headers, bold/italic, párrafos, tablas, callouts, code, listas
- [x] Módulo `notion/`: schemas, client, service, dependencies, router
- [x] Endpoints: `POST /notion/connect`, `GET /notion/status`, `GET /notion/search`, `PUT /notion/config`, `POST /projects/{id}/publish/notion`
- [x] Jerarquía: página raíz (resumen + índice) → 11 páginas hijas por sección
- [x] `notion_page_id` poblado en cada sección para re-publish idempotente
- [x] +`cryptography` a requirements.txt
- [x] 8 tests con mock de Notion API (connect válido/inválido, status, search, publish crea/actualiza, sin conexión)

### Archivos nuevos

- `backend/app/models/notion_config.py`
- `backend/alembic/versions/008_create_notion_configs_table.py`
- `backend/app/modules/notion/__init__.py`
- `backend/app/modules/notion/schemas.py`
- `backend/app/modules/notion/client.py`
- `backend/app/modules/notion/service.py`
- `backend/app/modules/notion/router.py`
- `backend/app/modules/notion/dependencies.py`
- `backend/tests/test_notion.py`

### Archivos modificados

- `backend/requirements.txt` — +`cryptography==44.*`
- `backend/app/main.py` — +router notion bajo `/api/v1`
- `backend/app/models/user.py` — +relación `notion_config`
- `backend/alembic/env.py` — +import `NotionConfig`
- `docs/12_roadmap_sprints.md` — Sprint 7 marcado como completado

---

## 2026-07-08 — Sprint 5: Merger + Compendium Generation

### Decisiones

| # | Decisión | Justificación | Alternativas |
|---|----------|---------------|-------------|
| D-023 | **Co-generación R-9 simplificada (Opción A)** | Secciones 4 y 5 generadas como llamadas independientes. El MAPA_ECOS + nota de co-generación en el prompt son suficientes para evitar redundancia | Context injection (requiere secuencialidad), session persistente (complejo, OpenRouter no garantiza session affinity) |
| D-024 | **Parche Gemini inyectado en cada sección Gemini (Opción A)** | Costo despreciable (~$0.02/compendio), implementación trivial, robusto. El parche refuerza densidad de citas y aislamiento de divergencias | Solo primera sección (frágil, acopla orden), no inyectar (el Dr. lo creó por algo) |
| D-025 | **Sin semáforo de concurrencia + retry/backoff con tenacity** | Confiar en rate-limiting de OpenRouter. `@retry` con exponential backoff en `openrouter_client.py` cubre HTTP 429. `tenacity` ya estaba en requirements.txt | Semáforo asyncio(5) (frena pipeline), solo retry sin backoff (insuficiente) |

### Implementado

- [x] Modelo `CompendiumSection` + migración `007_create_compendium_sections_table.py`
- [x] Campos: project_id, section_number (1-11), section_name, content, model_used, dosification, tokens, cost_usd, status, prompt_version, notion_page_id, error_message
- [x] UNIQUE(project_id, section_number) + relación con Project
- [x] Máquina de estados: añadida transición `DRAFT → GENERATING`
- [x] `SECTION_CONFIGS` con 11 entradas: nombre, siguiente sección, dosificación (🟢/🟡/🔴), motor (gemini/claude), MAPA_ECOS, nota co-generación
- [x] `build_section_prompt()`: función pura que construye el prompt completo de cada sección
- [x] Módulo `compendiums/`: schemas, service, dependencies, router
- [x] Endpoint `POST /projects/{id}/merge`: une extracciones completadas, limpia marcadores, guarda en `merged_content`
- [x] Endpoint `POST /projects/{id}/generate`: crea 11 CompendiumSection, transiciona a `GENERATING`, encola jobs ARQ
- [x] Endpoint `GET /projects/{id}/sections`: lista las 11 secciones
- [x] Endpoints `GET /sections/{id}`, `PUT /sections/{id}`, `POST /sections/{id}/regenerate`
- [x] Worker `generate_section()`: carga prompts de DB, construye prompt, llama a OpenRouter, guarda resultado
- [x] Auto-transición `GENERATING → REVIEW` cuando las 11 secciones completan
- [x] Retry/backoff con `tenacity` en `OpenRouterClient.generate()`: 3 intentos, exponential backoff (4s→16s→64s)
- [x] Tests: 10 de section_builder, 12 de compendiums API, 9 de generation worker

### Archivos nuevos

- `backend/app/models/compendium_section.py`
- `backend/alembic/versions/007_create_compendium_sections_table.py`
- `backend/app/modules/prompts/section_builder.py`
- `backend/app/modules/compendiums/__init__.py`
- `backend/app/modules/compendiums/schemas.py`
- `backend/app/modules/compendiums/dependencies.py`
- `backend/app/modules/compendiums/service.py`
- `backend/app/modules/compendiums/router.py`
- `backend/app/workers/generation_worker.py`
- `backend/tests/test_section_builder.py`
- `backend/tests/test_compendiums.py`
- `backend/tests/test_generation_worker.py`

### Archivos modificados

- `backend/app/models/project.py` — +transición DRAFT→GENERATING, +relación `sections`
- `backend/alembic/env.py` — +imports Extraction, PromptTemplate, CompendiumSection
- `backend/app/workers/__init__.py` — +registro `generate_section`
- `backend/app/main.py` — +router compendiums
- `backend/app/modules/ai_gateway/openrouter_client.py` — +decorador `@retry` con tenacity

---

## 2026-07-07 — Sprint 4: Extracción real (opt-in, con presupuesto)

### Implementado

- [x] Endpoint `POST /projects/{id}/extract-all` — crea extracciones para todos los documentos del proyecto y encola jobs ARQ
- [x] Auto-transición `extracting` → `draft` en el worker cuando todas las extracciones del proyecto terminan
- [x] Logging de costos con structlog: `extraction_completed` (model, tokens, cost_usd) y `extraction_failed` (error)
- [x] Manejo de errores del worker: fallos en OpenRouter se guardan en `extraction.error_message` y documento pasa a `error`
- [x] Tests: extract-all crea extracciones, salta docs activos, transiciona proyecto, proyecto vacío, auto-draft, docs pendientes
- [x] 39 tests pasando (18 base + 15 módulos + 6 Sprint 4)

### Archivos modificados

- `backend/app/modules/extractions/schemas.py` — +`ExtractAllResponse`
- `backend/app/modules/extractions/service.py` — +`extract_all_for_project()`
- `backend/app/modules/extractions/router.py` — +`POST /projects/{id}/extract-all`
- `backend/app/workers/extraction_worker.py` — +`_check_project_extractions_done()`, +structlog
- `backend/tests/test_extractions.py` — +4 tests de extract-all
- `backend/tests/test_extraction_worker.py` — +2 tests de auto-transición
- `docs/12_roadmap_sprints.md` — Sprint 4 marcado como completado

---

## 2026-07-07 (noche) — Sprint 0: Consolidación Arquitectónica

### Decisiones

| # | Decisión | Justificación | Alternativas |
|---|----------|---------------|-------------|
| D-017 | **OpenRouter como AI Gateway principal** | Una sola API key/SDK, pricing transparente, acceso a Gemini/Claude/+200 modelos. Interfaz extensible para proveedores nativos futuros | SDKs nativos separados desde el inicio |
| D-018 | **Tests con mocks + E2E controlado** | Tests automáticos sin costo de API; test real opcional con presupuesto fijo | Solo tests reales (costoso) o solo mocks (poco realista) |
| D-019 | **Worker ARQ en contenedor separado** | Escalable desde el inicio, misma imagen que backend | Worker en mismo contenedor |
| D-020 | **S3/MinIO para compendios en local y prod** | Compendios `.md` públicos; MinIO en Docker para dev, S3 en producción | Filesystem local para compendios |
| D-021 | **Frontend después del MVP backend** | Validar pipeline vía API antes de invertir en UI | Frontend en paralelo desde inicio |
| D-022 | **Respuestas API directas (sin envelope)** | Mantiene lo que funciona; envelope puede agregarse vía middleware si se necesita | Envelope `{data, meta, error}` desde inicio |

### Implementado

- [x] Roadmap maestro en `docs/12_roadmap_sprints.md`
- [x] Stack actualizado: OpenRouter, S3/MinIO, workers, tests
- [x] `requirements.txt` actualizado (`openai`, `aiobotocore`, `tenacity`, `pytest`, etc.)
- [x] `S3StorageBackend` con `aiobotocore` + bucket auto-creación + MinIO local en Docker Compose
- [x] Worker ARQ base (`backend/app/workers/`) + servicio `worker` en Docker Compose
- [x] Relaciones SQLAlchemy entre `User`, `Project`, `SourceDocument`
- [x] Schema corregido: `projects.description` opcional, `source_documents.document_type` NOT NULL default `article`
- [x] Máquina de estados `ProjectStatus` con validación de transiciones
- [x] Campos de publicación en `projects` (`is_published`, `s3_bucket`, `s3_key`, `public_url`)
- [x] CORS configurable vía `BACKEND_CORS_ORIGINS`
- [x] `POST /auth/refresh` con refresh tokens separados
- [x] Scaffold de tests con `pytest-asyncio`, nested transactions, 18 tests pasando
- [x] Migración `004` (7bb70c4aeb77) con ajustes de schema

---

## 2026-07-07 (noche) — Iteración 2: Documents Module

### Decisiones

| # | Decisión | Justificación | Alternativas |
|---|----------|---------------|-------------|
| D-016 | **Storage local con abstracción para S3** | Permite MVP sin dependencias de AWS; abstracción `StorageBackend` facilita migración a S3 sin tocar lógica de negocio. `file_path` usa URI (`local://...` / `s3://...`) | S3 desde inicio (requiere credenciales AWS), filesystem sin abstracción (deuda técnica) |

### Implementado

- [x] Módulo Documents: upload múltiple, list, get, delete, download
- [x] Storage abstraction (`app/services/storage.py`) con `LocalStorageBackend` + placeholder `S3StorageBackend`
- [x] Modelo `SourceDocument` + migración `003`
- [x] Docker Compose: volumen `pdf_data` para persistencia de PDFs
- [x] Configuración: `PDF_STORAGE_PATH`, `MAX_UPLOAD_SIZE_MB`, `MAX_FILES_PER_UPLOAD`

### Migración futura a S3

Ver `backend/app/services/storage.py` para guía completa de migración.

---

## 2026-07-06 (tarde) — Refinamiento: OpenRouter + S3 + Visor Público

### Decisiones

| # | Decisión | Justificación | Alternativas |
|---|----------|---------------|-------------|
| D-011 | **OpenRouter como AI Gateway unificado** | Una sola API key, un solo SDK (compatible con OpenAI), pricing transparente en cada response, ruteo a Gemini y Claude desde el mismo cliente | SDKs nativos de Google y Anthropic por separado (más código, más keys, más complejidad) |
| D-012 | **S3 para almacenamiento de compendios** | Los .md generados son costosos (~$7-10/patología); deben ser reutilizables. S3 permite servirlos públicamente sin pasar por el backend | Servir desde PostgreSQL (carga la DB, latencia), filesystem local (no escala, backups manuales) |
| D-013 | **Visor público sin autenticación** | Maximiza el retorno de inversión: un compendio generado puede ser consultado por cualquier residente sin necesidad de cuenta | Solo usuarios autenticados (limita el valor del contenido generado) |
| D-014 | **marked.js para renderizado Markdown** | Librería mínima (19KB), sin dependencias, renderizado client-side desde el .md en S3 | React-markdown (más pesado), renderizado server-side (carga el backend) |
| D-015 | **Rol `creator` (único que genera)** | Solo usuarios autenticados con rol creator pueden crear proyectos y generar compendios (gastar créditos de API). El público solo lee | Cualquier usuario autenticado puede generar (riesgo de gasto descontrolado) |

### Cambios en docs
- `01_requisitos.md`: + roles, + RF-01.5 (publicar), + RF-08 (visor público), + RNF-04 (control costos)
- `02_arquitectura.md`: Diagrama actualizado con OpenRouter + S3 + visor público
- `03_stack_tecnologico.md`: Gemini/Claude SDKs → OpenRouter SDK, + marked.js, + S3/MinIO
- `04_modelo_datos.md`: + role en users, + is_published/S3 fields en projects, unificada api_keys
- `05_api_design.md`: + endpoints públicos (`/public/*`), + Notion+S3 en publish
- `09_pipeline_ia.md`: Reescrito para OpenRouter (cliente único, pricing automático)

---

## 2026-07-06 (mañana) — Inicio del Proyecto

### Decisiones

| # | Decisión | Justificación | Alternativas |
|---|----------|---------------|-------------|
| D-001 | **Monolito modular** sobre microservicios | 1 solo desarrollador, VPS único, ~50 usuarios máximo | Microservicios (overkill), serverless (cold start en IA jobs) |
| D-002 | **FastAPI** como framework backend | Async nativo, OpenAPI auto, Pydantic integrado | Django, Express/Node |
| D-003 | **React + TypeScript + Vite** como frontend | SPA simple, sin SSR necesario | Next.js, Vue, HTMX |
| D-004 | **PostgreSQL** como base de datos | JSONB para prompts versionados, robustez probada | SQLite, MongoDB |
| D-005 | **ARQ** como cola de tareas | Más simple que Celery, Python puro, async nativo | Celery, RQ, Dramatiq |
| D-006 | **Docker Compose** para despliegue | Reproducible, un solo comando | Kubernetes, Ansible, bare metal |
| D-007 | **Email/password inicial**, OAuth después | MVP rápido | OAuth desde el inicio |
| D-008 | **API key del sistema** (no por usuario) | El Dr. paga las APIs; los usuarios son colaboradores | API keys por usuario |
| D-009 | **shadcn/ui + Tailwind** para componentes | Componentes accesibles, personalizables, sin lock-in | MUI, Ant Design, Bootstrap |
| D-010 | **Estructura de módulos autocontenidos** | Cada módulo con router/service/models propio | Capas horizontales (acoplamiento) |

### Estado actual del proyecto

- [x] Documentación de arquitectura completa (`docs/00-12`)
- [x] Material de referencia del Dr. organizado (`memory/`)
- [x] Refinamiento con OpenRouter + S3 + visor público
- [x] Backend: Auth + Projects + Documents + Extractions + Prompts + AI Gateway + Workers + S3/MinIO
- [x] Docker Compose con Postgres + Redis + backend + worker + MinIO + volumen PDFs
- [x] 39 tests pasando (auth, projects, documents, extractions, worker, AI gateway, prompts)
- [ ] Frontend: scaffold inicial
- [ ] Compendium module (merge + generation)
- [ ] Publishing module (S3 upload + public viewer)
- [ ] Notion integration

---

> **Documento anterior:** [10_deployment.md](10_deployment.md)
> **Volver al inicio:** [00_vision.md](00_vision.md)
