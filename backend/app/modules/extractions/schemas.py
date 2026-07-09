from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ExtractRequest(BaseModel):
    extraction_model: str | None = Field(
        default=None,
        description="OpenRouter model ID. None = default.",
    )


class ExtractionResponse(BaseModel):
    id: str
    source_document_id: str
    content: str
    model_used: str | None
    input_tokens: int | None
    output_tokens: int | None
    cost_usd: float | None
    status: str
    error_message: str | None
    audit_completed: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ExtractionStatusResponse(BaseModel):
    id: str
    status: str
    input_tokens: int | None
    output_tokens: int | None
    error_message: str | None

    model_config = {"from_attributes": True}


class RetryResponse(BaseModel):
    id: str
    status: str
    message: str


class ExtractAllResponse(BaseModel):
    project_id: str
    total_documents: int
    enqueued: int
    retried: int
    skipped: int
    project_status: str
