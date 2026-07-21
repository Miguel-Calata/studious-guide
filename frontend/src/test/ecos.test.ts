import { describe, it, expect, vi, beforeEach } from 'vitest'

import {
  getActiveEcoMap,
  getPendingDraft,
  listEcoMaps,
  proposeEcoMap,
  updateEcoMap,
  approveEcoMap,
} from '@/api/ecos'
import { ApiError } from '@/api/client'
import type { EcosMap } from '@/types/ecos'

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

const notFound = () =>
  new Response(JSON.stringify({ detail: 'No encontrado' }), {
    status: 404,
    headers: { 'Content-Type': 'application/json' },
  })

const ecosMap: EcosMap = {
  id: 'm1',
  pathology_key: 'aki',
  pathology_name: 'AKI',
  version: 1,
  status: 'draft',
  origin: 'autopopulated',
  is_active: false,
  sections: {
    '1': [],
    '2': ['Definición clínica (→ ver Sección 1)'],
    '3': [],
    '4': [],
    '5': [],
    '6': [],
    '7': [],
    '8': [],
    '9': [],
    '10': [],
    '11': [],
  },
  description: 'Borrador auto-poblado v1',
  approved_by: null,
  approved_at: null,
  created_at: '2026-07-21T00:00:00Z',
  updated_at: '2026-07-21T00:00:00Z',
}

describe('api/ecos', () => {
  beforeEach(() => vi.resetAllMocks())

  it('getActiveEcoMap devuelve mapa en 200', async () => {
    mockFetch((url) => {
      expect(url).toBe('/api/v1/pathologies/aki/ecos-map')
      return ok({ ...ecosMap, status: 'approved', is_active: true })
    })
    const res = await getActiveEcoMap('aki')
    expect(res).not.toBeNull()
    expect(res!.status).toBe('approved')
  })

  it('getActiveEcoMap devuelve null en 404', async () => {
    mockFetch(() => notFound())
    const res = await getActiveEcoMap('no-existe')
    expect(res).toBeNull()
  })

  it('getPendingDraft devuelve borrador en 200', async () => {
    mockFetch((url) => {
      expect(url).toBe(
        '/api/v1/pathologies/aki/ecos-map/pending-draft'
      )
      return ok(ecosMap)
    })
    const res = await getPendingDraft('aki')
    expect(res).not.toBeNull()
    expect(res!.status).toBe('draft')
  })

  it('getPendingDraft devuelve null en 404', async () => {
    mockFetch(() => notFound())
    const res = await getPendingDraft('aki')
    expect(res).toBeNull()
  })

  it('listEcoMaps devuelve lista', async () => {
    mockFetch(() => ok([ecosMap]))
    const res = await listEcoMaps('aki')
    expect(res).toHaveLength(1)
  })

  it('proposeEcoMap hace POST y devuelve borrador', async () => {
    mockFetch((url, init) => {
      expect(url).toBe(
        '/api/v1/pathologies/aki/ecos-map:propose'
      )
      expect(init?.method).toBe('POST')
      return ok(ecosMap, 201)
    })
    const res = await proposeEcoMap('aki')
    expect(res.id).toBe('m1')
  })

  it('updateEcoMap hace PUT con sections', async () => {
    const newSections = { '1': [], '2': ['eco editado'] }
    mockFetch((url, init) => {
      expect(url).toBe('/api/v1/ecos-maps/m1')
      expect(init?.method).toBe('PUT')
      expect(JSON.parse(init?.body as string)).toEqual({
        sections: newSections,
      })
      return ok({ ecos_map: { ...ecosMap, sections: newSections }, warnings: [] })
    })
    const res = await updateEcoMap('m1', { sections: newSections })
    expect(res.warnings).toEqual([])
    expect(res.ecos_map.sections['2']).toEqual(['eco editado'])
  })

  it('updateEcoMap 409 lanza ApiError', async () => {
    mockFetch(() =>
      new Response(
        JSON.stringify({
          detail: 'Solo se pueden editar borradores',
        }),
        { status: 409, headers: { 'Content-Type': 'application/json' } }
      )
    )
    await expect(
      updateEcoMap('m1', { sections: {} })
    ).rejects.toBeInstanceOf(ApiError)
  })

  it('approveEcoMap hace POST', async () => {
    mockFetch((url, init) => {
      expect(url).toBe('/api/v1/ecos-maps/m1/approve')
      expect(init?.method).toBe('POST')
      return ok({ ...ecosMap, status: 'approved', is_active: true })
    })
    const res = await approveEcoMap('m1')
    expect(res.status).toBe('approved')
    expect(res.is_active).toBe(true)
  })

  it('propaga errores no-404 de getActiveEcoMap', async () => {
    mockFetch(() =>
      new Response(
        JSON.stringify({ detail: 'Error interno' }),
        { status: 500, headers: { 'Content-Type': 'application/json' } }
      )
    )
    await expect(getActiveEcoMap('aki')).rejects.toBeInstanceOf(
      ApiError
    )
  })
})
