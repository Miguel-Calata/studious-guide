from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.modules.ai_gateway.conversation import Conversation


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
        prompt: str | None = None,
        *,
        model: str,
        temperature: float = 0.1,
        max_tokens: int = 65536,
        system_prompt: str | None = None,
        messages: list[dict] | None = None,
        **kwargs,
    ) -> AIResult: ...

    @abstractmethod
    async def generate_in_conversation(
        self,
        conversation: "Conversation",
        user_message: str,
        *,
        model: str,
        temperature: float = 0.1,
        max_tokens: int = 65536,
        system_prompt: str | None = None,
        max_continuations: int = 10,
        **kwargs,
    ) -> AIResult:
        """Anexa user_message a la conversación, ejecuta (con
        continuaciones automáticas si el modelo marca [CONTINÚA] o el
        output se trunca), acumula las respuestas del asistente de
        vuelta en la conversación y devuelve el resultado consolidado.
        """
        ...

    @abstractmethod
    async def generate_with_continuations(
        self,
        prompt: str,
        model: str | None = None,
        temperature: float = 0.1,
        max_continuations: int = 10,
    ) -> AIResult:
        """API legacy: prompt único + bucle de continuación.
        Internamente construye una Conversation, llama a
        generate_in_conversation y descarta la conversación resultante.
        Se conserva para extracciones (un solo documento, un solo hilo
        efímero).
        """
        ...
