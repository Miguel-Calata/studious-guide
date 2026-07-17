import { describe, it, expect, vi, beforeEach } from 'vitest'
import {
  listCompendiumSources,
  getSourceDownloadUrl,
} from '@/api/public'

function mockFetch(handler: (url: string) => Response) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => handler(String(input)))
  )
}

const ok = (body: unknown) =>
  new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })

describe('api/public sources', () => {
  beforeEach(() => vi.resetAllMocks())

  it('listCompendiumSources hace GET a /public/compendiums/{slug}/sources', async () => {
    mockFetch((url) => {
      expect(url).toBe('/public/compendiums/lra/sources')
      return ok([
        {
          id: 'doc-1',
          filename: 'kdigo_2026.pdf',
          document_type: 'guideline',
          file_size: 204800,
          uploaded_at: '2026-07-08T00:00:00Z',
        },
      ])
    })
    const res = await listCompendiumSources('lra')
    expect(res).toHaveLength(1)
    expect(res[0].filename).toBe('kdigo_2026.pdf')
    expect(res[0].document_type).toBe('guideline')
    expect(res[0].file_size).toBe(204800)
  })

  it('listCompendiumSources lanza error en 401', async () => {
    mockFetch(() => new Response(null, { status: 401 }))
    await expect(listCompendiumSources('lra')).rejects.toThrow()
  })

  it('getSourceDownloadUrl construye la URL correcta', () => {
    expect(getSourceDownloadUrl('lra', 'doc-1')).toBe(
      '/public/compendiums/lra/sources/doc-1'
    )
    expect(getSourceDownloadUrl('mi patología', 'doc-2')).toBe(
      '/public/compendiums/mi%20patolog%C3%ADa/sources/doc-2'
    )
  })
})
