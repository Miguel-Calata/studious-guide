# 12 — Roadmap de Sprints

Documento maestro de planificación. Cada sprint tiene objetivo, tareas, tests de aceptación y dependencias.

---

## 0. Decisiones arquitectónicas vigentes

| # | Decisión | Valor elegido | Notas |
|---|----------|---------------|-------|
| D-017 | AI Gateway | **OpenRouter** como proveedor principal, usando el SDK compatible con OpenAI. La arquitectura del AI Gateway se diseña con una interfaz clara para poder agregar proveedores nativos (Gemini, Anthropic, etc.) en el futuro sin cambiar la lógica de negocio. | Actualizado en `03_stack_tecnologico.md`. |
| D-018 | Tests de IA | **Mocks por defecto** en CI/tests automáticos. **Un test E2E controlado** contra OpenRouter se puede ejecutar manualmente con un PDF pequeño y presupuesto fijo. | Evita costos sorpresa. |
| D-019 | Workers ARQ | **Contenedor `worker` separado** en `docker-compose.yml`, compartiendo imagen con el backend. | Escalable desde el inicio. |
| D-020 | Storage de compendios | **S3 / S3-compatible (MinIO) tanto en local como en prod**. Los PDFs fuente permanecen en storage local abstracto. | MinIO en Docker para dev; S3 real en prod. |
| D-021 | Frontend | **Después del MVP backend**. El Dr. valida el pipeline vía API/CLI primero. | Fase 2. |
| D-022 | Envelope de respuesta API | **Pendiente de decidir**. Por ahora se mantiene el estilo directo (`ProjectResponse`, listas planas). Si más adelante se necesita envelope, se implementa con un middleware. | Baja prioridad. |

---

## 1. Estado previo al Sprint 0

### ✅ Hecho
- Auth (register, login, me)
- Projects (CRUD + soft-delete + slug auto)
- Documents (multi-upload, download, delete, storage local abstracto)
- Docker Compose: Postgres + Redis + Backend

### ⚠️ Inconsistencias a resolver
- `03_stack_tecnologico.md` aún menciona SDKs nativos de Gemini/Claude.
- `requirements.txt` no incluye `openai` ni dependencias S3.
- No existe backend de S3/MinIO a pesar de que se decidió usarlo.
- No hay workers ARQ ni servicio `worker` en Docker Compose.
- No hay tests.
- La máquina de estados de `Project` no se respeta.
- Faltan relaciones SQLAlchemy entre modelos.
- Inconsistencia en schema: `description` es obligatoria en DB pero opcional en docs; `document_type` es opcional en DB pero obligatoria en docs.
- CORS hardcodeado.
- Falta `POST /auth/refresh`.

---

## 2. Fase 0 — Consolidación Arquitectónica

### Sprint 0: Base sólida

**Objetivo:** Resolver inconsistencias antes de construir el pipeline de IA.

#### Tareas
- [x] Actualizar `docs/03_stack_tecnologico.md`: OpenRouter principal, S3/MinIO, workers ARQ, extensibilidad a otros proveedores.
- [x] Actualizar `backend/requirements.txt`: agregar `openai`, `aiobotocore` (para S3 async), `tenacity`; quitar `google-generativeai` y `anthropic` del stack principal (se pueden re-agregar cuando se implemente otro proveedor).
- [x] Implementar `S3StorageBackend` en `backend/app/services/storage.py` usando `aiobotocore` + endpoint configurable para MinIO.
- [x] Añadir servicio `minio` a `docker/docker-compose.yml` con volúmenes y healthcheck.
- [x] Añadir servicio `worker` a `docker/docker-compose.yml` compartiendo imagen del backend.
- [x] Crear `backend/app/workers/__init__.py` con `WorkerSettings` base.
- [x] Añadir relaciones SQLAlchemy: `User.projects`, `Project.documents`, `Project.extractions`, `Project.sections`.
- [x] Corregir schema:
  - `projects.description` → opcional.
  - `source_documents.document_type` → NOT NULL con default `'article'`.
- [x] Implementar validación de máquina de estados para `Project`.
- [x] Mover CORS a `Settings` (`BACKEND_CORS_ORIGINS`).
- [x] Implementar `POST /auth/refresh`.
- [x] Crear scaffold de tests: `backend/tests/conftest.py`, `backend/tests/test_auth.py`, `backend/tests/test_projects.py`, `backend/tests/test_documents.py`.

#### Tests de aceptación
- [x] `docker compose up` levanta postgres, redis, backend, worker y minio.
- [x] `alembic upgrade head` aplica todas las migraciones sin errores.
- [x] Todos los tests de auth, projects y documents pasan.
- [x] No hay imports rotos ni dependencias huérfanas.
- [x] `POST /auth/refresh` devuelve un nuevo access token válido.
- [x] La máquina de estados rechaza transiciones inválidas.

---

## 3. Fase 1 — MVP Backend (pipeline completo)

### Sprint 1: Extractions — modelo y API

**Objetivo:** Crear y consultar extracciones, aún sin ejecutar IA.

#### Tareas
- [x] Modelo `Extraction` + migración `004_create_extractions_table.py`.
- [x] Módulo `extractions/`: schemas, service, dependencies, router.
- [x] Endpoints:
  - `POST /documents/{id}/extract`
  - `GET /extractions/{id}`
  - `GET /extractions/{id}/status`
  - `POST /extractions/{id}/retry`
- [x] Actualizar `source_document.status` y `project.status` al crear/reintentar extracciones.

#### Tests
- [x] Crear extracción devuelve `201` y estado `pending`.
- [x] No se puede crear segunda extracción para un documento con extracción no-fallida.
- [x] Retry solo funciona en estado `failed`.
- [x] Proyecto pasa a `extracting` cuando hay extracciones activas.

---

### Sprint 2: AI Gateway + Prompt Engine semilla

**Objetivo:** Cliente OpenRouter testeable y prompts iniciales en DB.

#### Tareas
- [x] `backend/app/modules/ai_gateway/openrouter_client.py` con `generate()` y `generate_with_continuations()`.
- [x] Interfaz `AIGatewayClient` abstracta para futuros proveedores.
- [x] `backend/app/modules/prompts/`: modelo `PromptTemplate`, migración `005`, endpoints GET/PUT.
- [x] Seed inicial de prompts vía migración: `system_prompt_sam_v9`, `extraction_v3_bmj`, `extraction_v5_guideline`, `extraction_articles`, `audit`, `patch_gemini_density`.
- [x] Esqueleto de `backend/app/services/orchestrator.py`.

#### Tests
- [x] Llamada mock a OpenRouter devuelve `AIResult` con tokens y costo.
- [x] `generate_with_continuations` concatena correctamente al detectar `[CONTINÚA...]`.
- [x] Seed carga al menos 6 prompts activos.
- [x] GET `/prompts/{name}` devuelve el prompt activo.

---

### Sprint 3: Worker de extracción (con mocks)

**Objetivo:** El worker procesa extracciones sin costo real.

#### Tareas
- [x] `backend/app/workers/extraction_worker.py` con función `extract_document`.
- [x] Leer PDF desde storage local.
- [x] Seleccionar prompt según `document_type`.
- [x] Guardar resultado en `Extraction.content`.
- [x] Manejar fallos (`status = failed`, `error_message`).
- [x] Encolar `audit_extraction` al completar.

#### Tests
- [x] Encolar un job y ejecutarlo con worker de test actualiza `Extraction` a `completed`.
- [x] Worker con mock de OpenRouter guarda contenido esperado.
- [x] Si OpenRouter falla, estado pasa a `failed` con mensaje.
- [x] Auditoría se encola automáticamente tras extracción exitosa.

---

### Sprint 4: Extracción real (opt-in, con presupuesto)

**Objetivo:** Conectar con OpenRouter real de forma controlada.

#### Tareas
- [x] `OPENROUTER_API_KEY` en `.env`.
- [x] Endpoint `POST /projects/{id}/extract-all`.
- [x] Proyecto pasa `extracting` y luego `draft` al finalizar.
- [x] Logs de costos por extracción.

#### Tests
- [x] Con API key válida, extrae un PDF pequeño real (< $0.50).
- [x] Con API key inválida, falla gracefulmente.
- [x] Costo total se guarda en `Extraction.cost_usd`.

---

### Sprint 5: Merger + Compendium Generation

**Objetivo:** Unir extracciones y generar las 11 secciones.

#### Tareas
- [x] Modelo `CompendiumSection` + migración `007_create_compendium_sections_table.py`.
- [x] Módulo `compendiums/`: schemas, service, router.
- [x] `POST /projects/{id}/merge` → guarda `projects.merged_content`.
- [x] `POST /projects/{id}/generate` → encola 11 jobs `generate_section`.
- [x] `backend/app/workers/generation_worker.py` con selección de modelo según `SECTION_CONFIGS`.
- [x] Guardar secciones en `compendium_sections`.
- [x] Proyecto pasa `extracting → generating → review`.

#### Tests
- [x] Merge con 2 extracciones produce `merged_content` no vacío.
- [x] Generar compendio crea 11 jobs.
- [x] Cada sección se guarda con `model_used`, `cost_usd`, `prompt_version`.
- [x] En tests con mock, secciones 🔴 usan modelo Claude y 🟢🟡 usan Gemini.

---

### Sprint 6: Public viewer + Publishing

**Objetivo:** Publicar compendio final y servir markdown público.

#### Tareas
- [x] Módulo `publishing/`.
- [x] `POST /projects/{id}/publish` → ensambla `.md`, sube a S3/MinIO, guarda URL.
- [x] Endpoints públicos:
  - `GET /public/compendiums`
  - `GET /public/compendiums/{slug}`
  - `GET /public/compendiums/{slug}/download`
- [x] Proyecto pasa a `completed`, `is_published = True`.

#### Tests
- [x] Publish genera archivo `.md` accesible en S3/MinIO.
- [x] Endpoint público devuelve metadata sin auth.
- [x] Download devuelve el contenido exacto.

---

### Sprint 7: Notion Integration

**Objetivo:** Publicar en Notion.

#### Tareas
- [x] Módulo `notion/` + modelo `NotionConfig`.
- [x] `POST /notion/connect` con API key encriptada (Fernet).
- [x] `GET /notion/status` para ver estado de conexión.
- [x] `GET /notion/search?query=` para buscar páginas padre.
- [x] `PUT /notion/config` para setear `default_parent_page_id`.
- [x] `POST /projects/{id}/publish/notion` → crea página raíz (con resumen + índice) + 11 páginas hijas.
- [x] Conversor Markdown → Notion blocks (headers, bold/italic, tablas, callouts, code, listas).
- [x] Re-publish actualiza páginas existentes (vía `notion_page_id` en secciones).
- [x] API key encriptada con `cryptography.fernet` (key derivada de JWT secret).

#### Tests
- [x] Mock de Notion API: connect guarda config encriptada, publish crea 12 páginas.
- [x] 8 tests: connect válido/inválido, status conectado/desconectado, search, publish crea, publish actualiza existente, publish sin conexión.
- [ ] Test E2E opcional con Notion real en página de prueba.

---

## 4. Fase 2 — Frontend (después del MVP backend)

### Sprint 8: Frontend scaffold ✅
- [x] Scaffold Vite + React 19 + TypeScript en `frontend/`.
- [x] Tailwind CSS + shadcn/ui (Button, Input, Card, Label, utils).
- [x] Proxy de Vite: `/api/v1/*` → `http://localhost:8000` con `credentials: include`.
- [x] Auth con **cookies httpOnly** en backend (`login`/`refresh` setean cookies, nuevo `/auth/logout`, `me` y rutas protegidas leen cookie con fallback a Bearer).
- [x] Auth Context + refresh automático en el cliente (reintenta `/auth/refresh` ante 401).
- [x] React Router v6: rutas públicas (`/login`, `/register`) y protegidas (`/` AppShell + Header).
- [x] SWR configurado con fetcher de `api`.
- [x] Formularios con react-hook-form + zod (login/register).
- [x] Tests Vitest: AuthContext, ProtectedRoute, api client (5 tests).
- [x] Docs actualizadas (README + changelog).

> **Decisión F-1:** Auth vía cookies httpOnly desde el inicio (no localStorage) para mitigar robo de token por XSS. El dominio de cookie es configurable (`COOKIE_DOMAIN`) para compartir entre subdominios (`.astreo.space`). `secure` y `samesite` configurables para prod. Logout solo limpia cookies (sin denylist de refresh token en backend; ver nota de seguridad en changelog).

### Sprint 9: Dashboard de proyectos
- Login screen.
- Lista de proyectos.
- Crear proyecto.
- Subir PDFs.

### Sprint 10: Pipeline UI
- Botón "Extraer todo".
- Ver estado de extracciones.
- Botón "Generar compendio".
- Editor Markdown para revisar secciones.

### Sprint 11: Public viewer + publish
- Pantalla de publicar.
- Visor público de compendios.
- Botón "Abrir en Notion".

---

## 5. Fase 3 — Multi-user & Admin

### Sprint 12: Roles y permisos
- Admin puede editar prompts.
- Gestión de usuarios básica.

### Sprint 13: Control de costos
- Dashboard de costos por proyecto/mes.
- Alerta de umbral configurable.

---

## 6. Fase 4 — Colaboración (futuro)

### Sprint 14+
- Comentarios en secciones.
- Revisión por pares.
- Historial de cambios.

---

## 7. Estrategia de tests

| Tipo | Cuándo | Ejemplos |
|------|--------|----------|
| Unitarios | Lógica pura | builders de prompts, merge de extracciones, cálculo de costos, máquina de estados |
| Integración API | Cada endpoint nuevo | auth, CRUDs, upload, extracciones, publicación |
| Integración worker | Jobs de ARQ | extraction_worker, generation_worker con mocks |
| E2E controlado | Antes de cerrar sprints de IA/Notion | 1 extracción real con PDF pequeño, 1 publicación real en Notion sandbox |
| Contrato | CI | OpenAPI spec vs implementación |

---

## 8. Dependencias entre sprints

```
Sprint 0 ──▶ Sprint 1 ──▶ Sprint 2 ──▶ Sprint 3 ──▶ Sprint 4
   │            │            │            │
   │            ▼            ▼            ▼
   │         (modelo     (AI client   (OpenRouter
   │          Extract)    + prompts)    real)
   │
   └──────────────▶ Sprint 5 ──▶ Sprint 6 ──▶ Sprint 7
                    (Merger +      (Publish +    (Notion)
                     Generation)    Public viewer)

Sprint 8-11: Frontend (paralelizable desde Sprint 5)
Sprint 12-14: Admin + multi-user (después de Fase 1)
```

---

## 9. Notas para agents

- Nunca avanzar a un sprint sin que los tests de aceptación del anterior pasen.
- Antes de implementar un nuevo módulo, revisar este documento y `02_arquitectura.md`.
- Cualquier cambio de decisión arquitectónica debe registrarse en `11_changelog.md` y actualizar este roadmap si afecta el orden o alcance de los sprints.
