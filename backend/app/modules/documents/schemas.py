from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class DocumentCreate(BaseModel):
    document_type: Literal["bmj", "guideline", "article"] = "article"


class DocumentResponse(BaseModel):
    id: str
    project_id: str
    filename: str
    file_size: int
    document_type: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentUploadResponse(BaseModel):
    documents: list[DocumentResponse]
