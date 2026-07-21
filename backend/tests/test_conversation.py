"""
Tests de la Tarea 1 — Conversation, continuaciones reales, guardia de
overflow, extra_params.thinking y orquestador secuencial.

Estos tests verifican el comportamiento REAL del mecanismo de
continuidad de contexto y NO el código legacy de
generate_with_continuations.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.ai_gateway.conversation import (
    ContextOverflowError,
    Conversation,
    estimate_tokens,
)
from app.services.orchestrator import (
    COGENERATION_PAIRS,
    _build_extra_params,
    _infer_motor_from_model,
    _resolve_motor_for_section,
)

# ── Conversation / mensajes ──────────────────────────────────────────


def test_estimate_tokens_simple():
    assert estimate_tokens("") == 0
    assert estimate_tokens("a" * 7) == 2  # 7*2//7 = 2
    assert estimate_tokens("a" * 350) == 100  # 350*2//7 = 100
    assert estimate_tokens("a" * 351) >= 100


def test_conversation_from_initial():
    conv = Conversation.from_initial(
        system_prompt="[SYS] SAM v9",
        source_block="# Fuentes\nContenido...",
    )
    assert len(conv.messages) == 1
    assert conv.messages[0].role == "user"
    assert "[SYS] SAM v9" in conv.messages[0].content
    assert "# Fuentes" in conv.messages[0].content


def test_conversation_add_messages():
    conv = Conversation()
    conv.add_user("primera instrucción")
    conv.add_assistant("primera respuesta")
    conv.add_user("segunda instrucción")
    assert [m.role for m in conv.messages] == [
        "user",
        "assistant",
        "user",
    ]


def test_conversation_replace_last_assistant():
    conv = Conversation()
    conv.add_user("inst")
    conv.add_assistant("primera")
    conv.add_user("inst 2")
    conv.add_assistant("segunda")
    conv.replace_last_assistant("segunda CORREGIDA")
    assert conv.messages[-1].content == "segunda CORREGIDA"


def test_conversation_to_api_messages_format():
    conv = Conversation()
    conv.add_user("hola")
    conv.add_assistant("mundo")
    api_msgs = conv.to_api_messages()
    assert api_msgs == [
        {"role": "user", "content": "hola"},
        {"role": "assistant", "content": "mundo"},
    ]


def test_conversation_needs_continuation_detection():
    assert Conversation.needs_continuation("fin [CONTINÚA]") is True
    assert (
        Conversation.needs_continuation("fin [Fin de la Parte 2]") is True
    )
    assert Conversation.needs_continuation("fin sin marcador") is False


def test_conversation_is_truncated():
    assert Conversation.is_truncated("length") is True
    assert Conversation.is_truncated("stop") is False
    assert Conversation.is_truncated("unknown") is False


# ── Guardia de overflow ──────────────────────────────────────────────


def test_check_overflow_raises_when_over_limit():
    conv = Conversation()
    big = "x" * 100_000
    conv.add_user(big)
    with pytest.raises(ContextOverflowError):
        conv.check_overflow(
            model_context_window=10_000,
            reserved_for_output=2_000,
        )


def test_check_overflow_passes_when_within_limit():
    conv = Conversation()
    conv.add_user("hola")
    conv.check_overflow(
        model_context_window=1_000_000,
        reserved_for_output=8_192,
    )


def test_check_overflow_explicit_no_silent_truncation():
    """
    La garantía clave: NUNCA se truncan mensajes previos en silencio.
    El error debe ser explícito y mencionar que no se truncará.
    """
    conv = Conversation()
    # Hilo denso que fuerza el overflow con ventana pequeña
    big = "x" * 8000  # ~2000 tokens
    conv.add_user(big)
    conv.add_assistant(big)
    conv.add_user(big)
    with pytest.raises(ContextOverflowError) as exc:
        conv.check_overflow(
            model_context_window=1_000,
            reserved_for_output=200,
        )
    assert "truncar" in str(exc.value).lower()


# ── Continuaciones reales (regression del bug) ──────────────────────


@pytest.mark.asyncio
async def test_continuation_carries_full_message_history():
    """
    Regresión: el bug original de
    `generate_with_continuations` era que la segunda llamada recibía
    solo "Continúa" sin el prompt original. Este test verifica que la
    NUEVA implementación envía el historial COMPLETO de mensajes en
    cada llamada de continuación.
    """
    from app.modules.ai_gateway.openrouter_client import OpenRouterClient

    client = OpenRouterClient(api_key="test-key", base_url="http://test")

    captured_calls: list[list[dict]] = []

    async def fake_create(*args, **kwargs):
        # Capturamos los mensajes enviados en cada llamada
        captured_calls.append(kwargs.get("messages") or [])
        # Primera respuesta: marcador de continuación
        # Segunda: respuesta final sin marcador
        if len(captured_calls) == 1:
            resp = MagicMock()
            resp.model = "google/gemini-3.1-pro-preview"
            resp.cost = 0.05
            choice = MagicMock()
            choice.message.content = "Parte 1 [CONTINÚA — falta más]"
            choice.finish_reason = "stop"
            resp.choices = [choice]
            usage = MagicMock()
            usage.prompt_tokens = 100
            usage.completion_tokens = 50
            resp.usage = usage
            return resp
        else:
            resp = MagicMock()
            resp.model = "google/gemini-3.1-pro-preview"
            resp.cost = 0.05
            choice = MagicMock()
            choice.message.content = "Parte 2 final."
            choice.finish_reason = "stop"
            resp.choices = [choice]
            usage = MagicMock()
            usage.prompt_tokens = 200
            usage.completion_tokens = 80
            resp.usage = usage
            return resp

    with patch.object(
        client.client.chat.completions,
        "create",
        new_callable=AsyncMock,
        side_effect=fake_create,
    ):
        await client.generate_with_continuations(
            prompt="Prompt inicial largo del compendio",
            model="google/gemini-3.1-pro-preview",
        )

    assert len(captured_calls) == 2

    # Primera llamada: solo el prompt del usuario
    assert len(captured_calls[0]) == 1
    assert captured_calls[0][0]["role"] == "user"
    assert "Prompt inicial largo" in captured_calls[0][0]["content"]

    # Segunda llamada: historial COMPLETO (user prompt + assistant
    # parte 1 + user "Continúa"). ESTO es lo que fallaba antes.
    assert len(captured_calls[1]) == 3
    assert captured_calls[1][0]["role"] == "user"
    assert "Prompt inicial largo" in captured_calls[1][0]["content"]
    assert captured_calls[1][1]["role"] == "assistant"
    assert "Parte 1" in captured_calls[1][1]["content"]
    assert captured_calls[1][2]["role"] == "user"
    assert captured_calls[1][2]["content"] == "Continúa"


@pytest.mark.asyncio
async def test_continuation_preserves_long_source_through_8_to_11():
    """
    Aceptación Tarea 1: fuente larga + secciones 8-11 sin
    truncamiento silencioso de mensajes previos. Simula un hilo
    acumulado de 7 secciones completadas y verifica que la 8ª
    llamada (primera del rango 8-11) incluye los mensajes
    acumulados de las secciones previas.
    """
    from app.modules.ai_gateway.openrouter_client import OpenRouterClient

    client = OpenRouterClient(api_key="test-key", base_url="http://test")

    long_source = "FUENTE_LARGA " * 5000  # ~30k chars ~ 7.5k tokens
    captured_msgs: list[list[dict]] = []

    async def fake_create(*args, **kwargs):
        msgs = kwargs.get("messages") or []
        captured_msgs.append(msgs)
        resp = MagicMock()
        resp.model = "google/gemini-3.1-pro-preview"
        resp.cost = 0.0
        choice = MagicMock()
        choice.message.content = "ok"
        choice.finish_reason = "stop"
        resp.choices = [choice]
        usage = MagicMock()
        usage.prompt_tokens = sum(len(m["content"]) // 4 for m in msgs)
        usage.completion_tokens = 10
        resp.usage = usage
        return resp

    with patch.object(
        client.client.chat.completions,
        "create",
        new_callable=AsyncMock,
        side_effect=fake_create,
    ):
        # Construir hilo equivalente a secciones 1-7 ya generadas
        conv = Conversation.from_initial(
            system_prompt="[SYS]", source_block=long_source
        )
        for n in range(1, 8):
            conv.add_user(f"instrucción sección {n}")
            conv.add_assistant(f"contenido sección {n} " * 100)

        # Ahora ejecutar sección 8
        await client.generate_in_conversation(
            conversation=conv,
            user_message="instrucción sección 8",
            model="google/gemini-3.1-pro-preview",
            max_tokens=8192,
        )

    # La llamada a la API debe llevar TODO el historial acumulado
    sent = captured_msgs[0]
    assert len(sent) == 1 + (7 * 2) + 1  # init + 7×(user+assistant) + sección 8
    assert "FUENTE_LARGA" in sent[0]["content"]
    for n in range(1, 8):
        idx = 1 + (n - 1) * 2
        assert f"instrucción sección {n}" in sent[idx]["content"]
        assert f"contenido sección {n}" in sent[idx + 1]["content"]
    assert "instrucción sección 8" in sent[-1]["content"]


@pytest.mark.asyncio
async def test_continuation_truncation_raises_loudly():
    """
    Si el modelo se trunca repetidamente (finish_reason='length')
    y se agotan las continuaciones, NO se devuelve el contenido
    truncado en silencio: debe lanzar excepción.
    """
    from app.modules.ai_gateway.openrouter_client import (
        ContinuationExhaustedError,
        OpenRouterClient,
    )

    client = OpenRouterClient(api_key="test-key", base_url="http://test")

    async def always_truncated(*args, **kwargs):
        resp = MagicMock()
        resp.model = "x"
        resp.cost = 0
        choice = MagicMock()
        choice.message.content = "fragmento"
        choice.finish_reason = "length"  # SIEMPRE truncado
        resp.choices = [choice]
        usage = MagicMock()
        usage.prompt_tokens = 10
        usage.completion_tokens = 5
        resp.usage = usage
        return resp

    with patch.object(
        client.client.chat.completions,
        "create",
        new_callable=AsyncMock,
        side_effect=always_truncated,
    ):
        conv = Conversation()
        conv.add_user("x")
        with pytest.raises(ContinuationExhaustedError, match="truncado"):
            await client.generate_in_conversation(
                conversation=conv,
                user_message="",
                model="x",
                max_tokens=10,
                max_continuations=2,
            )


# ── Resolución de motor (Tarea 5 + preparativos Tarea 1) ────────────


def test_resolve_motor_default_uses_config():
    from app.modules.prompts.section_builder import SECTION_CONFIGS

    motor = _resolve_motor_for_section(1, {}, prior_pair_motor=None)
    assert motor == SECTION_CONFIGS[1].motor


def test_resolve_motor_pair_inherits_anchor():
    # Sección 5 (parte del par 4-5) hereda el motor del ancla (4)
    motor = _resolve_motor_for_section(
        5, {}, prior_pair_motor="claude"
    )
    assert motor == "claude"
    # Si no hay ancla todavía, usa el config
    motor = _resolve_motor_for_section(5, {}, prior_pair_motor=None)
    assert motor == "claude"  # SECTION_CONFIGS[5].motor == "claude"


def test_cogeneration_pairs_constant():
    assert COGENERATION_PAIRS[5] == 4


def test_infer_motor_from_model_id():
    assert _infer_motor_from_model("anthropic/claude-sonnet-5") == "claude"
    assert _infer_motor_from_model("google/gemini-3.1-pro") == "gemini"
    assert _infer_motor_from_model("") == "gemini"


# ── extra_params.thinking (Tarea 1 — implementación real) ──────────


def test_extra_params_thinking_for_claude_red():
    params = _build_extra_params("claude", 3, "anthropic/claude-sonnet-5")
    assert "reasoning" in params
    assert params["reasoning"]["enabled"] is True
    assert params["reasoning"]["max_tokens"] == 16000


def test_extra_params_no_thinking_for_gemini():
    assert _build_extra_params("gemini", 3, "google/gemini-3.1-pro-preview") == {}


def test_extra_params_no_thinking_for_claude_non_red():
    # Sección 4 es 🟢 para claude-mapped... espera, sección 4 es gemini.
    # Verificamos una sección 🟢: sección 1 (epidemiología)
    assert _build_extra_params("claude", 1, "anthropic/claude-sonnet-5") == {}


def test_extra_params_no_thinking_when_model_not_claude():
    # Motor claude pero modelo Gemini → no reasoning
    assert _build_extra_params("claude", 3, "google/gemini-3.1-pro-preview") == {}


def test_extra_params_thinking_all_red_sections():
    for n in (3, 5, 8, 9):
        params = _build_extra_params("claude", n, "anthropic/claude-sonnet-5")
        assert params.get("reasoning", {}).get("enabled") is True
