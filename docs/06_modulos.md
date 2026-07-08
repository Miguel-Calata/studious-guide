# 06 — Módulos del Sistema

## 🧩 Desglose de Módulos

Cada módulo sigue la misma estructura interna:

```
backend/app/modules/<nombre>/
├── __init__.py          # Exporta router
├── router.py            # Endpoints FastAPI
├── schemas.py           # Pydantic models (request/response)
├── service.py           # Lógica de negocio
├── models.py            # SQLAlchemy models (si aplica)
└── dependencies.py      # Dependencias FastAPI
```

---

## 1. Auth Module

**Responsabilidad:** Registro, login, gestión de sesiones JWT.

```
auth/
├── router.py            # POST /register, /login, /refresh, GET /me
├── schemas.py           # RegisterRequest, LoginRequest, TokenResponse, UserResponse
├── service.py           # create_user, authenticate_user, create_tokens, verify_token
├── models.py            # User (SQLAlchemy)
└── dependencies.py      # get_current_user (JWT dependency)
```

**Dependencias:** PostgreSQL (tabla `users`), `PyJWT`, `bcrypt`

---

## 2. Projects Module

**Responsabilidad:** CRUD de proyectos (patologías), estado del pipeline.

```
projects/
├── router.py            # CRUD endpoints
├── schemas.py           # ProjectCreate, ProjectUpdate, ProjectResponse, ProjectList
├── service.py           # create_project, get_project, list_projects, update_status
├── models.py            # Project (SQLAlchemy)
└── dependencies.py      # get_project_or_404
```

**Dependencias:** PostgreSQL (tabla `projects`), Auth module (owner verification)

**Máquina de estados del proyecto:**
```
draft → extracting → generating → review → completed
  ↓         ↓            ↓
  └─────────┴────────────┴──→ archived
```

---

## 3. Documents Module

**Responsabilidad:** Upload, almacenamiento, clasificación y gestión de PDFs fuente.

```
documents/
├── router.py            # CRUD + download endpoints
├── schemas.py           # DocumentUpload, DocumentResponse, DocumentClassify
├── service.py           # upload_pdf, classify_document, get_file_path, delete_pdf
├── models.py            # SourceDocument (SQLAlchemy)
└── dependencies.py      # get_document_or_404
```

**Almacenamiento:** Filesystem local en `/data/pdfs/{project_id}/{uuid}.pdf`
- Configurable vía `PDF_STORAGE_PATH`
- `S3StorageBackend` ya implementado con `aiobotocore` para MinIO (local) y S3 (producción)

**Validaciones:**
- Extensión: solo `.pdf`
- Tamaño máximo: 50MB
- Nombre de archivo sanitizado (elimina caracteres especiales)

---

## 4. Extractions Module

**Responsabilidad:** Orquestar la extracción de contenido de PDFs usando OpenRouter (Gemini vía API unificada).

```
extractions/
├── router.py            # POST extract, POST extract-all, GET status, GET result, POST retry
├── schemas.py           # ExtractionResponse, ExtractionStatusResponse, ExtractAllResponse
├── service.py           # start_extraction, get_extraction, retry_extraction, extract_all_for_project
├── dependencies.py      # get_extraction_or_404, get_document_for_extract
```

**Flujo interno:**
1. `start_extraction(document_id)` → crea registro en `extractions` con status `pending`
2. Encola job `extract_document` en ARQ
3. Worker `extraction_worker.py`:
   a. Carga PDF desde storage y convierte a Markdown (pymupdf4llm)
   b. Selecciona prompt según `document_type`
   c. Llama a OpenRouter (Gemini 2.5 Pro) con `generate_with_continuations`
   d. Guarda extracción completa (content, tokens, cost_usd)
   e. Encola job `audit_extraction`
   f. Verifica si todas las extracciones del proyecto terminaron → transiciona a `draft`
4. `extract_all_for_project(project_id)` → crea extracciones pendientes para todos los documentos del proyecto, encola jobs ARQ, transiciona proyecto a `extracting`

**Prompt mapping:**
| document_type | Prompt name |
|--------------|-------------|
| `bmj` | `extraction_v3_bmj` |
| `guideline` | `extraction_v5_guideline` |
| `article` | `extraction_articles` |

---

## 5. Compendium Module

**Responsabilidad:** Unir extracciones, generar las 11 secciones del compendio usando Gemini + Claude.

```
compendiums/
├── router.py            # POST merge, POST generate, GET sections, PUT section, POST regenerate
├── schemas.py           # MergeResponse, GenerateRequest, SectionResponse, SectionUpdate
├── service.py           # merge_extractions, generate_sections, regenerate_section
├── models.py            # CompendiumSection (SQLAlchemy)
└── dependencies.py
```

**Flujo interno `merge_extractions`:**
1. Obtiene todas las extracciones completadas del proyecto
2. Concatena contenido en orden (usando lógica de `unir_extraccion.py` legacy)
3. Limpia marcadores `[CONTINÚA...]`
4. Guarda en `projects.merged_content`

**Flujo interno `generate_sections`:**
1. Verifica que `merged_content` existe
2. Para cada sección solicitada (o las 11):
   a. Carga el prompt template (System Prompt SAM v9)
   b. Construye prompt específico con MAPA_ECOS para esa sección
   c. Determina motor: `motor_map[section_number]` → Gemini o Claude
   d. Determina dosificación: `dosification_map[section_number]` → parámetros del modelo
   e. Encola job `generate_section` en ARQ
3. Workers procesan jobs en paralelo (con límite de concurrencia para no saturar APIs)

**Worker `generation_worker.py`:**
1. Recibe section_number, project_id
2. Obtiene `merged_content` del proyecto
3. Construye prompt final (system prompt + sección + MAPA_ECOS)
4. Llama a Gemini o Claude según motor
5. Guarda resultado en `compendium_sections`
6. Actualiza contador de tokens y costo

---

## 6. Prompt Engine Module

**Responsabilidad:** Almacenar, versionar y servir los prompts del sistema.

```
prompts/
├── router.py            # GET list, GET by name, PUT update, GET versions
├── schemas.py           # PromptResponse, PromptUpdate, PromptVersion
├── service.py           # get_active_prompt, create_version, build_section_prompt
├── models.py            # PromptTemplate (SQLAlchemy)
└── dependencies.py
```

**Prompts del sistema (semillas iniciales):**

| Name | Type | Descripción |
|------|------|-------------|
| `system_prompt_sam_v9` | `system` | System Prompt con 5 Pilares y 10 Leyes |
| `extraction_v3_bmj` | `extraction` | Prompt para BMJ Best Practice |
| `extraction_v5_guideline` | `extraction` | Prompt para guías completas (KDIGO, WHO, etc.) |
| `extraction_articles` | `extraction` | Prompt para artículos (Lancet, NEJM, etc.) |
| `audit` | `audit` | Prompt de auditoría post-extracción |
| `patch_gemini_density` | `patch` | Parche de densidad de citas para Gemini |

**Servicio `build_section_prompt`:**
```python
def build_section_prompt(
    section_number: int,
    merged_content: str,
    pathology_name: str,
    source_filename: str
) -> str:
    """
    Construye el prompt completo para una sección,
    incluyendo system prompt, MAPA_ECOS, dosificación y motor.
    
    Replica la lógica de sam_v9_generador.py.construir_prompt_corto()
    """
```

**MAPA_ECOS:** Viene del script legacy (`sam_v9_generador.py`). Cada sección 2-11 tiene una lista de temas ya cubiertos que no debe repetir.

**DOSIFICACION:**
| Sección | Nivel | Motor | Extended Thinking |
|---------|-------|-------|-------------------|
| 1, 2, 4, 7 | 🟢 STANDARD | Gemini | No |
| 3, 5, 8, 9 | 🔴 MAX | Claude | Sí |
| 6, 10, 11 | 🟡 HIGH | Gemini | No |

---

## 7. AI Gateway Module

**Responsabilidad:** Abstracción unificada para llamadas a modelos de IA vía OpenRouter.

```
ai_gateway/
├── interfaces.py          # AIGatewayClient (ABC) + AIResult (dataclass)
└── openrouter_client.py   # Implementación con SDK openai compatible
```

**Archivos implementados:**

- `interfaces.py`: Define `AIGatewayClient` (interfaz abstracta) y `AIResult` (dataclass con content, model, tokens, cost_usd, finish_reason). Permite agregar proveedores nativos futuros sin cambiar lógica de negocio.
- `openrouter_client.py`: Implementación con `AsyncOpenAI` apuntando a OpenRouter. Incluye `generate()` y `generate_with_continuations()` (detecta `[CONTINÚA...]` y pide más contenido).

**Modelos disponibles:**
```python
MODELS = {
    "gemini": "google/gemini-2.5-pro",
    "claude": "anthropic/claude-3.5-sonnet",
}
```

**No expone endpoints propios** — es usado internamente por workers y orchestrator.

**Cost tracking:** OpenRouter devuelve el costo en USD en cada response (`response.cost`). No se necesita CostTracker propio.

---

## 8. Notion Module

**Responsabilidad:** Integración con Notion API para publicación de compendios.

```
notion/
├── router.py            # POST connect, GET status, GET search, POST publish
├── schemas.py           # NotionConnect, NotionStatus, PublishRequest
├── service.py           # connect_notion, search_pages, publish_section, publish_compendium
├── models.py            # NotionConfig (SQLAlchemy)
└── client.py            # Wrapper sobre Notion SDK
```

**Flujo de publicación:**
1. `publish_compendium(project_id, parent_page_id)`:
   a. Crea página principal con nombre de la patología
   b. Para cada sección completada:
      - Crea página hija con el contenido Markdown
      - Notion API convierte MD a bloques de Notion
      - Guarda `notion_page_id` en la sección
   c. Retorna resumen de páginas creadas

---

## 9. Workers (ARQ)

```
workers/
├── __init__.py              # WorkerSettings (registra funciones)
└── extraction_worker.py     # extract_document + audit_extraction
```

Cada worker es una función async registrada en ARQ. Se ejecutan en el contenedor `worker` (misma imagen que backend). `WorkerSettings` en `__init__.py` registra las funciones disponibles.

---

## 🔗 Comunicación entre Módulos

```
                   ┌─────────────┐
                   │ Orchestrator │  (coordina flujos complejos)
                   └──┬───┬───┬──┘
                      │   │   │
          ┌───────────┼───┼───┼───────────┐
          ▼           ▼   ▼   ▼           ▼
    ┌──────────┐ ┌──────┐ ┌──────┐ ┌──────────┐
    │Extractions│ │Merger│ │Prompt│ │Generation│
    │ Service  │ │Service│ │Engine│ │ Service  │
    └──────────┘ └──────┘ └──────┘ └──────────┘
          │                    │          │
          └────────────────────┼──────────┘
                               ▼
                        ┌──────────┐
                        │AI Gateway│
                        └──────────┘
```

- **Orchestrator** (`backend/app/services/orchestrator.py`): coordina el pipeline completo (extraer todo → unir → generar secciones). Es llamado desde endpoints y desde workers.
- Los módulos **no se importan entre sí** directamente. Usan servicios compartidos del `orchestrator` o se comunican vía jobs en Redis.

---

> **Próximo documento:** [07_notion.md](07_notion.md)
