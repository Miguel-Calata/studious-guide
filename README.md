# SAM Platform

Plataforma de automatización para la creación de compendios médicos de alta densidad clínica, utilizando IA (Gemini + Claude) como motor de extracción y redacción.

## 🎯 ¿Qué hace?

Convierte PDFs de guías clínicas y artículos científicos en compendios médicos estructurados en 11 secciones, listos para estudio y consulta, y los publica automáticamente en Notion.

```
PDFs de guías (KDIGO, BMJ, NICE, ...)  →  OpenRouter (Gemini + Claude)  →  Compendio público en S3 + Notion
```

## 📂 Estructura del Proyecto

```
ProyectoJorge/
├── docs/                    ← Documentación de arquitectura y decisiones
├── memory/                  ← Documentación original del Dr. Jorge (referencia)
├── backend/                 ← API y lógica de negocio (FastAPI + Python)
├── frontend/                ← Interfaz web (React + TypeScript)
├── docker/                  ← Dockerfiles + nginx
│   ├── Dockerfile.backend
│   ├── Dockerfile.frontend
│   └── nginx.frontend.conf
├── docker-compose.yml       ← Stack completo (Coolify / local)
├── .env.example             ← Variables para Compose / Coolify
└── .gitignore
```

## 🚀 Stack

| Capa | Tecnología |
|------|-----------|
| Backend | FastAPI (Python 3.12), SQLAlchemy 2.0, ARQ + Redis |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS, shadcn/ui (nginx en prod) |
| Base de datos | PostgreSQL 16 |
| Cache/Queue | Redis 7 |
| AI Gateway | OpenRouter API |
| Almacenamiento | AWS S3 (prod) / MinIO opcional (`--profile local`) |
| Despliegue | Docker Compose + Coolify (Traefik TLS) |
| Target | Ubuntu 24.04 VPS |

## 📋 Requisitos Previos

- Docker + Docker Compose
- API Keys: OpenRouter (+ Notion OAuth si se usa)
- Bucket S3 (producción)
- Para dev sin Docker: Python 3.12+, Node.js 20+

## ⚡ Inicio Rápido

### Opción A: Docker Compose (recomendado)

```bash
git clone <repo-url>
cd ProyectoJorge

cp .env.example .env
# Editar .env: SECRET_KEY, POSTGRES_PASSWORD, OPENROUTER_API_KEY, FRONTEND_URL, S3_*

# Producción / stack base (sin MinIO)
docker compose up --build -d

# Desarrollo local con MinIO
docker compose --profile local up --build
```

- Frontend (nginx + proxy API): http://localhost:5173
- API health (vía nginx): http://localhost:5173/api/v1/health
- Backend no se publica al host en prod (solo red interna Docker)

> Tras cambiar código en `backend/`, reconstruye: `docker compose up --build backend worker`.

### Opción B: Desarrollo local (sin Docker)

```bash
# Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload

# Frontend
cd frontend && npm install && npm run dev

# Workers
cd backend && arq app.workers.WorkerSettings --watch
```

### Despliegue en Coolify

1. Subir el repo a GitHub/GitLab
2. Coolify → **New Resource** → **Docker Compose**
3. Apuntar al repo (detecta `docker-compose.yml` en la raíz)
4. Configurar variables del `.env.example` en el dashboard
5. Asignar el dominio **solo al servicio `frontend`** (puerto contenedor 80)
6. Deploy

**Variables mínimas en Coolify:**

| Variable | Ejemplo |
|----------|---------|
| `POSTGRES_PASSWORD` | secreto fuerte |
| `SECRET_KEY` | `openssl rand -hex 32` |
| `OPENROUTER_API_KEY` | `sk-or-v1-...` |
| `FRONTEND_URL` | `https://tu-dominio` |
| `COOKIE_SECURE` | `true` |
| `STORAGE_BACKEND` | `s3` |
| `S3_ACCESS_KEY` / `S3_SECRET_KEY` / `S3_BUCKET` | credenciales AWS u otro S3 |
| `NOTION_OAUTH_REDIRECT_URI` | `https://tu-dominio/api/v1/notion/oauth/callback` |

Un solo dominio: nginx en `frontend` hace proxy de `/api/v1` y `/public` al backend. No hace falta exponer el servicio `backend`.

## 📖 Documentación

Ver [`docs/`](docs/), en especial [Despliegue](docs/10_deployment.md).

## 🔐 Licencia

Privado — Todos los derechos reservados.

---

**Cliente:** Dr. Jorge  
**Desarrollador:** Calata  
**Inicio del proyecto:** Julio 2026
