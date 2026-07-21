from datetime import datetime

from pydantic import BaseModel, Field


class PublishResponse(BaseModel):
    project_id: str
    slug: str
    public_url: str
    sections_included: int
    project_status: str


class PublicCompendiumListItem(BaseModel):
    slug: str
    name: str
    description: str | None
    section_count: int
    published_at: datetime | None

    model_config = {"from_attributes": True}


class PublicSectionSummary(BaseModel):
    section_number: int
    section_name: str


class PublicCompendiumDetail(BaseModel):
    slug: str
    name: str
    description: str | None
    section_count: int
    sections: list[PublicSectionSummary]
    published_at: datetime | None
    public_url: str | None

    model_config = {"from_attributes": True}


class PublicSectionResponse(BaseModel):
    section_number: int
    section_name: str
    content: str
    dosification: str


class SourceDocumentPublic(BaseModel):
    id: str
    filename: str
    document_type: str
    file_size: int
    uploaded_at: datetime = Field(validation_alias="created_at")

    model_config = {"from_attributes": True, "populate_by_name": True}
