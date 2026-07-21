# 14 — Guía de Implementación Frontend: Revisión de Ecos Map

## Objetivo

Implementar una card en `ProjectDetailPage` que muestre el estado
del ecos map de la patología del proyecto, permita al doctor
revisar, editar y aprobar el borrador generado automáticamente.

---

## Estado actual (backend listo)

Los endpoints ya existen y son funcionales:

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/api/v1/pathologies/{key}/ecos-map/pending-draft` | GET | Borrador pendiente (draft) más reciente, o 404 |
| `/api/v1/pathologies/{key}/ecos-map` | GET | Mapa aprobado activo, o 404 |
| `/api/v1/pathologies/{key}/ecos-maps` | GET | Historial completo (todas las versiones) |
| `/api/v1/ecos-maps/{id}` | PUT | Editar borrador (draft-only) |
| `/api/v1/ecos-maps/{id}/approve` | POST | Aprobar borrador |

Todos requieren autenticación (cookie httpOnly).

---

## Flujo de UX

### 1. Estado: "Sin mapa"

El proyecto se creó pero aún no se hizo merge, o el merge no
encoló el auto-propose (por ejemplo, ya había un mapa aprobado
que luego se eliminó).

**UI:** Card con badge gris "Sin mapa de ecos" y texto informativo:
"Haz merge de las extracciones para generar automáticamente un
borrador del mapa de ecos."

### 2. Estado: "Generando borrador"

El merge encoló el job `propose_ecos_map_job` pero aún no terminó.

**UI:** Card con spinner + "Generando borrador del mapa de ecos..."
+ polling cada 5s sobre `GET /pathologies/{key}/ecos-map/pending-draft`.
Cuando devuelva 200 (en vez de 404), transicionar a estado 3.

### 3. Estado: "Borrador pendiente de revisión"

El borrador existe (status=draft, is_active=false).

**UI:** Card con badge amarillo "Borrador pendiente" +
- Lista de 11 secciones, cada una con sus ecos como items editables.
- Cada sección es un textarea o lista editable (ver abajo).
- Botón "Guardar cambios" → `PUT /ecos-maps/{id}`.
- Botón "Aprobar" → `POST /ecos-maps/{id}/approve`.
- Si `PUT` devuelve `warnings`, mostrarlas como badges amarillos
  junto a la sección correspondiente (no bloquean el guardado).

### 4. Estado: "Aprobado"

El mapa está aprobado y activo.

**UI:** Card con badge verde "Mapa aprobado (vN)" +
- Lista de 11 secciones en modo lectura (solo visualización).
- Botón "Regenerar borrador" → `POST /pathologies/{key}/ecos-map:propose`
  (crea una nueva versión draft; transicionar a estado 3).

---

## Datos del API

### GET `/pathologies/{key}/ecos-map/pending-draft`

Respuesta 200:
```json
{
  "id": "uuid",
  "pathology_key": "aki-2-0",
  "pathology_name": "Aki 2 0",
  "version": 1,
  "status": "draft",
  "origin": "autopopulated",
  "is_active": false,
  "sections": {
    "1": [],
    "2": ["Definición clínica de LRA (→ ver Sección 1)", ...],
    ...
    "11": [...]
  },
  "description": "Borrador auto-poblado v1",
  "approved_by": null,
  "approved_at": null,
  "created_at": "2026-07-21T...",
  "updated_at": "2026-07-21T..."
}
```

404: `{"detail": "No hay borrador pendiente para 'aki-2-0'."}`

### PUT `/ecos-maps/{id}`

Request:
```json
{
  "sections": {
    "1": [],
    "2": ["eco editado 1", "eco editado 2"],
    ...
  },
  "description": "editado por el doctor"
}
```

Respuesta 200:
```json
{
  "ecos_map": { ... },
  "warnings": ["slot 'mecanismo_molecular' no aparece como eco..."]
}
```

409: `{"detail": "Solo se pueden editar borradores (estado actual: approved)"}`

### POST `/ecos-maps/{id}/approve`

Respuesta 200: `{ ...ecos_map serializado con status=approved... }`

---

## Componente sugerido: `EcosMapCard`

Ubicación: `frontend/src/components/pipeline/EcosMapCard.tsx`

Props:
```typescript
interface EcosMapCardProps {
  projectId: string;
  pathologyKey: string;  // derivado del project.name en frontend
  projectStatus: string;
}
```

Sub-componentes:
- `EcosSectionEditor`: para cada sección (1-11), lista de ecos
  editables. Puede ser un textarea con un eco por línea, o una
  lista de chips/badges editables.
- `EcosSectionViewer`: modo lectura (cuando está aprobado).

### API client: `frontend/src/api/ecos.ts`

```typescript
export async function getPendingDraft(key: string): Promise<EcosMap | null> {
  try {
    return await request<EcosMap>(`/pathologies/${key}/ecos-map/pending-draft`);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
}

export async function getApprovedMap(key: string): Promise<EcosMap | null> {
  try {
    return await request<EcosMap>(`/pathologies/${key}/ecos-map`);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
}

export async function updateDraft(
  id: string,
  sections: Record<string, string[]>,
  description?: string,
): Promise<{ ecos_map: EcosMap; warnings: string[] }> {
  return await request(`/ecos-maps/${id}`, {
    method: "PUT",
    body: JSON.stringify({ sections, description }),
  });
}

export async function approveMap(id: string): Promise<EcosMap> {
  return await request(`/ecos-maps/${id}`, { method: "POST" });
}
```

### Integración en `ProjectDetailPage`

Añadir `EcosMapCard` después de `CompendiumCard`:

```tsx
<EcosMapCard
  projectId={project.id}
  pathologyKey={pathologyKeyFor(project.name)}
  projectStatus={project.status}
/>
```

Donde `pathologyKeyFor` replica la lógica del backend:
```typescript
function pathologyKeyFor(name: string): string {
  return name
    .normalize("NFD").replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}
```

### Polling

Usar `useSWR` con `refreshInterval` condicional:
- Estado "generando": 5s
- Estado "borrador pendiente": 0 (manual refresh tras editar)
- Estado "aprobado": 0

---

## Notas de implementación

1. **Secciones vacías:** La sección 1 siempre tiene ecos vacíos
   (no hay secciones anteriores). El editor debe permitir una
   lista vacía sin errores.

2. **Validación de cobertura:** El `PUT` devuelve `warnings`
   (slots faltantes). Mostrar como badges informativos, no como
   errores bloqueantes. El doctor puede decidir ignorarlos.

3. **Re-aprobar:** Tras aprobar, si el doctor quiere regenerar,
   el `POST /pathologies/{key}/ecos-map:propose` crea una nueva
   versión draft. El flujo vuelve al estado 3.

4. **Error handling:** Los 409 del `PUT` (edición de aprobado) y
   del `approve` (ya aprobado) deben mostrar toasts con el
   `detail` del backend (patrón existente con sonner).

5. **Accesibilidad:** Los textareas de ecos deben tener labels
   ("Sección N — Nombre de sección") y los botones deben ser
   descriptivos ("Guardar cambios", "Aprobar mapa de ecos").
