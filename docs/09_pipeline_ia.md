# 09 — Pipeline de IA (Orquestación vía OpenRouter)

## 🎯 Objetivo

Automatizar completamente las Fases 1-5 del flujo manual del Dr., reemplazando el copy-paste entre interfaces web por llamadas directas a **OpenRouter**, que unifica el acceso a Gemini, Claude y otros modelos bajo una sola API.

## 🔌 Por qué OpenRouter

| Ventaja | Detalle |
|---------|---------|
| **Una sola API key** | No necesitas keys separadas de Google y Anthropic |
| **Un solo SDK** | API compatible con OpenAI SDK (`openai` python package) |
| **Pricing transparente** | Cada response incluye `usage.cost` en USD |
| **Multi-modelo** | Gemini 2.5 Pro, Claude 3.5 Sonnet, y +200 modelos más |
| **Fallback automático** | Si un proveedor falla, puedes rutear a otro |
| **Sin prompt caching manual** | OpenRouter maneja caching internamente para algunos modelos |

---

## 🔄 Flujo Completo del Pipeline

```
┌──────────────────────────────────────────────────────────────────┐
│                    PIPELINE DE IA AUTOMÁTICO                      │
│                                                                   │
│  FASE 1: EXTRACCIÓN — cada PDF → OpenRouter (Gemini 2.5 Pro)      │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌──────────────┐   │
│  │ PDF 1   │    │ PDF 2   │    │ PDF N   │    │ Auditoría    │   │
│  │ (BMJ)   │───▶│ (Guía)  │───▶│ (Art.)  │───▶│ post-        │   │
│  │         │    │         │    │         │    │ extracción   │   │
│  └─────────┘    └─────────┘    └─────────┘    └──────────────┘   │
│       │              │              │              │              │
│       ▼              ▼              ▼              ▼              │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │                 MERGER (unir_extraccion.py)               │    │
│  │        Todas las extracciones → merged_document.md        │    │
│  └──────────────────────────────────────────────────────────┘    │
│                              │                                    │
│  FASE 2: GENERACIÓN — OpenRouter rutea cada sección               │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │              SECTION GENERATOR (11 secciones)             │    │
│  │                                                          │    │
│  │  ┌─────────────────────┐   ┌─────────────────────────┐   │    │
│  │  │ GEMINI (7 secciones)│   │ CLAUDE (4 secciones)    │   │    │
│  │  │ vía OpenRouter      │   │ vía OpenRouter          │   │    │
│  │  │                     │   │                         │   │    │
│  │  │ 🟢 01 Descr+Epidem  │   │ 🔴 03 Fisiopatología    │   │    │
│  │  │ 🟢 02 Clasificación │   │ 🔴 05 Diagnóstico       │   │    │
│  │  │ 🟢 04 Cuadro Clínico│   │ 🔴 08 Farmacológico     │   │    │
│  │  │ 🟡 06 Escalas       │   │ 🔴 09 Protocolo Integr. │   │    │
│  │  │ 🟢 07 No Farmacol.  │   │                         │   │    │
│  │  │ 🟡 10 Poblaciones   │   │                         │   │    │
│  │  │ 🟡 11 Perioperatorio│   │                         │   │    │
│  │  └─────────────────────┘   └─────────────────────────┘   │    │
│  │         ▲                           ▲                    │    │
│  │         └───────────┬───────────────┘                    │    │
│  │                     │                                    │    │
│  │           UN solo cliente OpenRouter                     │    │
│  │           model="google/gemini-2.5-pro"                  │    │
│  │           model="anthropic/claude-3.5-sonnet"            │    │
│  └──────────────────────────────────────────────────────────┘    │
│                              │                                    │
│                              ▼                                    │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │              COMPENDIO FINAL (11 secciones)               │    │
│  │              + Referencias Bibliográficas                  │    │
│  │              → Subida a S3 + URL pública                   │    │
│  └──────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────┘
```

---

## 🔌 OpenRouter Client (AI Gateway Unificado)

> **Actualizado Sprint 12.** El cliente ahora soporta mensajes
> explícitos (`generate(messages=...)`), continuaciones con
> historial real (`generate_in_conversation`), y guardia de
> overflow con `ContextOverflowError`. El catálogo de modelos
> vive en `app/modules/ai_gateway/models.py:AVAILABLE_MODELS`
> (intacto, validado contra el spec).

```python
# backend/app/modules/ai_gateway/openrouter_client.py

from openai import AsyncOpenAI
from dataclasses import dataclass, field

@dataclass
class AIResult:
    content: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    finish_reason: str

class OpenRouterClient:
    """
    Cliente unificado para OpenRouter API.
    Compatible con OpenAI SDK → mismo código para cualquier modelo.
    """

    # Modelos disponibles — Sprint 12: el catálogo está en
    # AVAILABLE_MODELS (NO hardcoded). Se valida contra la lista
    # en runtime (harness de Tarea 4).
    # Última actualización conocida: 16 modelos incluyendo
    # Claude Opus 4.8, Claude Sonnet 5, Gemini 3.1 Pro, Gemini 3.5
    # Flash, GPT-5 Pro, Qwen3.6 Flash, etc.

    def __init__(self, api_key: str, base_url: str = "https://openrouter.ai/api/v1"):
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            default_headers={
                "HTTP-Referer": "https://sam-platform.app",  # Opcional: para rankings
                "X-Title": "SAM Platform",
            }
        )

    async def generate(
        self,
        prompt: str | None = None,
        *,
        model: str,
        temperature: float = 0.1,
        max_tokens: int = 65536,
        system_prompt: str | None = None,
        messages: list[dict] | None = None,
        **kwargs,
    ) -> AIResult:
        """
        Llamada unificada a cualquier modelo vía OpenRouter.

        - Si se pasa `messages`, se usan directamente (recomendado
          para Conversation: historial completo de la sesión).
        - Si se pasa `prompt`, se construye un único turno user.
        - `**kwargs` se envían como `extra_body` (ej.
          `reasoning`, etc.).
        """
        if messages is None:
            messages = []
            if system_prompt:
                messages.append(
                    {"role": "system", "content": system_prompt}
                )
            if prompt is None:
                raise ValueError(
                    "generate requiere 'messages' o 'prompt'"
                )
            messages.append({"role": "user", "content": prompt})

        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            extra_body=kwargs,
        )

        choice = response.choices[0]
        usage = response.usage
        cost_usd = response.cost if hasattr(response, 'cost') else 0.0

        return AIResult(
            content=choice.message.content or "",
            model=response.model,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            cost_usd=cost_usd,
            finish_reason=choice.finish_reason or "unknown",
        )
    
    async def generate_with_continuations(
        self,
        prompt: str,
        model: str = "google/gemini-2.5-pro",
        temperature: float = 0.1,
        max_continuations: int = 10
    ) -> AIResult:
        """
        Genera contenido manejando continuaciones automáticas.

        Sprint 12 (Tarea 1): la implementación REAL acumula el
        historial de mensajes. La implementación original (v8)
        enviaba solo "Continúa" sin contexto, perdiendo toda la
        fuente documental en cada continuación.
        """
        conv = Conversation()
        conv.add_user(prompt)
        return await self.generate_in_conversation(
            conversation=conv,
            user_message="",
            model=model,
            temperature=temperature,
            max_continuations=max_continuations,
        )
```

> **Sprint 12 — `generate_in_conversation` (nuevo):** acumula
> los mensajes assistant en una `Conversation` y reenvía el
> historial COMPLETO en cada llamada de continuación. Antes de
> la primera llamada, valida que la conversación acumulada +
> output reservado quepan en la ventana del modelo
> (`ContextOverflowError` si se supera — NUNCA trunca en
> silencio). Tras agotar `max_continuations`, si la respuesta
> sigue truncada (`finish_reason='length'`), lanza
> `ContinuationExhaustedError` y se rehúsa devolver contenido
> truncado.

---

## 💰 Control de Costos con OpenRouter

OpenRouter **devuelve el costo en USD en cada response**, lo que simplifica enormemente el tracking:

```python
# El costo viene en la response de OpenRouter
response = await client.chat.completions.create(...)
cost = response.cost  # Ya calculado por OpenRouter

# No necesitamos CostTracker propio — OpenRouter lo hace por nosotros
```

### Estimación por patología (con OpenRouter)

> ⚠️ **Pendiente Sprint 12 Tarea 4.** Las estimaciones de costo
> y la decisión de bifurcación entre Gemini 3.1 Pro / Claude
> Sonnet 5 / Claude Opus 4.8 requieren una comparación empírica
> contra el catálogo actual de `AVAILABLE_MODELS`. Mientras
> tanto, el `MOTOR_MODEL_MAP` por defecto mapea ambos motores
> (gemini, claude) a `google/gemini-3.1-pro-preview`. Ver
> `docs/13_comparacion_motores.md` para el harness
> (`backend/scripts/compare_motors.py`) y la rúbrica de
> decisión.

| Fase | Modelo (default) | Input (est.) | Output (est.) | Costo OpenRouter (est.) |
|------|--------|-------------|---------------|------------------------|
| Extracción ×3 PDFs | Gemini 3.1 Pro | ~450k | ~250k | ~$2.50-3.50 |
| Auditoría ×3 | keyword match v1 | — | — | ~$0 (local, sin API) |
| Secciones 🟢🟡 ×7 | Gemini 3.1 Pro | ~1M | ~56k | ~$2.00-3.00 |
| Secciones 🔴 ×4 | Gemini 3.1 Pro* | ~600k | ~32k | ~$2.00-3.00 |
| **TOTAL** | | | | **~$7-10 USD** |

\* Cuando se decida la bifurcación post-Tarea 4, las secciones
🔴 usarán un Claude con `reasoning: {enabled: True}` y el costo
puede subir ~$1-3 USD adicionales.

---

## 🔄 Orquestador del Pipeline

> **Actualizado Sprint 12.** El `PipelineOrchestrator` pasó de
> stub (`pass`) a implementación real, con generación SECUENCIAL
> 1 → 11 sobre un único hilo de conversación (Tarea 1), cascada
> R-9 (Tarea 5) y verificación de eco map aprobado (Tarea 3).

```python
# backend/app/services/orchestrator.py

class PipelineOrchestrator:
    """
    Coordina la generación de un compendio completo manteniendo
    continuidad real de contexto entre secciones (hilo acumulado
    derivado del estado de la BD), con motor resuelto por
    sección, soporte de co-generación 4-5 y verificación de mapa
    de ecos aprobado.
    """

    COGENERATION_PAIRS = {5: 4}  # R-9

    async def generate_all_sections(
        self,
        project_id: str,
        motor_model_map: dict[str, str] | None = None,
        eco_map_lookup=None,
        eco_map=None,
    ) -> OrchestratorResult:
        # 1. Cargar eco map aprobado (bloquear 409 si no existe)
        # 2. Para cada sección 1..11:
        #    a. Resolver motor con regla R-9 (5 hereda de 4)
        #    b. Construir hilo (replay de secciones previas)
        #    c. Generar con extended thinking si Claude + 🔴
        #    d. Persistir sección + prompt_version + ecos_map_version
        # 3. Transición DRAFT/REVIEW → GENERATING → REVIEW
```

**Job ARQ único**: `generate_compendium` (sustituye los 11 jobs
paralelos `generate_section` del Sprint 8). El orquestador
corre las 11 secciones en orden, manteniendo la conversación en
memoria durante el job. La conversación se reconstruye por
sección desde el estado de la BD sin llamadas extra a la API
(las respuestas assistant se recuperan de
`CompendiumSection.content`).

**Regeneración**: `regenerate_section_job` regenera una sección
individual. Si es la 4 o 5 del par R-9, ambas se regeneran con
el mismo motor (cascada).

---

## ⚡ Control de Concurrencia

```python
# backend/app/workers/generation_worker.py

import asyncio

# OpenRouter rate limits: ~20 req/min para planes gratuitos, +200 para pagos
# Semáforo conservador: 5 concurrentes máximo
AI_SEMAPHORE = asyncio.Semaphore(5)

async def generate_section(ctx, project_id: str, section_number: int, model_id: str):
    async with AI_SEMAPHORE:
        config = SECTION_CONFIGS[section_number]
        
        # 1. Construir prompt
        system_prompt = await get_active_prompt("system_prompt_sam_v9")
        section_prompt = await build_section_prompt(section_number, ...)
        
        # 2. Parámetros extra según modelo
        extra_params = {}
        if "claude" in model_id and "🔴" in config.dosification_level:
            # Extended thinking para Claude en secciones críticas.
            # Formato REAL de OpenRouter (Sprint 12, Tarea 1):
            # `reasoning: {enabled: True, max_tokens: N}`.
            # La doc original mencionaba `thinking` (incorrecto).
            extra_params["reasoning"] = {"enabled": True, "max_tokens": 16000}
        
        # 3. Llamada unificada vía OpenRouter
        result = await openrouter_client.generate(
            prompt=section_prompt,
            model=model_id,
            system_prompt=system_prompt.content,
            temperature=0.1,
            **extra_params
        )
        
        # 4. Guardar resultado
        await save_section(project_id, section_number, result)
```

---

## 🛡️ Retry y Manejo de Errores

```python
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=60),
    retry_error_callback=lambda retry_state: None
)
async def call_with_retry(client_call, *args, **kwargs):
    """Reintenta llamadas a API con backoff exponencial."""
    try:
        return await client_call(*args, **kwargs)
    except Exception as e:
        if "rate_limit" in str(e).lower() or "429" in str(e):
            logger.warning("Rate limit alcanzado, reintentando...")
            raise  # tenacity lo reintenta
        elif "overloaded" in str(e).lower() or "529" in str(e):
            logger.warning("Servidor sobrecargado, reintentando...")
            raise
        else:
            logger.error(f"Error no recuperable: {e}")
            raise
```

---

## 📊 Estimación de Costos (OpenRouter)

OpenRouter pricing es transparente y se actualiza en tiempo real. Cada llamada devuelve el costo exacto.

### Estrategia para minimizar costos

1. **Modelo correcto para cada sección**: Gemini para secciones descriptivas (más barato), Claude solo para las 4 secciones 🔴 que requieren razonamiento profundo. La decisión final (qué modelo exacto para cada par) la decide Tarea 4 con evidencia empírica.
2. **Hilo acumulado compartido** (Sprint 12, Tarea 1): cada sección reusa las respuestas de las anteriores sin pagar de más. Tradeoff: las primeras secciones son más caras porque el prompt crece; mitigable con OpenRouter prompt caching.
3. **Auditoría v1 sin API** (Sprint 12, Tarea 2): matching de keywords contra checklist curado. Cero tokens para esta fase.
4. **Reutilizar el compendio generado**: Una vez publicado en S3 + Notion, no se re-genera a menos que cambien las fuentes
5. **Previsualización sin costo**: El visor público carga el .md desde S3 → cero costo de API
6. **Futuro**: Explorar modelos más baratos en OpenRouter para secciones 🟢 (ej. Gemini Flash, Claude Haiku) — la decisión de bifurcación post-Tarea 4 puede considerar estos.

---

> **Próximo documento:** [10_deployment.md](10_deployment.md)
