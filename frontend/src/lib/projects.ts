import type { ProjectStatus } from '@/types/project'
import type { DocumentType } from '@/types/document'

const STATUS_LABELS: Record<ProjectStatus, string> = {
  draft: 'Borrador',
  extracting: 'Extrayendo',
  generating: 'Generando',
  review: 'En revisión',
  completed: 'Completado',
  archived: 'Archivado',
}

type BadgeVariant =
  | 'muted'
  | 'info'
  | 'warning'
  | 'review'
  | 'success'
  | 'destructive'

const STATUS_VARIANTS: Record<ProjectStatus, BadgeVariant> = {
  draft: 'muted',
  extracting: 'info',
  generating: 'warning',
  review: 'review',
  completed: 'success',
  archived: 'destructive',
}

export function statusLabel(status: ProjectStatus): string {
  return STATUS_LABELS[status] ?? status
}

export function statusVariant(status: ProjectStatus): BadgeVariant {
  return STATUS_VARIANTS[status] ?? 'muted'
}

const DOCUMENT_TYPE_LABELS: Record<DocumentType, string> = {
  bmj: 'BMJ Best Practice',
  guideline: 'Guía clínica',
  article: 'Artículo',
}

export function documentTypeLabel(type: DocumentType): string {
  return DOCUMENT_TYPE_LABELS[type] ?? type
}

const GUIDELINE_HINTS = [
  'guideline',
  'guia',
  'guía',
  'kdigo',
  'nice',
  'oms',
  'who',
  'oecd',
  'updates',
]

const BMJ_HINTS = ['bmj', 'best practice', 'best-practice']

export function inferDocumentType(filename: string): DocumentType {
  const lower = filename.toLowerCase()
  if (BMJ_HINTS.some((h) => lower.includes(h))) {
    return 'bmj'
  }
  if (GUIDELINE_HINTS.some((h) => lower.includes(h))) {
    return 'guideline'
  }
  return 'article'
}
