import { api } from './client'
import type {
  Extraction,
  ExtractAllResponse,
  RetryResponse,
  ExtractionStatusResponse,
} from '@/types/extraction'

export function extractAllForProject(
  projectId: string,
  body?: { extraction_model?: string }
): Promise<ExtractAllResponse> {
  return api.post<ExtractAllResponse>(`/projects/${projectId}/extract-all`, body)
}

export function getExtraction(id: string): Promise<Extraction> {
  return api.get<Extraction>(`/extractions/${id}`)
}

export function getExtractionStatus(
  id: string
): Promise<ExtractionStatusResponse> {
  return api.get<ExtractionStatusResponse>(`/extractions/${id}/status`)
}

export function retryExtraction(id: string): Promise<RetryResponse> {
  return api.post<RetryResponse>(`/extractions/${id}/retry`)
}
