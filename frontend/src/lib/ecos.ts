import type { BadgeVariant } from '@/lib/pipeline'
import type { EcosMapUiState } from '@/types/ecos'
import { TOTAL_ECOS_SECTIONS } from '@/types/ecos'

/**
 * Deriva la pathology_key a partir del nombre del proyecto.
 * Espejo EXACTO de backend/app/modules/prompts/ecos_service.py:56-73.
 */
export function pathologyKeyFor(name: string): string {
  if (!name) return ''
  // NFKD strip combining marks (acentos, diacríticos)
  const nfkd = name.normalize('NFKD')
  const withoutAccents = nfkd.replace(/[\u0300-\u036f]/g, '')
  return withoutAccents
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

// --- Labels y variantes para la UI ---

const UI_STATE_LABELS: Record<EcosMapUiState, string> = {
  no_map: 'Sin mapa',
  proposing: 'Generando borrador…',
  draft_pending: 'Borrador pendiente',
  approved: 'Aprobado',
}

const UI_STATE_VARIANTS: Record<EcosMapUiState, BadgeVariant> = {
  no_map: 'muted',
  proposing: 'info',
  draft_pending: 'warning',
  approved: 'success',
}

export function ecosUiStateLabel(state: EcosMapUiState): string {
  return UI_STATE_LABELS[state]
}

export function ecosUiStateVariant(state: EcosMapUiState): BadgeVariant {
  return UI_STATE_VARIANTS[state]
}

/**
 * Convierte las secciones del ecos map a texto multilínea para
 * los Textareas (un eco por línea).
 */
export function ecosToTextareas(
  sections: Record<string, string[]>
): Record<string, string> {
  const result: Record<string, string> = {}
  for (let i = 1; i <= TOTAL_ECOS_SECTIONS; i++) {
    const key = String(i)
    result[key] = (sections[key] ?? []).join('\n')
  }
  return result
}

/**
 * Convierte los textareas de vuelta a listas de ecos.
 * Filtra líneas vacías; strip de bullets "-•" al inicio.
 */
export function textareasToEcos(
  textareas: Record<string, string>
): Record<string, string[]> {
  const result: Record<string, string[]> = {}
  for (let i = 1; i <= TOTAL_ECOS_SECTIONS; i++) {
    const key = String(i)
    const text = textareas[key] ?? ''
    result[key] = text
      .split('\n')
      .map((line) => line.replace(/^[-•*\s]+/, '').trim())
      .filter(Boolean)
  }
  return result
}
