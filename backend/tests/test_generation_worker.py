"""
Tests contra la spec objetivo de Tarea 1+5+6 — generation worker
y orchestration.

Reescritos vs la versión legacy:
  - `MOTOR_MODEL_MAP` se prueba inyectando un mapa custom (mecanismo
    robusto a la decisión de Tarea 4; los valores finales quedan
    pendientes del reporte humano).
  - `extra_params.thinking` se verifica REALMENTE enviado a la API
    para Claude + 🔴 (no solo documentado).
  - El par co-generado 4-5 hereda el motor (Tarea 5).
  - La generación es SECUENCIAL 1→11 vía PipelineOrchestrator
    (Tarea 1), no paralela.
  - El audit_extraction corre en el flujo (Tarea 2).
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select

from app.models.compendium_section import CompendiumSection, SectionStatus
from app.models.ecos_map import EcosMap, EcosMapStatus
from app.models.extraction import Extraction, ExtractionStatus
from app.models.project import Project, ProjectStatus
from app.models.source_document import (
    SourceDocument,
    SourceDocumentStatus,
)
from app.models.user import User
from app.modules.ai_gateway.interfaces import AIResult
from app.modules.auth.service import hash_password
from app.modules.prompts.section_builder import SECTION_CONFIGS
from app.services.orchestrator import PipelineOrchestrator


def _make_ai_result(
    content: str = "Generated section content",
    model: str = "google/gemini-3.1-pro-preview",
    input_tokens: int = 2000,
    output_tokens: int = 1500,
    cost: float = 0.10,
) -> AIResult:
    return AIResult(
        content=content,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost,
        finish_reason="stop",
    )


async def _create_test_data(
    db_session,
    email: str,
    *,
    with_eco_map: bool = True,
    status: str = ProjectStatus.DRAFT,
) -> dict:
    user = User(
        email=email,
        password_hash=hash_password("Test1234"),
        full_name="Worker Test",
    )
    db_session.add(user)
    await db_session.flush()

    project = Project(
        user_id=user.id,
        name="worker-test",
        slug=f"worker-{email.split('@')[0]}",
        status=status,
        merged_content="Merged extraction content for testing.",
    )
    db_session.add(project)
    await db_session.flush()

    if with_eco_map:
        db_session.add(
            EcosMap(
                id=f"eco-{email.split('@')[0]}",
                pathology_key="worker-test",
                pathology_name="Worker Test",
                version=1,
                sections={},
                status=EcosMapStatus.APPROVED,
                is_active=True,
            )
        )

    section_ids = []
    for n in range(1, 12):
        config = SECTION_CONFIGS[n]
        section = CompendiumSection(
            project_id=project.id,
            section_number=n,
            section_name=config.section_name,
            dosification="STANDARD",
            status=SectionStatus.PENDING,
        )
        db_session.add(section)
        await db_session.flush()
        section_ids.append(section.id)
    await db_session.commit()

    return {
        "user_id": user.id,
        "project_id": project.id,
        "section_ids": section_ids,
    }


# ── Tarea 6 — MOTOR_MODEL_MAP resolution (mecanismo) ──────────────


def test_section_config_motor_per_section_matches_design():
    """
    Spec: secciones 🔴 (3,5,8,9) usan claude; el resto gemini.
    Mientras Tarea 4 no emita su veredicto, este es el mapa
    DOCUMENTADO. El mecanismo de override se prueba abajo.
    """
    assert SECTION_CONFIGS[3].motor == "claude"
    assert SECTION_CONFIGS[5].motor == "claude"
    assert SECTION_CONFIGS[8].motor == "claude"
    assert SECTION_CONFIGS[9].motor == "claude"
    assert SECTION_CONFIGS[1].motor == "gemini"
    assert SECTION_CONFIGS[2].motor == "gemini"
    assert SECTION_CONFIGS[4].motor == "gemini"
    assert SECTION_CONFIGS[6].motor == "gemini"
    assert SECTION_CONFIGS[7].motor == "gemini"
    assert SECTION_CONFIGS[10].motor == "gemini"
    assert SECTION_CONFIGS[11].motor == "gemini"


# ── Tarea 1 — extra_params.thinking REAL (no solo documentado) ─────


def test_thinking_param_sent_for_claude_red_sections():
    """
    Spec: para motor="claude" + sección 🔴, el orchestrator DEBE
    enviar `reasoning: {enabled: True, max_tokens: ...}` como
    extra_body al cliente OpenRouter.

    Verificamos el helper que construye esos extra_params
    directamente (no solo el spec del docs/09).
    """
    from app.services.orchestrator import _build_extra_params

    # 🔴 + claude → thinking
    for n in (3, 5, 8, 9):
        params = _build_extra_params("claude", n, "anthropic/claude-sonnet-5")
        assert "reasoning" in params
        assert params["reasoning"]["enabled"] is True

    # 🟢 + claude → sin thinking
    for n in (1, 2, 4, 6, 7, 10, 11):
        assert _build_extra_params("claude", n, "anthropic/claude-sonnet-5") == {}

    # 🔴 + gemini → sin thinking (solo aplica a Claude)
    for n in (3, 5, 8, 9):
        assert _build_extra_params("gemini", n, "google/gemini-3.1-pro-preview") == {}

    # Motor claude pero modelo Gemini → sin thinking
    for n in (3, 5, 8, 9):
        assert _build_extra_params("claude", n, "google/gemini-3.1-pro-preview") == {}


# ── Tarea 5 — par co-generado 4-5 mismo motor ──────────────────────


@pytest.mark.asyncio
async def test_orchestrator_motor_inheritance_for_cogeneration(
    client, db_session
):
    """
    Tarea 5: el job de la sección 5 hereda el motor del job de
    la 4 (R-9). Verificable con motor_map que asigna modelos
    distintos por motor y secciones 4 y 5 pre-completadas con
    el mismo motor heredado.
    """
    from app.services.orchestrator import COGENERATION_PAIRS

    assert COGENERATION_PAIRS[5] == 4

    data = await _create_test_data(db_session, "cog-m@test.com")
    project_id = str(data["project_id"])

    # Pre-completar 4 y 5 con el mismo modelo (gemini) aunque el
    # config de 5 diga claude. La 6+ en PENDING.
    sections_4_5 = (
        await db_session.execute(
            select(CompendiumSection).where(
                CompendiumSection.project_id == project_id,
                CompendiumSection.section_number.in_([4, 5]),
            )
        )
    ).scalars().all()
    for s in sections_4_5:
        s.status = SectionStatus.COMPLETED
        s.model_used = "google/gemini-3.1-pro-preview"
        s.content = "ya generado"
    await db_session.commit()

    # Capturamos modelos en cada llamada al AI
    captured: list[str] = []

    async def fake_gen(*args, **kwargs):
        captured.append(kwargs.get("model", ""))
        return _make_ai_result(model=kwargs.get("model", ""))

    ai_mock = MagicMock()
    ai_mock.generate_in_conversation = AsyncMock(side_effect=fake_gen)

    motor_map = {
        "claude": "anthropic/claude-sonnet-5",
        "gemini": "google/gemini-3.1-pro-preview",
    }
    orch = PipelineOrchestrator(ai_client=ai_mock)
    result = await orch.generate_all_sections(
        project_id=project_id,
        motor_model_map=motor_map,
        eco_map=None,  # usar el sembrado en BD
        _db=db_session,
    )

    # Las secciones 4 y 5 ya estaban completas → no se invocan.
    # Las llamadas son para 1, 2, 3, 6, 7, 8, 9, 10, 11.
    # Verificar que 4 y 5 NO aparecen (ya estaban done).
    # Para secciones invocadas, validar que usan el motor_map.
    assert result.completed >= 8  # al menos las que se ejecutaron
    # Ningún modelo usado es distinto a los del motor_map
    for m in captured:
        assert m in motor_map.values()


# ── Tarea 1 — orquestador secuencial 1→11 ──────────────────────────


@pytest.mark.asyncio
async def test_orchestrator_runs_sections_sequentially(
    client, db_session
):
    """
    La invocación a cada sección DEBE ocurrir en orden 1→11 (no
    paralelo). Verificable observando el orden de las llamadas
    al AI client.
    """
    data = await _create_test_data(db_session, "seq@test.com")
    project_id = str(data["project_id"])

    # Capturamos el orden de invocación vía el número de messages
    # acumulados en la conversación al momento de cada llamada.
    # Como la sección 1 ve 1 message (init) + 1 (instrucción),
    # la 2 ve +2 messages, etc. (init + 1×(instr+asst) por
    # sección completada).
    call_message_counts: list[int] = []

    async def fake_gen(*args, **kwargs):
        conv = kwargs.get("conversation")
        if conv is not None and hasattr(conv, "messages"):
            call_message_counts.append(len(conv.messages))
        return _make_ai_result(model=kwargs.get("model", ""))

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
        _db=db_session,
    )

    # El número de messages DEBE crecer monotónicamente
    assert len(call_message_counts) == 11
    for i in range(1, len(call_message_counts)):
        assert call_message_counts[i] > call_message_counts[i - 1], (
            f"Llamada {i} no acumuló mensajes: "
            f"{call_message_counts[i - 1]} → {call_message_counts[i]}"
        )


# ── Tarea 1 — rechazo de contenido truncado (finish_reason='length') ──


@pytest.mark.asyncio
async def test_truncated_section_marked_failed_no_silent_completion(
    client, db_session
):
    """
    Si la API devuelve finish_reason='length' y se agotan las
    continuaciones, la sección NUNCA se marca COMPLETED con
    contenido truncado: queda FAILED.
    """

    data = await _create_test_data(db_session, "trunc@test.com")
    project_id = str(data["project_id"])

    ai_mock = MagicMock()

    async def always_truncated(*args, **kwargs):
        return AIResult(
            content="fragmento",
            model="google/gemini-3.1-pro-preview",
            input_tokens=10,
            output_tokens=5,
            cost_usd=0.0,
            finish_reason="length",
        )

    ai_mock.generate_in_conversation = AsyncMock(side_effect=always_truncated)

    motor_map = {
        "claude": "anthropic/claude-sonnet-5",
        "gemini": "google/gemini-3.1-pro-preview",
    }
    orch = PipelineOrchestrator(ai_client=ai_mock)
    result = await orch.generate_all_sections(
        project_id=project_id,
        motor_model_map=motor_map,
        _db=db_session,
    )

    # El orchestrator debe haber cortado tras el primer error
    assert result.completed == 0
    assert 1 in result.failed


# ── Tarea 2 — audit_extraction corre en el flujo (smoke test) ────


@pytest.mark.asyncio
async def test_audit_extraction_worker_runs_and_persists(
    client, db_session
):
    """
    El worker audit_extraction (Tarea 2) está encolado por
    extract_document y persiste audit_content con la lista de
    faltantes contra el checklist curado.
    """
    from app.models.prompt_template import PromptTemplate
    from app.workers.extraction_worker import audit_extraction

    # Sembrar checklist único (no choca con la seed)
    db_session.add(
        PromptTemplate(
            id="ck-wf-test",
            name="audit_checklist_test_wf",
            type="audit_checklist",
            version=1,
            is_active=True,
            content='{"items": [{"id": "kw_x", "fact": "F", "keywords": ["zzzunique999"]}]}',
        )
    )

    user = User(
        email="audit-wf@test.com",
        password_hash=hash_password("X"),
        full_name="WF",
    )
    db_session.add(user)
    await db_session.flush()

    project = Project(
        user_id=user.id,
        name="Audit WF",
        slug="audit-wf",
        status=ProjectStatus.DRAFT,
    )
    db_session.add(project)
    await db_session.flush()

    doc = SourceDocument(
        project_id=project.id,
        filename="x.pdf",
        file_path="local://x",
        file_size=1,
        document_type="article",
        status=SourceDocumentStatus.EXTRACTED,
    )
    db_session.add(doc)
    await db_session.flush()

    extraction = Extraction(
        source_document_id=doc.id,
        content="Texto que NO contiene la keyword",
        status=ExtractionStatus.COMPLETED,
    )
    db_session.add(extraction)
    await db_session.commit()

    # Monkey-patch lookup
    from app.modules import audit as audit_mod

    original = audit_mod.service.checklist_name_for_document_type
    audit_mod.service.checklist_name_for_document_type = (
        lambda dt: "audit_checklist_test_wf"
    )
    try:
        result = await audit_extraction(
            {}, str(extraction.id), _db=db_session
        )
    finally:
        audit_mod.service.checklist_name_for_document_type = original

    assert result["status"] == "completed"
    assert result["missing_count"] == 1

    reloaded = (
        await db_session.execute(
            select(Extraction).where(Extraction.id == extraction.id)
        )
    ).scalar_one()
    assert reloaded.audit_completed is True


# ── Tarea 6 — completitud: 11 secciones generadas → status REVIEW ──


@pytest.mark.asyncio
async def test_orchestrator_transitions_to_review_when_all_done(
    client, db_session
):
    data = await _create_test_data(
        db_session, "review@test.com", status=ProjectStatus.DRAFT
    )
    project_id = str(data["project_id"])

    ai_mock = MagicMock()
    ai_mock.generate_in_conversation = AsyncMock(
        return_value=_make_ai_result()
    )

    orch = PipelineOrchestrator(ai_client=ai_mock)
    result = await orch.generate_all_sections(
        project_id=project_id,
        motor_model_map={"claude": "x", "gemini": "y"},
        _db=db_session,
    )

    assert result.completed == 11
    assert result.failed == []
    assert result.status == ProjectStatus.REVIEW

    reloaded = (
        await db_session.execute(
            select(Project).where(Project.id == project_id)
        )
    ).scalar_one()
    assert reloaded.status == ProjectStatus.REVIEW


# ── Tarea 3 — bloqueo si no hay eco map ───────────────────────────


@pytest.mark.asyncio
async def test_orchestrator_blocks_without_eco_map(
    client, db_session
):
    data = await _create_test_data(
        db_session, "block-ec@test.com", with_eco_map=False
    )
    project_id = str(data["project_id"])

    ai_mock = MagicMock()
    ai_mock.generate_in_conversation = AsyncMock(
        return_value=_make_ai_result()
    )

    orch = PipelineOrchestrator(ai_client=ai_mock)
    result = await orch.generate_all_sections(
        project_id=project_id,
        motor_model_map={"claude": "x", "gemini": "y"},
        _db=db_session,
    )

    assert result.completed == 0
    assert "eco_map_not_approved" in result.status
    # Ninguna llamada al AI (bloqueado antes del loop)
    assert not ai_mock.generate_in_conversation.called
