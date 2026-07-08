import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { ProtectedRoute } from '@/routes/ProtectedRoute'
import { AuthProvider } from '@/contexts/AuthContext'

function LocationProbe() {
  const loc = useLocation()
  return <span data-testid="path">{loc.pathname}</span>
}

describe('ProtectedRoute', () => {
  beforeEach(() => vi.resetAllMocks())

  it('redirige a /login cuando no hay sesión', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(null, { status: 401 }))
    )
    render(
      <MemoryRouter initialEntries={['/']}>
        <AuthProvider>
          <ProtectedRoute>
            <div>Protegido</div>
          </ProtectedRoute>
          <LocationProbe />
        </AuthProvider>
      </MemoryRouter>
    )
    await waitFor(() =>
      expect(screen.getByTestId('path').textContent).toBe('/login')
    )
    expect(screen.queryByText('Protegido')).toBeNull()
  })

  it('muestra loading mientras verifica la sesión', () => {
    vi.stubGlobal('fetch', vi.fn(() => new Promise(() => {})))
    render(
      <MemoryRouter initialEntries={['/']}>
        <AuthProvider>
          <ProtectedRoute>
            <div>Protegido</div>
          </ProtectedRoute>
        </AuthProvider>
      </MemoryRouter>
    )
    expect(screen.getByText('Cargando…')).toBeTruthy()
  })
})
