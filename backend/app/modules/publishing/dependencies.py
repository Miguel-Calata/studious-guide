from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.project import Project
from app.models.user import User
from app.modules.auth.dependencies import get_current_user


async def get_project_for_publish(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Project:
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
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
