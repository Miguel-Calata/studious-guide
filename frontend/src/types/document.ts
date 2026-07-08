export type DocumentType = 'bmj' | 'guideline' | 'article'

export interface SourceDocument {
  id: string
  project_id: string
  filename: string
  file_size: number
  document_type: DocumentType
  status: string
  created_at: string
  updated_at: string
}

export interface DocumentUploadResponse {
  documents: SourceDocument[]
}
