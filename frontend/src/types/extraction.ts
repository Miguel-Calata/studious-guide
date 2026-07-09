export type ExtractionStatus =
  | 'pending'
  | 'processing'
  | 'completed'
  | 'failed'

export interface Extraction {
  id: string
  source_document_id: string
  content: string
  model_used: string | null
  input_tokens: number | null
  output_tokens: number | null
  cost_usd: number | null
  status: ExtractionStatus
  error_message: string | null
  audit_completed: boolean
  created_at: string
  updated_at: string
}

export interface ExtractionStatusResponse {
  id: string
  status: ExtractionStatus
  input_tokens: number | null
  output_tokens: number | null
  error_message: string | null
}

export interface RetryResponse {
  id: string
  status: ExtractionStatus
  message: string
}

export interface ExtractAllResponse {
  project_id: string
  total_documents: number
  enqueued: number
  retried: number
  skipped: number
  project_status: string
}
