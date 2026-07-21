"""
Router para gestión de ecos maps (Tarea 3).

Endpoints:
  POST   /api/v1/pathologies/{key}/ecos-map:propose
          → genera borrador vía mini-prompt LLM (draft, no activo)
  POST   /api/v1/ecos-maps/{id}/approve
          → aprueba y activa un borrador (desactiva anteriores)
  GET    /api/v1/pathologies/{key}/ecos-map
          → mapa aprobado activo actual
  GET    /api/v1/pathologies/{key}/ecos-maps
          → historial de todas las versiones
"""


from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.ecos_map import EcosMap
from app.modules.ai_gateway.openrouter_client import OpenRouterClient
from app.modules.auth.dependencies import get_current_user
from app.modules.prompts.ecos_service import (
    approve_ecos_map,
    get_active_ecos_map,
    propose_ecos_map,
)

router = APIRouter(tags=["Ecos Maps"])


@router.post(
    "/pathologies/{key}/ecos-map:propose",
    status_code=status.HTTP_201_CREATED,
)
async def propose_eco_map(
    key: str,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _user=Depends(get_current_user)  # noqa: B008,
) -> dict:
    """
    Genera un borrador de ecos map para una patología nueva usando
    el mini-prompt 'ecos_map_autopopulate'. El borrador queda en
    estado `draft`; requiere aprobación humana explícita.
    """
    # El `key` es el slug normalizado; el pathology_name humano se
    # reconstruye capitalizando para el LLM.
    pathology_name = key.replace("-", " ").title()
    ai = OpenRouterClient()
    eco_map = await propose_ecos_map(db, ai, pathology_name)
    return _serialize(eco_map)


@router.post("/ecos-maps/{ecos_map_id}/approve")
async def approve_eco_map(
    ecos_map_id: str,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    user=Depends(get_current_user)  # noqa: B008,
) -> dict:
    eco_map = await approve_ecos_map(db, ecos_map_id, str(user.id))
    return _serialize(eco_map)


@router.get("/pathologies/{key}/ecos-map")
async def get_active_eco_map(
    key: str,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _user=Depends(get_current_user)  # noqa: B008,
) -> dict:
    eco_map = await get_active_ecos_map(db, key)
    if eco_map is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"No existe ecos_map aprobado activo para '{key}'."
            ),
        )
    return _serialize(eco_map)


@router.get("/pathologies/{key}/ecos-maps")
async def list_eco_maps(
    key: str,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _user=Depends(get_current_user)  # noqa: B008,
) -> list[dict]:
    result = await db.execute(
        select(EcosMap)
        .where(EcosMap.pathology_key == key)
        .order_by(EcosMap.version.desc())
    )
    return [_serialize(m) for m in result.scalars().all()]


def _serialize(eco_map: EcosMap) -> dict:
    return {
        "id": eco_map.id,
        "pathology_key": eco_map.pathology_key,
        "pathology_name": eco_map.pathology_name,
        "version": eco_map.version,
        "status": eco_map.status,
        "origin": eco_map.origin,
        "is_active": eco_map.is_active,
        "sections": eco_map.sections,
        "description": eco_map.description,
        "approved_by": eco_map.approved_by,
        "approved_at": (
            eco_map.approved_at.isoformat() if eco_map.approved_at else None
        ),
        "created_at": eco_map.created_at.isoformat(),
        "updated_at": eco_map.updated_at.isoformat(),
    }
