import type { ProjectStatus } from '@/types/project'
import type { ExtractionStatus } from '@/types/extraction'
import type { SectionStatus, Dosification } from '@/types/compendium'

export type BadgeVariant =
  | 'default'
  | 'secondary'
  | 'destructive'
  | 'outline'
  | 'success'
  | 'info'
  | 'warning'
  | 'review'
  | 'muted'

// --- Extracción (estado de Extraction) ---
const EXTRACTION_STATUS_LABELS: Record<ExtractionStatus, string> = {
  pending: 'En cola',
  processing: 'Procesando',
  completed: 'Completada',
  failed: 'Fallida',
}

const EXTRACTION_STATUS_VARIANTS: Record<ExtractionStatus, BadgeVariant> = {
  pending: 'muted',
  processing: 'info',
  completed: 'success',
  failed: 'destructive',
}

export function extractionStatusLabel(status: ExtractionStatus): string {
  return EXTRACTION_STATUS_LABELS[status] ?? status
}

export function extractionStatusVariant(
  status: ExtractionStatus
): BadgeVariant {
  return EXTRACTION_STATUS_VARIANTS[status] ?? 'muted'
}

// --- Documento (estado de SourceDocument durante el pipeline) ---
export type DocumentStatus =
  | 'uploaded'
  | 'extracting'
  | 'extracted'
  | 'error'

const DOCUMENT_STATUS_LABELS: Record<DocumentStatus, string> = {
  uploaded: 'Subido',
  extracting: 'Extrayendo',
  extracted: 'Extraído',
  error: 'Error',
}

const DOCUMENT_STATUS_VARIANTS: Record<DocumentStatus, BadgeVariant> = {
  uploaded: 'muted',
  extracting: 'info',
  extracted: 'success',
  error: 'destructive',
}

export function documentStatusLabel(status: string): string {
  return (
    (DOCUMENT_STATUS_LABELS as Record<string, string>)[status] ?? status
  )
}

export function documentStatusVariant(status: string): BadgeVariant {
  return (
    (DOCUMENT_STATUS_VARIANTS as Record<string, BadgeVariant>)[status] ??
    'muted'
  )
}

// --- Secciones del compendio ---
const SECTION_STATUS_LABELS: Record<SectionStatus, string> = {
  pending: 'En cola',
  processing: 'Generando',
  completed: 'Completada',
  failed: 'Fallida',
  approved: 'Aprobada',
}

const SECTION_STATUS_VARIANTS: Record<SectionStatus, BadgeVariant> = {
  pending: 'muted',
  processing: 'info',
  completed: 'success',
  failed: 'destructive',
  approved: 'review',
}

export function sectionStatusLabel(status: SectionStatus): string {
  return SECTION_STATUS_LABELS[status] ?? status
}

export function sectionStatusVariant(status: SectionStatus): BadgeVariant {
  return SECTION_STATUS_VARIANTS[status] ?? 'muted'
}

// --- Dosificación (motor/nivel del modelo) ---
const DOSIFICATION_LABELS: Record<Dosification, string> = {
  STANDARD: 'Estándar',
  HIGH: 'Alta',
  MAX: 'Máxima',
}

export function dosificationLabel(value: string): string {
  return (
    (DOSIFICATION_LABELS as Record<string, string>)[value] ?? value
  )
}

// --- Polling: estados "ocupados" del proyecto ---
export const POLL_INTERVAL_MS = 3000

export const BUSY_STATUSES: ProjectStatus[] = ['extracting', 'generating']

export function isProjectBusy(status: ProjectStatus): boolean {
  return BUSY_STATUSES.includes(status)
}
