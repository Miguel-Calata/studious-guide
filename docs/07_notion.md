# 07 — Integración con Notion

## 🎯 Objetivo

Publicar automáticamente los compendios generados como páginas estructuradas en Notion, eliminando la Fase 6 manual del pipeline actual (copiar y pegar sección por sección).

---

## 🔌 Conexión con Notion API

### Método: OAuth Public Integration

Cada usuario conecta **su propia cuenta de Notion** mediante OAuth 2.0, sin compartir API keys. El usuario autoriza la integración y selecciona las páginas a las que SAM puede acceder.

```
Flujo OAuth:
┌──────────┐     ┌──────────┐     ┌──────────────┐
│ Frontend │────▶│ Backend  │────▶│  Notion API  │
│          │     │ /start   │     │  /authorize   │
└──────────┘     └──────────┘     └──────┬───────┘
     ▲                                    │
     │         ┌──────────┐               │ redirect
     │◀────────│ Backend  │◀──────────────┘
     │         │ /callback│     ?code=...&state=...
     │         └────┬─────┘
     │              │ POST /oauth/token
     │              │ (HTTP Basic client_id:client_secret)
     │              ▼
     │         ┌──────────┐
     │         │ Notion   │
     │         │ API      │
     │         └──────────┘
     │
     └── ?notion=connected (redirect al frontend)
```

#### Pasos para configurar la integración pública en Notion

1. Ir a https://www.notion.so/my-integrations → **Create new integration** → tipo **Public integration**
2. Rellenar:
   - **Name**: SAM Platform
   - **Redirect URIs**: `https://<dominio>/api/v1/notion/oauth/callback` (y `http://localhost:8000/api/v1/notion/oauth/callback` para dev)
3. Marcar **capabilities**:
   - ✅ Read user information (including email addresses)
   - ✅ Read content, Insert content, Update content
   - ✅ Page metadata
4. Copiar **OAuth client ID** (UUID) y **OAuth client secret** (`secret_...`)
5. Configurar en `.env`:
   ```
   NOTION_OAUTH_CLIENT_ID=<client_id>
   NOTION_OAUTH_CLIENT_SECRET=<client_secret>
   NOTION_OAUTH_REDIRECT_URI=https://app.dominio/api/v1/notion/oauth/callback
   ```

#### Endpoints OAuth

| Endpoint | Descripción |
|----------|-------------|
| `GET /notion/oauth/start` | Genera URL de autorización + state JWT (cookie efímera). El frontend redirige al usuario a esa URL |
| `GET /notion/oauth/callback` | Recibe `code` + `state` de Notion, intercambia por tokens, guarda en BD, redirige al frontend |
| `POST /notion/disconnect` | Borra tokens y marca como desconectado |
| `GET /notion/status` | Devuelve estado, `needs_reconnect` si el token expiró sin refresh posible |

#### Seguridad del state OAuth

- El `state` es un JWT firmado con `SECRET_KEY` que contiene `{sub: user_id, nonce, exp}`.
- Se setea una cookie httpOnly efímera (5 min) con el mismo valor.
- En el callback se valida que el JWT sea válido y que coincida con la cookie (protección CSRF + anti-replay).

---

## 📊 Estructura de Publicación

### Jerarquía en Notion

```
📁 Compendios SAM (Página padre configurada)
  └── 📄 Lesión Renal Aguda (Página del compendio)
        ├── 📄 01 — Descripción y Epidemiología
        ├── 📄 02 — Clasificación
        ├── 📄 03 — Fisiopatología
        ├── 📄 04 — Cuadro Clínico
        ├── 📄 05 — Diagnóstico
        ├── 📄 06 — Escalas y Estratificación de Riesgo
        ├── 📄 07 — Manejo No Farmacológico
        ├── 📄 08 — Manejo Farmacológico
        ├── 📄 09 — Protocolo Integrado y Urgencias
        ├── 📄 10 — Poblaciones Especiales
        ├── 📄 11 — Protocolo Perioperatorio
        └── 📄 Referencias Bibliográficas
```

---

## 🛠️ Implementación Técnica

### NotionClient (wrapper)

```python
# backend/app/modules/notion/client.py

from notion_client import AsyncClient

class NotionClientWrapper:
    def __init__(self, api_key: str):
        self.client = AsyncClient(auth=api_key)
    
    async def search_pages(self, query: str) -> list[dict]:
        """Buscar páginas y bases de datos."""
        response = await self.client.search(query=query)
        return response["results"]
    
    async def create_page(
        self,
        parent_page_id: str,
        title: str,
        content_markdown: str
    ) -> str:
        """
        Crea una página en Notion con contenido Markdown.
        Retorna el page_id.
        """
        # 1. Convertir Markdown → bloques de Notion
        blocks = self._md_to_notion_blocks(content_markdown)
        
        # 2. Crear página
        response = await self.client.pages.create(
            parent={"page_id": parent_page_id},
            properties={
                "title": {
                    "title": [{"text": {"content": title}}]
                }
            },
            children=blocks[:100]  # Límite: 100 bloques por llamada
        )
        
        page_id = response["id"]
        
        # 3. Si hay más de 100 bloques, hacer append en lotes
        for i in range(100, len(blocks), 100):
            await self.client.blocks.children.append(
                block_id=page_id,
                children=blocks[i:i+100]
            )
        
        return page_id
    
    async def update_page(self, page_id: str, content_markdown: str):
        """Actualiza el contenido de una página existente."""
        # 1. Obtener bloques existentes y eliminarlos
        existing = await self.client.blocks.children.list(block_id=page_id)
        for block in existing["results"]:
            await self.client.blocks.delete(block_id=block["id"])
        
        # 2. Crear nuevos bloques
        blocks = self._md_to_notion_blocks(content_markdown)
        for i in range(0, len(blocks), 100):
            await self.client.blocks.children.append(
                block_id=page_id,
                children=blocks[i:i+100]
            )
    
    def _md_to_notion_blocks(self, md_content: str) -> list[dict]:
        """
        Convierte Markdown a bloques de Notion API.
        
        Soporte:
        - ## ### #### → heading_1, heading_2, heading_3
        - Párrafos con **negrita** y _cursiva_
        - Tablas → table blocks
        - > callouts → callout blocks
        - ```code``` → code blocks
        - Listas numeradas y no numeradas
        """
        # TODO: Implementar parser Markdown → Notion blocks
        # Opciones:
        # a) Usar librería como md2notion o notion2md
        # b) Implementar parser propio con regex (más control)
        # c) Usar los bloques Markdown de Notion (si están disponibles en API)
        pass
```

### Servicio de Publicación

```python
# backend/app/modules/notion/service.py

class NotionService:
    async def publish_compendium(
        self,
        project_id: UUID,
        parent_page_id: str | None = None
    ) -> PublishResult:
        """
        Publica un compendio completo en Notion.
        
        1. Crea página principal con nombre de la patología
        2. Para cada sección completada, crea subpágina
        3. Retorna resumen
        """
        project = await get_project(project_id)
        config = await get_notion_config(project.user_id)
        
        client = NotionClientWrapper(decrypt(config.api_key))
        
        # Usar parent_page_id del request o el default del usuario
        target_parent = parent_page_id or config.default_parent_page_id
        
        # 1. Crear página del compendio
        compendium_page_id = await client.create_page(
            parent_page_id=target_parent,
            title=project.name,
            content_markdown=""  # Página vacía, solo contenedor
        )
        
        # 2. Publicar cada sección
        sections = await get_completed_sections(project_id)
        published = []
        
        for section in sections:
            page_id = await client.create_page(
                parent_page_id=compendium_page_id,
                title=f"{section.section_number:02d} — {section.section_name}",
                content_markdown=section.content
            )
            
            # Guardar page_id en la sección
            await update_section_notion_id(section.id, page_id)
            published.append({
                "section_number": section.section_number,
                "section_name": section.section_name,
                "notion_page_id": page_id
            })
        
        return PublishResult(
            compendium_page_id=compendium_page_id,
            sections_published=published
        )
```

---

## ⚠️ Limitaciones de Notion API

| Limitación | Impacto | Mitigación |
|-----------|---------|------------|
| Máx 100 bloques por llamada | Secciones muy largas requieren múltiples llamadas | Append en lotes de 100 |
| Bloques Markdown no nativos | Hay que convertir MD → Notion blocks manualmente | Parser propio o librería |
| Rate limit: 3 req/segundo | Publicación de 11 secciones toma unos segundos | Retry con backoff |
| Tamaño máximo de request: 500KB | Secciones muy extensas pueden exceder | Chunking por bloques |
| No soporta todos los elementos MD | Algunos formatos se pierden | Testear con compendios reales |

---

## 📝 Conversión Markdown → Notion Blocks

Ejemplo de mapping:

```python
# Input MD:
"""
## Clasificación KDIGO

La clasificación se basa en **dos criterios**:

| Estadio | Creatinina | Diuresis |
|---------|-----------|----------|
| 1 | ≥0.3 mg/dL | <0.5 mL/kg/h |
| 2 | ≥2.0x basal | <0.5 mL/kg/h por 12h |

> ⚠️ **Nota:** El estadio 3 incluye TRR.
"""

# Output Notion blocks:
[
    {
        "type": "heading_2",
        "heading_2": {
            "rich_text": [{"type": "text", "text": {"content": "Clasificación KDIGO"}}]
        }
    },
    {
        "type": "paragraph",
        "paragraph": {
            "rich_text": [
                {"type": "text", "text": {"content": "La clasificación se basa en "}},
                {"type": "text", "text": {"content": "dos criterios"}, "annotations": {"bold": True}},
                {"type": "text", "text": {"content": ":"}},
            ]
        }
    },
    {
        "type": "table",
        "table": {
            "table_width": 3,
            "has_column_header": True,
            "children": [...]
        }
    },
    {
        "type": "callout",
        "callout": {
            "rich_text": [
                {"type": "text", "text": {"content": "Nota:"}, "annotations": {"bold": True}},
                {"type": "text", "text": {"content": " El estadio 3 incluye TRR."}},
            ],
            "icon": {"emoji": "⚠️"}
        }
    }
]
```

---

## 🔁 Sincronización (Fase 2)

- Si una sección se re-genera, se actualiza automáticamente en Notion
- Opción: "Sync" vs "One-time publish"
- Tracking: `compendium_sections.notion_page_id` permite actualizar en vez de crear

---

> **Próximo documento:** [08_prompt_engine.md](08_prompt_engine.md)
