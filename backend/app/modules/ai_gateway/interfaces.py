from abc import ABC, abstractmethod
from dataclasses import dataclass


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
        model: str = "google/gemini-2.5-pro",
        temperature: float = 0.1,
        max_continuations: int = 10,
    ) -> AIResult: ...
