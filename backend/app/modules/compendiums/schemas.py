from datetime import datetime

from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    gemini_model: str | None = Field(
        default=None,
        description="OpenRouter model ID for gemini-powered sections. None = default.",
    )
    claude_model: str | None = Field(
        default=None,
        description="OpenRouter model ID for claude-powered sections. None = default.",
    )


class SectionResponse(BaseModel):
    id: str
    project_id: str
    section_number: int
    section_name: str
    content: str
    model_used: str | None
    dosification: str
    input_tokens: int | None
    output_tokens: int | None
    cost_usd: float | None
    status: str
    prompt_version: str | None
    ecos_map_version: str | None
    error_message: str | None
    is_stale: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SectionUpdate(BaseModel):
    content: str


class MergeResponse(BaseModel):
    project_id: str
    merged_char_count: int
    extraction_count: int
    project_status: str
    warnings: list[str] = Field(default_factory=list)
    ecos_map_enqueued: bool = Field(
        default=False,
        description="True si se encoló un auto-propose de ecos map",
    )


class GenerateResponse(BaseModel):
    project_id: str
    sections_created: int
    project_status: str
