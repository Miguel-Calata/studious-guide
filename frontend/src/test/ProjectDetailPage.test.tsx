import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { Toaster } from 'sonner'
import { SWRConfig } from 'swr'

import { ProjectDetailPage } from '@/pages/ProjectDetailPage'
import type { Project } from '@/types/project'
import type { SourceDocument } from '@/types/document'

const project: Project = {
  id: 'p1',
  name: 'LRA',
  slug: 'lra',
  description: null,
  status: 'draft',
  merged_content: null,
  is_published: false,
  public_url: null,
  created_at: '2026-07-06T18:00:00Z',
  updated_at: '2026-07-06T18:00:00Z',
}

const doc: SourceDocument = {
  id: 'd1',
  project_id: 'p1',
  filename: 'guia.pdf',
  file_size: 1234,
  document_type: 'guideline',
  status: 'uploaded',
  created_at: '2026-07-06T18:00:00Z',
  updated_at: '2026-07-06T18:00:00Z',
}

type SetupOpts = {
  status?: Project['status']
  docs?: SourceDocument[]
}

function setup({ status = 'draft', docs = [doc] }: SetupOpts = {}) {
  const proj: Project = { ...project, status }
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.includes('/projects/p1') && init?.method === 'POST') {
        return new Response(
          JSON.stringify({
            project_id: 'p1',
            total_documents: 1,
            enqueued: 1,
            skipped: 0,
            project_status: 'extracting',
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        )
      }
      if (url.endsWith('/documents')) {
        return new Response(JSON.stringify(docs), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }
      if (url.endsWith('/sections')) {
        return new Response('[]', {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }
      return new Response(JSON.stringify(proj), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    })
  )
}

function renderPage() {
  return render(
    <SWRConfig value={{ provider: () => new Map() }}>
      <MemoryRouter initialEntries={['/projects/p1']}>
        <Routes>
          <Route path="/projects/:id" element={<ProjectDetailPage />} />
        </Routes>
        <Toaster />
      </MemoryRouter>
    </SWRConfig>
  )
}

describe('ProjectDetailPage (pipeline)', () => {
  beforeEach(() => vi.resetAllMocks())

  it('muestra las tarjetas de extracción y compendio', async () => {
    setup()
    renderPage()
    expect(await screen.findByText('Extracción')).toBeTruthy()
    expect(await screen.findByText('Compendio')).toBeTruthy()
    expect(await screen.findByText('Extraer todo')).toBeTruthy()
    expect(await screen.findByText('Fusionar extracciones')).toBeTruthy()
    expect(await screen.findByText('Generar compendio')).toBeTruthy()
  })

  it('deshabilita "Extraer todo" cuando el proyecto no admite extracción (review)', async () => {
    setup({ status: 'review', docs: [doc] })
    renderPage()
    const btn = await screen.findByRole('button', { name: 'Extraer todo' })
    await waitFor(() => expect(btn).toBeDisabled())
  })

  it('al hacer clic en "Extraer todo" llama al endpoint y muestra toast', async () => {
    setup()
    renderPage()
    const btn = await screen.findByRole('button', { name: 'Extraer todo' })
    await waitFor(() => expect(btn).toBeEnabled())
    await userEvent.click(btn)
    await waitFor(() =>
      expect(screen.getByText(/Extracción iniciada/)).toBeTruthy()
    )
  })

  it('deshabilita "Generar compendio" sin contenido fusionado', async () => {
    setup()
    renderPage()
    const btn = await screen.findByRole('button', {
      name: 'Generar compendio',
    })
    await waitFor(() => expect(btn).toBeDisabled())
  })
})
