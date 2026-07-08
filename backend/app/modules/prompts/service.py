from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prompt_template import PromptTemplate


async def list_prompts(db: AsyncSession) -> list[PromptTemplate]:
    result = await db.execute(
        select(PromptTemplate)
        .where(PromptTemplate.is_active == True)
        .order_by(PromptTemplate.name)
    )
    return list(result.scalars().all())


async def get_active_prompt(db: AsyncSession, name: str) -> PromptTemplate:
    result = await db.execute(
        select(PromptTemplate).where(
            PromptTemplate.name == name,
            PromptTemplate.is_active == True,
        )
    )
    prompt = result.scalar_one_or_none()
    if prompt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prompt '{name}' no encontrado",
        )
    return prompt


async def update_prompt(
    db: AsyncSession,
    name: str,
    content: str,
    description: str | None = None,
) -> PromptTemplate:
    result = await db.execute(
        select(PromptTemplate).where(
            PromptTemplate.name == name,
            PromptTemplate.is_active == True,
        )
    )
    current = result.scalar_one_or_none()
    if current is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prompt '{name}' no encontrado",
        )

    current.is_active = False

    new_prompt = PromptTemplate(
        id=str(uuid4()),
        name=name,
        type=current.type,
        content=content,
        version=current.version + 1,
        is_active=True,
        description=description,
    )
    db.add(new_prompt)
    await db.commit()
    await db.refresh(new_prompt)
    return new_prompt
