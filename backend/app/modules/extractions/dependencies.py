from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.extraction import Extraction
from app.models.project import Project
from app.models.source_document import SourceDocument
from app.models.user import User
from app.modules.auth.dependencies import get_current_user


async def _get_extraction_with_ownership(
    extraction_id: str,
    current_user: User,
    db: AsyncSession,
) -> Extraction:
    result = await db.execute(
        select(Extraction).where(Extraction.id == extraction_id)
    )
    extraction = result.scalar_one_or_none()
    if extraction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Extracción no encontrada",
        )

    result = await db.execute(
        select(Project).where(
            Project.id == SourceDocument.project_id,
            Project.user_id == current_user.id,
        ).where(SourceDocument.id == extraction.source_document_id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Extracción no encontrada",
        )
    return extraction


async def get_extraction_or_404(
    extraction_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Extraction:
    return await _get_extraction_with_ownership(extraction_id, current_user, db)


async def get_document_for_extract(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SourceDocument:
    result = await db.execute(
        select(SourceDocument).where(SourceDocument.id == document_id)
    )
    document = result.scalar_one_or_none()
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documento no encontrado",
        )

    result = await db.execute(
        select(Project).where(
            Project.id == document.project_id,
            Project.user_id == current_user.id,
        )
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documento no encontrado",
        )
    return document
