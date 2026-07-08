import { api, uploadFile } from './client'
import type {
  DocumentType,
  DocumentUploadResponse,
  SourceDocument,
} from '@/types/document'

export function getDocuments(projectId: string): Promise<SourceDocument[]> {
  return api.get<SourceDocument[]>(`/projects/${projectId}/documents`)
}

export async function uploadDocuments(
  projectId: string,
  files: File[],
  documentType: DocumentType
): Promise<DocumentUploadResponse> {
  const formData = new FormData()
  for (const file of files) {
    formData.append('files', file)
  }
  formData.append('document_type', documentType)
  return uploadFile<DocumentUploadResponse>(
    `/projects/${projectId}/documents`,
    formData
  )
}

export function deleteDocument(documentId: string): Promise<void> {
  return api.delete<void>(`/documents/${documentId}`)
}
