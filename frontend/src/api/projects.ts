import { api } from './client'
import type { Project, ProjectCreateRequest } from '@/types/project'

export function getProjects(): Promise<Project[]> {
  return api.get<Project[]>('/projects')
}

export function getProject(id: string): Promise<Project> {
  return api.get<Project>(`/projects/${id}`)
}

export function createProject(data: ProjectCreateRequest): Promise<Project> {
  return api.post<Project>('/projects', data)
}

export function archiveProject(id: string): Promise<void> {
  return api.delete<void>(`/projects/${id}`)
}
