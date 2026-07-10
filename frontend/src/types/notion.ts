export interface NotionStatusResponse {
  is_connected: boolean
  needs_reconnect: boolean
  workspace_name: string | null
  workspace_id: string | null
  owner_email: string | null
  connected_at: string | null
  default_parent_page_id: string | null
}

export interface NotionOAuthStartResponse {
  authorize_url: string
}

export interface NotionSearchResult {
  id: string
  title: string
  object: string
}

export interface NotionPageInfo {
  section_number: number
  section_name: string
  notion_page_id: string
}

export interface PublishNotionResponse {
  project_id: string
  compendium_page_id: string
  sections_published: NotionPageInfo[]
  notion_url: string
}

export interface ExportPublicNotionResponse {
  slug: string
  notion_page_id: string
  notion_url: string
}
