import re
import unicodedata

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project, ProjectStatus
from app.modules.projects.schemas import ProjectCreate, ProjectUpdate


def _slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


async def _generate_unique_slug(db: AsyncSession, name: str) -> str:
    base_slug = _slugify(name)
    slug = base_slug
    counter = 1
    while True:
        result = await db.execute(select(Project).where(Project.slug == slug))
        if result.scalar_one_or_none() is None:
            return slug
        slug = f"{base_slug}-{counter}"
        counter += 1


async def create_project(
    db: AsyncSession, user_id: str, data: ProjectCreate
) -> Project:
    slug = await _generate_unique_slug(db, data.name)
    project = Project(
        user_id=user_id,
        name=data.name,
        slug=slug,
        description=data.description,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


async def list_active_projects(
    db: AsyncSession, user_id: str
) -> list[Project]:
    result = await db.execute(
        select(Project)
        .where(Project.user_id == user_id, Project.status != "archived")
        .order_by(Project.created_at.desc())
    )
    return list(result.scalars().all())


async def get_project(
    db: AsyncSession, project_id: str, user_id: str
) -> Project:
    result = await db.execute(
        select(Project).where(
            Project.id == project_id, Project.user_id == user_id
        )
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proyecto no encontrado",
        )
    return project


async def update_project(
    db: AsyncSession, project: Project, data: ProjectUpdate
) -> Project:
    if data.name is not None:
        project.name = data.name
    if data.description is not None:
        project.description = data.description
    await db.commit()
    await db.refresh(project)
    return project


async def archive_project(db: AsyncSession, project: Project) -> Project:
    project.set_status(ProjectStatus.ARCHIVED)
    await db.commit()
    await db.refresh(project)
    return project
