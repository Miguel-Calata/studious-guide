# 04 — Modelo de Datos

## 🗺️ Diagrama Entidad-Relación

```
┌──────────┐       ┌───────────┐       ┌──────────────┐
│   User   │──1:N──│  Project  │──1:N──│   Document   │
└──────────┘       └───────────┘       └──────────────┘
                                             │
                                             │ 1:N
                                             ▼
                    ┌───────────┐       ┌──────────────┐
                    │ Compendium│◄──1:1─│  Extraction  │
                    └───────────┘       └──────────────┘
                         │
                         │ 1:N
                         ▼
                    ┌───────────┐
                    │  Section  │
                    └───────────┘

┌──────────────┐
│ PromptTemplate│  (independiente, versionado)
└──────────────┘

┌──────────────┐
│ NotionConfig │──1:1── User
└──────────────┘

┌──────────┐
│   Job    │  (efímero, en Redis. Solo referencia en DB para auditoría)
└──────────┘
```

---

## 📋 Tablas

### `users`

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `id` | UUID (PK) | Identificador único |
| `email` | VARCHAR(255) UNIQUE NOT NULL | Email de login |
| `password_hash` | VARCHAR(255) NOT NULL | Hash bcrypt |
| `full_name` | VARCHAR(255) | Nombre completo |
| `role` | VARCHAR(20) DEFAULT 'creator' | `creator` (genera compendios), `admin` (gestiona prompts) |
| `is_active` | BOOLEAN DEFAULT TRUE | Soft delete / desactivación |
| `created_at` | TIMESTAMPTZ DEFAULT NOW() | |
| `updated_at` | TIMESTAMPTZ DEFAULT NOW() | |

### `projects`

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `id` | UUID (PK) | |
| `user_id` | UUID (FK → users) NOT NULL | Dueño del proyecto |
| `name` | VARCHAR(255) NOT NULL | Nombre de la patología (ej. "Lesión Renal Aguda") |
| `slug` | VARCHAR(255) UNIQUE NOT NULL | Slug para URLs (ej. "lesion-renal-aguda") |
| `description` | TEXT | Descripción opcional |
| `status` | VARCHAR(50) DEFAULT 'draft' | draft, extracting, generating, review, completed, archived |
| `merged_content` | TEXT | Resultado de unir todas las extracciones (documento fuente) |
| `is_published` | BOOLEAN DEFAULT FALSE | Si el compendio está publicado |
| `s3_bucket` | VARCHAR(255) | Bucket S3/MinIO del compendio publicado |
| `s3_key` | VARCHAR(500) | Key del archivo .md en S3/MinIO |
| `public_url` | VARCHAR(1000) | URL pública del compendio |
| `created_at` | TIMESTAMPTZ DEFAULT NOW() | |
| `updated_at` | TIMESTAMPTZ DEFAULT NOW() | |

### `source_documents`

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `id` | UUID (PK) | |
| `project_id` | UUID (FK → projects) NOT NULL | |
| `filename` | VARCHAR(500) NOT NULL | Nombre original del archivo |
| `file_path` | VARCHAR(1000) NOT NULL | URI de storage: `local://...` o `s3://...` |
| `file_size` | BIGINT NOT NULL | Bytes |
| `document_type` | VARCHAR(50) DEFAULT 'article' | `bmj`, `guideline`, `article` |
| `status` | VARCHAR(50) DEFAULT 'uploaded' | uploaded, extracting, extracted, error |
| `created_at` | TIMESTAMPTZ DEFAULT NOW() | |
| `updated_at` | TIMESTAMPTZ DEFAULT NOW() | |

### `extractions`

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `id` | UUID (PK) | |
| `source_document_id` | UUID (FK → source_documents) UNIQUE NOT NULL | Una extracción por documento |
| `content` | TEXT NOT NULL | Markdown crudo extraído |
| `model_used` | VARCHAR(100) | Ej. "gemini-2.5-pro" |
| `input_tokens` | INTEGER | Tokens consumidos (input) |
| `output_tokens` | INTEGER | Tokens consumidos (output) |
| `cost_usd` | NUMERIC(10,6) | Costo en USD |
| `status` | VARCHAR(50) DEFAULT 'pending' | pending, processing, completed, failed |
| `error_message` | TEXT | Mensaje de error si falló |
| `audit_completed` | BOOLEAN DEFAULT FALSE | Si ya pasó la auditoría |
| `audit_content` | TEXT | Adenda de auditoría (si aplica) |
| `created_at` | TIMESTAMPTZ DEFAULT NOW() | |
| `updated_at` | TIMESTAMPTZ DEFAULT NOW() | |

### `compendium_sections`

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `id` | UUID (PK) | |
| `project_id` | UUID (FK → projects) NOT NULL | |
| `section_number` | INTEGER NOT NULL | 1-11 |
| `section_name` | VARCHAR(255) NOT NULL | Ej. "Descripción y Epidemiología" |
| `content` | TEXT | Markdown generado |
| `model_used` | VARCHAR(100) | gemini-2.5-pro o claude-3.5-sonnet |
| `dosification` | VARCHAR(10) | 🟢 STANDARD, 🟡 HIGH, 🔴 MAX |
| `input_tokens` | INTEGER | |
| `output_tokens` | INTEGER | |
| `cost_usd` | NUMERIC(10,6) | |
| `status` | VARCHAR(50) DEFAULT 'pending' | pending, processing, completed, failed, approved |
| `prompt_version` | VARCHAR(50) | Versión del prompt usado |
| `notion_page_id` | VARCHAR(255) | ID de la página en Notion (si se publicó) |
| `created_at` | TIMESTAMPTZ DEFAULT NOW() | |
| `updated_at` | TIMESTAMPTZ DEFAULT NOW() | |

> **Constraint:** UNIQUE(project_id, section_number) — solo una versión activa de cada sección.
> **Nota:** La publicación (S3, URL pública) se gestiona a nivel de `projects`, no de secciones individuales.

### `prompt_templates`

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `id` | UUID (PK) | |
| `name` | VARCHAR(255) UNIQUE NOT NULL | Ej. "system_prompt_v9", "extraction_v3_bmj" |
| `type` | VARCHAR(50) NOT NULL | `system`, `extraction`, `audit`, `patch` |
| `content` | TEXT NOT NULL | El prompt completo |
| `version` | INTEGER NOT NULL DEFAULT 1 | |
| `is_active` | BOOLEAN DEFAULT TRUE | Si es la versión activa |
| `description` | TEXT | Nota de cambio entre versiones |
| `created_at` | TIMESTAMPTZ DEFAULT NOW() | |

> **Constraint:** UNIQUE(name, version) — historial de versiones de cada prompt.

### `notion_configs`

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `id` | UUID (PK) | |
| `user_id` | UUID (FK → users) UNIQUE NOT NULL | Una config por usuario |
| `api_key` | TEXT NOT NULL | API key de Notion (encriptada) |
| `workspace_name` | VARCHAR(255) | Nombre del workspace |
| `default_parent_page_id` | VARCHAR(255) | Página padre donde se crean los compendios |
| `is_connected` | BOOLEAN DEFAULT FALSE | Estado de la conexión |
| `created_at` | TIMESTAMPTZ DEFAULT NOW() | |
| `updated_at` | TIMESTAMPTZ DEFAULT NOW() | |

---

## 🗂️ Índices Recomendados

```sql
-- Proyectos por usuario
CREATE INDEX idx_projects_user_id ON projects(user_id);

-- Documentos por proyecto
CREATE INDEX idx_source_documents_project_id ON source_documents(project_id);

-- Extracciones por documento
CREATE INDEX idx_extractions_document_id ON extractions(source_document_id);

-- Secciones por proyecto (ordenadas)
CREATE INDEX idx_sections_project_id ON compendium_sections(project_id, section_number);

-- Prompt templates activos por tipo
CREATE INDEX idx_prompts_active ON prompt_templates(type) WHERE is_active = TRUE;
```

---

## 🔄 Job Queue (Redis / ARQ)

Los jobs se gestionan en Redis vía ARQ. El worker corre en un contenedor separado.

### Jobs actuales

| Job | Descripción | Duración estimada |
|-----|-------------|-------------------|
| `extract_document` | Extrae contenido de un PDF con OpenRouter (Gemini) | 30-120s |
| `audit_extraction` | Audita extracción contra PDF original (placeholder) | — |

### Jobs futuros (Sprint 5+)

| Job | Descripción | Duración estimada |
|-----|-------------|-------------------|
| `generate_section` | Genera una sección del compendio | 30-90s |
| `publish_to_notion` | Publica secciones en Notion | 5-15s |

### Estructura del Job en ARQ

```python
# Enqueue
await queue.enqueue_job(
    'extract_document',
    document_id=str(doc.id),
    project_id=str(project.id),
)

# Worker
async def extract_document(ctx, document_id: str, project_id: str):
    # 1. Cargar documento y prompt
    # 2. Llamar a Gemini
    # 3. Guardar extracción
    # 4. Disparar job de auditoría
```

---

> **Próximo documento:** [05_api_design.md](05_api_design.md)
