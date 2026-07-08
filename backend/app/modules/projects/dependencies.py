from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.project import Project
from app.models.user import User
from app.modules.auth.dependencies import get_current_user
from app.modules.projects.service import get_project


async def get_project_or_404(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Project:
    return await get_project(db, str(project_id), current_user.id)
