import { describe, it, expect, vi, beforeEach } from 'vitest'
import {
  listPublicCompendiums,
  getPublicCompendium,
  getPublicSection,
  getPublicDownloadUrl,
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

describe('api/public', () => {
  beforeEach(() => vi.resetAllMocks())

  it('listPublicCompendiums hace GET a /public/compendiums', async () => {
    mockFetch((url) => {
      expect(url).toBe('/public/compendiums')
      return ok([
        {
          slug: 'lra',
          name: 'LRA',
          description: null,
          section_count: 11,
          published_at: '2026-07-08T00:00:00Z',
        },
      ])
    })
    const res = await listPublicCompendiums()
    expect(res).toHaveLength(1)
    expect(res[0].slug).toBe('lra')
  })

  it('getPublicCompendium hace GET a /public/compendiums/{slug}', async () => {
    mockFetch((url) => {
      expect(url).toBe('/public/compendiums/lra')
      return ok({
        slug: 'lra',
        name: 'LRA',
        description: null,
        section_count: 2,
        sections: [
          { section_number: 1, section_name: 'Resumen' },
          { section_number: 2, section_name: 'Epidemiología' },
        ],
        published_at: '2026-07-08T00:00:00Z',
        public_url: '/public/compendiums/lra/download',
      })
    })
    const res = await getPublicCompendium('lra')
    expect(res.sections).toHaveLength(2)
  })

  it('getPublicSection hace GET a /public/compendiums/{slug}/sections/{n}', async () => {
    mockFetch((url) => {
      expect(url).toBe('/public/compendiums/lra/sections/1')
      return ok({
        section_number: 1,
        section_name: 'Resumen',
        content: '# Resumen',
        dosification: 'MAX',
      })
    })
    const res = await getPublicSection('lra', 1)
    expect(res.content).toBe('# Resumen')
  })

  it('getPublicDownloadUrl construye la URL correcta', () => {
    expect(getPublicDownloadUrl('lra')).toBe(
      '/public/compendiums/lra/download'
    )
    expect(getPublicDownloadUrl('mi patología')).toBe(
      '/public/compendiums/mi%20patolog%C3%ADa/download'
    )
  })
})
