"""
Modelo de contexto de tokens por modelo soportado en OpenRouter.

Usado por la guardia de overflow del hilo acumulado de conversación.
Los valores son ventanas aproximadas de input del proveedor; cuando
OpenRouter o el modelo las cambien, ajustar aquí.
"""

from app.modules.ai_gateway.models import AVAILABLE_MODELS


def _default_window_for(model_id: str) -> int:
    mid = (model_id or "").lower()
    if "gemini" in mid:
        return 1_000_000
    if "claude" in mid:
        return 200_000
    if "gpt-5" in mid:
        return 400_000
    if "gpt-4o" in mid:
        return 128_000
    if "qwen" in mid:
        return 128_000
    if "llama" in mid:
        return 128_000
    if "mistral" in mid:
        return 64_000
    if "deepseek" in mid:
        return 128_000
    if "grok" in mid:
        return 256_000
    return 128_000


def get_context_window(model_id: str) -> int:
    """
    Ventana de contexto del modelo. Si el id aparece en AVAILABLE_MODELS,
    usa la heurística de su familia; en otro caso devuelve 128k por
    defecto. Documentar el ajuste manual aquí cuando un proveedor
    cambie su ventana.
    """
    if any(m["id"] == model_id for m in AVAILABLE_MODELS):
        return _default_window_for(model_id)
    return _default_window_for(model_id)
