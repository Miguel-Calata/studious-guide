# 08 — Prompt Engine (Corazón de SAM)

## 🧬 ¿Por qué es el corazón del sistema?

El valor diferencial de SAM no está en la tecnología (FastAPI, React, PostgreSQL son commodities), sino en la **ingeniería de prompts** desarrollada por el Dr. Jorge a lo largo de múltiples iteraciones:

- **5 Pilares** de redacción clínica
- **10 Leyes Absolutas** que garantizan calidad y consistencia
- **MAPA_ECOS**: sistema anti-redundancia entre secciones
- **Dosificación de razonamiento**: cuándo usar Extended Thinking
- **Bifurcación Gemini/Claude**: cada sección al modelo óptimo

El Prompt Engine debe **replicar fielmente** la lógica de `sam_v9_generador.py` pero en tiempo real y con datos vivos.

---

## 📦 Componentes del Prompt Engine

### 1. System Prompt Base

El **System Prompt SAM v9** (5 Pilares, 10 Leyes) es el ADN del sistema. Define:
- Cómo redacta la IA
- Qué formato usa (callouts, tablas, mnemotecnias)
- Cómo cita fuentes
- Cómo maneja divergencias entre guías
- Cómo respeta el MAPA_ECOS

Este prompt se almacena en `prompt_templates` como `system_prompt_sam_v9` y es **versionado**. Si el Dr. mejora una ley o añade un pilar, se crea una nueva versión sin romper compendios anteriores.

### 2. Prompts de Extracción

Tres variantes según el tipo de fuente:

| Prompt | Tipo de fuente | Característica clave |
|--------|---------------|---------------------|
| `extraction_v3_bmj` | BMJ Best Practice, NICE CKS, Oxford Handbook | Transcribe TODO, preserva estructura nativa, protocolo anti-ciclo |
| `extraction_v5_guideline` | KDIGO, WHO, ESC, AHA | Excluye secciones administrativas (metodología, comités), conserva solo contenido clínico |
| `extraction_articles` | Lancet, NEJM, JAMA, Nature | Reformula para evitar copyright, extrae mecanismos + datos por separado |

### 3. Prompt de Auditoría

Post-extracción, Gemini compara su output contra el PDF original y añade lo que faltó. Es una **red de seguridad** contra omisiones.

### 4. Parche Gemini (Densidad de Citas)

Se inyecta al inicio de la sesión de Gemini para forzar:
- Citación granular (cada número pegado a su cita)
- Bloques de divergencia explícitos (📋 Nota de divergencia)

### 5. Builder de Secciones

Construye el prompt final para cada sección combinando:
```
[System Prompt SAM v9]
[MAPA_ECOS de esta sección]
[Dosificación de razonamiento]
[Motor recomendado]
[Nota de co-generación si aplica]
[Instrucción específica de sección]
```

---

## 🏗️ Arquitectura del Prompt Engine

```
┌─────────────────────────────────────────────────┐
│                Prompt Engine                     │
│                                                 │
│  ┌─────────────┐  ┌──────────────┐              │
│  │ Template     │  │ Section      │              │
│  │ Repository   │  │ Builder      │              │
│  │              │  │              │              │
│  │ - get(name)  │  │ - build(     │              │
│  │ - activate() │  │     section, │              │
│  │ - history()  │  │     ecos,    │              │
│  │              │  │     motor)   │              │
│  └─────────────┘  └──────┬───────┘              │
│                          │                      │
│  ┌───────────────────────▼───────────────────┐  │
│  │           Section Prompt Builder          │  │
│  │                                           │  │
│  │  build_section_prompt(                    │  │
│  │    section_number: int,                   │  │
│  │    merged_content: str,                   │  │
│  │    pathology_name: str,                   │  │
│  │    source_filename: str,                  │  │
│  │    is_first: bool,                        │  │
│  │    is_last: bool                          │  │
│  │  ) → str   # Prompt completo              │  │
│  └───────────────────────────────────────────┘  │
│                                                 │
│  ┌───────────────────────────────────────────┐  │
│  │           MAPA_ECOS Engine                │  │
│  │                                           │  │
│  │  get_ecos(section_number) → list[str]     │  │
│  │                                           │  │
│  │  Sección 1: []                            │  │
│  │  Sección 2: [definición LRA, cifras...]   │  │
│  │  Sección 3: [criterios KDIGO/NICE...]     │  │
│  │  ...                                      │  │
│  │  Sección 11: [fluidoterapia, PAM, TRR...] │  │
│  └───────────────────────────────────────────┘  │
│                                                 │
│  ┌───────────────────────────────────────────┐  │
│  │           Dosification Engine             │  │
│  │                                           │  │
│  │  get_config(section_number) → {           │  │
│  │    level: 🟢|🟡|🔴,                       │  │
│  │    motor: gemini|claude,                  │  │
│  │    extended_thinking: bool,               │  │
│  │    temperature: float                     │  │
│  │  }                                        │  │
│  └───────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

---

## 📝 Implementación: Section Prompt Builder

```python
# backend/app/modules/prompts/section_builder.py

from dataclasses import dataclass
from typing import Optional

@dataclass
class SectionConfig:
    section_number: int
    section_name: str
    next_section: str
    dosification_level: str      # 🟢 STANDARD / 🟡 HIGH / 🔴 MAX
    dosification_desc: str
    motor: str                    # gemini / claude
    ecos: list[str]               # Temas ya cubiertos (R-1)
    is_cogeneration_pair: bool    # R-9 (secciones 4-5)
    cogeneration_note: str | None

# Configuración centralizada (misma data que sam_v9_generador.py)
SECTION_CONFIGS = {
    1: SectionConfig(
        section_number=1,
        section_name="DESCRIPCIÓN Y EPIDEMIOLOGÍA",
        next_section="2. CLASIFICACIÓN",
        dosification_level="🟢 ESTÁNDAR",
        dosification_desc="Epidemiología descriptiva. No requiere Extended Thinking.",
        motor="gemini",
        ecos=[],
        is_cogeneration_pair=False,
        cogeneration_note=None,
    ),
    2: SectionConfig(
        section_number=2,
        section_name="CLASIFICACIÓN",
        next_section="3. FISIOPATOLOGÍA",
        dosification_level="🟢 ESTÁNDAR",
        dosification_desc="Clasificación estructurada. No requiere Extended Thinking.",
        motor="gemini",
        ecos=[
            "Definición clínica de LRA, ERA y ERC (→ ver Descripción).",
            "Cifras de incidencia/mortalidad global (→ ver Epidemiología).",
            "Distinción LRA comunitaria vs. hospitalaria (→ ver Epidemiología).",
        ],
        is_cogeneration_pair=False,
        cogeneration_note=None,
    ),
    # ... (secciones 3-11 con sus respectivos ecos y configs)
}


async def build_section_prompt(
    section_number: int,
    merged_content: str,
    pathology_name: str,
    source_filename: str,
    is_first: bool,
    is_last: bool,
) -> str:
    """
    Construye el prompt completo para una sección del compendio.
    Replica exactamente la lógica de sam_v9_generador.py.
    """
    config = SECTION_CONFIGS[section_number]
    
    # 1. Obtener System Prompt activo
    system_prompt = await get_active_prompt("system_prompt_sam_v9")
    
    # 2. Construir bloque MAPA_ECOS
    ecos_block = _build_ecos_block(config.ecos)
    
    # 3. Construir nota de co-generación (R-9)
    cogen_note = _build_cogeneration_note(config)
    
    # 4. Construir avisos de adjunto
    attachment_note = _build_attachment_note(is_first)
    
    # 5. Construir aviso de última sección
    last_section_note = _build_last_section_note(is_last)
    
    # 6. Ensamblar prompt final
    prompt = f"""{system_prompt.content}

{"="*70}
INSTRUCCIÓN DE SESIÓN — SAM v9
{"="*70}

PATOLOGÍA : {pathology_name}
FUENTE(S) : {source_filename}
MOTOR     : {config.motor}  {"(Extended Thinking / Max Thinking)" if "🔴" in config.dosification_level else ""}
{attachment_note}
SECCIÓN A DESARROLLAR : {config.section_name}
SECCIÓN SIGUIENTE     : {config.next_section}

DOSIFICACIÓN DEL RAZONAMIENTO PARA ESTA SECCIÓN:
  {config.dosification_level} — {config.dosification_desc}
{ecos_block}
{cogen_note}
{last_section_note}
INSTRUCCIÓN: Desarrolla ÚNICAMENTE la sección "{config.section_name}" del
compendio, usando exclusivamente los documentos adjuntos. No incluyas
contenido de otras secciones del compendio.

{"="*70}
COMIENZA AHORA: {config.section_name}
{"="*70}
"""
    return prompt


def _build_ecos_block(ecos: list[str]) -> str:
    if not ecos:
        return ""
    items = "\n".join(f"  - {eco}" for eco in ecos)
    return f"""
──────────────────────────────────────────────────────────────
MAPA DE ECOS — CONTENIDO YA CUBIERTO (R-1: solo referencia cruzada):
{items}
──────────────────────────────────────────────────────────────
"""


def _build_cogeneration_note(config: SectionConfig) -> str:
    if config.section_number == 4:
        return """
⚡ AVISO LEY R-9 (CO-GENERACIÓN CLÍNICA):
Esta es la sección CUADRO CLÍNICO. El prompt de DIAGNÓSTICO (05) se
pegará en la MISMA conversación, a continuación.
"""
    elif config.section_number == 5:
        return """
⚡ AVISO LEY R-9 (CO-GENERACIÓN CLÍNICA):
Esta es la sección DIAGNÓSTICO. Acabas de generar CUADRO CLÍNICO en este
mismo chat. Aplica R-1 estrictamente.
"""
    return ""


def _build_attachment_note(is_first: bool) -> str:
    if is_first:
        return """
📎 Adjunta los documentos fuente a esta conversación AHORA,
antes de enviar este prompt (una sola vez para toda la sesión).
"""
    return """
📎 Los documentos fuente YA están adjuntos desde el inicio de
esta conversación — no los vuelvas a adjuntar.
Esta es una SECCIÓN NUEVA del compendio, no una continuación
de la sección anterior. Comienza directamente.
"""


def _build_last_section_note(is_last: bool) -> str:
    if not is_last:
        return ""
    return """
⚠️ ESTA ES LA ÚLTIMA SECCIÓN DEL COMPENDIO.
Al terminar el cuerpo de esta sección, genera el bloque
## Referencias Bibliográficas con todas las fuentes del compendio.
"""
```

---

## 🔄 Versionado de Prompts

```
prompt_templates:
┌────────────────────────────────────────────────────────────┐
│ name: system_prompt_sam_v9                                 │
│ type: system                                                │
│ version: 3  (active)                                       │
│ content: "[SYSTEM — SAM v9 — CATEDRÁTICO..."                │
│ created_at: 2026-07-01                                      │
├────────────────────────────────────────────────────────────┤
│ version: 2                                                  │
│ content: "[SYSTEM — SAM v8 — 5 PILARES...]"                │
│ description: "Añadida Ley R-10 y ajuste en R-7"            │
│ created_at: 2026-06-15                                      │
├────────────────────────────────────────────────────────────┤
│ version: 1                                                  │
│ content: "[SYSTEM — SAM v7 — ...]"                         │
│ description: "Versión inicial con 5 Pilares"               │
│ created_at: 2026-06-01                                      │
└────────────────────────────────────────────────────────────┘
```

Al generar un compendio, se registra `prompt_version` en cada sección para trazabilidad.

---

## 🌱 Seed Data (Migración Inicial)

Al levantar el sistema por primera vez, se cargan los prompts desde los archivos legacy:

```
backend/alembic/versions/XXXX_seed_prompts.py
```

Los prompts iniciales se extraen del documento `memory/NUEVO - IA -.md` del Dr.:
- `PROMPT_EXTRACCION_v3_CORREGIDO.txt` → `extraction_v3_bmj` v1
- `PROMPT_EXTRACCION_v5_guias_completas.txt` → `extraction_v5_guideline` v1
- `PROMPT_EXTRACCION_ARTICULOS_UNIFICADO.txt` → `extraction_articles` v1
- `PROMPT_AUDITORIA.txt` → `audit` v1
- `PARCHE_GEMINI_DENSIDAD.txt` → `patch_gemini_density` v1
- System Prompt de `sam_v9_generador.py` → `system_prompt_sam_v9` v1

---

> **Próximo documento:** [09_pipeline_ia.md](09_pipeline_ia.md)
