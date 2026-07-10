from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.compendium_section import CompendiumSection, SectionStatus
from app.models.notion_config import NotionConfig
from app.models.project import Project, ProjectStatus
from app.models.user import User
from app.modules.notion.client import NotionClientWrapper
from app.modules.notion.oauth_service import try_refresh_token
from app.modules.notion.schemas import NotionConfigUpdate


def needs_reconnect(config: NotionConfig) -> bool:
    """Check if the connection needs manual re-authentication.

    Returns True when the access token is expired (or about to expire) AND
    no refresh token is available to recover it.
    """
    if not config.is_connected:
        return False
    if config.token_expires_at and config.token_expires_at < datetime.now(UTC):
        if not config.refresh_token:
            return True
    return False


async def get_notion_config(
    db: AsyncSession,
    user: User,
) -> NotionConfig | None:
    result = await db.execute(
        select(NotionConfig).where(NotionConfig.user_id == user.id)
    )
    return result.scalar_one_or_none()


async def update_notion_config(
    db: AsyncSession,
    user: User,
    update: NotionConfigUpdate,
) -> NotionConfig:
    config = await get_notion_config(db, user)
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No hay configuración de Notion. Conéctate primero.",
        )

    if update.default_parent_page_id is not None:
        config.default_parent_page_id = update.default_parent_page_id
    if update.workspace_name is not None:
        config.workspace_name = update.workspace_name

    await db.commit()
    await db.refresh(config)
    return config


async def ensure_fresh_token(
    db: AsyncSession,
    config: NotionConfig,
) -> None:
    """Ensure the access token is not expired.

    If expired and a refresh token exists, attempt to refresh.
    If refresh fails, mark as disconnected and raise 409.
    """
    if not config.is_connected:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No hay conexión con Notion",
        )

    if config.token_expires_at and config.token_expires_at < datetime.now(UTC):
        success = await try_refresh_token(db, config)
        if not success:
            config.is_connected = False
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="La sesión de Notion ha expirado. Reconecta tu cuenta.",
            )


async def search_pages(
    db: AsyncSession,
    config: NotionConfig,
    query: str,
) -> list[dict]:
    await ensure_fresh_token(db, config)
    wrapper = NotionClientWrapper(config.api_key)
    return await wrapper.search(query)


async def disconnect_notion(
    db: AsyncSession,
    user: User,
) -> None:
    """Disconnect Notion for the given user."""
    config = await get_notion_config(db, user)
    if config is not None:
        config.clear_tokens()
        await db.commit()


async def publish_compendium_to_notion(
    db: AsyncSession,
    project: Project,
    config: NotionConfig,
    parent_page_id: str | None = None,
) -> dict:
    await ensure_fresh_token(db, config)

    if project.status not in (ProjectStatus.REVIEW, ProjectStatus.COMPLETED):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"El proyecto no se puede publicar (estado: {project.status})",
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
        names = ", ".join(f"{s.section_number}. {s.section_name}" for s in incomplete)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Secciones incompletas: {names}",
        )

    target_parent = parent_page_id or config.default_parent_page_id
    if not target_parent:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se especificó parent_page_id y no hay uno por defecto.",
        )

    wrapper = NotionClientWrapper(config.api_key)

    root_content = _build_root_content(project, sections)
    compendium_page_id = await wrapper.create_page(
        parent_page_id=target_parent,
        title=project.name,
        content_markdown=root_content,
    )

    published = []
    for section in sections:
        section_md = f"# {section.section_name}\n\n{section.content}"
        if section.notion_page_id:
            await wrapper.update_page(section.notion_page_id, section_md)
            page_id = section.notion_page_id
        else:
            page_id = await wrapper.create_page(
                parent_page_id=compendium_page_id,
                title=f"{section.section_number:02d} — {section.section_name}",
                content_markdown=section.content,
            )
            section.notion_page_id = page_id
        published.append(
            {
                "section_number": section.section_number,
                "section_name": section.section_name,
                "notion_page_id": page_id,
            }
        )

    await db.commit()

    return {
        "project_id": str(project.id),
        "compendium_page_id": compendium_page_id,
        "sections_published": published,
        "notion_url": f"https://www.notion.so/{compendium_page_id.replace('-', '')}",
    }


def _build_root_content(
    project: Project,
    sections: list[CompendiumSection],
) -> str:
    lines = [
        f"# {project.name}",
        "",
        f"> 📅 **Publicado:** {datetime.now(UTC).strftime('%Y-%m-%d')}",
        "",
    ]
    if project.description:
        lines.append(f"**Descripción:** {project.description}")
        lines.append("")
    lines.append(f"**Secciones:** {len(sections)}")
    lines.append("")
    lines.append("## Índice de secciones")
    lines.append("")
    for s in sections:
        lines.append(f"- {s.section_number:02d}. {s.section_name}")
    lines.append("")
    return "\n".join(lines)
