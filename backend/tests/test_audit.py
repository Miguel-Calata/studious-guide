"""
Tests de la Tarea 2 — audit_extraction v1.

Cubre:
  - normalize_text y matching por keyword
  - find_missing_facts (función pura) — caso de aceptación: un
    merged_document con un hecho deliberadamente omitido debe
    reportarlo como faltante
  - parse_checklist (JSON inválido no rompe)
  - run_audit_for_extraction persiste audit_content + audit_completed
  - flujo: extracción completada → audit encolado → audit corre →
    extraction.audit_content poblado con lista de faltantes
"""

import json

import pytest
from sqlalchemy import select

from app.models.extraction import Extraction, ExtractionStatus
from app.models.prompt_template import PromptTemplate
from app.models.source_document import (
    SourceDocument,
    SourceDocumentStatus,
)
from app.modules.audit.service import (
    ExpectedFact,
    checklist_name_for_document_type,
    find_missing_facts,
    keyword_present,
    normalize_text,
    parse_checklist,
    run_audit_for_extraction,
)

# ── Normalización y matching ──────────────────────────────────────────


def test_normalize_lowercase_no_accents():
    assert "kdigo 2026" in normalize_text("KDIGO 2026")
    assert normalize_text("Niño") == "nino"
    assert normalize_text("AÉREO") == "aereo"


def test_normalize_collapses_whitespace():
    assert normalize_text("  hola\n\n  mundo  ") == "hola mundo"


def test_normalize_empty():
    assert normalize_text("") == ""


def test_keyword_present_simple():
    # `keyword_present` espera el contenido ya normalizado.
    norm = normalize_text(
        "el documento sigue las guías KDIGO 2026 y hemodiálisis"
    )
    assert keyword_present("kdigo", norm)
    assert keyword_present("KDIGO", norm)
    assert not keyword_present("peritoneal", norm)
    assert not keyword_present("anuria", "")


# ── find_missing_facts (caso de aceptación) ──────────────────────────


def test_find_missing_facts_reports_omitted_fact():
    """
    Aceptación Tarea 2: un merged_document con un hecho deliberadamente
    omitido debe reportarlo como faltante.
    """
    checklist = [
        ExpectedFact(
            id="kdigo_aumento_creatinina",
            fact="Criterio KDIGO: aumento creatinina >=0.3 mg/dL en 48h",
            keywords=("0.3 mg/dl", "48 h", "kdigo"),
        ),
        ExpectedFact(
            id="furosemide_stress_test",
            fact="Furosemide Stress Test",
            keywords=("furosemide stress test", "fst"),
        ),
    ]
    # Texto que SÍ menciona KDIGO + 48h pero OMITE deliberadamente
    # tanto la keyword "furosemide stress test" como "fst".
    merged = """
    Documento de la guía KDIGO 2026. Cubre el aumento de creatinina
    en 48h pero NO menciona la prueba de estrés con diurético.
    Tampoco discute la dosis de contraste yodado en detalle.
    """
    missing = find_missing_facts(merged, checklist)
    missing_ids = [f.id for f in missing]
    # El FST debe faltar; el criterio KDIGO está cubierto.
    assert "furosemide_stress_test" in missing_ids
    assert "kdigo_aumento_creatinina" not in missing_ids


def test_find_missing_facts_all_present_returns_empty():
    checklist = [
        ExpectedFact(
            id="x",
            fact="X",
            keywords=("kdigo",),
        ),
    ]
    text = "Mencionamos kdigo ampliamente."
    assert find_missing_facts(text, checklist) == []


def test_find_missing_facts_empty_checklist():
    assert find_missing_facts("cualquier cosa", []) == []


def test_find_missing_facts_handles_empty_content():
    checklist = [
        ExpectedFact(id="x", fact="X", keywords=("foo",)),
    ]
    missing = find_missing_facts("", checklist)
    assert len(missing) == 1


def test_find_missing_facts_normalizes_accents_in_keywords():
    checklist = [
        ExpectedFact(
            id="pediatria",
            fact="Manejo pediátrico",
            keywords=("pediátrico",),  # acento
        ),
    ]
    # Texto sin acento: el matching debe encontrarlo igualmente
    assert find_missing_facts("manejo pediatrico en niños", checklist) == []


# ── parse_checklist ──────────────────────────────────────────────────


def test_parse_checklist_valid_json():
    raw = json.dumps(
        {
            "version": 1,
            "items": [
                {"id": "a", "fact": "A", "keywords": ["x", "y"]},
                {"id": "b", "fact": "B", "keywords": ["z"]},
            ],
        }
    )
    out = parse_checklist(raw)
    assert len(out) == 2
    assert out[0].id == "a"
    assert out[0].keywords == ("x", "y")
    assert out[1].id == "b"
    assert out[1].keywords == ("z",)


def test_parse_checklist_invalid_json_returns_empty():
    assert parse_checklist("{ malformed") == []
    assert parse_checklist("") == []


def test_parse_checklist_filters_malformed_items():
    raw = json.dumps(
        {
            "items": [
                {"id": "ok", "fact": "OK", "keywords": ["a"]},
                "not-a-dict",
                {"id": "no-kw", "fact": "X"},  # sin keywords
            ]
        }
    )
    out = parse_checklist(raw)
    assert len(out) == 1
    assert out[0].id == "ok"


# ── checklist_name_for_document_type ─────────────────────────────────


def test_checklist_name_mapping():
    assert checklist_name_for_document_type("bmj") == "audit_checklist_bmj"
    assert (
        checklist_name_for_document_type("guideline")
        == "audit_checklist_guideline"
    )
    assert (
        checklist_name_for_document_type("article")
        == "audit_checklist_article"
    )
    assert (
        checklist_name_for_document_type("unknown") == "audit_checklist_article"
    )


# ── run_audit_for_extraction (DB integration via conftest fixtures) ──


@pytest.mark.asyncio
async def test_run_audit_persists_report_with_missing(
    client, db_session
):
    """
    Flujo integrado: creamos una extracción con contenido que omite
    un hecho esperado del checklist, corremos run_audit_for_extraction
    y verificamos que audit_content persiste la lista de faltantes.

    Usa un nombre de checklist único (no colisiona con la seed) y
    monkey-patching del lookup para usar ese checklist.
    """
    unique_name = "audit_checklist_test_run"
    checklist = PromptTemplate(
        id="test-checklist-1",
        name=unique_name,
        type="audit_checklist",
        version=1,
        is_active=True,
        content=json.dumps(
            {
                "version": 1,
                "items": [
                    {
                        "id": "f1",
                        "fact": "F1",
                        "keywords": ["palabra_unica_xyz"],
                    },
                    {
                        "id": "f2",
                        "fact": "F2",
                        "keywords": ["otra_palabra_abc"],
                    },
                ],
            }
        ),
        description="test",
    )
    db_session.add(checklist)

    from app.models.user import User
    from app.modules.auth.service import hash_password

    user = User(
        email="audit-test@test.com",
        password_hash=hash_password("Test1234"),
        full_name="Audit Test",
    )
    db_session.add(user)
    await db_session.flush()

    from app.models.project import Project, ProjectStatus

    project = Project(
        user_id=user.id,
        name="Test AKI",
        slug="test-audit",
        status=ProjectStatus.DRAFT,
    )
    db_session.add(project)
    await db_session.flush()

    doc = SourceDocument(
        project_id=project.id,
        filename="x.pdf",
        file_path="local://test/x.pdf",
        file_size=1024,
        document_type="article",
        status=SourceDocumentStatus.EXTRACTED,
    )
    db_session.add(doc)
    await db_session.flush()

    extraction = Extraction(
        source_document_id=doc.id,
        content="Este documento menciona palabra_unica_xyz pero no la otra.",
        status=ExtractionStatus.COMPLETED,
    )
    db_session.add(extraction)
    await db_session.commit()

    # Monkey-patch el mapeo para usar el checklist único de este test
    from app.modules import audit as audit_mod

    original = audit_mod.service.checklist_name_for_document_type
    audit_mod.service.checklist_name_for_document_type = (
        lambda dt: unique_name
    )
    try:
        report = await run_audit_for_extraction(db_session, extraction, doc)
    finally:
        audit_mod.service.checklist_name_for_document_type = original

    assert report.total_facts == 2
    assert report.present_count == 1
    assert report.missing_count == 1
    assert report.missing[0].id == "f2"

    reloaded = (
        await db_session.execute(
            select(Extraction).where(Extraction.id == extraction.id)
        )
    ).scalar_one()
    assert reloaded.audit_completed is True
    assert reloaded.audit_content is not None
    parsed = json.loads(reloaded.audit_content)
    assert parsed["missing_count"] == 1
    assert parsed["missing"][0]["id"] == "f2"


@pytest.mark.asyncio
async def test_run_audit_no_checklist_graceful(client, db_session):
    """
    Si el checklist resuelto por document_type NO está sembrado, el
    pipeline no rompe: marca audit_completed=True con nota.

    Forzamos el caso monkey-patching el lookup a un nombre que no
    existe en la base de datos.
    """
    from app.models.project import Project, ProjectStatus
    from app.models.user import User
    from app.modules.auth.service import hash_password

    user = User(
        email="audit-noclist@test.com",
        password_hash=hash_password("Test1234"),
        full_name="No Clist",
    )
    db_session.add(user)
    await db_session.flush()

    project = Project(
        user_id=user.id,
        name="Test No Clist",
        slug="test-no-clist",
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
        content="algo",
        status=ExtractionStatus.COMPLETED,
    )
    db_session.add(extraction)
    await db_session.commit()

    from app.modules import audit as audit_mod

    original = audit_mod.service.checklist_name_for_document_type
    audit_mod.service.checklist_name_for_document_type = (
        lambda dt: "audit_checklist_does_not_exist_xyz"
    )
    try:
        report = await run_audit_for_extraction(db_session, extraction, doc)
    finally:
        audit_mod.service.checklist_name_for_document_type = original

    assert report.missing_count == 0
    assert report.total_facts == 0

    reloaded = (
        await db_session.execute(
            select(Extraction).where(Extraction.id == extraction.id)
        )
    ).scalar_one()
    assert reloaded.audit_completed is True
    parsed = json.loads(reloaded.audit_content)
    assert "checklist no disponible" in parsed.get("note", "")


# ── worker: integration test del flujo completo ─────────────────────


@pytest.mark.asyncio
async def test_audit_extraction_worker_reports_missing_in_flow(
    client, db_session
):
    """
    Aceptación de Tarea 2: tras extraer, el worker audit_extraction
    (ya encolado por extract_document) corre y deja un reporte que
    incluye los hechos faltantes.
    """
    from app.workers.extraction_worker import audit_extraction

    unique_name = "audit_checklist_test_worker_flow"
    db_session.add(
        PromptTemplate(
            id="ck-flow-test",
            name=unique_name,
            type="audit_checklist",
            version=1,
            is_active=True,
            content=json.dumps(
                {
                    "items": [
                        {
                            "id": "must_appear_keyword",
                            "fact": "Hecho que debe aparecer",
                            "keywords": ["debe_aparecer_zzz"],
                        }
                    ]
                }
            ),
        )
    )

    from app.models.project import Project, ProjectStatus
    from app.models.user import User
    from app.modules.auth.service import hash_password

    user = User(
        email="flow@test.com",
        password_hash=hash_password("Test1234"),
        full_name="Flow",
    )
    db_session.add(user)
    await db_session.flush()

    project = Project(
        user_id=user.id,
        name="Flow",
        slug="flow-test",
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
        content="Contenido que NO menciona la keyword requerida",
        status=ExtractionStatus.COMPLETED,
    )
    db_session.add(extraction)
    await db_session.commit()

    from app.modules import audit as audit_mod

    original = audit_mod.service.checklist_name_for_document_type
    audit_mod.service.checklist_name_for_document_type = (
        lambda dt: unique_name
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
    parsed = json.loads(reloaded.audit_content)
    assert parsed["missing"][0]["id"] == "must_appear_keyword"
