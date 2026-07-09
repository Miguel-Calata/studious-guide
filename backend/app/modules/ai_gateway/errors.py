import openai


def format_ai_error(exc: Exception) -> str:
    """Map OpenAI / OpenRouter exceptions to user-friendly Spanish messages."""

    if isinstance(exc, openai.AuthenticationError):
        return (
            "API key de OpenRouter inválida o ausente. "
            "Verifica OPENROUTER_API_KEY en la configuración."
        )

    if isinstance(exc, openai.PermissionDeniedError):
        return (
            "Permiso denegado por OpenRouter. "
            "Tu cuenta no tiene acceso al modelo solicitado."
        )

    if isinstance(exc, openai.RateLimitError):
        return (
            "Límite de velocidad alcanzado en OpenRouter. "
            "Espera unos minutos e intenta de nuevo."
        )

    if isinstance(exc, openai.APIStatusError):
        status = getattr(exc, "status_code", None)
        body = str(getattr(exc, "message", "")) or str(exc)

        if status == 402:
            return (
                "Créditos insuficientes en OpenRouter. "
                "Recarga créditos en openrouter.ai o reduce max_tokens."
            )
        if status == 429:
            return (
                "Límite de velocidad alcanzado en OpenRouter. "
                "Espera unos minutos e intenta de nuevo."
            )
        if status and status >= 500:
            return f"Error del servidor de OpenRouter (HTTP {status}). Intenta más tarde."

        return f"Error de OpenRouter (HTTP {status}): {body[:300]}"

    if isinstance(exc, openai.APIConnectionError):
        return "No se pudo conectar con OpenRouter. Verifica tu conexión a internet."

    if isinstance(exc, openai.APITimeoutError):
        return "OpenRouter tardó demasiado en responder. Intenta de nuevo."

    raw = str(exc)
    if len(raw) > 500:
        raw = raw[:500] + "…"
    return raw or "Error desconocido al llamar a OpenRouter."
