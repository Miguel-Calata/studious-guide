import { describe, it, expect, vi, beforeEach } from 'vitest'

import {
  extractAllForProject,
  getExtractionStatus,
  retryExtraction,
} from '@/api/extractions'
import { ApiError } from '@/api/client'
import type { ExtractionStatusResponse } from '@/types/extraction'

function mockFetch(handler: (url: string, init?: RequestInit) => Response) {
  const spy = vi.fn(
    async (input: RequestInfo | URL, init?: RequestInit) =>
      handler(String(input), init)
  )
  vi.stubGlobal('fetch', spy)
  return spy
}

const ok = (body: unknown) =>
  new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })

describe('api/extractions', () => {
  beforeEach(() => vi.resetAllMocks())

  it('extractAllForProject hace POST al endpoint sin slash final', async () => {
    const fetchMock = mockFetch((url, init) => {
      expect(url).toBe('/api/v1/projects/p1/extract-all')
      expect(init?.method).toBe('POST')
      return ok({
        project_id: 'p1',
        total_documents: 3,
        enqueued: 2,
        skipped: 1,
        project_status: 'extracting',
      })
    })
    const res = await extractAllForProject('p1')
    expect(res.enqueued).toBe(2)
    expect(res.skipped).toBe(1)
    expect(fetchMock).toHaveBeenCalledOnce()
  })

  it('getExtractionStatus devuelve el estado', async () => {
    const status: ExtractionStatusResponse = {
      id: 'e1',
      status: 'completed',
      input_tokens: 10,
      output_tokens: 20,
      error_message: null,
    }
    mockFetch(() => ok(status))
    const res = await getExtractionStatus('e1')
    expect(res.status).toBe('completed')
  })

  it('retryExtraction hace POST a /extractions/{id}/retry', async () => {
    mockFetch((url, init) => {
      expect(url).toBe('/api/v1/extractions/e1/retry')
      expect(init?.method).toBe('POST')
      return ok({ id: 'e1', status: 'pending', message: 'recolado' })
    })
    const res = await retryExtraction('e1')
    expect(res.status).toBe('pending')
  })

  it('propaga ApiError en fallo', async () => {
    mockFetch(() =>
      new Response(JSON.stringify({ detail: 'estado inválido' }), {
        status: 409,
        headers: { 'Content-Type': 'application/json' },
      })
    )
    await expect(extractAllForProject('p1')).rejects.toBeInstanceOf(ApiError)
  })
})
