from pydantic import BaseModel


class NotionOAuthStartResponse(BaseModel):
    authorize_url: str


class NotionConfigUpdate(BaseModel):
    default_parent_page_id: str | None = None
    workspace_name: str | None = None


class NotionStatusResponse(BaseModel):
    is_connected: bool
    needs_reconnect: bool = False
    workspace_name: str | None = None
    workspace_id: str | None = None
    owner_email: str | None = None
    connected_at: str | None = None
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
