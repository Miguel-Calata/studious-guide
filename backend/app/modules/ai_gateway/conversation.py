"""
Acumulación real de mensajes entre llamadas al mismo hilo de generación.

Una Conversation es una lista ordenada de mensajes (system/user/assistant)
más una utilidad de estimación de tokens y guardia de overflow. Se usa como
estado de la sesión de generación del compendio: cada sección del
compendio se genera como una nueva instrucción user dentro de la misma
conversación, de modo que la información de secciones previas queda
disponible para el modelo sin reenviar el prompt completo.

El estado de la conversación es DERIVADO: se reconstruye a partir de lo
que ya persiste la base de datos (project.merged_content + sections
previamente completadas). Esto permite que workers separados (o retries
aislados) reconstruyan el hilo sin compartir memoria mutable.
"""

from __future__ import annotations

from dataclasses import dataclass, field

CONTINUATION_MARKERS = ("[CONTINÚA", "[Fin de la Parte")
TRUNCATION_FINISH_REASONS = {"length"}


def estimate_tokens(text: str) -> int:
    """
    Estimación conservadora de tokens. Aproximación chars/4, suficiente
    para guardias de overflow. Documentado como heurística; no reemplaza
    un tokenizador real (tiktoken, etc.).
    """
    if not text:
        return 0
    return max(1, len(text) // 4)


@dataclass(frozen=True)
class Message:
    role: str  # "system" | "user" | "assistant"
    content: str

    def to_api(self) -> dict:
        return {"role": self.role, "content": self.content}


@dataclass
class Conversation:
    """
    Hilo de mensajes acumulado para una sesión de generación.

    Uso:
        conv = Conversation.from_initial(system_prompt, merged_content)
        conv.add_user("instrucción sección 1")
        # ... call generate(messages=conv.to_api_messages())
        conv.add_assistant(ai_response)
        # Sección 2 hereda todo el contexto previo.
    """

    messages: list[Message] = field(default_factory=list)

    # --- Construcción -----------------------------------------------------

    @classmethod
    def from_initial(
        cls, system_prompt: str, source_block: str
    ) -> Conversation:
        """
        Mensaje inicial del hilo: instrucciones del sistema + bloque de
        fuentes documentales. Este mensaje se envía UNA sola vez al
        inicio de la conversación; las secciones posteriores añaden
        sólo su instrucción (sin reenviar la fuente).
        """
        combined = (
            system_prompt.strip()
            + "\n\n"
            + (source_block or "").strip()
        )
        return cls(messages=[Message("user", combined)])

    # --- Mutación --------------------------------------------------------

    def add_user(self, content: str) -> None:
        self.messages.append(Message("user", content))

    def add_assistant(self, content: str) -> None:
        self.messages.append(Message("assistant", content))

    def replace_last_assistant(self, content: str) -> None:
        """
        Reemplaza el último mensaje assistant. Útil para secciones que
        se regeneran: en lugar de acumular duplicados, sustituye.
        """
        for i in range(len(self.messages) - 1, -1, -1):
            if self.messages[i].role == "assistant":
                self.messages[i] = Message("assistant", content)
                return
        raise ValueError(
            "replace_last_assistant: no hay mensaje assistant previo"
        )

    # --- Serialización ---------------------------------------------------

    def to_api_messages(self) -> list[dict]:
        return [m.to_api() for m in self.messages]

    # --- Estimación y guardia -------------------------------------------

    def estimated_tokens(self) -> int:
        return sum(estimate_tokens(m.content) for m in self.messages)

    def check_overflow(
        self,
        model_context_window: int,
        reserved_for_output: int,
    ) -> None:
        """
        Garantiza que el hilo cabe en la ventana del modelo dejando
        espacio para el output. Falla explícitamente (NUNCA trunca
        silenciosamente) si se supera el límite.
        """
        used = self.estimated_tokens()
        available = model_context_window - reserved_for_output
        if used > available:
            raise ContextOverflowError(
                f"Hilo acumulado ({used} tokens estimados) supera el "
                f"límite disponible ({available}) para el modelo "
                f"con ventana {model_context_window} y output reservado "
                f"de {reserved_for_output}. No se truncarán mensajes "
                f"previos en silencio."
            )

    # --- Detección de continuación / truncamiento -----------------------

    @staticmethod
    def needs_continuation(content: str) -> bool:
        return any(marker in content for marker in CONTINUATION_MARKERS)

    @staticmethod
    def is_truncated(finish_reason: str) -> bool:
        return finish_reason in TRUNCATION_FINISH_REASONS


class ContextOverflowError(Exception):
    """El hilo acumulado supera la ventana del modelo."""


def build_continuation_message() -> Message:
    """Mensaje de continuación estándar (idioma del SYSTEM_PROMPT)."""
    return Message("user", "Continúa")
