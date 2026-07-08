import { describe, it, expect, vi, beforeEach } from 'vitest'

import {
  mergeProject,
  generateProject,
  getSections,
  updateSection,
  regenerateSection,
} from '@/api/compendiums'
import { ApiError } from '@/api/client'
import type { CompendiumSection } from '@/types/compendium'

function mockFetch(handler: (url: string, init?: RequestInit) => Response) {
  const spy = vi.fn(
    async (input: RequestInfo | URL, init?: RequestInit) =>
      handler(String(input), init)
  )
  vi.stubGlobal('fetch', spy)
  return spy
}

const ok = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })

const section: CompendiumSection = {
  id: 's1',
  project_id: 'p1',
  section_number: 1,
  section_name: 'Resumen',
  content: '# Resumen',
  model_used: 'claude',
  dosification: 'MAX',
  input_tokens: 1,
  output_tokens: 2,
  cost_usd: 0.01,
  status: 'completed',
  prompt_version: 'v1',
  error_message: null,
  created_at: '2026-07-06T18:00:00Z',
  updated_at: '2026-07-06T18:00:00Z',
}

describe('api/compendiums', () => {
  beforeEach(() => vi.resetAllMocks())

  it('mergeProject hace POST a /projects/{id}/merge', async () => {
    const fetchMock = mockFetch((url, init) => {
      expect(url).toBe('/api/v1/projects/p1/merge')
      expect(init?.method).toBe('POST')
      return ok({
        project_id: 'p1',
        merged_char_count: 120,
        extraction_count: 3,
        project_status: 'review',
      })
    })
    const res = await mergeProject('p1')
    expect(res.merged_char_count).toBe(120)
    expect(fetchMock).toHaveBeenCalledOnce()
  })

  it('generateProject hace POST a /projects/{id}/generate', async () => {
    mockFetch((url, init) => {
      expect(url).toBe('/api/v1/projects/p1/generate')
      expect(init?.method).toBe('POST')
      return ok({
        project_id: 'p1',
        sections_created: 11,
        project_status: 'generating',
      })
    })
    const res = await generateProject('p1')
    expect(res.sections_created).toBe(11)
  })

  it('getSections devuelve la lista', async () => {
    mockFetch(() => ok([section]))
    const res = await getSections('p1')
    expect(res).toHaveLength(1)
    expect(res[0].section_name).toBe('Resumen')
  })

  it('updateSection hace PUT con el contenido', async () => {
    mockFetch((url, init) => {
      expect(url).toBe('/api/v1/sections/s1')
      expect(init?.method).toBe('PUT')
      expect(JSON.parse(init?.body as string)).toEqual({
        content: 'nuevo',
      })
      return ok({ ...section, content: 'nuevo' })
    })
    const res = await updateSection('s1', { content: 'nuevo' })
    expect(res.content).toBe('nuevo')
  })

  it('regenerateSection hace POST a /sections/{id}/regenerate', async () => {
    mockFetch((url, init) => {
      expect(url).toBe('/api/v1/sections/s1/regenerate')
      expect(init?.method).toBe('POST')
      return ok({ ...section, status: 'pending' })
    })
    const res = await regenerateSection('s1')
    expect(res.status).toBe('pending')
  })

  it('propaga ApiError en 409', async () => {
    mockFetch(() =>
      new Response(
        JSON.stringify({ detail: 'Ejecuta el merge primero' }),
        { status: 409, headers: { 'Content-Type': 'application/json' } }
      )
    )
    await expect(generateProject('p1')).rejects.toBeInstanceOf(ApiError)
  })
})
