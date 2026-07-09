from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.modules.ai_gateway.models import DEFAULT_EXTRACTION_MODEL


@dataclass
class AIResult:
    content: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    finish_reason: str


class AIGatewayClient(ABC):
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        model: str,
        temperature: float = 0.1,
        max_tokens: int = 65536,
        system_prompt: str | None = None,
        **kwargs,
    ) -> AIResult: ...

    @abstractmethod
    async def generate_with_continuations(
        self,
        prompt: str,
        model: str | None = None,
        temperature: float = 0.1,
        max_continuations: int = 10,
    ) -> AIResult: ...
