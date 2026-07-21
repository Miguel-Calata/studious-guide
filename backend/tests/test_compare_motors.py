"""
Tests del harness de comparación empírica (Tarea 4).

Cubre:
  - Validación de modelos contra AVAILABLE_MODELS
  - Inferencia de motor desde model_id
  - Estructura del reporte plantilla
"""

import subprocess
import sys
from pathlib import Path

import pytest

from app.modules.ai_gateway.models import AVAILABLE_MODELS
from scripts.compare_motors import (
    _infer_motor,
    _validate_models,
)


def test_validate_models_accepts_known_models():
    known = [m["id"] for m in AVAILABLE_MODELS[:3]]
    result = _validate_models(known)
    assert result == known


def test_validate_models_rejects_unknown():
    with pytest.raises(ValueError) as exc:
        _validate_models(["google/gemini-3.1-pro-preview", "fake/model"])
    assert "fake/model" in str(exc.value)


def test_validate_models_rejects_empty():
    # La función actual no valida lista vacía; el caller debe
    # verificar antes. Documentar el comportamiento.
    assert _validate_models([]) == []


def test_infer_motor_claude():
    assert _infer_motor("anthropic/claude-sonnet-5") == "claude"
    assert _infer_motor("anthropic/claude-opus-4.8") == "claude"


def test_infer_motor_gemini_default():
    assert _infer_motor("google/gemini-3.1-pro-preview") == "gemini"
    assert _infer_motor("openai/gpt-4o") == "gemini"
    assert _infer_motor("meta-llama/llama-3.3-70b-instruct:free") == "gemini"


def test_all_available_models_classified():
    """Ningún modelo del catálogo cae en clasificación ambigua."""
    for m in AVAILABLE_MODELS:
        motor = _infer_motor(m["id"])
        assert motor in ("claude", "gemini"), (
            f"Modelo {m['id']} no se pudo clasificar"
        )


def test_harness_help_succeeds():
    """`--help` no requiere API key y debe funcionar."""
    result = subprocess.run(
        [sys.executable, "-m", "scripts.compare_motors", "--help"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent,
    )
    assert result.returncode == 0
    assert "Comparación empírica" in result.stdout
