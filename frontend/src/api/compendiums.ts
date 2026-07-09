import { api } from './client'
import type {
  CompendiumSection,
  MergeResponse,
  GenerateResponse,
  SectionUpdate,
} from '@/types/compendium'

export function mergeProject(projectId: string): Promise<MergeResponse> {
  return api.post<MergeResponse>(`/projects/${projectId}/merge`)
}

export function generateProject(
  projectId: string,
  body?: { gemini_model?: string; claude_model?: string }
): Promise<GenerateResponse> {
  return api.post<GenerateResponse>(`/projects/${projectId}/generate`, body)
}

export function getSections(
  projectId: string
): Promise<CompendiumSection[]> {
  return api.get<CompendiumSection[]>(`/projects/${projectId}/sections`)
}

export function getSection(id: string): Promise<CompendiumSection> {
  return api.get<CompendiumSection>(`/sections/${id}`)
}

export function updateSection(
  id: string,
  body: SectionUpdate
): Promise<CompendiumSection> {
  return api.put<CompendiumSection>(`/sections/${id}`, body)
}

export function regenerateSection(
  id: string
): Promise<CompendiumSection> {
  return api.post<CompendiumSection>(`/sections/${id}/regenerate`)
}
