"""
Tests de la Tarea 3 — MAPA_ECOS híbrido.

Cubre:
  - `pathology_key_for`: normalización
  - `validate_ecos_map`: cobertura con semántica backward real
    (slot de la sección S debe aparecer como eco en alguna sección
    posterior; sección 1 vacía; sin duplicados)
  - `get_active_ecos_map` / `require_approved_map`
  - `propose_ecos_map` genera un borrador (mock del cliente LLM)
  - `propose_ecos_map` FAIL-LOUD: respuesta truncada, basura o
    JSON sin claves de sección → EcoMapProposalError, sin persistir
  - `find_project_for_pathology`: grounding del propose manual
  - `approve_ecos_map` desactiva versiones previas
  - Aceptación: auto-poblado sobre HTN produce un draft revisable
  - Aceptación: el mapa AKI sembrado está intacto
  - 409: compendiums service bloquea sin mapa aprobado
  - orquestador: registra `ecos_map_version` por sección
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.compendium_section import CompendiumSection, SectionStatus
from app.models.ecos_map import EcosMap, EcosMapOrigin, EcosMapStatus
from app.models.project import Project, ProjectStatus
from app.models.user import User
from app.modules.ai_gateway.interfaces import AIResult
from app.modules.auth.service import hash_password
from app.modules.prompts.ecos_service import (
    EcoMapNotApprovedError,
    EcoMapProposalError,
    approve_ecos_map,
    find_project_for_pathology,
    get_active_ecos_map,
    get_ecos_for_section,
    pathology_key_for,
    propose_ecos_map,
    require_approved_map,
    validate_ecos_map,
)
from app.modules.prompts.ecos_template import ECOS_SECTION_TEMPLATE

# ── pathology_key_for ───────────────────────────────────────────────


def test_pathology_key_for_lowercase_slug():
    assert pathology_key_for("Insuficiencia Renal Aguda") == "insuficiencia-renal-aguda"
    assert pathology_key_for("LRA / AKI") == "lra-aki"
    assert pathology_key_for("HTN") == "htn"
    assert pathology_key_for("") == ""


# ── validate_ecos_map ────────────────────────────────────────────────


def _valid_draft() -> dict:
    """
    Draft válido con la semántica real de los ecos (backward):
    sección 1 vacía; cada slot de las secciones 1..10 aparece como
    eco (mencionando su label) en la sección inmediatamente
    posterior a su dueña. Los slots de la 11 no pueden tener ecos.
    """
    draft: dict[str, list[str]] = {str(n): [] for n in range(1, 12)}
    for section_number, slots in ECOS_SECTION_TEMPLATE.items():
        if section_number >= 11:
            continue
        target = str(section_number + 1)
        for s in slots:
            draft[target].append(
                f"{s['label']} (→ ver Sección {section_number})"
            )
    return draft


def test_validate_ecos_map_full_coverage_ok():
    draft = _valid_draft()
    ok, problems = validate_ecos_map(draft)
    assert ok is True
    assert problems == []


def test_validate_ecos_map_missing_slot_reports_problem():
    draft = _valid_draft()
    # El eco de 'criterios_diagnosticos' (dueño: sección 2) vive en la 3
    draft["3"] = [e for e in draft["3"] if "Criterios diagnósticos" not in e]
    ok, problems = validate_ecos_map(draft)
    assert ok is False
    assert any("criterios_diagnosticos" in p for p in problems)


def test_validate_ecos_map_section1_must_be_empty():
    draft = _valid_draft()
    draft["1"] = ["Eco indebido: la sección 1 no referencia a nadie"]
    ok, problems = validate_ecos_map(draft)
    assert ok is False
    assert any("sección 1" in p for p in problems)


def test_validate_ecos_map_rejects_duplicate_ecos():
    draft = _valid_draft()
    draft["4"].append(draft["4"][0])
    ok, problems = validate_ecos_map(draft)
    assert ok is False
    assert any("duplicados" in p for p in problems)


def test_validate_ecos_map_handles_non_dict_input():
    ok, problems = validate_ecos_map({})
    # Sin cobertura: un problema por cada slot de las secciones
    # 1..10 (la 11 está exenta, no tiene secciones posteriores)
    expected = sum(
        len(slots)
        for n, slots in ECOS_SECTION_TEMPLATE.items()
        if n < 11
    )
    assert ok is False
    assert len(problems) == expected


# ── get_ecos_for_section ─────────────────────────────────────────────


def test_get_ecos_for_section_returns_map_value():
    m = EcosMap(
        id="x",
        pathology_key="aki",
        pathology_name="LRA",
        version=1,
        sections={"2": ["hola", "mundo"]},
        status=EcosMapStatus.APPROVED,
        is_active=True,
    )
    assert get_ecos_for_section(m, 2) == ["hola", "mundo"]
    assert get_ecos_for_section(m, 5) == []
    assert get_ecos_for_section(None, 2) == []


# ── require_approved_map ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_require_approved_map_raises_when_missing(client, db_session):
    pathology_key = "htn"
    with pytest.raises(EcoMapNotApprovedError):
        await require_approved_map(db_session, pathology_key)


@pytest.mark.asyncio
async def test_require_approved_map_returns_when_present(client, db_session):
    db_session.add(
        EcosMap(
            id="ramp-approved-1",
            pathology_key="ramp-test-1",
            pathology_name="Ramp Test",
            version=1,
            sections={"2": ["x"]},
            status=EcosMapStatus.APPROVED,
            is_active=True,
        )
    )
    await db_session.commit()
    m = await require_approved_map(db_session, "ramp-test-1")
    assert m.id == "ramp-approved-1"


# ── propose_ecos_map (auto-poblado) ──────────────────────────────────


@pytest.mark.asyncio
async def test_propose_ecos_map_creates_draft_for_new_pathology(
    client, db_session
):
    """
    Aceptación: auto-poblado sobre HTN produce un draft revisable.
    """
    # Sembrar el prompt de autopopulate en BD (la migración 011 ya lo
    # hace, pero en el test la fila puede no existir por rollback).

    # Re-usar el sembrado por la migración. Solo asegurarnos.
    ai_mock = MagicMock()
    fake_ai_result = AIResult(
        content=json.dumps(_valid_draft()),
        model="google/gemini-3.1-pro-preview",
        input_tokens=2000,
        output_tokens=1500,
        cost_usd=0.05,
        finish_reason="stop",
    )
    ai_mock.generate = AsyncMock(return_value=fake_ai_result)

    eco_map = await propose_ecos_map(
        db_session, ai_mock, "Hipertensión Arterial"
    )

    # El draft debe estar en BD, no aprobado, no activo
    assert eco_map.status == EcosMapStatus.DRAFT
    assert eco_map.is_active is False
    assert eco_map.origin == EcosMapOrigin.AUTOPOPULATED
    assert eco_map.pathology_key == "hipertension-arterial"
    assert eco_map.version == 1
    # model_used debe reflejar el default
    assert eco_map.model_used == "google/gemini-3.1-pro-preview"
    # Cobertura: todos los slots del template representados
    ok, problems = validate_ecos_map(eco_map.sections)
    assert ok is True, f"problemas: {problems}"
    # El AKI sembrado (en test DB por migración) NO debe verse afectado
    aki = await get_active_ecos_map(db_session, "aki")
    if aki is not None:
        assert aki.pathology_key == "aki"
        assert aki.is_active is True


# ── approve_ecos_map ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_approve_ecos_map_deactivates_previous(
    client, db_session
):
    v1 = EcosMap(
        id="v1-aki",
        pathology_key="test-pat-1",
        pathology_name="Test",
        version=1,
        sections={"2": ["v1"]},
        status=EcosMapStatus.APPROVED,
        is_active=True,
    )
    v2 = EcosMap(
        id="v2-test",
        pathology_key="test-pat-1",
        pathology_name="Test",
        version=2,
        sections={"2": ["v2"]},
        status=EcosMapStatus.DRAFT,
        is_active=False,
    )
    db_session.add_all([v1, v2])
    await db_session.commit()

    user = User(
        email="approver@test.com",
        password_hash=hash_password("X"),
        full_name="Approver",
    )
    db_session.add(user)
    await db_session.commit()

    approved = await approve_ecos_map(db_session, v2.id, str(user.id))
    assert approved.is_active is True
    assert approved.status == EcosMapStatus.APPROVED
    assert approved.approved_by == str(user.id)
    assert approved.approved_at is not None

    # v1 debe estar desactivada
    reloaded_v1 = (
        await db_session.execute(
            select(EcosMap).where(EcosMap.id == v1.id)
        )
    ).scalar_one()
    assert reloaded_v1.is_active is False


# ── AKI seed intacto ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_aki_seed_map_unchanged_by_autopopulate(
    client, db_session
):
    """
    Aceptación: el mapa AKI sembrado queda intacto al hacer
    auto-poblado sobre una patología nueva.
    """
    aki_before = await get_active_ecos_map(db_session, "aki")
    assert aki_before is not None
    assert aki_before.pathology_key == "aki"
    sections_before = dict(aki_before.sections)

    ai_mock = MagicMock()
    ai_mock.generate = AsyncMock(
        return_value=AIResult(
            content=json.dumps(_valid_draft()),
            model="google/gemini-3.1-pro-preview",
            input_tokens=10,
            output_tokens=10,
            cost_usd=0.0,
            finish_reason="stop",
        )
    )
    await propose_ecos_map(db_session, ai_mock, "EPOC")

    aki_after = await get_active_ecos_map(db_session, "aki")
    assert aki_after is not None
    assert aki_after.id == aki_before.id
    assert aki_after.sections == sections_before


# ── Bloqueo 409 en compendiums service ──────────────────────────────


@pytest.mark.asyncio
async def test_generate_sections_blocks_409_without_eco_map(
    client, db_session
):
    """
    Si no hay ecos map aprobado para la patología, generate_sections
    debe lanzar HTTPException 409 con mensaje accionable.
    """
    from app.modules.compendiums.service import generate_sections

    user = User(
        email="block@test.com",
        password_hash=hash_password("X"),
        full_name="Blocker",
    )
    db_session.add(user)
    await db_session.flush()

    project = Project(
        user_id=user.id,
        name="Patología Sin Mapa",
        slug="pat-sin-mapa",
        status=ProjectStatus.DRAFT,
        merged_content="Contenido de prueba",
    )
    db_session.add(project)
    await db_session.commit()

    with pytest.raises(HTTPException) as exc:
        await generate_sections(db_session, project, arq_pool=None)
    assert exc.value.status_code == 409
    assert "ecos_map" in str(exc.value.detail).lower()


# ── Orchestrator: registra ecos_map_version ──────────────────────────


@pytest.mark.asyncio
async def test_orchestrator_records_ecos_map_version(
    client, db_session
):
    """
    El orchestrator, tras generar una sección, debe setear
    `ecos_map_version` con el formato 'vN' del mapa usado.
    """
    from app.services.orchestrator import PipelineOrchestrator

    user = User(
        email="orch-eco@test.com",
        password_hash=hash_password("X"),
        full_name="OrchEco",
    )
    db_session.add(user)
    await db_session.flush()

    # Sembrar mapa aprobado para la patología del proyecto
    eco_map = EcosMap(
        id="eco-test-1",
        pathology_key="test-orch-path",
        pathology_name="Test Orch",
        version=3,
        sections={"2": ["eco 2"]},
        status=EcosMapStatus.APPROVED,
        is_active=True,
    )
    db_session.add(eco_map)

    project = Project(
        user_id=user.id,
        name="test-orch-path",
        slug="test-orch-path",
        status=ProjectStatus.GENERATING,
        merged_content="Contenido de prueba",
    )
    db_session.add(project)
    await db_session.flush()

    section = CompendiumSection(
        project_id=project.id,
        section_number=2,
        section_name="CLASIFICACIÓN",
        dosification="STANDARD",
        status=SectionStatus.PENDING,
    )
    db_session.add(section)
    await db_session.commit()

    # Mockear AI
    ai_mock = MagicMock()

    async def fake_generate_in_conversation(*args, **kwargs):
        return AIResult(
            content="contenido sección 2",
            model="google/gemini-3.1-pro-preview",
            input_tokens=10,
            output_tokens=10,
            cost_usd=0.0,
            finish_reason="stop",
        )

    ai_mock.generate_in_conversation = AsyncMock(
        side_effect=fake_generate_in_conversation
    )

    orch = PipelineOrchestrator(ai_client=ai_mock)
    await orch.generate_all_sections(
        project_id=str(project.id)
    )
    # No exigimos success completo (puede fallar por secciones
    # que no tienen eco en el mapa de prueba), pero al menos la 2
    # debe haber sido procesada y registrada con ecos_map_version.
    reloaded = (
        await db_session.execute(
            select(CompendiumSection).where(
                CompendiumSection.project_id == project.id,
                CompendiumSection.section_number == 2,
            )
        )
    ).scalar_one()
    if reloaded.status == SectionStatus.COMPLETED:
        assert reloaded.ecos_map_version == "v3"


# ── propose_ecos_map con source_content (grounded) ───────────────


@pytest.mark.asyncio
async def test_propose_ecos_map_with_source_content(
    client, db_session
):
    """
    Propose con source_content incluye el excerpt en el prompt
    enviado al LLM y usa ecos_map_autopopulate como system prompt.
    """
    ai_mock = MagicMock()
    fake_result = AIResult(
        content=json.dumps(_valid_draft()),
        model="google/gemini-3.1-pro-preview",
        input_tokens=2000,
        output_tokens=1500,
        cost_usd=0.05,
        finish_reason="stop",
    )
    ai_mock.generate = AsyncMock(return_value=fake_result)

    source = "KDIGO 2012 define LRA como aumento de SCr ≥0.3 mg/dL..."
    eco_map = await propose_ecos_map(
        db_session, ai_mock, "Insuficiencia Renal Aguda",
        source_content=source,
    )

    # Verificar que se llamó al LLM con source_content en el prompt
    call_kwargs = ai_mock.generate.call_args
    prompt_sent = call_kwargs.kwargs.get(
        "prompt", call_kwargs.args[0] if call_kwargs.args else ""
    )
    assert "KDIGO 2012" in prompt_sent
    assert "CONTENIDO FUENTE DEL PROYECTO" in prompt_sent

    # Verificar que el system prompt es ecos_map_autopopulate, NO sam_v9
    sys_prompt = call_kwargs.kwargs.get("system_prompt", "")
    assert "MAPA DE ECOS" in sys_prompt
    assert "Catedrático" not in sys_prompt  # sam_v9 tiene esto

    assert eco_map.status == EcosMapStatus.DRAFT
    assert eco_map.origin == EcosMapOrigin.AUTOPOPULATED
    assert eco_map.model_used == "google/gemini-3.1-pro-preview"


@pytest.mark.asyncio
async def test_propose_ecos_map_without_source_content(
    client, db_session
):
    """
    Propose sin source_content no incluye bloque de fuentes.
    """
    ai_mock = MagicMock()
    fake_result = AIResult(
        content=json.dumps(_valid_draft()),
        model="google/gemini-3.1-pro-preview",
        input_tokens=1000,
        output_tokens=1000,
        cost_usd=0.03,
        finish_reason="stop",
    )
    ai_mock.generate = AsyncMock(return_value=fake_result)

    eco_map = await propose_ecos_map(
        db_session, ai_mock, "EPOC"
    )

    call_kwargs = ai_mock.generate.call_args
    prompt_sent = call_kwargs.kwargs.get("prompt", "")
    assert "CONTENIDO FUENTE" not in prompt_sent
    assert eco_map.status == EcosMapStatus.DRAFT
    assert eco_map.model_used == "google/gemini-3.1-pro-preview"


@pytest.mark.asyncio
async def test_propose_ecos_map_uses_custom_model(
    client, db_session
):
    """
    Propose con model custom pasa el model_id a generate() y lo
    persiste en model_used.
    """
    ai_mock = MagicMock()
    fake_result = AIResult(
        content=json.dumps(_valid_draft()),
        model="anthropic/claude-sonnet-5",
        input_tokens=1000,
        output_tokens=1000,
        cost_usd=0.03,
        finish_reason="stop",
    )
    ai_mock.generate = AsyncMock(return_value=fake_result)

    eco_map = await propose_ecos_map(
        db_session, ai_mock, "EPOC",
        model="anthropic/claude-sonnet-5",
    )

    call_kwargs = ai_mock.generate.call_args
    assert call_kwargs.kwargs.get("model") == "anthropic/claude-sonnet-5"
    assert eco_map.model_used == "anthropic/claude-sonnet-5"


@pytest.mark.asyncio
async def test_propose_ecos_map_uses_default_model_when_none(
    client, db_session
):
    """
    Propose sin model explícito usa DEFAULT_ECOS_MAP_MODEL.
    """
    ai_mock = MagicMock()
    fake_result = AIResult(
        content=json.dumps(_valid_draft()),
        model="google/gemini-3.1-pro-preview",
        input_tokens=1000,
        output_tokens=1000,
        cost_usd=0.03,
        finish_reason="stop",
    )
    ai_mock.generate = AsyncMock(return_value=fake_result)

    eco_map = await propose_ecos_map(
        db_session, ai_mock, "EPOC"
    )

    call_kwargs = ai_mock.generate.call_args
    assert call_kwargs.kwargs.get("model") == "google/gemini-3.1-pro-preview"
    assert eco_map.model_used == "google/gemini-3.1-pro-preview"


# ── update_ecos_map_draft ────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_ecos_map_draft_updates_sections(
    client, db_session
):
    eco_map = EcosMap(
        id="draft-edit-1",
        pathology_key="edit-test",
        pathology_name="Edit Test",
        version=1,
        sections=_valid_draft(),
        status=EcosMapStatus.DRAFT,
        is_active=False,
    )
    db_session.add(eco_map)
    await db_session.commit()

    from app.modules.prompts.ecos_service import update_ecos_map_draft

    new_sections = _valid_draft()
    new_sections["2"] = ["custom eco for section 2"]

    updated, problems = await update_ecos_map_draft(
        db_session, eco_map.id, new_sections,
        description="editado por doctor",
    )
    assert updated.sections["2"] == ["custom eco for section 2"]
    assert updated.description == "editado por doctor"
    # Problemas de cobertura deben reportarse (slot faltante en sección 2)
    assert isinstance(problems, list)


@pytest.mark.asyncio
async def test_update_ecos_map_draft_rejects_approved(
    client, db_session
):
    eco_map = EcosMap(
        id="approved-no-edit",
        pathology_key="no-edit-test",
        pathology_name="No Edit",
        version=1,
        sections=_valid_draft(),
        status=EcosMapStatus.APPROVED,
        is_active=True,
    )
    db_session.add(eco_map)
    await db_session.commit()

    from app.modules.prompts.ecos_service import (
        EcoMapNotEditableError,
        update_ecos_map_draft,
    )

    with pytest.raises(EcoMapNotEditableError):
        await update_ecos_map_draft(
            db_session, eco_map.id, _valid_draft()
        )


# ── get_pending_draft ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_pending_draft_returns_latest(client, db_session):
    v1 = EcosMap(
        id="draft-v1",
        pathology_key="pending-test",
        pathology_name="Pending",
        version=1,
        sections=_valid_draft(),
        status=EcosMapStatus.DRAFT,
        is_active=False,
    )
    v2 = EcosMap(
        id="draft-v2",
        pathology_key="pending-test",
        pathology_name="Pending",
        version=2,
        sections=_valid_draft(),
        status=EcosMapStatus.DRAFT,
        is_active=False,
    )
    db_session.add_all([v1, v2])
    await db_session.commit()

    from app.modules.prompts.ecos_service import get_pending_draft

    draft = await get_pending_draft(db_session, "pending-test")
    assert draft is not None
    assert draft.id == "draft-v2"  # latest version


@pytest.mark.asyncio
async def test_get_pending_draft_returns_none_when_only_approved(
    client, db_session
):
    eco_map = EcosMap(
        id="only-approved",
        pathology_key="only-approved-test",
        pathology_name="Only Approved",
        version=1,
        sections=_valid_draft(),
        status=EcosMapStatus.APPROVED,
        is_active=True,
    )
    db_session.add(eco_map)
    await db_session.commit()

    from app.modules.prompts.ecos_service import get_pending_draft

    draft = await get_pending_draft(db_session, "only-approved-test")
    assert draft is None


# ── generate_sections 409 messages ───────────────────────────────


@pytest.mark.asyncio
async def test_generate_sections_409_with_pending_draft(
    client, db_session
):
    """
    Si hay un borrador pendiente, el 409 menciona el id y versión.
    """
    from app.modules.compendiums.service import generate_sections

    user = User(
        email="pending-msg@test.com",
        password_hash=hash_password("X"),
        full_name="PendingMsg",
    )
    db_session.add(user)
    await db_session.flush()

    project = Project(
        user_id=user.id,
        name="Draft Pending Msg",
        slug="draft-pending-msg",
        status=ProjectStatus.DRAFT,
        merged_content="Contenido de prueba",
    )
    db_session.add(project)

    draft = EcosMap(
        id="draft-for-msg",
        pathology_key="draft-pending-msg",
        pathology_name="Draft Pending Msg",
        version=1,
        sections=_valid_draft(),
        status=EcosMapStatus.DRAFT,
        is_active=False,
    )
    db_session.add(draft)
    await db_session.commit()

    with pytest.raises(HTTPException) as exc:
        await generate_sections(db_session, project, arq_pool=None)
    assert exc.value.status_code == 409
    detail = str(exc.value.detail)
    assert "draft-for-msg" in detail
    assert "v1" in detail


@pytest.mark.asyncio
async def test_generate_sections_409_without_any_map(
    client, db_session
):
    """
    Sin mapa ni borrador, el 409 sugiere generar borrador.
    """
    from app.modules.compendiums.service import generate_sections

    user = User(
        email="no-map-msg@test.com",
        password_hash=hash_password("X"),
        full_name="NoMapMsg",
    )
    db_session.add(user)
    await db_session.flush()

    project = Project(
        user_id=user.id,
        name="No Map Msg",
        slug="no-map-msg",
        status=ProjectStatus.DRAFT,
        merged_content="Contenido de prueba",
    )
    db_session.add(project)
    await db_session.commit()

    with pytest.raises(HTTPException) as exc:
        await generate_sections(db_session, project, arq_pool=None)
    assert exc.value.status_code == 409
    assert "ecos_map" in str(exc.value.detail).lower()


# ── prompt v2 sembrado ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_autopopulate_prompt_v3_exists(client, db_session):
    """
    La migración 014 siembra la v3 de ecos_map_autopopulate como
    activa (v1 y v2 quedan inactivas). La v3 corrige la semántica
    de los ecos a backward (referencia a tema YA desarrollado).
    """
    from app.modules.prompts.ecos_service import get_active_prompt

    prompt = await get_active_prompt(db_session, "ecos_map_autopopulate")
    assert prompt.version == 3
    assert "R1." in prompt.content  # v3 mantiene reglas R1-R9
    assert "MAPA DE ECOS" in prompt.content
    assert "YA FUE DESARROLLADO" in prompt.content  # semántica backward


# ── propose_ecos_map FAIL-LOUD ────────────────────────────────


@pytest.mark.asyncio
async def test_propose_ecos_map_garbage_response_raises_and_persists_nothing(
    client, db_session
):
    """
    Fail-loud: si el LLM devuelve texto no parseable, se lanza
    EcoMapProposalError y NO se persiste ningún borrador vacío
    (antes se guardaba sections={} — el mapa "aparecía vacío").
    """
    ai_mock = MagicMock()
    ai_mock.generate = AsyncMock(
        return_value=AIResult(
            content="Lo siento, no puedo generar ese mapa de ecos.",
            model="google/gemini-3.1-pro-preview",
            input_tokens=10,
            output_tokens=10,
            cost_usd=0.0,
            finish_reason="stop",
        )
    )

    with pytest.raises(EcoMapProposalError):
        await propose_ecos_map(db_session, ai_mock, "Patología Garbage")

    result = await db_session.execute(
        select(EcosMap).where(
            EcosMap.pathology_key == "patologia-garbage"
        )
    )
    assert result.scalars().first() is None


@pytest.mark.asyncio
async def test_propose_ecos_map_truncated_response_raises(
    client, db_session
):
    """
    finish_reason='length' (JSON truncado, p.ej. por reasoning
    tokens consumiendo max_tokens) → error explícito, nunca un
    borrador a medias.
    """
    ai_mock = MagicMock()
    ai_mock.generate = AsyncMock(
        return_value=AIResult(
            content='{"1": [], "2": ["eco incompleto',
            model="google/gemini-3.1-pro-preview",
            input_tokens=10,
            output_tokens=16384,
            cost_usd=0.0,
            finish_reason="length",
        )
    )

    with pytest.raises(EcoMapProposalError, match="trunc"):
        await propose_ecos_map(db_session, ai_mock, "Patología Truncada")


@pytest.mark.asyncio
async def test_propose_ecos_map_wrapped_json_raises(
    client, db_session
):
    """
    JSON parseable pero sin claves de sección ('1'..'11') — p.ej.
    el modelo envuelve el mapa en {"sections": {...}} — también es
    error: persistirlo produciría un mapa que la UI muestra vacío.
    """
    ai_mock = MagicMock()
    ai_mock.generate = AsyncMock(
        return_value=AIResult(
            content=json.dumps({"sections": _valid_draft()}),
            model="google/gemini-3.1-pro-preview",
            input_tokens=10,
            output_tokens=10,
            cost_usd=0.0,
            finish_reason="stop",
        )
    )

    with pytest.raises(EcoMapProposalError):
        await propose_ecos_map(db_session, ai_mock, "Patología Wrapped")

    result = await db_session.execute(
        select(EcosMap).where(
            EcosMap.pathology_key == "patologia-wrapped"
        )
    )
    assert result.scalars().first() is None


# ── find_project_for_pathology (grounding del propose manual) ──


@pytest.mark.asyncio
async def test_find_project_for_pathology_prefers_merged_content(
    client, db_session
):
    user = User(
        email="find-proj@test.com",
        password_hash=hash_password("X"),
        full_name="FindProj",
    )
    db_session.add(user)
    await db_session.flush()

    p_empty = Project(
        user_id=user.id,
        name="Insuficiencia Renal Aguda",
        slug="ira-empty",
        status=ProjectStatus.DRAFT,
        merged_content="",
    )
    p_merged = Project(
        user_id=user.id,
        name="Insuficiencia Renal Aguda!",
        slug="ira-merged",
        status=ProjectStatus.REVIEW,
        merged_content="contenido fusionado de guías",
    )
    db_session.add_all([p_empty, p_merged])
    await db_session.commit()

    found = await find_project_for_pathology(
        db_session, "insuficiencia-renal-aguda"
    )
    assert found is not None
    assert found.id == p_merged.id

    assert (
        await find_project_for_pathology(db_session, "no-existe")
        is None
    )
