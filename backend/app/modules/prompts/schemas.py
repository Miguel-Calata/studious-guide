from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class PromptResponse(BaseModel):
    id: str
    name: str
    type: str
    content: str
    version: int
    is_active: bool
    description: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PromptUpdate(BaseModel):
    content: str
    description: str | None = None
