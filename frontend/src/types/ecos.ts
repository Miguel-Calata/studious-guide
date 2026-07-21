export type EcosMapStatus = 'draft' | 'approved'
export type EcosMapOrigin = 'seed' | 'autopopulated' | 'manual'

/** Estado UI compuesto (no viene del backend). */
export type EcosMapUiState =
  | 'no_map'
  | 'proposing'
  | 'draft_pending'
  | 'approved'

export interface EcosMap {
  id: string
  pathology_key: string
  pathology_name: string
  version: number
  status: EcosMapStatus
  origin: EcosMapOrigin
  is_active: boolean
  sections: Record<string, string[]>
  description: string | null
  approved_by: string | null
  approved_at: string | null
  created_at: string
  updated_at: string
}

export interface EcosMapUpdateRequest {
  sections: Record<string, string[]>
  description?: string | null
}

export interface EcosMapUpdateResponse {
  ecos_map: EcosMap
  warnings: string[]
}

export const TOTAL_ECOS_SECTIONS = 11

/** Nombres de sección usados como fallback en la UI. */
export const ECOS_SECTION_NAMES: Record<number, string> = {
  1: 'DESCRIPCIÓN Y EPIDEMIOLOGÍA',
  2: 'CLASIFICACIÓN',
  3: 'FISIOPATOLOGÍA',
  4: 'CUADRO CLÍNICO',
  5: 'DIAGNÓSTICO',
  6: 'ESCALAS Y BIOMARCADORES',
  7: 'MANEJO INICIAL',
  8: 'FARMACOLOGÍA',
  9: 'MANEJO AVANZADO',
  10: 'POBLACIONES ESPECIALES',
  11: 'PERIOPERATORIO',
}
