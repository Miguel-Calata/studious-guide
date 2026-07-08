import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { ProjectCard } from '@/components/projects/ProjectCard'
import { CreateProjectDialog } from '@/components/projects/CreateProjectDialog'
import type { Project } from '@/types/project'

const project: Project = {
  id: 'p1',
  name: 'Lesión Renal Aguda',
  slug: 'lesion-renal-aguda',
  description: 'Compendio sobre LRA',
  status: 'draft',
  merged_content: null,
  is_published: false,
  public_url: null,
  created_at: '2026-07-06T18:00:00Z',
  updated_at: '2026-07-06T18:00:00Z',
}

function LocationProbe() {
  const loc = useLocation()
  return <span data-testid="path">{loc.pathname}</span>
}

describe('ProjectCard', () => {
  beforeEach(() => vi.resetAllMocks())

  it('muestra nombre, descripción y estado en español', () => {
    render(
      <MemoryRouter>
        <ProjectCard project={project} />
      </MemoryRouter>
    )
    expect(screen.getByText('Lesión Renal Aguda')).toBeTruthy()
    expect(screen.getByText('Compendio sobre LRA')).toBeTruthy()
    expect(screen.getByText('Borrador')).toBeTruthy()
  })

  it('navega al detalle del proyecto al hacer clic', async () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <ProjectCard project={project} />
        <LocationProbe />
      </MemoryRouter>
    )
    screen.getByRole('button').click()
    await waitFor(() =>
      expect(screen.getByTestId('path').textContent).toBe('/projects/p1')
    )
  })
})

describe('CreateProjectDialog', () => {
  beforeEach(() => vi.resetAllMocks())

  it('llama a onCreated con el proyecto creado', async () => {
    const created: Project = { ...project, name: 'Nuevo' }
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        if (url.includes('/auth/me')) {
          return new Response(
            JSON.stringify({
              id: 'u1',
              email: 'dr@astreo.space',
              full_name: 'Dr. Jorge',
              role: 'creator',
              is_active: true,
              created_at: '2026-07-06T18:00:00Z',
              updated_at: '2026-07-06T18:00:00Z',
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } }
          )
        }
        if (url.includes('/projects') && init?.method === 'POST') {
          return new Response(JSON.stringify(created), {
            status: 201,
            headers: { 'Content-Type': 'application/json' },
          })
        }
        return new Response('{}', { status: 200 })
      })
    )

    const onCreated = vi.fn()
    const onOpenChange = vi.fn()

    render(
      <MemoryRouter>
        <CreateProjectDialog
          open
          onOpenChange={onOpenChange}
          onCreated={onCreated}
        />
      </MemoryRouter>
    )

    const nameInput = screen.getByLabelText('Nombre') as HTMLInputElement
    fireEvent.change(nameInput, { target: { value: 'Nuevo' } })

    screen.getByRole('button', { name: /Crear proyecto/i }).click()

    await waitFor(() => expect(onCreated).toHaveBeenCalledWith(created))
  })
})
