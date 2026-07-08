from datetime import datetime

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, min_length=1, max_length=2000)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, min_length=1, max_length=2000)


class ProjectResponse(BaseModel):
    id: str
    name: str
    slug: str
    description: str | None
    status: str
    merged_content: str | None
    is_published: bool
    public_url: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
