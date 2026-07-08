export type SectionStatus =
  | 'pending'
  | 'processing'
  | 'completed'
  | 'failed'
  | 'approved'

export type Dosification = 'STANDARD' | 'HIGH' | 'MAX'

export interface CompendiumSection {
  id: string
  project_id: string
  section_number: number
  section_name: string
  content: string
  model_used: string | null
  dosification: Dosification
  input_tokens: number | null
  output_tokens: number | null
  cost_usd: number | null
  status: SectionStatus
  prompt_version: string | null
  error_message: string | null
  created_at: string
  updated_at: string
}

export interface SectionUpdate {
  content: string
}

export interface MergeResponse {
  project_id: string
  merged_char_count: number
  extraction_count: number
  project_status: string
}

export interface GenerateResponse {
  project_id: string
  sections_created: number
  project_status: string
}

export const TOTAL_SECTIONS = 11
