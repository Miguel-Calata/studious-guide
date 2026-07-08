import { describe, it, expect } from 'vitest'
import {
  extractionStatusLabel,
  extractionStatusVariant,
  sectionStatusLabel,
  sectionStatusVariant,
  documentStatusLabel,
  documentStatusVariant,
  dosificationLabel,
  isProjectBusy,
} from '@/lib/pipeline'

describe('lib/pipeline', () => {
  it('mapea estados de extracción a etiqueta y variante', () => {
    expect(extractionStatusLabel('completed')).toBe('Completada')
    expect(extractionStatusVariant('failed')).toBe('destructive')
    expect(extractionStatusVariant('pending')).toBe('muted')
  })

  it('mapea estados de sección a etiqueta y variante', () => {
    expect(sectionStatusLabel('approved')).toBe('Aprobada')
    expect(sectionStatusVariant('approved')).toBe('review')
    expect(sectionStatusVariant('completed')).toBe('success')
  })

  it('mapea estados de documento a etiqueta y variante', () => {
    expect(documentStatusLabel('extracted')).toBe('Extraído')
    expect(documentStatusVariant('error')).toBe('destructive')
    expect(documentStatusLabel('desconocido')).toBe('desconocido')
  })

  it('mapea dosificación', () => {
    expect(dosificationLabel('MAX')).toBe('Máxima')
    expect(dosificationLabel('STANDARD')).toBe('Estándar')
  })

  it('detecta estados ocupados del proyecto', () => {
    expect(isProjectBusy('extracting')).toBe(true)
    expect(isProjectBusy('generating')).toBe(true)
    expect(isProjectBusy('draft')).toBe(false)
    expect(isProjectBusy('review')).toBe(false)
  })
})
