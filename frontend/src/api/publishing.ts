import { api } from '@/api/client'
import type { PublishResponse } from '@/types/publishing'

export function publishProject(projectId: string): Promise<PublishResponse> {
  return api.post<PublishResponse>(`/projects/${projectId}/publish`)
}
