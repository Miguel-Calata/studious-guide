from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.project import Project
from app.models.source_document import SourceDocument
from app.models.user import User
from app.modules.auth.dependencies import get_current_user
from app.modules.documents.dependencies import (
    get_document_or_404,
    get_project_for_documents,
)
from app.modules.documents.schemas import (
    DocumentResponse,
    DocumentUploadResponse,
)
from app.modules.documents.service import (
    delete_document,
    list_project_documents,
    resolve_file_path,
    upload_documents,
)

router = APIRouter(tags=["Documents"])


@router.post(
    "/projects/{project_id}/documents",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload(
    project: Project = Depends(get_project_for_documents),
    files: list[UploadFile] = [],
    document_type: str = Query(default="article", enum=["bmj", "guideline", "article"]),
    db: AsyncSession = Depends(get_db),
) -> dict:
    docs = await upload_documents(db, project.id, files, document_type)
    return {"documents": docs}


@router.get(
    "/projects/{project_id}/documents",
    response_model=list[DocumentResponse],
)
async def list_all(
    project: Project = Depends(get_project_for_documents),
    db: AsyncSession = Depends(get_db),
) -> list[SourceDocument]:
    return await list_project_documents(db, project.id)


@router.get(
    "/documents/{document_id}",
    response_model=DocumentResponse,
)
async def get_one(
    document: SourceDocument = Depends(get_document_or_404),
) -> SourceDocument:
    return document


@router.delete(
    "/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete(
    document: SourceDocument = Depends(get_document_or_404),
    db: AsyncSession = Depends(get_db),
) -> None:
    await delete_document(db, document)


@router.get(
    "/documents/{document_id}/download",
)
async def download(
    document: SourceDocument = Depends(get_document_or_404),
) -> FileResponse:
    file_path = resolve_file_path(document)
    if not file_path.exists():
        return FileResponse(
            path="/dev/null",
            status_code=404,
            media_type="application/json",
        )
    return FileResponse(
        path=str(file_path),
        filename=document.filename,
        media_type="application/pdf",
    )
