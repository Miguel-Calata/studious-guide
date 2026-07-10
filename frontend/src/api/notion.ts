import { api } from '@/api/client'
import type {
  NotionStatusResponse,
  NotionOAuthStartResponse,
  NotionSearchResult,
  PublishNotionResponse,
} from '@/types/notion'

export function getNotionStatus(): Promise<NotionStatusResponse> {
  return api.get<NotionStatusResponse>('/notion/status')
}

export async function startNotionOAuth(): Promise<NotionOAuthStartResponse> {
  return api.get<NotionOAuthStartResponse>('/notion/oauth/start')
}

export function disconnectNotion(): Promise<void> {
  return api.post<void>('/notion/disconnect')
}

export function searchNotionPages(
  query: string
): Promise<NotionSearchResult[]> {
  return api.get<NotionSearchResult[]>(
    `/notion/search?query=${encodeURIComponent(query)}`
  )
}

export function updateNotionConfig(body: {
  default_parent_page_id?: string
  workspace_name?: string
}): Promise<NotionStatusResponse> {
  return api.put<NotionStatusResponse>('/notion/config', body)
}

export function publishToNotion(
  projectId: string,
  parentPageId?: string
): Promise<PublishNotionResponse> {
  return api.post<PublishNotionResponse>(
    `/projects/${projectId}/publish/notion`,
    parentPageId ? { parent_page_id: parentPageId } : null
  )
}
