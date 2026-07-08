from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.project import Project
from app.models.user import User
from app.modules.auth.dependencies import get_current_user
from app.modules.projects.dependencies import get_project_or_404
from app.modules.projects.schemas import (
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
)
from app.modules.projects.service import (
    archive_project,
    create_project,
    list_active_projects,
    update_project,
)

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create(
    data: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Project:
    return await create_project(db, current_user.id, data)


@router.get("/", response_model=list[ProjectResponse])
async def list_all(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Project]:
    return await list_active_projects(db, current_user.id)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_one(
    project: Project = Depends(get_project_or_404),
) -> Project:
    return project


@router.put("/{project_id}", response_model=ProjectResponse)
async def update(
    data: ProjectUpdate,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
) -> Project:
    return await update_project(db, project, data)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
) -> None:
    await archive_project(db, project)
