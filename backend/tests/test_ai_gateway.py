from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.ai_gateway.interfaces import AIResult
from app.modules.ai_gateway.openrouter_client import OpenRouterClient


def _make_response(content: str, model: str = "google/gemini-2.5-pro"):
    response = MagicMock()
    response.model = model
    response.cost = 0.05

    choice = MagicMock()
    choice.message.content = content
    choice.finish_reason = "stop"
    response.choices = [choice]

    usage = MagicMock()
    usage.prompt_tokens = 1000
    usage.completion_tokens = 500
    response.usage = usage

    return response


def _make_continuation_response():
    return _make_response("Some content [CONTINÚA — Pendiente desde: ...]")


def _make_final_response():
    return _make_response("Final content without continuation marker.")


@pytest.mark.asyncio
async def test_generate_returns_airesult():
    client = OpenRouterClient(api_key="test-key", base_url="http://test")

    with patch.object(
        client.client.chat.completions, "create", new_callable=AsyncMock
    ) as mock_create:
        mock_create.return_value = _make_response("Hello from OpenRouter")

        result = await client.generate(
            prompt="Test prompt",
            model="google/gemini-2.5-pro",
        )

        assert isinstance(result, AIResult)
        assert result.content == "Hello from OpenRouter"
        assert result.model == "google/gemini-2.5-pro"
        assert result.input_tokens == 1000
        assert result.output_tokens == 500
        assert result.cost_usd == 0.05
        assert result.finish_reason == "stop"


@pytest.mark.asyncio
async def test_generate_with_continuations_concatenates():
    client = OpenRouterClient(api_key="test-key", base_url="http://test")

    with patch.object(
        client.client.chat.completions, "create", new_callable=AsyncMock
    ) as mock_create:
        mock_create.side_effect = [
            _make_continuation_response(),
            _make_final_response(),
        ]

        result = await client.generate_with_continuations(
            prompt="Test prompt",
            model="google/gemini-2.5-pro",
        )

    assert mock_create.call_count == 2
    assert "Some content [CONTINÚA" in result.content
    assert "Final content without continuation marker." in result.content
    assert result.input_tokens == 2000
    assert result.output_tokens == 1000
    assert result.cost_usd == 0.10


@pytest.mark.asyncio
async def test_continuation_call_carries_full_message_history():
    """
    Regresión Tarea 1: la segunda llamada de continuación DEBE
    incluir el historial completo de mensajes, no solo "Continúa".
    """
    client = OpenRouterClient(api_key="test-key", base_url="http://test")

    captured_calls: list[list[dict]] = []

    async def fake_create(*args, **kwargs):
        captured_calls.append(kwargs.get("messages") or [])
        if len(captured_calls) == 1:
            return _make_continuation_response()
        return _make_final_response()

    with patch.object(
        client.client.chat.completions,
        "create",
        new_callable=AsyncMock,
        side_effect=fake_create,
    ):
        await client.generate_with_continuations(
            prompt="Prompt inicial largo con datos clínicos importantes",
            model="google/gemini-2.5-pro",
        )

    assert len(captured_calls) == 2
    # Segunda llamada: 3 mensajes (user inicial + assistant 1 + user Continúa)
    assert len(captured_calls[1]) == 3
    assert captured_calls[1][0]["role"] == "user"
    assert "Prompt inicial" in captured_calls[1][0]["content"]
    assert captured_calls[1][1]["role"] == "assistant"
    assert "Some content" in captured_calls[1][1]["content"]
    assert captured_calls[1][2]["role"] == "user"
    assert captured_calls[1][2]["content"] == "Continúa"


@pytest.mark.asyncio
async def test_truncation_exhaustion_raises_loudly():
    """
    Tarea 1: si el modelo devuelve finish_reason='length' en
    TODAS las continuaciones posibles, se rehúsa devolver
    contenido truncado en silencio.
    """
    from app.modules.ai_gateway.openrouter_client import (
        ContinuationExhaustedError,
    )

    client = OpenRouterClient(api_key="test-key", base_url="http://test")

    def always_truncated_response(*args, **kwargs):
        resp = _make_response("fragmento")
        resp.choices[0].finish_reason = "length"
        return resp

    with patch.object(
        client.client.chat.completions,
        "create",
        new_callable=AsyncMock,
        side_effect=always_truncated_response,
    ), pytest.raises(ContinuationExhaustedError):
        await client.generate_with_continuations(
            prompt="x",
            model="google/gemini-2.5-pro",
            max_continuations=2,
        )


@pytest.mark.asyncio
async def test_generate_in_conversation_appends_to_history():
    """
    Tarea 1: el método `generate_in_conversation` acumula los
    mensajes assistant en la conversación tras cada llamada,
    permitiendo que la siguiente llamada herede el contexto.
    """
    from app.modules.ai_gateway.conversation import Conversation

    client = OpenRouterClient(api_key="test-key", base_url="http://test")
    conv = Conversation()
    conv.add_user("primera pregunta")

    call_count = 0

    async def fake_create(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _make_continuation_response()
        return _make_final_response()

    with patch.object(
        client.client.chat.completions,
        "create",
        new_callable=AsyncMock,
        side_effect=fake_create,
    ):
        await client.generate_in_conversation(
            conversation=conv,
            user_message="",  # ya está en conv
            model="google/gemini-2.5-pro",
            max_continuations=5,
        )

    # La conversación DEBE tener el historial completo
    assert len(conv.messages) == 4  # user1 + assistant1 + user2(Continúa) + assistant2
    assert conv.messages[0].role == "user"
    assert conv.messages[1].role == "assistant"
    assert "Some content" in conv.messages[1].content
    assert conv.messages[2].role == "user"
    assert conv.messages[2].content == "Continúa"
    assert conv.messages[3].role == "assistant"
