import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { SWRConfig } from 'swr'

import { SourcesPanel } from '@/components/compendium/SourcesPanel'
import type { SourceDocumentPublic } from '@/types/public'

const mockSources: SourceDocumentPublic[] = [
  {
    id: 'doc-1',
    filename: 'kdigo_2026.pdf',
    document_type: 'guideline',
    file_size: 204800,
    uploaded_at: '2026-07-08T00:00:00Z',
  },
  {
    id: 'doc-2',
    filename: 'nice_ng148.pdf',
    document_type: 'guideline',
    file_size: 102400,
    uploaded_at: '2026-07-08T00:00:00Z',
  },
]

let currentUser: { email: string } | null = null

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({
    user: currentUser,
    isLoading: false,
    isAuthenticated: currentUser !== null,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
  }),
}))

function setup(sources: SourceDocumentPublic[] = mockSources) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      if (url.includes('/sources')) {
        return new Response(JSON.stringify(sources), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }
      return new Response(null, { status: 404 })
    })
  )
}

function renderPanel() {
  return render(
    <SWRConfig value={{ provider: () => new Map() }}>
      <MemoryRouter>
        <SourcesPanel slug="lra" />
      </MemoryRouter>
    </SWRConfig>
  )
}

describe('SourcesPanel', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    currentUser = null
  })

  it('muestra CTA de iniciar sesión cuando el usuario no está autenticado', async () => {
    currentUser = null
    setup()
    renderPanel()
    expect(await screen.findByText('Iniciar sesión')).toBeTruthy()
    expect(
      screen.getByText(
        'Inicia sesión para acceder a los PDFs fuente del compendio.'
      )
    ).toBeTruthy()
  })

  it('no muestra el panel si el usuario no está autenticado y hay error de fetch', async () => {
    currentUser = null
    setup([])
    renderPanel()
    expect(await screen.findByText('Iniciar sesión')).toBeTruthy()
  })

  it('muestra la lista de documentos fuente cuando el usuario está autenticado', async () => {
    currentUser = { email: 'test@test.com' }
    setup()
    renderPanel()
    expect(await screen.findByText('kdigo_2026.pdf')).toBeTruthy()
    expect(await screen.findByText('nice_ng148.pdf')).toBeTruthy()
    expect(screen.getByText('Documentos fuente')).toBeTruthy()
  })

  it('muestra el tamaño de archivo formateado', async () => {
    currentUser = { email: 'test@test.com' }
    setup()
    renderPanel()
    expect(await screen.findByText('200 KB')).toBeTruthy()
    expect(await screen.findByText('100 KB')).toBeTruthy()
  })

  it('no se renderiza si no hay documentos fuente', async () => {
    currentUser = { email: 'test@test.com' }
    setup([])
    renderPanel()
    await waitFor(() => {
      expect(screen.queryByText('Documentos fuente')).toBeNull()
    })
  })

  it('no se renderiza si falla la carga', async () => {
    currentUser = { email: 'test@test.com' }
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(null, { status: 500 }))
    )
    renderPanel()
    await waitFor(() => {
      expect(screen.queryByText('Documentos fuente')).toBeNull()
    })
  })

  it('cada documento tiene un enlace que abre en nueva pestaña', async () => {
    currentUser = { email: 'test@test.com' }
    setup()
    renderPanel()
    const links = await screen.findAllByRole('link')
    expect(links.length).toBeGreaterThanOrEqual(2)
    for (const link of links) {
      expect(link).toHaveAttribute('target', '_blank')
      expect(link).toHaveAttribute('rel', 'noopener noreferrer')
    }
  })
})
