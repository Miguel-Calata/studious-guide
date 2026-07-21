import openai
from openai import AsyncOpenAI
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import settings
from app.modules.ai_gateway.context_windows import get_context_window
from app.modules.ai_gateway.conversation import (
    Conversation,
    Message,
    build_continuation_message,
)
from app.modules.ai_gateway.interfaces import AIGatewayClient, AIResult
from app.modules.ai_gateway.models import AVAILABLE_MODELS, DEFAULT_EXTRACTION_MODEL


class OpenRouterClient(AIGatewayClient):
    AVAILABLE_MODELS = AVAILABLE_MODELS

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self.client = AsyncOpenAI(
            api_key=api_key or settings.openrouter_api_key,
            base_url=base_url or settings.openrouter_base_url,
            default_headers={
                "HTTP-Referer": "https://sam-platform.app",
                "X-Title": "SAM Platform",
            },
        )

    @retry(
        retry=retry_if_exception_type(openai.RateLimitError),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        stop=stop_after_attempt(3),
        reraise=True,
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

        - Si se pasa `messages`, se usan directamente (recomendado para
          Conversation: historial completo de la sesión).
        - Si se pasa `prompt`, se construye un único turno user.
          `system_prompt` opcional se antepone.
        - `**kwargs` se envían como `extra_body` (ej. `reasoning`,
          `models` para fallbacks, etc.).
        """
        if messages is None:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
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
        cost_usd = response.cost if hasattr(response, "cost") else 0.0

        return AIResult(
            content=choice.message.content or "",
            model=response.model,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            cost_usd=cost_usd,
            finish_reason=choice.finish_reason or "unknown",
        )

    async def generate_in_conversation(
        self,
        conversation: Conversation,
        user_message: str,
        *,
        model: str,
        temperature: float = 0.1,
        max_tokens: int = 65536,
        system_prompt: str | None = None,
        max_continuations: int = 10,
        **kwargs,
    ) -> AIResult:
        """
        Inyecta `user_message` en la conversación, ejecuta, gestiona
        continuaciones ([CONTINÚA] o truncamiento) acumulando los
        mensajes assistant resultantes, y devuelve el contenido
        consolidado con tokens/costo agregados.

        Guardia de overflow: ANTES de la primera llamada se valida que
        la conversación acumulada + output reservado quepan en la
        ventana del modelo. Falla explícitamente — NUNCA trunca.
        """
        if user_message:
            conversation.add_user(user_message)
        if system_prompt and (
            not conversation.messages
            or conversation.messages[0].role != "system"
        ):
            conversation.messages.insert(0, Message("system", system_prompt))

        window = get_context_window(model)
        conversation.check_overflow(
            model_context_window=window,
            reserved_for_output=max_tokens,
        )

        messages = conversation.to_api_messages()
        result = await self.generate(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
        conversation.add_assistant(result.content)
        full_content = result.content
        total_input = result.input_tokens
        total_output = result.output_tokens
        total_cost = result.cost_usd
        continuation_count = 0
        last_finish = result.finish_reason

        while (
            Conversation.needs_continuation(result.content)
            or Conversation.is_truncated(result.finish_reason)
        ) and continuation_count < max_continuations:
            conversation.add_user(build_continuation_message().content)
            conversation.check_overflow(
                model_context_window=window,
                reserved_for_output=max_tokens,
            )
            result = await self.generate(
                messages=conversation.to_api_messages(),
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
            conversation.add_assistant(result.content)
            full_content += "\n\n" + result.content
            total_input += result.input_tokens
            total_output += result.output_tokens
            total_cost += result.cost_usd
            continuation_count += 1
            last_finish = result.finish_reason

        # Garantía Tarea 1: NUNCA devolver contenido truncado en
        # silencio. Si tras agotar continuaciones la respuesta sigue
        # truncada, fallar explícitamente.
        if Conversation.is_truncated(last_finish):
            raise ContinuationExhaustedError(
                f"Continuaciones agotadas ({continuation_count}) sin "
                f"obtener respuesta completa. finish_reason final: "
                f"{last_finish}. No se devolverá contenido truncado."
            )

        return AIResult(
            content=full_content,
            model=result.model,
            input_tokens=total_input,
            output_tokens=total_output,
            cost_usd=total_cost,
            finish_reason=last_finish,
        )

    async def generate_with_continuations(
        self,
        prompt: str,
        model: str | None = None,
        temperature: float = 0.1,
        max_continuations: int = 10,
    ) -> AIResult:
        """
        API legacy para extracciones: un único prompt, continuación
        loop sin estado persistente (la conversación es efímera).
        """
        resolved_model = model or DEFAULT_EXTRACTION_MODEL
        conv = Conversation()
        conv.add_user(prompt)
        return await self.generate_in_conversation(
            conversation=conv,
            user_message="",  # ya está dentro
            model=resolved_model,
            temperature=temperature,
            max_continuations=max_continuations,
        )


class ContinuationExhaustedError(Exception):
    """El modelo devolvió finish_reason='length' en todas las
    continuaciones posibles; se rehusa devolver contenido truncado."""


def get_ai_client() -> OpenRouterClient:
    return OpenRouterClient()
