import { describe, it, expect, vi, beforeEach } from 'vitest'
import { api } from '@/api/client'

describe('api client', () => {
  beforeEach(() => vi.resetAllMocks())

  it('envía credentials: include en las peticiones', async () => {
    const fetchMock = vi.fn(async () => new Response('{}', { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await api.get('/auth/me')
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/auth/me'),
      expect.objectContaining({ credentials: 'include' })
    )
  })

  it('lanza ApiError con el detalle del backend', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(
        async () =>
          new Response(JSON.stringify({ detail: 'Credenciales inválidas' }), {
            status: 401,
          })
      )
    )
    await expect(api.get('/auth/login')).rejects.toMatchObject({
      status: 401,
      message: 'Credenciales inválidas',
    })
  })
})
