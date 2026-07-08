import { describe, it, expect } from 'vitest'
import {
  statusLabel,
  statusVariant,
  documentTypeLabel,
  inferDocumentType,
} from '@/lib/projects'

describe('lib/projects', () => {
  it('mapea estados a etiquetas en español', () => {
    expect(statusLabel('draft')).toBe('Borrador')
    expect(statusLabel('extracting')).toBe('Extrayendo')
    expect(statusLabel('generating')).toBe('Generando')
    expect(statusLabel('review')).toBe('En revisión')
    expect(statusLabel('completed')).toBe('Completado')
    expect(statusLabel('archived')).toBe('Archivado')
  })

  it('mapea estados a variantes de badge', () => {
    expect(statusVariant('draft')).toBe('muted')
    expect(statusVariant('completed')).toBe('success')
    expect(statusVariant('review')).toBe('review')
  })

  it('mapea tipos de documento a etiquetas en español', () => {
    expect(documentTypeLabel('bmj')).toBe('BMJ Best Practice')
    expect(documentTypeLabel('guideline')).toBe('Guía clínica')
    expect(documentTypeLabel('article')).toBe('Artículo')
  })

  it('infiere el tipo de documento por el nombre del archivo', () => {
    expect(inferDocumentType('KDIGO_AKI_2026.pdf')).toBe('guideline')
    expect(inferDocumentType('BMJ_bronquitis.pdf')).toBe('bmj')
    expect(inferDocumentType('articulo_lancet.pdf')).toBe('article')
    expect(inferDocumentType('guia_nice_diabetes.pdf')).toBe('guideline')
  })
})
