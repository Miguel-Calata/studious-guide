import { describe, it, expect, vi, beforeEach } from 'vitest'
import { publishProject } from '@/api/publishing'
import { ApiError } from '@/api/client'

function mockFetch(handler: (url: string, init?: RequestInit) => Response) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) =>
      handler(String(input), init)
    )
  )
}

const ok = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })

describe('api/publishing', () => {
  beforeEach(() => vi.resetAllMocks())

  it('publishProject hace POST a /projects/{id}/publish', async () => {
    mockFetch((url, init) => {
      expect(url).toBe('/api/v1/projects/p1/publish')
      expect(init?.method).toBe('POST')
      return ok({
        project_id: 'p1',
        slug: 'lra',
        public_url: '/public/compendiums/lra/download',
        sections_included: 11,
        project_status: 'completed',
      })
    })
    const res = await publishProject('p1')
    expect(res.slug).toBe('lra')
    expect(res.sections_included).toBe(11)
  })

  it('propaga ApiError en 409', async () => {
    mockFetch(() =>
      new Response(
        JSON.stringify({ detail: 'Faltan secciones del compendio (8/11)' }),
        { status: 409, headers: { 'Content-Type': 'application/json' } }
      )
    )
    await expect(publishProject('p1')).rejects.toBeInstanceOf(ApiError)
  })
})
