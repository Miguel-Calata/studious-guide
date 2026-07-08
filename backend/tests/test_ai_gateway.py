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
