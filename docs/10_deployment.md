# 10 — Despliegue (Coolify + Docker Compose)

## 🖥️ Infraestructura

```
                      INTERNET
                         │
                         ▼
                ┌────────────────┐
                │ Coolify/Traefik │  TLS + reverse proxy
                └───────┬────────┘
                        │  dominio → servicio frontend :80
                        ▼
                ┌────────────────┐
                │   FRONTEND     │  nginx (SPA + proxy /api)
                │   BACKEND      │  FastAPI :8000 (interno)
                │   WORKER       │  ARQ (misma imagen)
                └───────┬────────┘
                        │
            ┌───────────┼───────────┐
            ▼           ▼           ▼
      ┌──────────┐ ┌──────────┐ ┌──────────┐
      │PostgreSQL│ │  Redis   │ │  S3 AWS  │
      │  :5432   │ │  :6379   │ │ (externo)│
      └──────────┘ └──────────┘ └──────────┘
```

**Un solo dominio.** El contenedor `frontend` sirve la SPA y hace proxy de `/api/v1/` y `/public/` al `backend` en la red Docker. Cookies httpOnly same-origin; no hace falta `COOKIE_DOMAIN` ni CORS complejo.

MinIO solo existe con `docker compose --profile local` (desarrollo). En producción se usa **S3 real**.

---

## 📦 Docker Compose

Archivo: **`docker-compose.yml` en la raíz del repo** (Coolify lo detecta sin Base Directory).

| Servicio | Imagen / build | Público |
|----------|----------------|---------|
| `postgres` | `postgres:16-alpine` | No |
| `redis` | `redis:7-alpine` | No |
| `backend` | `docker/Dockerfile.backend` | No (solo red interna) |
| `worker` | misma imagen, `arq app.workers.WorkerSettings` | No |
| `frontend` | `docker/Dockerfile.frontend` (nginx) | **Sí** — dominio Coolify, puerto 80 |
| `minio` | profile `local` | Solo local (9000/9001) |

Migraciones: el CMD del backend ejecuta `alembic upgrade head` antes de uvicorn.

---

## 🐳 Dockerfiles

### Backend (`docker/Dockerfile.backend`)

- Context de build: **raíz del repo**
- `COPY backend/...` → `/app`
- CMD: `alembic upgrade head && uvicorn ...`
- Compartido por `backend` y `worker`

### Frontend (`docker/Dockerfile.frontend`)

- Multi-stage: Node 20 build → `nginx:alpine`
- Config: `docker/nginx.frontend.conf`
- Proxy `/api/v1/` y `/public/` → `http://backend:8000`
- Health: `GET /healthz`

---

## 🌐 Coolify

1. Resource type: **Docker Compose**
2. Repo con `docker-compose.yml` en la raíz
3. Domain en el servicio **`frontend`** → `https://tu-dominio` (puerto contenedor 80)
4. Environment variables (dashboard) según `.env.example`
5. Deploy

No asignar dominio a `backend`, `postgres`, `redis` ni `worker`.

### Variables requeridas

| Variable | Notas |
|----------|--------|
| `POSTGRES_PASSWORD` | Obligatorio (`${POSTGRES_PASSWORD:?}`) |
| `SECRET_KEY` | `openssl rand -hex 32` |
| `OPENROUTER_API_KEY` | Pipeline IA |
| `FRONTEND_URL` | `https://tu-dominio` (redirects OAuth) |
| `COOKIE_SECURE` | `true` en HTTPS |
| `STORAGE_BACKEND` | `s3` |
| `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_BUCKET` | Bucket de compendios |
| `S3_REGION`, `S3_USE_SSL` | defaults `us-east-1` / `true` |
| `S3_ENDPOINT` | vacío = AWS; o endpoint S3-compatible |
| `NOTION_OAUTH_*` | redirect: `https://tu-dominio/api/v1/notion/oauth/callback` |

Opcionales: `COOKIE_DOMAIN` (vacío con un dominio), `BACKEND_CORS_ORIGINS`, `DEBUG=false`.

---

## 🚀 Primer despliegue (VPS manual)

```bash
git clone <repo-url> && cd ProyectoJorge
cp .env.example .env
# Editar secretos, FRONTEND_URL, S3_*

docker compose up --build -d
docker compose ps
curl -sS http://localhost:5173/api/v1/health
curl -sS http://localhost:5173/healthz
```

Con MinIO local:

```bash
# En .env: S3_ENDPOINT=http://minio:9000, S3_USE_SSL=false, COOKIE_SECURE=false, FRONTEND_URL=http://localhost:5173
docker compose --profile local up --build
```

---

## 📋 Mantenimiento

### Backup PostgreSQL

```bash
0 2 * * * docker compose exec -T postgres pg_dump -U sam sam_platform | gzip > /backup/sam_$(date +\%Y\%m\%d).sql.gz
```

### Logs

Todos los servicios usan rotación `json-file` (10m × 3).

### Health

- App: `https://tu-dominio/api/v1/health` (DB + Redis)
- Nginx: `https://tu-dominio/healthz`
- Monitor: UptimeRobot u similar

---

## 🖥️ Especificaciones mínimas del VPS

| Recurso | Mínimo | Recomendado |
|---------|--------|-------------|
| CPU | 2 vCPU | 4 vCPU |
| RAM | 2 GB | 4 GB |
| Disco | 20 GB SSD | 50 GB SSD |
| OS | Ubuntu 22.04/24.04 | Ubuntu 24.04 LTS |

**Proveedores:** Hetzner, DigitalOcean, etc. Coolify en el VPS gestiona Traefik/TLS.

---

## Por qué no Railpacks

El stack es multi-proceso (API + worker + postgres + redis + nginx). Railpacks/Nixpacks orientan a un solo proceso por app. **Docker Compose** es el empaquetado correcto para Coolify en este proyecto.

---

> **Próximo documento:** [11_changelog.md](11_changelog.md)
