"""
Router para gestión de ecos maps (Tarea 3).

Endpoints:
  POST   /api/v1/pathologies/{key}/ecos-map:propose
          → genera borrador vía mini-prompt LLM (draft, no activo)
  POST   /api/v1/ecos-maps/{id}/approve
          → aprueba y activa un borrador (desactiva anteriores)
  PUT    /api/v1/ecos-maps/{id}
          → edita un borrador (draft-only)
  GET    /api/v1/pathologies/{key}/ecos-map
          → mapa aprobado activo actual
  GET    /api/v1/pathologies/{key}/ecos-maps
          → historial de todas las versiones
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.ecos_map import EcosMap
from app.modules.ai_gateway.openrouter_client import OpenRouterClient
from app.modules.auth.dependencies import get_current_user
from app.modules.prompts.ecos_service import (
    EcoMapNotEditableError,
    EcoMapNotFoundError,
    EcoMapProposalError,
    approve_ecos_map,
    find_project_for_pathology,
    get_active_ecos_map,
    get_pending_draft,
    propose_ecos_map,
    update_ecos_map_draft,
)

router = APIRouter(tags=["Ecos Maps"])


class EcosMapProposeRequest(BaseModel):
    model: str | None = Field(
        default=None,
        description="OpenRouter model ID. None = default.",
    )


class EcosMapUpdateRequest(BaseModel):
    sections: dict[str, list[str]] = Field(
        ..., description="Ecos por sección: {'1': [...], ..., '11': [...]}"
    )
    description: str | None = Field(
        default=None, max_length=1000
    )


class EcosMapUpdateResponse(BaseModel):
    ecos_map: dict
    warnings: list[str] = Field(
        default_factory=list,
        description="Problemas de cobertura detectados (no bloquean)",
    )


@router.post(
    "/pathologies/{key}/ecos-map:propose",
    status_code=status.HTTP_201_CREATED,
)
async def propose_eco_map(
    key: str,
    body: EcosMapProposeRequest = EcosMapProposeRequest(),
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _user=Depends(get_current_user),  # noqa: B008
) -> dict:
    """
    Genera un borrador de ecos map para una patología usando el
    mini-prompt 'ecos_map_autopopulate'. El borrador queda en
    estado `draft`; requiere aprobación humana explícita.

    Si existe un proyecto con esta pathology_key, el propose es
    GROUNDED: usa el nombre real del proyecto y su merged_content
    (igual que el auto-propose tras merge). Si no existe proyecto
    (mapa preparado antes de crearlo), cae al nombre derivado de
    la key sin contenido fuente.
    """
    project = await find_project_for_pathology(db, key)
    if project is not None:
        pathology_name = project.name
        source_content = project.merged_content
    else:
        pathology_name = key.replace("-", " ").title()
        source_content = None

    ai = OpenRouterClient()
    try:
        eco_map = await propose_ecos_map(
            db, ai, pathology_name, source_content=source_content,
            model=body.model,
        )
    except EcoMapProposalError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from None
    except RuntimeError as exc:
        # Prompt autopopulate no sembrado (error de configuración)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from None
    return _serialize(eco_map)


@router.post("/ecos-maps/{ecos_map_id}/approve")
async def approve_eco_map(
    ecos_map_id: str,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    user=Depends(get_current_user),  # noqa: B008
) -> dict:
    try:
        eco_map = await approve_ecos_map(db, ecos_map_id, str(user.id))
    except EcoMapNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ecos_map '{ecos_map_id}' no encontrado",
        ) from None
    return _serialize(eco_map)


@router.put(
    "/ecos-maps/{ecos_map_id}",
    response_model=EcosMapUpdateResponse,
)
async def update_eco_map(
    ecos_map_id: str,
    body: EcosMapUpdateRequest,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _user=Depends(get_current_user),  # noqa: B008
) -> dict:
    """
    Edita un borrador de ecos map (draft-only). Devuelve el mapa
    actualizado y warnings de cobertura si los hay. El criterio
    del doctor manda: puede guardar con warnings.
    """
    try:
        eco_map, warnings = await update_ecos_map_draft(
            db, ecos_map_id, body.sections, body.description
        )
    except EcoMapNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ecos_map '{ecos_map_id}' no encontrado",
        ) from None
    except EcoMapNotEditableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from None
    return {"ecos_map": _serialize(eco_map), "warnings": warnings}


@router.get("/pathologies/{key}/ecos-map")
async def get_active_eco_map(
    key: str,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _user=Depends(get_current_user),  # noqa: B008
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
    _user=Depends(get_current_user),  # noqa: B008
) -> list[dict]:
    result = await db.execute(
        select(EcosMap)
        .where(EcosMap.pathology_key == key)
        .order_by(EcosMap.version.desc())
    )
    return [_serialize(m) for m in result.scalars().all()]


@router.get("/pathologies/{key}/ecos-map/pending-draft")
async def get_pending_draft_map(
    key: str,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _user=Depends(get_current_user),  # noqa: B008
) -> dict:
    """Devuelve el borrador pendiente (draft) más reciente, o 404."""
    draft = await get_pending_draft(db, key)
    if draft is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No hay borrador pendiente para '{key}'.",
        )
    return _serialize(draft)


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
        "model_used": eco_map.model_used,
        "approved_by": eco_map.approved_by,
        "approved_at": (
            eco_map.approved_at.isoformat() if eco_map.approved_at else None
        ),
        "created_at": eco_map.created_at.isoformat(),
        "updated_at": eco_map.updated_at.isoformat(),
    }
