from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.notion_config import NotionConfig
from app.modules.auth.dependencies import get_current_user
from app.modules.notion.service import needs_reconnect


async def get_notion_config(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotionConfig:
    result = await db.execute(
        select(NotionConfig).where(NotionConfig.user_id == current_user.id)
    )
    config = result.scalar_one_or_none()
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No hay conexión con Notion configurada",
        )
    if not config.is_connected:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La conexión con Notion no está activa",
        )
    if needs_reconnect(config):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La sesión de Notion ha expirado. Reconecta tu cuenta.",
        )
    return config
