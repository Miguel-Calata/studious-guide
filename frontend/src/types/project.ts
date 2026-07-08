export type ProjectStatus =
  | 'draft'
  | 'extracting'
  | 'generating'
  | 'review'
  | 'completed'
  | 'archived'

export interface Project {
  id: string
  name: string
  slug: string
  description: string | null
  status: ProjectStatus
  merged_content: string | null
  is_published: boolean
  public_url: string | null
  created_at: string
  updated_at: string
}

export interface ProjectCreateRequest {
  name: string
  description?: string
}
