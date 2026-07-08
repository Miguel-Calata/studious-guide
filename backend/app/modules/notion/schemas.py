from pydantic import BaseModel


class NotionConnectRequest(BaseModel):
    api_key: str


class NotionConfigUpdate(BaseModel):
    default_parent_page_id: str | None = None
    workspace_name: str | None = None


class NotionStatusResponse(BaseModel):
    is_connected: bool
    workspace_name: str | None = None
    default_parent_page_id: str | None = None


class NotionSearchResult(BaseModel):
    id: str
    title: str
    object: str  # "page" or "database"


class PublishNotionRequest(BaseModel):
    parent_page_id: str | None = None


class NotionPageInfo(BaseModel):
    section_number: int
    section_name: str
    notion_page_id: str


class PublishNotionResponse(BaseModel):
    project_id: str
    compendium_page_id: str
    sections_published: list[NotionPageInfo]
    notion_url: str
