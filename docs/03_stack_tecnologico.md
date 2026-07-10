# 03 — Stack Tecnológico

## 🐍 Backend

| Componente | Tecnología | Justificación |
|-----------|-----------|---------------|
| **Framework** | **FastAPI** (Python 3.12+) | Async nativo, validación automática con Pydantic, OpenAPI/Swagger auto-generado, excelente performance |
| **ORM** | **SQLAlchemy 2.0** (async) | El estándar de facto en Python, soporte async nativo desde 2.0, migraciones con Alembic |
| **Migraciones** | **Alembic** | Integración perfecta con SQLAlchemy, versionado de esquema |
| **Validación** | **Pydantic v2** | Integrado con FastAPI, schemas tipados, serialización rápida |
| **Autenticación** | **PyJWT** (JWT) + **bcrypt** | JWT stateless, bcrypt para hashing de contraseñas |
| **Task Queue** | **ARQ** (Async Redis Queue) | Más simple que Celery, Python puro, async nativo, basado en Redis |
| **AI Gateway** | **OpenRouter** vía SDK `openai` | Proveedor principal unificado para Gemini, Claude y +200 modelos. El gateway se diseña con interfaz extensible para agregar SDKs nativos en el futuro |
| **PDF Processing** | **pymupdf4llm** + **pymupdf** | Extracción de texto de PDFs como fallback si falla el modelo |
| **HTTP Client** | **httpx** (async) | Para llamadas a Notion API y otros servicios externos |
| **Logging** | **structlog** | Logs JSON estructurados, ideal para observabilidad |
| **Tests** | **pytest** + **httpx.AsyncClient** + **pytest-asyncio** | Testing async, fixtures, cobertura |
| **Notion SDK** | **notion-client** (o SDK oficial) | Cliente tipado para Notion API |
| **Retry / resilience** | **tenacity** | Backoff exponencial en llamadas a APIs externas |

### Dependencias clave (`requirements.txt`)

```
fastapi==0.115.*
uvicorn[standard]==0.32.*
sqlalchemy[asyncio]==2.0.*
asyncpg==0.30.*
alembic==1.14.*
pydantic==2.10.*
pydantic-settings==2.7.*
pydantic[email]
PyJWT==2.10.*
bcrypt==4.2.*
python-multipart==0.0.*
arq==0.26.*
redis==5.2.*
httpx==0.28.*
structlog==24.*
openai==1.61.*
aiobotocore==2.21.*
tenacity==9.0.*
pymupdf4llm==0.0.*
notion-client==2.2.*
pytest==8.*
pytest-asyncio==0.24.*
```

> **Nota:** `google-generativeai` y `anthropic` no están en el stack principal porque OpenRouter los unifica. Se pueden agregar más adelante si se implementa un proveedor nativo adicional.

---

## 🎨 Frontend

| Componente | Tecnología | Justificación |
|-----------|-----------|---------------|
| **Framework** | **React 18+** con **Vite** | Rápido, moderno, amplio ecosistema |
| **Lenguaje** | **TypeScript** | Tipado estático, mejor DX, menos bugs |
| **Router** | **React Router v6** | SPA routing estándar |
| **UI Components** | **shadcn/ui** (Tailwind CSS) | Componentes accesibles, personalizables, no lock-in |
| **Estilos** | **Tailwind CSS** | Utility-first, rápido de prototipar, consistente |
| **HTTP Client** | **fetch / ky** | Ligero, sin dependencias pesadas como axios |
| **Estado** | **React Context + SWR** (o TanStack Query) | Server state management, caching automático |
| **Editor MD** | **@uiw/react-md-editor** | Editor Markdown con preview, simple y funcional |
| **Testing** | **Vitest** + **React Testing Library** | Compatible con Vite, rápido |
| **Build** | **Vite** | Dev server rápido, builds optimizados |

### Principio: Simplicidad

- **Sin Redux** → React Context + hooks son suficientes para esta app
- **Sin Next.js** → SPA pura es adecuada (no necesitamos SSR para un dashboard interno)
- **Componentes mínimos** → shadcn/ui da botones, diálogos, tabs, etc. sin inflar el bundle

---

## 🗄️ Base de Datos

| Componente | Tecnología | Justificación |
|-----------|-----------|---------------|
| **DBMS** | **PostgreSQL 16** | Robusto, open source, JSONB para prompts versionados,全文検索 con tsvector para búsqueda de compendios |
| **Driver Python** | **asyncpg** (vía SQLAlchemy) | El driver async más rápido para PostgreSQL |

---

## 📦 Infraestructura y DevOps

| Componente | Tecnología | Justificación |
|-----------|-----------|---------------|
| **Contenedores** | **Docker** + **Docker Compose** | Despliegue reproducible en cualquier VPS |
| **VPS Management** | **Coolify** | One-click deploy desde Docker Compose, gestiona dominios, TLS, health checks |
| **Proxy reverso** | Coolify (Traefik integrado) | TLS automático, reverse proxy, sin Nginx manual |
| **Cache / Queue** | **Redis 7** | ARQ depende de Redis, además cache de sesiones |
| **Object Storage** | **MinIO** (local/dev) + **AWS S3** (prod) | API S3-compatible; compendios .md públicos, PDFs fuente privados |
| **CI/CD** | **GitHub Actions** | Corre tests, build de imágenes, deploy automático al VPS |
| **VPS Target** | Ubuntu 24.04 LTS | El estándar para hosting |

### Docker Compose (Coolify-compatible)

`docker-compose.yml` en la **raíz del repo**. Servicios: PostgreSQL, Redis, backend, worker, frontend (nginx). MinIO solo con `--profile local`. Prod usa S3 real.

```yaml
services:
  postgres:    # PostgreSQL 16 Alpine
  redis:       # Redis 7 Alpine
  backend:     # FastAPI + Alembic on startup (interno)
  worker:      # ARQ worker
  frontend:    # nginx SPA + proxy /api → backend (dominio público)
  minio:       # profile: local
```

**Variables clave:** ver `.env.example` en la raíz (`SECRET_KEY`, `FRONTEND_URL`, `COOKIE_SECURE`, `S3_*`, etc.).

**Coolify:** Docker Compose, domain solo en `frontend` (puerto 80). Detalle en `docs/10_deployment.md`.

---

## 🧩 ¿Por qué NO microservicios?

| Factor | Monolito Modular | Microservicios |
|--------|-----------------|----------------|
| Equipo | 1 desarrollador | Necesita +3 devs |
| Complejidad | Baja | Alta (red, latencia, consistencia) |
| Despliegue | 1 `docker compose up` | Kubernetes o múltiples VPS |
| Debugging | Trazas locales | Trazas distribuidas |
| ¿Escala necesaria? | 10-50 usuarios | Cientos/miles |
| Costo infra | $10-20/mes VPS | $50-200+/mes |

---

## 🗺️ Estructura de Carpetas del Proyecto

```
ProyectoJorge/
├── docker-compose.yml            # Stack Coolify / local (raíz)
├── .env.example                  # Template Compose / Coolify
├── docker/
│   ├── Dockerfile.backend        # Context raíz; compartido backend + worker
│   ├── Dockerfile.frontend       # Multi-stage Node → nginx
│   └── nginx.frontend.conf       # SPA + proxy API
│
├── backend/
│   ├── app/
│   │   ├── main.py               # FastAPI app factory + lifespan
│   │   ├── config.py             # Settings (pydantic-settings, lee .env)
│   │   ├── database.py           # SQLAlchemy engine + session
│   │   ├── dependencies.py       # get_arq_pool (dependency compartida)
│   │   ├── models/               # SQLAlchemy models (todas las tablas)
│   │   │   ├── base.py           # Base + TimestampMixin + UUIDMixin
│   │   │   ├── user.py
│   │   │   ├── project.py
│   │   │   ├── source_document.py
│   │   │   ├── extraction.py
│   │   │   └── prompt_template.py
│   │   ├── modules/              # Módulos de negocio (autocontenidos)
│   │   │   ├── auth/             # router, schemas, service, dependencies
│   │   │   ├── projects/         # router, schemas, service, dependencies
│   │   │   ├── documents/        # router, schemas, service, dependencies
│   │   │   ├── extractions/      # router, schemas, service, dependencies
│   │   │   ├── prompts/          # router, schemas, service
│   │   │   └── ai_gateway/       # interfaces.py, openrouter_client.py
│   │   ├── services/             # Servicios compartidos
│   │   │   ├── storage.py        # StorageBackend (local + S3/MinIO)
│   │   │   └── orchestrator.py   # PipelineOrchestrator (stub)
│   │   └── workers/              # ARQ workers
│   │       ├── __init__.py       # WorkerSettings
│   │       └── extraction_worker.py
│   ├── alembic/                  # Migraciones
│   │   ├── env.py
│   │   └── versions/             # 001-006 + sprint0 cleanup
│   ├── tests/                    # 39 tests (pytest-asyncio)
│   ├── requirements.txt
│   ├── pyproject.toml
│   └── pytest.ini
│
├── frontend/                     # (pendiente — Fase 2)
│
├── docs/                         # Documentación (docs/00-12)
└── memory/                       # Referencia original del Dr.
```

---

> **Próximo documento:** [04_modelo_datos.md](04_modelo_datos.md)
