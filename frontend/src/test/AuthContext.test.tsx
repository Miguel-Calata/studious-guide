import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { AuthProvider, useAuth } from '@/contexts/AuthContext'

function readCookie(name: string): string | undefined {
  const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'))
  return match ? match[2] : undefined
}

describe('AuthContext', () => {
  beforeEach(() => {
    document.cookie = 'access_token=; Max-Age=0; path=/'
    document.cookie = 'refresh_token=; Max-Age=0; path=/'
    vi.resetAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('loadUser llama a /auth/me al montar y restaura la sesión', async () => {
    const user = {
      id: 'u1',
      email: 'dr@astreo.space',
      full_name: 'Dr. Jorge',
      role: 'creator',
      is_active: true,
      created_at: '2026-07-06T18:00:00Z',
      updated_at: '2026-07-06T18:00:00Z',
    }
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input)
        return new Response(JSON.stringify(url.includes('/auth/me') ? user : {}), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      })
    )

    function Probe() {
      const { user, isLoading } = useAuth()
      return (
        <div>
          <span data-testid="loading">{String(isLoading)}</span>
          <span data-testid="email">{user?.email ?? 'none'}</span>
        </div>
      )
    }

    render(
      <MemoryRouter>
        <AuthProvider>
          <Probe />
        </AuthProvider>
      </MemoryRouter>
    )

    await waitFor(() =>
      expect(screen.getByTestId('email').textContent).toBe('dr@astreo.space')
    )
    expect(readCookie('access_token')).toBeUndefined()
  })
})
