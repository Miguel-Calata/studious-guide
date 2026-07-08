# 02 — Arquitectura de Alto Nivel

## 🧱 Patrón: Monolito Modular

```
┌──────────────────────────────────────────────────────────────────┐
│                      FRONTEND (React SPA)                         │
│                                                                    │
│  ┌─────────────────────┐        ┌─────────────────────────────┐  │
│  │   Creator Dashboard  │        │     Visor Público            │  │
│  │   (auth required)   │        │   (sin auth, marked.js)     │  │
│  │                     │        │                             │  │
│  │  Dashboard          │        │  Listado de compendios       │  │
│  │  Proyectos           │        │  Visor Markdown minimalista  │  │
│  │  Editor MD           │        │  Descargar .md               │  │
│  │  Notion Config       │        │  Abrir en Notion 🔗          │  │
│  └──────────┬──────────┘        └──────────────┬──────────────┘  │
└─────────────┼──────────────────────────────────┼─────────────────┘
              │ HTTPS / REST API (JWT)           │ HTTPS / REST API (público)
┌─────────────▼──────────────────────────────────▼─────────────────┐
│                      BACKEND (FastAPI)                            │
│                                                                    │
│  ┌──────────┐ ┌───────────┐ ┌────────────┐ ┌─────────┐           │
│  │  Auth    │ │ Projects  │ │ Documents  │ │ Notion  │           │
│  │ Module   │ │ Module    │ │ Module     │ │ Module  │           │
│  └──────────┘ └───────────┘ └────────────┘ └─────────┘           │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │            ORCHESTRATOR (Pipeline Engine)                 │    │
│  │  ┌──────────┐  ┌──────────┐  ┌───────────────┐           │    │
│  │  │ Extraction│  │  Merger  │  │  Generation   │           │    │
│  │  │ Service   │  │  Service │  │  Service      │           │    │
│  │  └──────────┘  └──────────┘  └───────────────┘           │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │            PROMPT ENGINE (SAM Core)                       │    │
│  │  Templates │ Versioning │ Section Builder │ EcoMap        │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │            AI GATEWAY (OpenRouter)                        │    │
│  │  OpenRouter Client (único) → Gemini / Claude / ...       │    │
│  │  Cost Tracker │ Model Router                             │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │            PUBLISHING SERVICE                             │    │
│  │  S3 Upload │ Public URL Generator │ Cache Headers         │    │
│  └──────────────────────────────────────────────────────────┘    │
└──────────────┬──────────────────────┬────────────────────────────┘
               │                      │
    ┌──────────▼────────┐  ┌─────────▼──────────┐  ┌──────────────┐
    │    PostgreSQL      │  │  Redis + ARQ        │  │  AWS S3 /    │
    │  (datos + estado)  │  │  (cola de trabajos)  │  │  Compatible  │
    └───────────────────┘  └─────────────────────┘  │  (compendios) │
                                                     └──────────────┘

                     ┌─── OPENROUTER API ───┐
                     │   modelo único unificado   │
                     │  ├─ Gemini 2.5 Pro    │
                     │  ├─ Claude 3.5 Sonnet │
                     │  └─ ... otros modelos │
                     └───────────────────────┘
```

## 📦 Módulos del Backend

### 1. Auth Module (`backend/app/modules/auth/`)
- Registro (email + password)
- Login → JWT (access + refresh tokens)
- Middleware de autenticación
- Endpoints: `POST /auth/register`, `POST /auth/login`, `POST /auth/refresh`

### 2. Projects Module (`backend/app/modules/projects/`)
- CRUD de proyectos (patologías)
- Cada proyecto pertenece a un usuario
- Estado: `draft`, `extracting`, `generating`, `review`, `completed`, `archived`
- Endpoints: `GET/POST /projects`, `GET/PUT/DELETE /projects/{id}`

### 3. Documents Module (`backend/app/modules/documents/`)
- Upload de PDFs (multipart)
- Clasificación por tipo: `bmj`, `guideline`, `article`
- Almacenamiento en filesystem local con `S3StorageBackend` para MinIO/S3
- Endpoints: `POST /projects/{id}/documents`, `GET/DELETE /documents/{id}`

### 4. Extractions Module (`backend/app/modules/extractions/`)
- Dispara jobs de extracción vía ARQ
- Extracción individual (un PDF) y masiva (todos los docs del proyecto)
- Cada PDF → llamada a OpenRouter (Gemini) con el prompt correcto
- Maneja continuaciones automáticas
- Transición automática `extracting` → `draft` al completar
- Endpoints: `POST /documents/{id}/extract`, `POST /projects/{id}/extract-all`, `GET /extractions/{id}`, `GET /extractions/{id}/status`, `POST /extractions/{id}/retry`

### 5. Compendium Module (`backend/app/modules/compendiums/`)
- Une extracciones → documento fuente único
- Dispara generación de las 11 secciones
- Bifurca entre Gemini y Claude según tabla DOSIFICACION
- Aplica MAPA_ECOS en tiempo real
- Re-generación de secciones individuales
- Endpoints: `POST /projects/{id}/generate`, `GET /projects/{id}/sections`, `GET/PUT /sections/{id}`

### 6. Prompt Engine (`backend/app/modules/prompts/`)
- Templates versionados de todos los prompts del sistema
- Builder que construye el prompt final por sección
- Incluye: System Prompt SAM v9, prompts de extracción, auditoría, parche Gemini
- Endpoints: `GET/PUT /prompts/{type}`, `GET /prompts/{type}/versions`

### 7. AI Gateway — OpenRouter (`backend/app/modules/ai_gateway/`)
- Cliente único para OpenRouter API (SDK compatible con OpenAI)
- Interfaz abstracta `AIGatewayClient` para agregar proveedores nativos futuros
- Manejo de continuaciones automáticas (`[CONTINÚA...]`)
- Tracking de tokens y costos (OpenRouter devuelve pricing en cada response)
- No expone endpoints propios (uso interno)

### 8. Notion Module (`backend/app/modules/notion/`)
- OAuth con Notion
- Mapeo de secciones a páginas de Notion
- Publicación con estructura jerárquica
- Endpoints: `POST /notion/connect`, `GET /notion/databases`, `POST /projects/{id}/publish`

### 9. Publishing Module (`backend/app/modules/publishing/`)
- Subida de compendios finales a S3 (bucket público o pre-signed URLs)
- Generación de URLs públicas para el visor
- Invalidación de cache cuando se re-genera un compendio
- Endpoints públicos: `GET /public/compendiums`, `GET /public/compendiums/{slug}`

### 10. Workers (`backend/app/workers/`)
- `extraction_worker.py`: Procesa jobs de extracción (ARQ) + auto-transición de estado del proyecto
- `generation_worker.py`: (pendiente — Sprint 5) Procesa jobs de generación de secciones
- `notion_worker.py`: (pendiente — Sprint 7) Procesa publicación a Notion

---

## 🔄 Flujo de Datos Principal

```
1. Creator sube PDFs
   ↓
2. Creator clasifica PDFs (BMJ / Guía / Artículo)
   ↓
3. Creator pulsa "Extraer"
   → Se crea Job en Redis
   → Worker: llama a OpenRouter (modelo Gemini) con prompt de extracción
   → Worker: ejecuta auditoría post-extracción
   → Resultado guardado en PostgreSQL
   ↓
4. Creator pulsa "Unir"
   → Merger Service: concatena todas las extracciones
   → Resultado: merged_document.md en PostgreSQL
   ↓
5. Creator pulsa "Generar Compendio"
   → Se crean 11 Jobs en Redis (uno por sección)
   → Prompt Engine: construye prompt para cada sección (con MAPA_ECOS)
   → OpenRouter: envía secciones 🟢🟡 a Gemini, secciones 🔴 a Claude
   → Resultados guardados en PostgreSQL
   ↓
6. Creator pulsa "Publicar"
   → Se ensambla compendio final .md
   → Se sube a S3 (bucket público)
   → Se guarda S3 URL en DB
   → (Opcional) Se publica en Notion
   ↓
7. Público visita /compendios
   → Listado de compendios publicados
   → Visor minimalista (marked.js) carga .md desde S3
   → Botones: Descargar .md | Abrir en Notion
```

---

## 🗄️ Almacenamiento

| Tipo de dato | Dónde se guarda | Notas |
|-------------|-----------------|-------|
| Datos relacionales (usuarios, proyectos, estado) | PostgreSQL | ORM: SQLAlchemy, migraciones: Alembic |
| Cola de trabajos (jobs, resultados temporales) | Redis + ARQ | Jobs tienen TTL de 24h |
| PDFs fuente | Filesystem local (volumen Docker) | Ruta: `/app/data/pdfs/`. Storage abstracto con `S3StorageBackend` (MinIO en Docker, S3 en prod) |
| Compendios publicados | S3 / MinIO | Archivos `.md` públicos, servidos por URL |
| Extracciones (texto Markdown) | PostgreSQL (TEXT) | Podría migrar a S3-compatible si escala |
| Prompts templates | PostgreSQL (JSONB) | Versionados, con historial |
| API Keys (OpenRouter, Notion) | PostgreSQL (encriptadas) vía `.env` en MVP | Encriptación simétrica AES-256 en Fase 2 |

---

## 🔐 Seguridad

```
Cliente ── HTTPS ──▶ Nginx ── HTTP ──▶ FastAPI (interno)
                          │
                     TLS termination
                     Rate limiting

FastAPI:
  - CORS restrictivo (origen configurado)
  - JWT validación en cada request (middleware)
  - API Keys encriptadas en DB (nunca en logs)
  - PDFs: acceso solo vía API autenticada
  - Input validation (Pydantic schemas)
```

---

## 📐 Principio de Modularidad

Cada módulo del backend es autocontenido:

```
backend/app/modules/<nombre>/
├── __init__.py          # Exporta el router
├── router.py            # Endpoints FastAPI
├── schemas.py           # Pydantic models (request/response)
├── service.py           # Lógica de negocio
├── models.py            # SQLAlchemy models (si tiene tablas propias)
└── dependencies.py      # FastAPI dependencies (auth, etc.)
```

Los módulos se comunican vía **servicios** y **eventos**, no directamente entre routers:
- `Orchestrator` coordina módulos → llama a servicios
- Los workers consumen jobs de Redis → llaman a servicios
- Los módulos no se importan entre sí; dependen de abstracciones comunes

---

> **Próximo documento:** [03_stack_tecnologico.md](03_stack_tecnologico.md)
