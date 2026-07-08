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
│   ├── 00_vision.md
│   ├── 01_requisitos.md
│   ├── 02_arquitectura.md
│   ├── 03_stack_tecnologico.md
│   ├── 04_modelo_datos.md
│   ├── 05_api_design.md
│   ├── 06_modulos.md
│   ├── 07_notion.md
│   ├── 08_prompt_engine.md
│   ├── 09_pipeline_ia.md
│   ├── 10_deployment.md
│   └── 11_changelog.md
│
├── memory/                  ← Documentación original del Dr. Jorge (referencia)
│   ├── NUEVO - IA -.md      ← Especificación completa del sistema SAM
│   └── scripts/             ← Scripts legacy (sam_v8, sam_v9, unir)
│
├── backend/                 ← API y lógica de negocio (FastAPI + Python)
├── frontend/                ← Interfaz web (React + TypeScript)
├── docker/                  ← Configuración de despliegue
└── .gitignore
```

## 🚀 Stack

| Capa | Tecnología |
|------|-----------|
| Backend | FastAPI (Python 3.12), SQLAlchemy 2.0, ARQ + Redis |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, shadcn/ui, marked.js |
| Base de datos | PostgreSQL 16 |
| Cache/Queue | Redis 7 |
| AI Gateway | OpenRouter API (Gemini 2.5 Pro, Claude 3.5 Sonnet, +200 modelos) |
| Almacenamiento | AWS S3 (compendios .md públicos) / MinIO (desarrollo local) |
| Despliegue | Docker Compose, Nginx, GitHub Actions |
| Target | Ubuntu 24.04 VPS |

## 📋 Requisitos Previos

- Python 3.12+
- Node.js 20+
- Docker + Docker Compose
- PostgreSQL 16 (o usar el contenedor)
- API Keys: OpenRouter + Notion

## ⚡ Inicio Rápido

### Opción A: Docker Compose (Recomendado)

```bash
# 1. Clonar
git clone <repo-url>
cd ProyectoJorge

# 2. Configurar variables
cd docker
cp .env.docker.example .env
# Editar .env con tus API keys

# 3. Levantar todo
docker compose up --build

# API disponible en http://localhost:8000
# Swagger UI en http://localhost:8000/docs
```

### Opción B: Desarrollo Local (sin Docker)

```bash
# 1. Clonar
git clone <repo-url>
cd ProyectoJorge

# 2. Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # Configurar API keys y DATABASE_URL
alembic upgrade head
uvicorn app.main:app --reload

# 3. Frontend (otra terminal)
cd frontend
npm install
npm run dev
# Disponible en http://localhost:5173 (proxy a :8000 en /api/v1)

# 4. Workers (otra terminal)
cd backend
arq app.workers.WorkerSettings --watch
```

### Despliegue en Coolify (VPS)

1. Subir el repo a GitHub/GitLab
2. Crear proyecto en Coolify → Docker Compose
3. Apuntar al directorio `docker/`
4. Configurar variables de entorno en el dashboard de Coolify
5. Deploy one-click

## 📖 Documentación

Toda la documentación del proyecto está en la carpeta [`docs/`](docs/). Se recomienda leer en orden:

1. [Visión del proyecto](docs/00_vision.md)
2. [Requisitos](docs/01_requisitos.md)
3. [Arquitectura](docs/02_arquitectura.md)
4. [Stack tecnológico](docs/03_stack_tecnologico.md)
5. [Modelo de datos](docs/04_modelo_datos.md)
6. [Diseño de API](docs/05_api_design.md)
7. [Módulos](docs/06_modulos.md)
8. [Integración Notion](docs/07_notion.md)
9. [Prompt Engine](docs/08_prompt_engine.md)
10. [Pipeline IA](docs/09_pipeline_ia.md)
11. [Despliegue](docs/10_deployment.md)
12. [Changelog](docs/11_changelog.md)

## 🔐 Licencia

Privado — Todos los derechos reservados.

---

**Cliente:** Dr. Jorge  
**Desarrollador:** Calata  
**Inicio del proyecto:** Julio 2026
