from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.compendium_section import CompendiumSection, SectionStatus
from app.models.project import Project, ProjectStatus
from app.services.storage import StorageBackend


def assemble_markdown(project_name: str, sections: list[CompendiumSection]) -> str:
    parts = [f"# {project_name}\n"]
    for section in sorted(sections, key=lambda s: s.section_number):
        parts.append("\n---\n")
        parts.append(f"\n{section.content.strip()}\n")
    parts.append("\n---\n")
    return "".join(parts)


async def publish_compendium(
    db: AsyncSession,
    project: Project,
    storage: StorageBackend,
) -> dict:
    if project.status not in (ProjectStatus.REVIEW, ProjectStatus.COMPLETED):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"El proyecto no se puede publicar "
                f"(estado actual: {project.status})"
            ),
        )

    result = await db.execute(
        select(CompendiumSection)
        .where(CompendiumSection.project_id == project.id)
        .order_by(CompendiumSection.section_number)
    )
    sections = list(result.scalars().all())

    if len(sections) < 11:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Faltan secciones del compendio ({len(sections)}/11)",
        )

    incomplete = [
        s
        for s in sections
        if s.status not in (SectionStatus.COMPLETED, SectionStatus.APPROVED)
    ]
    if incomplete:
        names = ", ".join(
            f"{s.section_number}. {s.section_name}" for s in incomplete
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Secciones incompletas: {names}",
        )

    markdown_content = assemble_markdown(project.name, sections)
    content_bytes = markdown_content.encode("utf-8")
    key = f"compendiums/{project.slug}.md"

    await storage.save_bytes(key, content_bytes)

    project.s3_key = key
    project.public_url = f"/public/compendiums/{project.slug}/download"
    project.is_published = True

    if project.status == ProjectStatus.REVIEW:
        project.set_status(ProjectStatus.COMPLETED)

    await db.commit()
    await db.refresh(project)

    return {
        "project_id": str(project.id),
        "slug": project.slug,
        "public_url": project.public_url,
        "sections_included": len(sections),
        "project_status": project.status,
    }


async def list_public_compendiums(
    db: AsyncSession,
) -> list[dict]:
    result = await db.execute(
        select(Project)
        .where(Project.is_published.is_(True))
        .options(selectinload(Project.sections))
        .order_by(Project.updated_at.desc())
    )
    projects = list(result.scalars().all())

    return [
        {
            "slug": p.slug,
            "name": p.name,
            "description": p.description,
            "section_count": len(p.sections),
            "published_at": p.updated_at,
        }
        for p in projects
    ]


async def get_public_compendium(
    db: AsyncSession,
    slug: str,
) -> dict:
    result = await db.execute(
        select(Project)
        .where(Project.slug == slug, Project.is_published.is_(True))
        .options(selectinload(Project.sections))
    )
    project = result.scalar_one_or_none()

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Compendio no encontrado",
        )

    sections = sorted(project.sections, key=lambda s: s.section_number)
    return {
        "slug": project.slug,
        "name": project.name,
        "description": project.description,
        "section_count": len(sections),
        "sections": [
            {"section_number": s.section_number, "section_name": s.section_name}
            for s in sections
        ],
        "published_at": project.updated_at,
        "public_url": project.public_url,
    }


async def get_public_section(
    db: AsyncSession,
    slug: str,
    section_number: int,
) -> CompendiumSection:
    result = await db.execute(
        select(Project).where(
            Project.slug == slug, Project.is_published.is_(True)
        )
    )
    project = result.scalar_one_or_none()

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Compendio no encontrado",
        )

    result = await db.execute(
        select(CompendiumSection).where(
            CompendiumSection.project_id == project.id,
            CompendiumSection.section_number == section_number,
        )
    )
    section = result.scalar_one_or_none()

    if section is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sección {section_number} no encontrada",
        )

    return section


async def download_compendium(
    db: AsyncSession,
    slug: str,
    storage: StorageBackend,
) -> tuple[str, bytes]:
    result = await db.execute(
        select(Project).where(
            Project.slug == slug, Project.is_published.is_(True)
        )
    )
    project = result.scalar_one_or_none()

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Compendio no encontrado",
        )

    key = f"local://compendiums/{project.slug}.md"
    content = await storage.read_bytes(key)
    filename = f"{project.slug}.md"
    return filename, content
