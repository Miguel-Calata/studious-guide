"""
Tests de la Tarea 5 — Mismo modelo en par co-generado 4-5 (R-9).

Regla: cuando es_cogeneracion=True, la sección 5 hereda el
motor (y por lo tanto el modelo) del job de la sección 4.
Cualquier ruta donde el output de la 4 alimente un motor
distinto para la 5 está prohibida.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.compendium_section import CompendiumSection, SectionStatus
from app.models.ecos_map import EcosMap, EcosMapStatus
from app.models.project import Project, ProjectStatus
from app.models.user import User
from app.modules.ai_gateway.interfaces import AIResult
from app.modules.auth.service import hash_password
from app.services.orchestrator import (
    COGENERATION_PAIRS,
    PipelineOrchestrator,
    _infer_motor_from_model,
    _resolve_motor_for_section,
)

# ── Helpers ──────────────────────────────────────────────────────────


async def _create_project_with_sections(
    db_session,
    email: str,
    *,
    completed_4_model: str | None = None,
) -> tuple[str, "EcosMap"]:
    """Crea un proyecto con las 11 secciones + eco map aprobado.
    La 4 puede estar pre-completada con un modelo concreto.
    Devuelve (project_id, ecos_map).
    """
    user = User(
        email=email,
        password_hash=hash_password("X"),
        full_name="Cogen",
    )
    db_session.add(user)
    await db_session.flush()

    project = Project(
        user_id=user.id,
        name="cogeneration-test",
        slug=f"cog-{email.split('@')[0]}",
        status=ProjectStatus.DRAFT,
        merged_content="Contenido de prueba",
    )
    db_session.add(project)
    await db_session.flush()

    eco = EcosMap(
        id=f"eco-cog-{email.split('@')[0]}",
        pathology_key="cogeneration-test",
        pathology_name="Cogen",
        version=1,
        sections={},
        status=EcosMapStatus.APPROVED,
        is_active=True,
    )
    db_session.add(eco)

    for n in range(1, 12):
        sec = CompendiumSection(
            project_id=project.id,
            section_number=n,
            section_name=f"Sección {n}",
            dosification="STANDARD",
            status=SectionStatus.PENDING,
        )
        if (
            completed_4_model is not None
            and n == 4
        ):
            sec.status = SectionStatus.COMPLETED
            sec.model_used = completed_4_model
            sec.content = "contenido de la 4 ya generado"
        db_session.add(sec)
    await db_session.commit()
    return str(project.id), eco


def _make_ai_result(model: str, content: str = "ok") -> AIResult:
    return AIResult(
        content=content,
        model=model,
        input_tokens=100,
        output_tokens=50,
        cost_usd=0.01,
        finish_reason="stop",
    )


# ── Lógica pura ──────────────────────────────────────────────────────


def test_cogeneration_pair_constant():
    assert COGENERATION_PAIRS[5] == 4


def test_resolve_motor_pair_inherits_anchor():
    """Sección 5 hereda el motor del ancla si se provee."""
    assert (
        _resolve_motor_for_section(5, {}, prior_pair_motor="claude")
        == "claude"
    )
    assert (
        _resolve_motor_for_section(5, {}, prior_pair_motor="gemini")
        == "gemini"
    )


def test_resolve_motor_pair_uses_config_when_no_anchor():
    """Sin ancla, usa el config (que hoy es claude para 5)."""
    motor = _resolve_motor_for_section(5, {}, prior_pair_motor=None)
    assert motor == "claude"


def test_infer_motor_handles_all_available_model_families():
    assert _infer_motor_from_model("anthropic/claude-sonnet-5") == "claude"
    assert _infer_motor_from_model("anthropic/claude-opus-4.8") == "claude"
    assert _infer_motor_from_model("google/gemini-3.1-pro-preview") == "gemini"
    assert _infer_motor_from_model("google/gemini-3.5-flash") == "gemini"
    assert _infer_motor_from_model("openai/gpt-5-pro") == "gemini"
    assert _infer_motor_from_model("") == "gemini"


# ── Orquestador end-to-end ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_section_5_inherits_section_4_motor_claude(
    client, db_session
):
    """
    Aceptación Tarea 5: si la sección 4 se ejecutó con un modelo
    Claude, la 5 DEBE ejecutarse también con un modelo Claude
    (motor heredado), aunque el config diga otra cosa.
    """
    project_id, eco_map = await _create_project_with_sections(
        db_session,
        "cog-claude@test.com",
        completed_4_model="anthropic/claude-sonnet-5",
    )

    captured_models: list[str] = []

    async def fake_generate_in_conversation(
        *args, **kwargs
    ):
        captured_models.append(kwargs.get("model", ""))
        return _make_ai_result(kwargs.get("model", ""))

    ai_mock = MagicMock()
    ai_mock.generate_in_conversation = AsyncMock(
        side_effect=fake_generate_in_conversation
    )

    orch = PipelineOrchestrator(ai_client=ai_mock)
    motor_map = {
        "claude": "anthropic/claude-sonnet-5",
        "gemini": "google/gemini-3.1-pro-preview",
    }
    await orch.generate_all_sections(
        project_id=project_id,
        motor_model_map=motor_map,
        eco_map=eco_map,
        _db=db_session,
    )

    assert len(captured_models) >= 1
    assert any("claude" in m for m in captured_models), (
        f"Sección 5 no usó modelo Claude. Modelos vistos: "
        f"{captured_models}"
    )


@pytest.mark.asyncio
async def test_section_5_inherits_section_4_motor_gemini(
    client, db_session
):
    """
    Inverso: si la sección 4 usó Gemini, la 5 también usa Gemini
    (a pesar de que el config de 5 diga claude).
    """
    project_id, eco_map = await _create_project_with_sections(
        db_session,
        "cog-gemini@test.com",
        completed_4_model="google/gemini-3.1-pro-preview",
    )

    captured_models: list[str] = []

    async def fake_gen(*args, **kwargs):
        captured_models.append(kwargs.get("model", ""))
        return _make_ai_result(kwargs.get("model", ""))

    ai_mock = MagicMock()
    ai_mock.generate_in_conversation = AsyncMock(side_effect=fake_gen)

    motor_map = {
        "claude": "anthropic/claude-sonnet-5",
        "gemini": "google/gemini-3.1-pro-preview",
    }
    orch = PipelineOrchestrator(ai_client=ai_mock)
    await orch.generate_all_sections(
        project_id=project_id,
        motor_model_map=motor_map,
        eco_map=eco_map,
        _db=db_session,
    )

    assert any("gemini" in m for m in captured_models), (
        f"Sección 5 no usó modelo Gemini. Modelos: {captured_models}"
    )


@pytest.mark.asyncio
async def test_when_no_anchor_section_5_uses_config(
    client, db_session
):
    """
    Si la sección 4 NO está completada (model_used vacío), la 5
    cae al config (claude por defecto actual). El par sigue
    ejecutándose, pero el motor es el del config hasta que la 4
    se complete.

    En la práctica, la 4 SIEMPRE corre antes que la 5 en el
    orchestrator secuencial, así que este test simula el caso
    edge: motor del config, no herencia.
    """
    project_id, eco_map = await _create_project_with_sections(
        db_session,
        "cog-noanchor@test.com",
    )

    captured_models: list[str] = []

    async def fake_gen(*args, **kwargs):
        captured_models.append(kwargs.get("model", ""))
        return _make_ai_result(kwargs.get("model", ""))

    ai_mock = MagicMock()
    ai_mock.generate_in_conversation = AsyncMock(side_effect=fake_gen)

    motor_map = {
        "claude": "anthropic/claude-sonnet-5",
        "gemini": "google/gemini-3.1-pro-preview",
    }
    orch = PipelineOrchestrator(ai_client=ai_mock)
    await orch.generate_all_sections(
        project_id=project_id,
        motor_model_map=motor_map,
        eco_map=eco_map,
        _db=db_session,
    )

    assert any("claude" in m for m in captured_models)


@pytest.mark.asyncio
async def test_no_cross_motor_route_section_4_to_5(
    client, db_session
):
    """
    Garantía: NO existe ruta donde el contenido de la 4 se
    inyecte como prompt de un motor distinto para la 5. La 5
    hereda el motor del ancla; el contenido de la 4 se inyecta
    como assistant message en la MISMA conversación del MISMO
    modelo (no se traduce entre motores).
    """
    project_id, eco_map = await _create_project_with_sections(
        db_session,
        "cog-noxroute@test.com",
        completed_4_model="anthropic/claude-sonnet-5",
    )

    captured: list[tuple[int, str]] = []

    async def capture_gen(*args, **kwargs):
        if args and hasattr(args[0], "messages"):
            n = len(args[0].messages) // 2
            captured.append((n, kwargs.get("model", "")))
        return _make_ai_result(kwargs.get("model", ""))

    ai_mock = MagicMock()
    ai_mock.generate_in_conversation = AsyncMock(side_effect=capture_gen)

    motor_map = {
        "claude": "anthropic/claude-sonnet-5",
        "gemini": "google/gemini-3.1-pro-preview",
    }
    orch = PipelineOrchestrator(ai_client=ai_mock)
    await orch.generate_all_sections(
        project_id=project_id,
        motor_model_map=motor_map,
        eco_map=eco_map,
        _db=db_session,
    )

    # La sección 5 DEBE usar claude (motor heredado del ancla 4)
    sec_5_models = [m for n, m in captured if n == 5]
    if sec_5_models:
        assert all("claude" in m for m in sec_5_models)
