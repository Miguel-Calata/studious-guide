from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.extraction import Extraction, ExtractionStatus
from app.models.project import Project, ProjectStatus
from app.models.source_document import SourceDocument, SourceDocumentStatus
from app.modules.ai_gateway.interfaces import AIResult
from app.workers.extraction_worker import extract_document


@asynccontextmanager
async def _test_session(db: AsyncSession | None):
    if db is not None:
        yield db
    else:
        async with async_session() as new_db:
            yield new_db


def _make_ai_result(content: str = "Contenido extraído del PDF") -> AIResult:
    return AIResult(
        content=content,
        model="google/gemini-2.5-pro",
        input_tokens=1000,
        output_tokens=500,
        cost_usd=0.05,
        finish_reason="STOP",
    )


async def _create_test_data(db: AsyncSession, email: str) -> dict:
    from app.models.user import User
    from app.modules.auth.service import hash_password

    user = User(
        email=email,
        password_hash=hash_password("Test1234"),
        full_name="Worker Test",
    )
    db.add(user)
    await db.flush()

    project = Project(
        user_id=user.id,
        name="LRA Test",
        slug=f"lra-{email.split('@')[0]}",
        status=ProjectStatus.EXTRACTING,
    )
    db.add(project)
    await db.flush()

    doc = SourceDocument(
        project_id=project.id,
        filename="bmj_test.pdf",
        file_path="local://proj1/doc1.pdf",
        file_size=1024,
        document_type="bmj",
        status=SourceDocumentStatus.EXTRACTING,
    )
    db.add(doc)
    await db.flush()

    extraction = Extraction(
        source_document_id=doc.id,
        content="",
        status=ExtractionStatus.PENDING,
    )
    db.add(extraction)
    await db.commit()

    return {
        "user_id": user.id,
        "project_id": project.id,
        "doc_id": doc.id,
        "extraction_id": extraction.id,
    }


@pytest.mark.asyncio
async def test_extract_document_success(client, db_session):
    data = await _create_test_data(db_session, "worker-success@test.com")
    doc_id = data["doc_id"]

    fake_text = "# Contenido del PDF\n\nPaciente de 45 años con dolor..."

    with (
        patch(
            "app.workers.extraction_worker.get_storage_backend"
        ) as mock_storage,
        patch(
            "app.workers.extraction_worker.pymupdf4llm.to_markdown"
        ) as mock_md,
        patch(
            "app.workers.extraction_worker.OpenRouterClient"
        ) as MockAI,
    ):
        mock_storage.return_value.read_bytes = AsyncMock(
            return_value=b"%PDF-1.4 fake"
        )
        mock_md.return_value = fake_text

        mock_ai_instance = MagicMock()
        mock_ai_instance.generate_with_continuations = AsyncMock(
            return_value=_make_ai_result()
        )
        MockAI.return_value = mock_ai_instance

        result = await extract_document({}, document_id=doc_id, _db=db_session)

        assert result["status"] == "completed"

        ext = (
            await db_session.execute(
                select(Extraction).where(
                    Extraction.source_document_id == doc_id
                )
            )
        ).scalar_one()
        assert ext.status == ExtractionStatus.COMPLETED
        assert ext.content == "Contenido extraído del PDF"
        assert ext.model_used == "google/gemini-2.5-pro"
        assert ext.input_tokens == 1000
        assert ext.output_tokens == 500
        assert float(ext.cost_usd) == 0.05

        doc = (
            await db_session.execute(
                select(SourceDocument).where(SourceDocument.id == doc_id)
            )
        ).scalar_one()
        assert doc.status == SourceDocumentStatus.EXTRACTED


@pytest.mark.asyncio
async def test_extract_document_failure(client, db_session):
    data = await _create_test_data(db_session, "worker-fail@test.com")
    doc_id = data["doc_id"]

    with (
        patch(
            "app.workers.extraction_worker.get_storage_backend"
        ) as mock_storage,
        patch(
            "app.workers.extraction_worker.pymupdf4llm.to_markdown"
        ) as mock_md,
        patch(
            "app.workers.extraction_worker.OpenRouterClient"
        ) as MockAI,
    ):
        mock_storage.return_value.read_bytes = AsyncMock(
            return_value=b"%PDF-1.4"
        )
        mock_md.return_value = "text"
        mock_ai_instance = MagicMock()
        mock_ai_instance.generate_with_continuations = AsyncMock(
            side_effect=Exception("API error")
        )
        MockAI.return_value = mock_ai_instance

        result = await extract_document({}, document_id=doc_id, _db=db_session)

        assert result["status"] == "failed"
        assert "API error" in result["error"]

        ext = (
            await db_session.execute(
                select(Extraction).where(
                    Extraction.source_document_id == doc_id
                )
            )
        ).scalar_one()
        assert ext.status == ExtractionStatus.FAILED
        assert "API error" in ext.error_message

        doc = (
            await db_session.execute(
                select(SourceDocument).where(SourceDocument.id == doc_id)
            )
        ).scalar_one()
        assert doc.status == SourceDocumentStatus.ERROR


@pytest.mark.asyncio
async def test_audit_enqueued_after_success(client, db_session):
    data = await _create_test_data(db_session, "worker-audit@test.com")
    doc_id = data["doc_id"]
    extraction_id = data["extraction_id"]

    mock_arq = MagicMock()
    mock_arq.enqueue_job = AsyncMock()

    with (
        patch(
            "app.workers.extraction_worker.get_storage_backend"
        ) as mock_storage,
        patch(
            "app.workers.extraction_worker.pymupdf4llm.to_markdown"
        ) as mock_md,
        patch(
            "app.workers.extraction_worker.OpenRouterClient"
        ) as MockAI,
    ):
        mock_storage.return_value.read_bytes = AsyncMock(
            return_value=b"%PDF-1.4"
        )
        mock_md.return_value = "text"
        mock_ai_instance = MagicMock()
        mock_ai_instance.generate_with_continuations = AsyncMock(
            return_value=_make_ai_result()
        )
        MockAI.return_value = mock_ai_instance

        ctx = {"arq_pool": mock_arq}
        await extract_document(
            ctx, document_id=doc_id, _db=db_session
        )

        mock_arq.enqueue_job.assert_called_once_with(
            "audit_extraction",
            extraction_id=str(extraction_id),
            _job_id=f"audit_{extraction_id}",
        )


@pytest.mark.asyncio
async def test_correct_prompt_by_document_type(client, db_session):
    data = await _create_test_data(db_session, "worker-prompt@test.com")
    doc_id = data["doc_id"]

    with (
        patch(
            "app.workers.extraction_worker.get_storage_backend"
        ) as mock_storage,
        patch(
            "app.workers.extraction_worker.pymupdf4llm.to_markdown"
        ) as mock_md,
        patch(
            "app.workers.extraction_worker.OpenRouterClient"
        ) as MockAI,
    ):
        mock_storage.return_value.read_bytes = AsyncMock(
            return_value=b"%PDF-1.4"
        )
        mock_md.return_value = "text"
        mock_ai_instance = MagicMock()
        mock_ai_instance.generate_with_continuations = AsyncMock(
            return_value=_make_ai_result()
        )
        MockAI.return_value = mock_ai_instance

        await extract_document(
            {}, document_id=doc_id, _db=db_session
        )

        call_args = (
            mock_ai_instance.generate_with_continuations.call_args
        )
        prompt = call_args.kwargs.get("prompt") or call_args.args[0]
        assert "transcriptor clínico" in prompt.lower()


@pytest.mark.asyncio
async def test_project_auto_draft_when_all_done(client, db_session):
    data = await _create_test_data(db_session, "worker-draft@test.com")
    doc_id = data["doc_id"]

    fake_text = "# Contenido del PDF\n\nPaciente de 45 años con dolor..."

    with (
        patch(
            "app.workers.extraction_worker.get_storage_backend"
        ) as mock_storage,
        patch(
            "app.workers.extraction_worker.pymupdf4llm.to_markdown"
        ) as mock_md,
        patch(
            "app.workers.extraction_worker.OpenRouterClient"
        ) as MockAI,
    ):
        mock_storage.return_value.read_bytes = AsyncMock(
            return_value=b"%PDF-1.4 fake"
        )
        mock_md.return_value = fake_text

        mock_ai_instance = MagicMock()
        mock_ai_instance.generate_with_continuations = AsyncMock(
            return_value=_make_ai_result()
        )
        MockAI.return_value = mock_ai_instance

        await extract_document({}, document_id=doc_id, _db=db_session)

        project = (
            await db_session.execute(
                select(Project).where(Project.id == data["project_id"])
            )
        ).scalar_one()
        assert project.status == ProjectStatus.DRAFT


@pytest.mark.asyncio
async def test_project_stays_extracting_with_pending_docs(client, db_session):
    data = await _create_test_data(db_session, "worker-still@test.com")
    doc_id = data["doc_id"]

    doc2 = SourceDocument(
        project_id=data["project_id"],
        filename="extra.pdf",
        file_path="local://proj1/extra.pdf",
        file_size=2048,
        document_type="article",
        status=SourceDocumentStatus.UPLOADED,
    )
    db_session.add(doc2)
    await db_session.commit()

    fake_text = "# Contenido del PDF"

    with (
        patch(
            "app.workers.extraction_worker.get_storage_backend"
        ) as mock_storage,
        patch(
            "app.workers.extraction_worker.pymupdf4llm.to_markdown"
        ) as mock_md,
        patch(
            "app.workers.extraction_worker.OpenRouterClient"
        ) as MockAI,
    ):
        mock_storage.return_value.read_bytes = AsyncMock(
            return_value=b"%PDF-1.4 fake"
        )
        mock_md.return_value = fake_text

        mock_ai_instance = MagicMock()
        mock_ai_instance.generate_with_continuations = AsyncMock(
            return_value=_make_ai_result()
        )
        MockAI.return_value = mock_ai_instance

        await extract_document({}, document_id=doc_id, _db=db_session)

        project = (
            await db_session.execute(
                select(Project).where(Project.id == data["project_id"])
            )
        ).scalar_one()
        assert project.status == ProjectStatus.EXTRACTING
