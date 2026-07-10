import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { Toaster } from 'sonner'
import { SWRConfig } from 'swr'

import { ProjectDetailPage } from '@/pages/ProjectDetailPage'
import type { Project } from '@/types/project'
import type { SourceDocument } from '@/types/document'
import type { CompendiumSection } from '@/types/compendium'

const project: Project = {
  id: 'p1',
  name: 'LRA',
  slug: 'lra',
  description: null,
  status: 'review',
  merged_content: 'merged',
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
  status: 'extracted',
  created_at: '2026-07-06T18:00:00Z',
  updated_at: '2026-07-06T18:00:00Z',
}

function makeSections(n: number): CompendiumSection[] {
  return Array.from({ length: n }, (_, i) => ({
    id: `s${i + 1}`,
    project_id: 'p1',
    section_number: i + 1,
    section_name: `Sección ${i + 1}`,
    content: `# Sección ${i + 1}`,
    model_used: 'gemini',
    dosification: 'STANDARD' as const,
    input_tokens: 100,
    output_tokens: 200,
    cost_usd: 0.01,
    status: 'completed' as const,
    prompt_version: 'v1',
    notion_page_id: null,
    error_message: null,
    created_at: '2026-07-06T18:00:00Z',
    updated_at: '2026-07-06T18:00:00Z',
  }))
}

function setup(overrides: { proj?: Partial<Project>; sections?: CompendiumSection[] } = {}) {
  const proj = { ...project, ...overrides.proj }
  const sections = overrides.sections ?? makeSections(11)

  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.includes('/publish') && init?.method === 'POST') {
        return new Response(
          JSON.stringify({
            project_id: 'p1',
            slug: 'lra',
            public_url: '/public/compendiums/lra/download',
            sections_included: 11,
            project_status: 'completed',
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        )
      }
      if (url.includes('/notion/status')) {
        return new Response(
          JSON.stringify({
            is_connected: false,
            needs_reconnect: false,
            workspace_name: null,
            workspace_id: null,
            owner_email: null,
            connected_at: null,
            default_parent_page_id: null,
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        )
      }
      if (url.endsWith('/documents')) {
        return new Response(JSON.stringify([doc]), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }
      if (url.endsWith('/sections')) {
        return new Response(JSON.stringify(sections), {
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

describe('PublishCard en ProjectDetailPage', () => {
  beforeEach(() => vi.resetAllMocks())

  it('muestra la sección de publicación', async () => {
    setup()
    renderPage()
    expect(await screen.findByText('Publicación')).toBeTruthy()
    expect(await screen.findByText('Web pública')).toBeTruthy()
    expect(await screen.findByText('Notion')).toBeTruthy()
  })

  it('muestra botón "Publicar" habilitado en review con 11 secciones', async () => {
    setup()
    renderPage()
    const btn = await screen.findByRole('button', { name: 'Publicar' })
    await waitFor(() => expect(btn).toBeEnabled())
  })

  it('muestra badge "Publicado" cuando is_published es true', async () => {
    setup({ proj: { is_published: true, status: 'completed' } })
    renderPage()
    const badges = await screen.findAllByText('Publicado')
    expect(badges.length).toBeGreaterThanOrEqual(1)
  })

  it('al publicar muestra toast de éxito y links', async () => {
    setup()
    renderPage()
    const btn = await screen.findByRole('button', { name: 'Publicar' })
    await waitFor(() => expect(btn).toBeEnabled())
    await userEvent.click(btn)
    await waitFor(() =>
      expect(screen.getByText(/publicado correctamente/i)).toBeTruthy()
    )
    expect(await screen.findByText('Ver visor público')).toBeTruthy()
    expect(await screen.findByText('Descargar .md')).toBeTruthy()
  })

  it('muestra Notion no conectado y botón OAuth', async () => {
    setup()
    renderPage()
    expect(await screen.findByText('Conectar con Notion')).toBeTruthy()
    // No longer shows API key input
    expect(screen.queryByLabelText(/api key de notion/i)).toBeNull()
  })

  it('muestra botón "Publicar" deshabilitado con menos de 11 secciones', async () => {
    setup({ sections: makeSections(5) })
    renderPage()
    const btn = await screen.findByRole('button', { name: 'Publicar' })
    await waitFor(() => expect(btn).toBeDisabled())
  })
})
