import re
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.extraction import Extraction, ExtractionStatus
from app.models.source_document import SourceDocument
from app.services.storage import get_storage_backend

_ALLOWED_EXTENSIONS = {".pdf"}
_CONTENT_TYPE = "application/pdf"


def _sanitize_filename(filename: str) -> str:
    name = Path(filename).stem
    name = re.sub(r"[^\w\s.-]", "", name)
    name = re.sub(r"\s+", "_", name)
    name = name.strip("._")
    if not name:
        name = "document"
    return f"{name}.pdf"


def _validate_file(file: UploadFile) -> None:
    ext = Path(file.filename or "").suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Extensión no permitida: {ext}. Solo se aceptan archivos .pdf",
        )


async def _validate_file_size(file: UploadFile) -> None:
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    content = await file.read()
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"El archivo excede el tamaño máximo de {settings.max_upload_size_mb}MB",
        )
    await file.seek(0)


async def upload_documents(
    db: AsyncSession,
    project_id: str,
    files: list[UploadFile],
    document_type: str = "article",
) -> list[SourceDocument]:
    if not files:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Debe proporcionar al menos un archivo",
        )

    if len(files) > settings.max_files_per_upload:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Máximo {settings.max_files_per_upload} archivos por subida",
        )

    storage = get_storage_backend()
    created: list[SourceDocument] = []

    for file in files:
        _validate_file(file)
        await _validate_file_size(file)

        document_id = str(uuid4())
        sanitized_name = _sanitize_filename(file.filename or "document.pdf")
        file_uri = await storage.save(file, project_id, document_id)

        doc = SourceDocument(
            id=document_id,
            project_id=project_id,
            filename=sanitized_name,
            file_path=file_uri,
            file_size=file.size or 0,
            document_type=document_type,
            status="uploaded",
        )
        db.add(doc)
        created.append(doc)

    await db.commit()
    for doc in created:
        await db.refresh(doc)
    return created


async def list_project_documents(
    db: AsyncSession, project_id: str
) -> list[dict]:
    result = await db.execute(
        select(SourceDocument)
        .where(SourceDocument.project_id == project_id)
        .order_by(SourceDocument.created_at.desc())
    )
    documents = list(result.scalars().all())

    doc_ids = [d.id for d in documents]
    if not doc_ids:
        return []

    ext_result = await db.execute(
        select(Extraction).where(
            Extraction.source_document_id.in_(doc_ids),
            Extraction.status == ExtractionStatus.FAILED,
        )
    )
    errors_by_doc: dict[str, str] = {}
    for ext in ext_result.scalars().all():
        if ext.error_message:
            errors_by_doc[ext.source_document_id] = ext.error_message

    return [
        {
            "id": d.id,
            "project_id": d.project_id,
            "filename": d.filename,
            "file_size": d.file_size,
            "document_type": d.document_type,
            "status": d.status,
            "error_message": errors_by_doc.get(d.id),
            "created_at": d.created_at,
            "updated_at": d.updated_at,
        }
        for d in documents
    ]


async def get_document(
    db: AsyncSession, document_id: str
) -> SourceDocument:
    result = await db.execute(
        select(SourceDocument).where(SourceDocument.id == document_id)
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documento no encontrado",
        )
    return doc


async def delete_document(
    db: AsyncSession, document: SourceDocument
) -> None:
    storage = get_storage_backend()
    await storage.delete(document.file_path)
    await db.delete(document)
    await db.commit()


def resolve_file_path(document: SourceDocument) -> Path:
    storage = get_storage_backend()
    return storage.get_local_path(document.file_path)
