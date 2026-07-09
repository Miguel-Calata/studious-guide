export interface NotionStatusResponse {
  is_connected: boolean
  workspace_name: string | null
  default_parent_page_id: string | null
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
