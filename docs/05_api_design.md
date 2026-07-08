# 05 — Diseño de API

## 🔌 Convenciones

- **Base URL:** `/api/v1`
- **Autenticación:** `Authorization: Bearer <jwt_token>`
- **Content-Type:** `application/json` (excepto uploads: `multipart/form-data`)
- **IDs:** UUID v4 en todos los recursos
- **Formato de respuesta:** Respuestas directas (sin envelope). Errores usan HTTP status codes estándar + `detail` en el body.

**Errores:**
```json
// 404 Not Found
{
  "detail": "Proyecto no encontrado"
}

// 409 Conflict
{
  "detail": "Ya existe una extracción activa para este documento"
}
```

> **Nota:** Se evaluó un envelope `{data, meta, error}` (D-022) pero se descartó por simplicidad. Si se necesita en el futuro, se implementa como middleware.

---

## 📋 Endpoints

### 🔐 Auth ✅ Implementado

| Método | Ruta | Descripción | Auth |
|--------|------|-------------|------|
| `POST` | `/auth/register` | Registrar nuevo usuario (creator) | ❌ |
| `POST` | `/auth/login` | Login → JWT tokens | ❌ |
| `POST` | `/auth/refresh` | Refrescar access token | ❌ (refresh token en body) |
| `GET` | `/auth/me` | Datos del usuario actual | ✅ |

> Solo el rol `creator` puede registrarse. El primer usuario puede ser promovido a `admin` manualmente en DB.

#### `POST /auth/register`
```json
// Request
{
  "email": "dr@example.com",
  "password": "securePass123!",
  "full_name": "Dr. Jorge"
}

// Response 201
{
  "id": "uuid",
  "email": "dr@example.com",
  "full_name": "Dr. Jorge",
  "role": "creator",
  "is_active": true,
  "created_at": "2026-07-06T18:00:00Z",
  "updated_at": "2026-07-06T18:00:00Z"
}
```

#### `POST /auth/login`
```json
// Request
{
  "email": "dr@example.com",
  "password": "securePass123!"
}

// Response 200
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

#### `POST /auth/refresh`
```json
// Request
{
  "refresh_token": "eyJ..."
}

// Response 200
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

---

### 📁 Projects ✅ Implementado

| Método | Ruta | Descripción | Auth |
|--------|------|-------------|------|
| `POST` | `/projects` | Crear proyecto | ✅ |
| `GET` | `/projects` | Listar proyectos activos del usuario | ✅ |
| `GET` | `/projects/{id}` | Detalle de proyecto (incluye archivados) | ✅ |
| `PUT` | `/projects/{id}` | Actualizar nombre/descripción | ✅ |
| `DELETE` | `/projects/{id}` | Archivar proyecto (soft delete) | ✅ |

#### `POST /projects`
```json
// Request
{
  "name": "Lesión Renal Aguda",
  "description": "Compendio completo sobre LRA basado en KDIGO 2026"
}

// Response 201
{
  "id": "uuid",
  "name": "Lesión Renal Aguda",
  "slug": "lesion-renal-aguda",
  "description": "Compendio completo sobre LRA basado en KDIGO 2026",
  "status": "draft",
  "is_published": false,
  "public_url": null,
  "created_at": "2026-07-06T18:00:00Z",
  "updated_at": "2026-07-06T18:00:00Z"
}
```

#### `GET /projects/{id}`
```json
// Response 200
{
  "id": "uuid",
  "name": "Lesión Renal Aguda",
  "slug": "lesion-renal-aguda",
  "description": "Compendio completo sobre LRA basado en KDIGO 2026",
  "status": "draft",
  "is_published": false,
  "public_url": null,
  "created_at": "...",
  "updated_at": "..."
}
```

> **Nota:** El slug es auto-generado y no editable. `DELETE` devuelve `204 No Content` y hace soft delete (status → `archived`). Los endpoints de `GET /projects` excluyen archivados.

---

### 📄 Documents (PDFs) ✅ Implementado

| Método | Ruta | Descripción | Auth |
|--------|------|-------------|------|
| `POST` | `/projects/{id}/documents` | Subir PDF(s) (multipart, max 15 archivos) | ✅ |
| `GET` | `/projects/{id}/documents` | Listar documentos del proyecto | ✅ |
| `GET` | `/documents/{id}` | Detalle de documento | ✅ |
| `DELETE` | `/documents/{id}` | Eliminar documento (físico + registro) | ✅ |
| `GET` | `/documents/{id}/download` | Descargar PDF original | ✅ |

#### `POST /projects/{id}/documents`
```
Content-Type: multipart/form-data

files: [pdf_file_1, pdf_file_2, ...]
document_type: bmj | guideline | article   (opcional, aplica a todos)
```

```json
// Response 201
{
  "documents": [
    {
      "id": "uuid",
      "project_id": "uuid",
      "filename": "KDIGO_AKI_2026.pdf",
      "file_size": 2500000,
      "document_type": "guideline",
      "status": "uploaded",
      "created_at": "...",
      "updated_at": "..."
    }
  ]
}
```

> **Nota:** Solo `.pdf`, max 50MB por archivo, max 15 archivos por request. El `document_type` es opcional y defaulta a `article`. Storage local con abstracción `S3StorageBackend` para MinIO/S3.

---

### 🤖 Extractions ✅ Implementado

| Método | Ruta | Descripción | Auth |
|--------|------|-------------|------|
| `POST` | `/documents/{id}/extract` | Iniciar extracción de un documento | ✅ |
| `POST` | `/projects/{id}/extract-all` | Extraer todos los documentos del proyecto | ✅ |
| `GET` | `/extractions/{id}` | Obtener resultado de una extracción | ✅ |
| `GET` | `/extractions/{id}/status` | Estado de la extracción | ✅ |
| `POST` | `/extractions/{id}/retry` | Re-ejecutar extracción fallida | ✅ |

#### `POST /documents/{id}/extract`
```json
// Response 201
{
  "id": "uuid",
  "source_document_id": "uuid",
  "content": "",
  "model_used": null,
  "input_tokens": null,
  "output_tokens": null,
  "cost_usd": null,
  "status": "pending",
  "error_message": null,
  "audit_completed": false,
  "created_at": "...",
  "updated_at": "..."
}
```

#### `POST /projects/{id}/extract-all`
```json
// Response 200
{
  "project_id": "uuid",
  "total_documents": 3,
  "enqueued": 2,
  "skipped": 1,
  "project_status": "extracting"
}
```

> **Nota:** Crea extracciones pendientes para todos los documentos del proyecto y encola jobs ARQ. Documentos con extracción activa (pending/processing/completed) se saltan. El proyecto pasa a `extracting`. Cuando terminan todas las extracciones, el worker transiciona automáticamente a `draft`.

#### `GET /extractions/{id}/status`
```json
// Response 200
{
  "id": "uuid",
  "status": "processing",
  "input_tokens": null,
  "output_tokens": null,
  "error_message": null
}
```

#### `GET /extractions/{id}` (completada)
```json
// Response 200
{
  "id": "uuid",
  "source_document_id": "uuid",
  "content": "# TRANSCRIPCIÓN FIEL: Lesión Renal Aguda\n\n...",
  "model_used": "google/gemini-2.5-pro",
  "input_tokens": 152000,
  "output_tokens": 85000,
  "cost_usd": 0.48,
  "status": "completed",
  "error_message": null,
  "audit_completed": false,
  "created_at": "..."
}
```

---

### 📝 Compendium (pendiente — Sprint 5+)

| Método | Ruta | Descripción | Auth |
|--------|------|-------------|------|
| `POST` | `/projects/{id}/merge` | Unir extracciones → documento fuente | ✅ |
| `POST` | `/projects/{id}/generate` | Generar las 11 secciones | ✅ |
| `GET` | `/projects/{id}/sections` | Listar secciones del compendio | ✅ |
| `GET` | `/sections/{id}` | Obtener sección específica | ✅ |
| `PUT` | `/sections/{id}` | Editar manualmente sección | ✅ |
| `POST` | `/sections/{id}/regenerate` | Re-generar UNA sección | ✅ |
| `GET` | `/projects/{id}/export` | Exportar compendio completo (.md) | ✅ |

---

### 🧠 Prompts ✅ Implementado

| Método | Ruta | Descripción | Auth |
|--------|------|-------------|------|
| `GET` | `/prompts` | Listar prompts activos | ✅ |
| `GET` | `/prompts/{name}` | Obtener prompt activo por nombre | ✅ |
| `PUT` | `/prompts/{name}` | Actualizar prompt (nueva versión) | ✅ (admin) |
| `GET` | `/prompts/{name}/versions` | Historial de versiones | ✅ |

---

### 📋 Notion (pendiente — Sprint 7)

| Método | Ruta | Descripción | Auth |
|--------|------|-------------|------|
| `POST` | `/notion/connect` | Conectar con Notion (guardar API key) | ✅ |
| `GET` | `/notion/status` | Estado de la conexión | ✅ |
| `GET` | `/notion/search` | Buscar páginas/bases de datos en Notion | ✅ |
| `POST` | `/projects/{id}/publish/notion` | Publicar compendio en Notion | ✅ (creator) |

---

### 🌐 Visor Público (pendiente — Sprint 6)

| Método | Ruta | Descripción | Auth |
|--------|------|-------------|------|
| `GET` | `/public/compendiums` | Listar compendios publicados | ❌ |
| `GET` | `/public/compendiums/{slug}` | Detalle de un compendio público | ❌ |
| `GET` | `/public/compendiums/{slug}/download` | Descargar .md | ❌ |
| `GET` | `/public/compendiums/{slug}/sections/{n}` | Sección individual (JSON) | ❌ |

---

## 🔄 WebSocket / SSE (Fase 2)

Para progreso en tiempo real en el frontend:

```
GET /ws/projects/{id}/progress
→ Server-Sent Events con actualizaciones de estado de jobs
```

---

## 📊 OpenAPI / Swagger

FastAPI autogenera documentación interactiva en:
- `/docs` — Swagger UI
- `/redoc` — ReDoc

---

> **Próximo documento:** [06_modulos.md](06_modulos.md)
