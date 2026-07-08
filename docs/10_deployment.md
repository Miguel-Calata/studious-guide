# 10 — Despliegue (VPS + Docker)

## 🖥️ Infraestructura

```
                     INTERNET
                        │
                        ▼
               ┌────────────────┐
               │  Coolify/Nginx  │  TLS + reverse proxy
               └───────┬────────┘
                       │
                       ▼
               ┌────────────────┐
               │   BACKEND       │  FastAPI (:8000)
               │   WORKER        │  ARQ (misma imagen)
               └───────┬────────┘
                       │
           ┌───────────┼───────────┐
           ▼           ▼           ▼
     ┌──────────┐ ┌──────────┐ ┌──────────┐
     │PostgreSQL│ │  Redis   │ │  MinIO   │
     │  :5432   │ │  :6379   │ │  :9000   │
     └──────────┘ └──────────┘ └──────────┘
```

---

## 📦 Docker Compose

El `docker-compose.yml` actual (`docker/docker-compose.yml`) define 5 servicios:

```yaml
services:
  postgres:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-sam}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-sam}
      POSTGRES_DB: ${POSTGRES_DB:-sam_platform}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-sam} -d ${POSTGRES_DB:-sam_platform}"]
      interval: 5s
      timeout: 3s
      retries: 5

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  backend:
    build:
      context: ../backend
      dockerfile: ../docker/Dockerfile.backend
    restart: unless-stopped
    ports:
      - "${BACKEND_PORT:-8000}:8000"
    environment:
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER:-sam}:${POSTGRES_PASSWORD:-sam}@postgres:5432/${POSTGRES_DB:-sam_platform}
      REDIS_URL: redis://redis:6379/0
      SECRET_KEY: ${SECRET_KEY:-change-me-in-production}
      OPENROUTER_API_KEY: ${OPENROUTER_API_KEY:-}
      OPENROUTER_BASE_URL: ${OPENROUTER_BASE_URL:-https://openrouter.ai/api/v1}
      PDF_STORAGE_PATH: /app/data/pdfs
      MAX_UPLOAD_SIZE_MB: ${MAX_UPLOAD_SIZE_MB:-50}
      MAX_FILES_PER_UPLOAD: ${MAX_FILES_PER_UPLOAD:-15}
      STORAGE_BACKEND: ${STORAGE_BACKEND:-local}
      S3_ENDPOINT: ${S3_ENDPOINT:-http://minio:9000}
      S3_ACCESS_KEY: ${S3_ACCESS_KEY:-minioadmin}
      S3_SECRET_KEY: ${S3_SECRET_KEY:-minioadmin}
      S3_BUCKET: ${S3_BUCKET:-compendiums}
      S3_REGION: ${S3_REGION:-us-east-1}
      S3_USE_SSL: ${S3_USE_SSL:-false}
      S3_PUBLIC_URL_PREFIX: ${S3_PUBLIC_URL_PREFIX:-}
      DEBUG: ${DEBUG:-false}
      UVICORN_RELOAD: ${UVICORN_RELOAD:-}
      BACKEND_CORS_ORIGINS: ${BACKEND_CORS_ORIGINS:-http://localhost:5173,http://localhost:3000}
    volumes:
      - pdf_data:/app/data/pdfs
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      minio:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 15s

  worker:
    build:
      context: ../backend
      dockerfile: ../docker/Dockerfile.backend
    restart: unless-stopped
    command: arq app.workers.WorkerSettings
    environment:
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER:-sam}:${POSTGRES_PASSWORD:-sam}@postgres:5432/${POSTGRES_DB:-sam_platform}
      REDIS_URL: redis://redis:6379/0
      SECRET_KEY: ${SECRET_KEY:-change-me-in-production}
      OPENROUTER_API_KEY: ${OPENROUTER_API_KEY:-}
      OPENROUTER_BASE_URL: ${OPENROUTER_BASE_URL:-https://openrouter.ai/api/v1}
      PDF_STORAGE_PATH: /app/data/pdfs
      STORAGE_BACKEND: ${STORAGE_BACKEND:-local}
      S3_ENDPOINT: ${S3_ENDPOINT:-http://minio:9000}
      S3_ACCESS_KEY: ${S3_ACCESS_KEY:-minioadmin}
      S3_SECRET_KEY: ${S3_SECRET_KEY:-minioadmin}
      S3_BUCKET: ${S3_BUCKET:-compendiums}
      S3_REGION: ${S3_REGION:-us-east-1}
      S3_USE_SSL: ${S3_USE_SSL:-false}
      S3_PUBLIC_URL_PREFIX: ${S3_PUBLIC_URL_PREFIX:-}
      DEBUG: ${DEBUG:-false}
    volumes:
      - pdf_data:/app/data/pdfs
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      minio:
        condition: service_healthy

  minio:
    image: minio/minio:latest
    restart: unless-stopped
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${S3_ACCESS_KEY:-minioadmin}
      MINIO_ROOT_PASSWORD: ${S3_SECRET_KEY:-minioadmin}
    volumes:
      - minio_data:/data
    ports:
      - "${MINIO_API_PORT:-9000}:9000"
      - "${MINIO_CONSOLE_PORT:-9001}:9001"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s

volumes:
  postgres_data:
  redis_data:
  pdf_data:
  minio_data:
```

---

## 🐳 Dockerfiles

### Backend (compartido por backend y worker)

```dockerfile
# docker/Dockerfile.backend
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data/pdfs

EXPOSE 8000

CMD alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 ${UVICORN_RELOAD:+--reload}
```

> **Nota:** La imagen es compartida entre `backend` y `worker`. El worker usa el mismo Dockerfile pero con `command: arq app.workers.WorkerSettings`.

---

## 🌐 Reverse Proxy (Coolify / Nginx)

En producción, se usa **Coolify** (Traefik integrado) o **Nginx** como reverse proxy con TLS. El backend expone el puerto 8000 internamente.

**Rates para Nginx (si se usa manualmente):**
- API general: 30 req/min
- Auth endpoints: 5 req/min
- Jobs largos: timeout 300s

---

## 📋 Mantenimiento

```bash
# docker/.env (NO COMMITEAR — añadir a .gitignore)

# PostgreSQL
POSTGRES_USER=sam
POSTGRES_PASSWORD=XXXXXXXXXXXXXXXX
POSTGRES_DB=sam_platform

# Backend
SECRET_KEY=XXXXXXXXXXXXXXXX  # openssl rand -hex 32
BACKEND_PORT=8000

# OpenRouter (único proveedor de IA)
OPENROUTER_API_KEY=sk-or-v1-XXXXXXXXXXXXXXXX
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

# Storage — PDFs (filesystem local)
STORAGE_BACKEND=local
PDF_STORAGE_PATH=/app/data/pdfs
MAX_UPLOAD_SIZE_MB=50
MAX_FILES_PER_UPLOAD=15

# Storage — Compendios (S3/MinIO)
S3_ENDPOINT=http://minio:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
S3_BUCKET=compendiums
S3_REGION=us-east-1
S3_USE_SSL=false
S3_PUBLIC_URL_PREFIX=

# CORS
BACKEND_CORS_ORIGINS=http://localhost:5173,http://localhost:3000

# Entorno
DEBUG=false
UVICORN_RELOAD=          # vacío en prod, "true" en local

# MinIO
MINIO_API_PORT=9000
MINIO_CONSOLE_PORT=9001
```

---

## 🚀 Primer Despliegue

```bash
# 1. Clonar repositorio en el VPS
ssh user@vps
git clone https://github.com/usuario/sam-platform.git
cd sam-platform

# 2. Configurar variables de entorno
cp docker/.env.example docker/.env
nano docker/.env   # Editar con valores reales (OPENROUTER_API_KEY, SECRET_KEY, etc.)

# 3. Levantar servicios
docker compose -f docker/docker-compose.yml up -d

# 4. Verificar
docker compose -f docker/docker-compose.yml ps
curl http://localhost:8000/api/v1/health

# 5. Migraciones se ejecutan automáticamente al iniciar el backend
# (Dockerfile ejecuta alembic upgrade head antes de uvicorn)

# 6. (Producción) Configurar Coolify o Nginx como reverse proxy con TLS
```

> **Nota:** En Coolify, configurar como proyecto Docker Compose, apuntar al repo, y setear variables de entorno en el dashboard.

---

## 🔄 CI/CD con GitHub Actions

```yaml
# .github/workflows/deploy.yml
name: Deploy to VPS

on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_DB: sam_platform_test
          POSTGRES_USER: sam
          POSTGRES_PASSWORD: sam
        ports:
          - 5432:5432
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install -r backend/requirements.txt
      - run: cd backend && pytest
        env:
          DATABASE_URL: postgresql+asyncpg://sam:sam@localhost:5432/sam_platform_test

  deploy:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - name: Deploy via SSH
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.VPS_HOST }}
          username: ${{ secrets.VPS_USER }}
          key: ${{ secrets.VPS_SSH_KEY }}
          script: |
            cd /opt/sam-platform
            git pull origin main
            docker compose -f docker/docker-compose.yml up -d --build
```

---

## 📋 Mantenimiento

### Backup de PostgreSQL

```bash
# Backup diario (cron en VPS)
0 2 * * * docker exec docker-postgres-1 pg_dump -U sam sam_platform | gzip > /backup/sam_$(date +\%Y\%m\%d).sql.gz

# Restaurar
gunzip < backup.sql.gz | docker exec -i docker-postgres-1 psql -U sam sam_platform
```

### Rotación de Logs

```yaml
# docker-compose.yml (añadir a cada servicio)
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"
```

### Health Checks

- `/api/v1/health` → verifica DB + Redis + estado general
- Uptime monitoring con [UptimeRobot](https://uptimerobot.com) (gratis para 1 URL)

---

## 🖥️ Especificaciones Mínimas del VPS

| Recurso | Mínimo | Recomendado |
|---------|--------|-------------|
| CPU | 2 vCPU | 4 vCPU |
| RAM | 2 GB | 4 GB |
| Disco | 20 GB SSD | 50 GB SSD |
| OS | Ubuntu 22.04/24.04 | Ubuntu 24.04 LTS |

**Proveedores sugeridos:**
- **Presupuesto ajustado**: DigitalOcean ($12/mes), Hetzner (~€4/mes), Netlify (free tier para frontend)
- **Latinoamérica**: AWS São Paulo, Google Cloud Santiago

---

> **Próximo documento:** [11_changelog.md](11_changelog.md)
