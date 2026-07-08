import openai
from openai import AsyncOpenAI
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import settings
from app.modules.ai_gateway.interfaces import AIResult, AIGatewayClient


class OpenRouterClient(AIGatewayClient):
    MODELS = {
        "gemini": "google/gemini-2.5-pro",
        "claude": "anthropic/claude-3.5-sonnet",
    }

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
        prompt: str,
        model: str,
        temperature: float = 0.1,
        max_tokens: int = 65536,
        system_prompt: str | None = None,
        **kwargs,
    ) -> AIResult:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
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

    async def generate_with_continuations(
        self,
        prompt: str,
        model: str = "google/gemini-2.5-pro",
        temperature: float = 0.1,
        max_continuations: int = 10,
    ) -> AIResult:
        result = await self.generate(prompt, model, temperature)
        full_content = result.content
        total_input = result.input_tokens
        total_output = result.output_tokens
        total_cost = result.cost_usd
        continuation_count = 0

        while (
            "[CONTINÚA" in result.content or "[Fin de la Parte" in result.content
        ) and continuation_count < max_continuations:
            result = await self.generate("Continúa", model, temperature)
            full_content += "\n\n" + result.content
            total_input += result.input_tokens
            total_output += result.output_tokens
            total_cost += result.cost_usd
            continuation_count += 1

        return AIResult(
            content=full_content,
            model=result.model,
            input_tokens=total_input,
            output_tokens=total_output,
            cost_usd=total_cost,
            finish_reason="STOP",
        )


def get_ai_client() -> OpenRouterClient:
    return OpenRouterClient()
