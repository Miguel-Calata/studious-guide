import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { Toaster } from 'sonner'
import { SWRConfig } from 'swr'

import { EcosMapCard } from '@/components/pipeline/EcosMapCard'
import type { Project } from '@/types/project'
import type { EcosMap } from '@/types/ecos'

const projectBase: Project = {
  id: 'p1',
  name: 'AKI',
  slug: 'aki',
  description: null,
  status: 'review',
  merged_content: 'contenido fusionado',
  is_published: false,
  public_url: null,
  created_at: '2026-07-06T18:00:00Z',
  updated_at: '2026-07-06T18:00:00Z',
}

const draftMap: EcosMap = {
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

const approvedMap: EcosMap = {
  ...draftMap,
  status: 'approved',
  is_active: true,
  approved_by: 'user-1',
  approved_at: '2026-07-21T01:00:00Z',
}

// ── Mock fetch scenarios ────────────────────────────────────────
function mockFetch(handlers: {
  active?: EcosMap | null
  pending?: EcosMap | null
  approveResult?: EcosMap
  updateWarnings?: string[]
}) {
  const spy = vi.fn(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)

      // POST /pathologies/{key}/ecos-map:propose
      if (url.includes(':propose') && init?.method === 'POST') {
        return new Response(JSON.stringify(draftMap), {
          status: 201,
          headers: { 'Content-Type': 'application/json' },
        })
      }

      // PUT /ecos-maps/{id}
      if (url.includes('/ecos-maps/') && init?.method === 'PUT') {
        return new Response(
          JSON.stringify({
            ecos_map: handlers.pending ?? draftMap,
            warnings: handlers.updateWarnings ?? [],
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        )
      }

      // POST /ecos-maps/{id}/approve
      if (url.includes('/approve') && init?.method === 'POST') {
        return new Response(
          JSON.stringify(handlers.approveResult ?? approvedMap),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        )
      }

      // GET pending-draft
      if (url.includes('pending-draft')) {
        if (handlers.pending) {
          return new Response(JSON.stringify(handlers.pending), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          })
        }
        return new Response(
          JSON.stringify({ detail: 'No hay borrador' }),
          { status: 404, headers: { 'Content-Type': 'application/json' } }
        )
      }

      // GET active map
      if (url.includes('/ecos-map')) {
        if (handlers.active) {
          return new Response(JSON.stringify(handlers.active), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          })
        }
        return new Response(
          JSON.stringify({ detail: 'No existe' }),
          { status: 404, headers: { 'Content-Type': 'application/json' } }
        )
      }

      // Project polling (fallback)
      return new Response(
        JSON.stringify({ detail: 'Not found' }),
        { status: 404, headers: { 'Content-Type': 'application/json' } }
      )
    }
  )
  vi.stubGlobal('fetch', spy)
  return spy
}

function renderCard(project = projectBase) {
  return render(
    <SWRConfig value={{ provider: () => new Map() }}>
      <MemoryRouter>
        <EcosMapCard project={project} onMutate={vi.fn()} />
        <Toaster />
      </MemoryRouter>
    </SWRConfig>
  )
}

describe('EcosMapCard', () => {
  beforeEach(() => vi.restoreAllMocks())

  it('estado no_map: muestra badge y mensaje', async () => {
    mockFetch({ active: null, pending: null })
    renderCard({ ...projectBase, merged_content: null })
    expect(await screen.findByText('Sin mapa')).toBeTruthy()
    expect(
      screen.getByText(/sube documentos, extrae y haz merge/i)
    ).toBeTruthy()
  })

  it('estado proposing: muestra spinner cuando hay merge pero no borrador', async () => {
    mockFetch({ active: null, pending: null })
    const { container } = renderCard({ ...projectBase, merged_content: 'contenido' })
    // Wait for SWR to resolve and component to update
    await waitFor(() => {
      expect(container.textContent).toContain('Generando borrador')
    }, { timeout: 5000 })
    expect(
      screen.getByRole('button', { name: /forzar/i })
    ).toBeTruthy()
  }, 10000)

  it('estado draft_pending: muestra acordeón y botones Guardar/Aprobar', async () => {
    mockFetch({ active: null, pending: draftMap })
    renderCard()
    expect(await screen.findByText('Aprobar')).toBeTruthy()
    expect(screen.getByText('Guardar cambios')).toBeTruthy()
    expect(
      screen.getByText(/borrador pendiente v1/i)
    ).toBeTruthy()
  })

  it('estado approved: muestra acordeón en readonly y botón Regenerar', async () => {
    mockFetch({ active: approvedMap, pending: null })
    renderCard()
    expect(
      await screen.findByText(/aprobado v1/i)
    ).toBeTruthy()
    expect(
      screen.getByRole('button', { name: /regenerar borrador/i })
    ).toBeTruthy()
  })

  it('clic Aprobar llama POST approve y muestra toast', async () => {
    const fetchSpy = mockFetch({ active: null, pending: draftMap })
    renderCard()
    await screen.findByText('Aprobar')

    await userEvent.click(screen.getByText('Aprobar'))

    await waitFor(() => {
      const calls = fetchSpy.mock.calls
      const approveCall = calls.find(
        ([url, init]) =>
          String(url).includes('/approve') &&
          (init as RequestInit)?.method === 'POST'
      )
      expect(approveCall).toBeTruthy()
    })

    await waitFor(() =>
      expect(
        screen.getByText(/ecos map aprobado/i)
      ).toBeTruthy()
    )
  })

  it('clic Guardar llama PUT con sections', async () => {
    const fetchSpy = mockFetch({ active: null, pending: draftMap })
    renderCard()
    await screen.findByText('Guardar cambios')

    await userEvent.click(screen.getByText('Guardar cambios'))

    await waitFor(() => {
      const calls = fetchSpy.mock.calls
      const putCall = calls.find(
        ([url, init]) =>
          String(url).includes('/ecos-maps/') &&
          (init as RequestInit)?.method === 'PUT'
      )
      expect(putCall).toBeTruthy()
      const body = JSON.parse((putCall![1] as RequestInit).body as string)
      expect(body.sections).toBeDefined()
      expect(body.sections['1']).toEqual([])
    })
  })

  it('no_map sin merge: no muestra botón Forzar', async () => {
    mockFetch({ active: null, pending: null })
    renderCard({ ...projectBase, merged_content: null })
    await screen.findByText('Sin mapa')
    expect(
      screen.queryByRole('button', { name: /forzar/i })
    ).toBeNull()
  })
})
