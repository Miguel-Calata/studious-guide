from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.modules.auth.dependencies import get_current_user
from app.modules.prompts.schemas import PromptResponse, PromptUpdate
from app.modules.prompts.service import get_active_prompt, list_prompts, update_prompt

router = APIRouter(prefix="/prompts", tags=["Prompts"])


@router.get("/", response_model=list[PromptResponse])
async def list_all(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list:
    return await list_prompts(db)


@router.get("/{name}", response_model=PromptResponse)
async def get_one(
    name: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_active_prompt(db, name)


@router.put("/{name}", response_model=PromptResponse)
async def update(
    name: str,
    data: PromptUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await update_prompt(db, name, data.content, data.description)
