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
    
    # Modelos disponibles (IDs de OpenRouter)
    MODELS = {
        "gemini": "google/gemini-2.5-pro",
        "claude": "anthropic/claude-3.5-sonnet",
        # Alternativas de respaldo:
        # "gemini-flash": "google/gemini-2.5-flash",
        # "claude-haiku": "anthropic/claude-3.5-haiku",
    }
    
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
        prompt: str,
        model: str,
        temperature: float = 0.1,
        max_tokens: int = 65536,
        system_prompt: str | None = None,
        **kwargs
    ) -> AIResult:
        """
        Llamada unificada a cualquier modelo vía OpenRouter.
        
        Args:
            model: ID del modelo (ej. "google/gemini-2.5-pro")
            prompt: Prompt del usuario
            system_prompt: System prompt opcional
            temperature: 0.1 para extracción/generación clínica
            max_tokens: Límite de output
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            extra_body=kwargs,  # Parámetros extra (ej. extended thinking para Claude)
        )
        
        choice = response.choices[0]
        usage = response.usage
        
        # OpenRouter devuelve el costo total en la response
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
        Si el modelo responde [CONTINÚA...], pide continuación.
        """
        result = await self.generate(prompt, model, temperature)
        full_content = result.content
        total_tokens = result.input_tokens + result.output_tokens
        total_cost = result.cost_usd
        continuation_count = 0
        
        while ("[CONTINÚA" in full_content or "[Fin de la Parte" in full_content) \
              and continuation_count < max_continuations:
            cont_result = await self.generate(
                "Continúa", model, temperature
            )
            full_content += "\n\n" + cont_result.content
            total_tokens += cont_result.input_tokens + cont_result.output_tokens
            total_cost += cont_result.cost_usd
            continuation_count += 1
        
        return AIResult(
            content=full_content,
            model=result.model,
            input_tokens=total_tokens,
            output_tokens=total_tokens,  # Simplificado
            cost_usd=total_cost,
            finish_reason="STOP",
        )
```

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

| Fase | Modelo | Input (est.) | Output (est.) | Costo OpenRouter (est.) |
|------|--------|-------------|---------------|------------------------|
| Extracción ×3 PDFs | Gemini 2.5 Pro | ~450k | ~250k | ~$2.50-3.50 |
| Auditoría ×3 | Gemini 2.5 Pro | ~200k | ~50k | ~$0.50-1.00 |
| Secciones 🟢🟡 ×7 | Gemini 2.5 Pro | ~1M | ~56k | ~$2.00-3.00 |
| Secciones 🔴 ×4 | Claude 3.5 Sonnet | ~600k | ~32k | ~$2.00-3.00 |
| **TOTAL** | | | | **~$7-10 USD** |

> ⚠️ Precios de OpenRouter varían. Verificar en [openrouter.ai/models](https://openrouter.ai/models) al implementar.

---

## 🔄 Orquestador del Pipeline

```python
# backend/app/services/orchestrator.py

class PipelineOrchestrator:
    """
    Coordina el pipeline completo usando OpenRouter.
    """
    
    def __init__(
        self,
        openrouter: OpenRouterClient,
        prompt_engine: PromptEngine,
        db_session: AsyncSession,
        redis_queue: ArqQueue,
    ):
        self.ai = openrouter
        self.prompts = prompt_engine
        self.db = db_session
        self.queue = redis_queue
    
    async def extract_all(self, project_id: UUID) -> None:
        """Fase 1: Extraer todos los PDFs (Gemini vía OpenRouter)."""
        documents = await self._get_pending_documents(project_id)
        for doc in documents:
            await self.queue.enqueue_job(
                'extract_document',
                document_id=str(doc.id),
                _job_id=f"extract_{doc.id}"
            )
    
    async def generate_all_sections(self, project_id: UUID) -> None:
        """Fase 3: Generar las 11 secciones con el modelo óptimo."""
        for section_number in SECTION_CONFIGS.keys():
            config = SECTION_CONFIGS[section_number]
            model_id = OpenRouterClient.MODELS[config.motor]  # "google/gemini-2.5-pro" o "anthropic/claude-3.5-sonnet"
            
            await self.queue.enqueue_job(
                'generate_section',
                project_id=str(project_id),
                section_number=section_number,
                model_id=model_id,
                _job_id=f"gen_{project_id}_{section_number}"
            )
```

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
            # Extended thinking para Claude en secciones críticas
            extra_params["thinking"] = {"type": "enabled", "budget_tokens": 16000}
        
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

1. **Modelo correcto para cada sección**: Gemini para secciones descriptivas (más barato), Claude solo para las 4 secciones 🔴 que requieren razonamiento profundo
2. **Reutilizar el compendio generado**: Una vez publicado en S3 + Notion, no se re-genera a menos que cambien las fuentes
3. **Previsualización sin costo**: El visor público carga el .md desde S3 → cero costo de API
4. **Futuro**: Explorar modelos más baratos en OpenRouter para secciones 🟢 (ej. Gemini Flash, Claude Haiku)

---

> **Próximo documento:** [10_deployment.md](10_deployment.md)
