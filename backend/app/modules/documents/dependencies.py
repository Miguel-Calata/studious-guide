from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.project import Project
from app.models.source_document import SourceDocument
from app.models.user import User
from app.modules.auth.dependencies import get_current_user
from app.modules.documents.service import get_document


async def get_project_for_documents(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Project:
    from sqlalchemy import select

    result = await db.execute(
        select(Project).where(
            Project.id == str(project_id),
            Project.user_id == current_user.id,
        )
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proyecto no encontrado",
        )
    return project


async def get_document_or_404(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SourceDocument:
    doc = await get_document(db, str(document_id))

    from sqlalchemy import select

    result = await db.execute(
        select(Project).where(
            Project.id == doc.project_id,
            Project.user_id == current_user.id,
        )
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documento no encontrado",
        )
    return doc
